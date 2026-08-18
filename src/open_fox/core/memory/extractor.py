# src/open_fox/core/memory/extractor.py
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """你是一个记忆提炼器。根据以下最近对话，提炼出**长效稳态**的用户/项目记忆。

规则（100% 跳过）：
- 单次临时提问、调试、改 Bug、参数微调
- 瞬时报错、一次性命令、临时尝试
- 无结论闲聊、试探性需求
- 与已有记忆语义高度重复

只保留：长期固定的代码风格/命名/技术栈/架构偏好、永久性项目约束/目录规范、
多轮稳定复现的工具/命令行使用习惯。

输出 JSON 数组（若无则 []），每项：
{{"section": "用户编码与风格偏好|项目约束与配置规范|工具与系统使用偏好", "content": "精简结论", "confidence": "高|中|低"}}

对话：
{messages}
"""


class MemoryExtractionTask:
    """池感知隐式记忆抽取：根据 notify 时传入的 username 解析对应用户的 MemoryManager。"""

    def __init__(self, pool, adapter, min_interval_turns: int = 5):
        self._pool = pool
        self._adapter = adapter
        # 捕获构造时的稳定 chat 引用，绕过 server 请求期间对 adapter.chat 的
        # monkey-patch（instrumented_chat），避免抽取调用污染该请求的 usage 统计
        self._chat = getattr(adapter, "chat", None) if adapter is not None else None
        self._min_interval = min_interval_turns
        self._task: asyncio.Task | None = None
        self._event = asyncio.Event()
        # 队列项：(messages, tool_used, username)
        self._queue: asyncio.Queue[tuple[list[dict], bool, str]] = asyncio.Queue()

    def _get_manager(self, username: str):
        if hasattr(self._pool, "get"):
            return self._pool.get(username)
        return self._pool

    async def _resolve_manager(self, username: str):
        manager = self._get_manager(username)
        return await manager if hasattr(manager, "__await__") else manager

    def _should_extract(self, manager=None, tool_used: bool = False, msg_count: int = 0) -> bool:
        # 兼容旧的单 MemoryManager 测试调用：_should_extract(tool_used=..., msg_count=...)
        if manager is None and not hasattr(self._pool, "get"):
            manager = self._pool
        if manager is None:
            return False
        if not tool_used:
            return False
        if msg_count < 6:
            return False
        return manager.turns_since_extract >= self._min_interval

    async def notify(self, messages: list[dict], tool_used: bool,
                     username: str = "Ciel") -> None:
        """AgentLoop 每轮完成后调用（fire-and-forget）。"""
        if self._task is None:
            return
        # 先用池中的 manager 检查是否需要抽取（节流判定）
        manager = await self._resolve_manager(username)
        if not self._should_extract(manager, tool_used, len(messages)):
            return
        await self._queue.put((messages, tool_used, username))
        self._event.set()

    async def _loop(self) -> None:
        while True:
            await self._event.wait()
            self._event.clear()
            try:
                while not self._queue.empty():
                    messages, _tool_used, username = await self._queue.get()
                    try:
                        await self._extract_once(messages, username)
                    except TypeError as exc:
                        # 兼容旧测试/扩展覆写的单参数抽取回调。
                        if "positional argument" not in str(exc):
                            raise
                        await self._extract_once(messages)
            except Exception as e:  # noqa: BLE001
                logger.warning("隐式记忆抽取失败：%s", e)

    async def _extract_once(self, messages: list[dict], username: str) -> None:
        if self._adapter is None or self._chat is None:
            return
        manager = await self._resolve_manager(username)
        # 取最近 10 条会话消息作为提炼输入
        recent = messages[-10:]
        text = "\n".join(
            f"{m.get('role')}: {str(m.get('content', ''))[:200]}"
            for m in recent
        )
        prompt = _EXTRACT_PROMPT.format(messages=text[:2000])
        resp = await self._chat([{"role": "user", "content": prompt}])
        content = getattr(resp, "content", "") or ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("隐式抽取输出非 JSON：%s", content[:200])
            return
        for item in data if isinstance(data, list) else []:
            section = item.get("section", "工具与系统使用偏好")
            conf = item.get("confidence", "低")
            text_item = item.get("content", "").strip()
            if text_item:
                await manager.add("implicit", section, text_item, conf)
        manager._last_extract_turn = manager._turn_count

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
