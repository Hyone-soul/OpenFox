"""Skill 进化后台任务：接收每轮轨迹，判定触发并调 LLM 生成候选入待确认队列。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable

from open_fox.config import SkillEvolutionConfig
from open_fox.core.evolution.detector import (
    EvolutionTrigger,
    EvolutionTriggerDetector,
)
from open_fox.core.evolution.manager import SkillEvolutionManager
from open_fox.core.evolution.pending import PendingQueue
from open_fox.core.evolution.stats import SkillInvocationTracker

logger = logging.getLogger(__name__)

_MIN_INTERVAL_TURNS = 5
_MIN_MSG_COUNT = 6
_MAX_PENDING = 5

_GENERATE_PROMPT = """你是 OpenFox 的 Skill 进化器。根据证据决定是否创建或修复 Skill，输出完整的新 SKILL.md。

SKILL.md 格式（frontmatter + Markdown 正文）：
---
name: <小写字母数字连字符>
description: <一句话：何时触发此技能>
trigger: <触发条件，可选>
---
<工作流正文：步骤、脚本调用方式、异常处理、示例>

规则：
1. 只封装可复用的执行流程，禁止把本次会话的具体业务数据硬编码进内容。
2. 修复时做增量最小修改，保留原有正确逻辑，禁止全盘重写。
3. 证据不足以支撑进化时，输出 {{"action": "skip"}}。
4. content 的 frontmatter 不要写 version 字段（版本号由系统管理）。

【分支类型】{branch}
【Skill 名】{skill_name}
【现有 SKILL.md】（修复分支有，新建分支为"（无）"）：
{current_skill}

【失败/重复证据】：
{evidence}

【会话上下文（截断 1500 字）】：
{context}

只输出一个 JSON 对象，不要输出其他文字：
{{"action": "fix|create|skip", "skill_name": "...", "reason": "简短中文说明", "content": "完整 SKILL.md 内容"}}
"""


class EvolutionTask:
    def __init__(
        self,
        config: SkillEvolutionConfig,
        manager: SkillEvolutionManager,
        tracker: SkillInvocationTracker,
        detector: EvolutionTriggerDetector,
        queue: PendingQueue,
        adapter,
        existing_skills: Callable[[], set[str]] | None = None,
        get_skill_md: Callable[[str], str] | None = None,
    ):
        self._config = config
        self.manager = manager
        self.tracker = tracker
        self.detector = detector
        self.queue = queue
        self._existing = existing_skills or (lambda: set())
        self._get_skill_md = get_skill_md
        # 捕获构造时稳定 chat 引用，规避 server 请求期 monkey-patch 的 usage 污染
        self._chat = getattr(adapter, "chat", None) if adapter is not None else None
        self._task: asyncio.Task | None = None
        self._event = asyncio.Event()
        self._notify_queue: asyncio.Queue = asyncio.Queue()
        self._last_trigger_turn = 0

    def pending_count(self) -> int:
        return len(self.queue.list("pending"))

    async def notify(self, session_id: str, messages: list[dict], tool_trace: list[dict]) -> None:
        self.tracker.register_turn()
        if self._task is None:
            return
        if not self._should_evolve(tool_trace, len(messages)):
            return
        await self._notify_queue.put((session_id, messages, tool_trace))
        self._event.set()

    def _should_evolve(self, tool_trace: list[dict], msg_count: int) -> bool:
        if not self._config.enabled:
            return False
        if not tool_trace:
            return False
        if msg_count < _MIN_MSG_COUNT:
            return False
        return self.tracker.turn() - self._last_trigger_turn >= _MIN_INTERVAL_TURNS

    async def _loop(self) -> None:
        while True:
            await self._event.wait()
            self._event.clear()
            try:
                while not self._notify_queue.empty():
                    session_id, messages, tool_trace = await self._notify_queue.get()
                    await self._process(session_id, messages, tool_trace)
            except Exception as e:  # noqa: BLE001
                logger.warning("Skill 进化生成失败：%s", e)

    async def _process(self, session_id: str, messages: list[dict], tool_trace: list[dict]) -> None:
        triggers = self.detector.evaluate(session_id, tool_trace)
        if not triggers:
            return
        # 任何检测到的触发（无论 LLM 后续是否出候选）都算一次"进化尝试"，
        # 重置 5 轮节流闸门，防止 skip 时无限重试。
        self._last_trigger_turn = self.tracker.turn()
        trigger = triggers[0]
        sig = trigger.signature

        def _suppress() -> None:
            if sig:
                self.detector.mark_rejected(sig)

        if self.pending_count() >= _MAX_PENDING:
            logger.info("待确认队列已满，跳过本次进化：%s", trigger.skill_name)
            return
        candidate = await self._generate(trigger, messages)
        if candidate is None:
            _suppress()
            return
        if candidate["action"] == "create":
            name = candidate["skill_name"]
            if not name or name in self._existing():
                _suppress()
                logger.info("跳过新建候选（缺名或已存在）：%s", name)
                return
        _suppress()
        await self.queue.enqueue(
            action=candidate["action"],
            skill_name=candidate["skill_name"],
            reason=candidate["reason"],
            content=candidate["content"],
        )

    async def _generate(self, trigger: EvolutionTrigger, messages: list[dict]) -> dict | None:
        if self._chat is None:
            return None
        current_skill = "（无）"
        if trigger.kind == "fix" and self._get_skill_md is not None:
            try:
                current_skill = self._get_skill_md(trigger.skill_name)
            except Exception:  # noqa: BLE001
                current_skill = "（读取失败）"
        evidence = "\n".join(trigger.evidence) or "（无）"
        context = "\n".join(
            f"{m.get('role')}: {str(m.get('content', ''))[:200]}"
            for m in messages[-8:]
        )[:1500]
        prompt = _GENERATE_PROMPT.format(
            branch="fix（修复）" if trigger.kind == "fix" else "create（新建）",
            skill_name=trigger.skill_name or "（新建，请自行命名）",
            current_skill=current_skill,
            evidence=evidence,
            context=context,
        )
        try:
            resp = await self._chat([{"role": "user", "content": prompt}])
        except Exception as e:  # noqa: BLE001
            logger.warning("进化 LLM 调用失败：%s", e)
            return None
        content = getattr(resp, "content", "") or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("进化输出非 JSON：%s", content[:200])
            return None
        if not isinstance(data, dict) or data.get("action") == "skip":
            return None
        action = data.get("action")
        if action not in ("fix", "create"):
            return None
        return {
            "action": action,
            "skill_name": str(data.get("skill_name", trigger.skill_name)),
            "reason": str(data.get("reason", "")),
            "content": str(data.get("content", "")),
        }

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
