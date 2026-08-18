"""Agent 主循环：构建 messages、调用 LLM、路由工具调用、收敛。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from open_fox.core.adapters.base import (
    AssistantMessage,
    ChatChunk,
    ModelAdapter,
    ToolCall,
    UsageInfo,
)
from open_fox.core.context.context_compressor import (
    CompressionConfig,
    CompressionResult,
    ContextCompressor,
)
from open_fox.core.context.context_breakdown import ContextSnapshot
from open_fox.core.context.token_estimator import (
    estimate_messages_tokens,
    estimate_tool_schemas_tokens,
)
from open_fox.core.memory.manager import MemoryManager
from open_fox.core.platform_context import build_platform_prompt
from open_fox.core.registry import Registry
from open_fox.core.scripts.runner import ScriptRunner
from open_fox.core.session import Session
from open_fox.core.skills.models import Skill
from open_fox.core.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# system 消息的版本元数据键（存于消息内部，随会话 JSON 持久化）
# - _meta.system_ver: 生成 system 的代码版本（与 SYSTEM_PROMPT/常量哈希联动）
# - _meta.skills_sig: 生成 system 时的 skill 清单签名（name+description 哈希）
# 每次 run() 时对比当前值，若不一致则重建 system 消息（修复"后加 Skill 不生效"问题）
_SYSTEM_META_KEY = "_meta"
_SYSTEM_VERSION_KEY = "system_version"
_SKILLS_SIG_KEY = "skills_sig"

# 当前 system 构建版本：SYSTEM_PROMPT/VIBE_CODING_PROMPT 等模板变更时应递增
_SYSTEM_PROMPT_VERSION = 3


def _skills_signature(skills: dict[str, Skill]) -> str:
    """计算 skill 清单签名：name + description 参与哈希，用于检测清单是否变化。"""
    import hashlib
    items = sorted(
        (name, getattr(s, "description", "") or "")
        for name, s in skills.items()
    )
    raw = "\n".join(f"{n}|{d}" for n, d in items)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


SYSTEM_PROMPT = """你是 OpenFox 框架内的助手，可以使用内置工具完成任务。

可用工具：run_shell、read_file、write_file、edit_file（详见 function calling schema）。
run_shell 的 cwd 是当前工作目录（见下方"当前工作目录"）；文件读写仅限白名单目录内。

可用 Skill（含 name + description 及 SKILL.md 路径）见下方"可用 Skill"列表。判断任务相关时，
用 read_file 读取列表中给出的 SKILL.md **完整路径**获取工作流与脚本调用方式，按其指引执行。

## 工具调用规范

1. **必须传入完整参数**：调用工具时，确保所有必填参数都已填写，不要省略或留空。
2. **同一工具连续失败不超过 2 次**：如果同一工具调用失败 2 次，停止重试，向用户说明原因并建议解决方案。
3. **参数格式**：工具参数必须是合法 JSON。字符串值用双引号，不要用单引号。
4. **不要空参数重试**：如果工具调用因参数为空而失败，不要在下一步用同样的空参数再次调用——必须修改参数内容。
"""


VIBE_CODING_PROMPT = """
## 工具扩展能力（Vibe Coding）

你可以使用两类外部工具：
- 本地 Python 自定义工具（用户写在 ./tools/ 下的 @tool 装饰函数）
- MCP 第三方工具集（用户写在 ./mcps/ 下的 yaml/json 配置）

按需引导用户：
1. 用户想新增 Python 工具 → 输出 @tool 装饰器模板，提示保存到 ./tools/xxx.py
2. 用户想接入 MCP 工具 → 根据 transport 输出对应 yaml/json 模板，提示保存到 ./mcps/
3. 用户想查看当前工具 → 汇总本地 + MCP 清单（按 source 标签区分）
4. 用户想重载 → 提示 /reload（CLI）或 POST /v1/reload（HTTP）
5. 工具调用失败 → 按错误前缀（本地工具异常 / MCP 连接失败 / MCP 调用失败）给出排查建议
"""


@dataclass
class AgentLoop:
    adapter: ModelAdapter
    registry: Registry
    session: Session
    script_runner: ScriptRunner | None
    skills: dict[str, Skill]
    max_steps: int = 500
    temperature: float | None = None
    extra_system_prompt: str = ""
    tool_trace: list[dict] = field(default_factory=list)
    workdir: str = ""  # 当前会话的工作目录（来自 Project 实体）
    # 每次运行累积的 token 用量（跨多步累加）
    accumulated_usage: UsageInfo = field(default_factory=UsageInfo)
    # 可选流式回调：传入则每次 LLM 调用走 stream=True 并把 chunk 喂给回调；
    # 传 None 则行为与改造前一致（非流式、拿精确 usage）。
    on_chunk: Callable[[ChatChunk], Awaitable[None]] | None = None
    # 工具事件回调：每步工具调用前后触发，用于 SSE 实时推送
    # 签名: async on_tool_event(event_type: str, data: dict)
    # event_type: "tool_call" | "tool_result" | "reply"
    on_tool_event: Callable[[str, dict], Awaitable[None]] | None = None
    # 全局记忆管理器：非空时把 memory_text() 注入 system prompt，每轮 register_turn()
    memory_manager: MemoryManager | None = None
    # 上下文压缩器（可选，为 None 则不触发压缩）
    compressor: ContextCompressor | None = None
    # 最近一次上下文快照（供 /context 命令和 API 查询用）
    last_context_snapshot: ContextSnapshot | None = None
    # 最近一次压缩结果
    last_compression_result: CompressionResult | None = None
    # 当前执行步数（供 on_chunk/on_tool_event 回调标记归属，前端按 step 穿插展示）
    current_step: int = 0

    async def run(self, user_input: str) -> str:
        self.tool_trace.clear()
        self.accumulated_usage = UsageInfo()  # 每次运行重置
        self.current_step = 0
        # 每轮通知记忆管理器（节流/轮次计数用）
        if self.memory_manager is not None:
            self.memory_manager.register_turn()
        # 注入系统提示与用户消息
        # 会话首部可能已有 __meta__ 消息（session.set_meta），故不能只看 [0]，
        # 需检查整个消息列表是否已存在 system 角色，避免多轮时重复注入导致上下文膨胀
        # 另外：即使已存在 system 消息，也要校验其版本与 skill 清单是否过期，
        # 过期则重建并替换（修复"会话创建后新增 Skill 无法获取"的问题）。
        self._ensure_fresh_system()
        self.session.add_message("user", user_input)

        stream = self.on_chunk is not None
        consecutive_failures = 0  # 连续工具失败计数（防止 LLM 陷入无限重试循环）
        MAX_CONSECUTIVE_FAILURES = 5
        for step in range(self.max_steps):
            self.current_step = step  # 供事件回调标记当前步（前端穿插展示）
            # ── Preflight 上下文压缩检查 ──
            # 每次 LLM 调用前检查，超阈值则先压缩再发请求
            if self.compressor is not None:
                should_compress, snapshot = self.compressor.should_compress(
                    messages=self.session.chat_messages(),
                    tool_schemas=self.registry.list_tool_schemas(),
                    model_name=self._get_model_name(),
                )
                self.last_context_snapshot = snapshot
                if should_compress:
                    logger.info(
                        "📦 Preflight compression: ~%d tokens >= threshold, compressing...",
                        snapshot.total_tokens,
                    )
                    compressed_msgs, result = await self.compressor.compress(
                        messages=self.session.get_messages(),  # 含 __meta__
                        tool_schemas=self.registry.list_tool_schemas(),
                        model_name=self._get_model_name(),
                    )
                    self.last_compression_result = result
                    if result.success:
                        self.session.set_messages(compressed_msgs)
                        logger.info(
                            "🗜️ Compressed ~%d → ~%d tokens, continuing turn...",
                            result.original_tokens, result.compressed_tokens,
                        )
                    else:
                        logger.warning(
                            "Context compression failed: %s", result.error
                        )

            assistant = await self._call_llm(stream)
            assert isinstance(assistant, AssistantMessage)
            # 累积每步 LLM 调用的 token 用量
            self.accumulated_usage += assistant.usage

            if not assistant.tool_calls:
                # 终态回复：把 reasoning_content 一起存到 assistant 消息，供下一轮回传
                msg: dict = {"role": "assistant", "content": assistant.content or ""}
                if assistant.reasoning_content:
                    msg["reasoning_content"] = assistant.reasoning_content
                self.session.add_raw(msg)
                self.session.save()

                # 通知外部：最终回复
                if self.on_tool_event is not None:
                    await self.on_tool_event("reply", {
                        "content": assistant.content or "",
                    })

                return assistant.content

            # 追加 assistant 消息（含 tool_calls）
            tool_call_msg: dict = {
                "role": "assistant",
                "content": assistant.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": json.dumps(tc.args, ensure_ascii=False)}}
                    for tc in assistant.tool_calls
                ],
            }
            if assistant.reasoning_content:
                tool_call_msg["reasoning_content"] = assistant.reasoning_content
            self.session.add_raw(tool_call_msg)

# 路由每个 tool_call
            step_all_failed = True  # 本步是否全部失败（用于连续失败计数）
            for _tc_idx, tc in enumerate(assistant.tool_calls):
                # 检测空参数：LLM 生成 tool_call 但 args 为空 dict
                # 仅对有必填参数的工具告警——无参数工具（如 get_current_datetime）
                # 收到空 dict 是正常行为，不应产生噪音
                if not tc.args and tc.name and self._tool_has_required_params(tc.name):
                    logger.warning(
                        "工具 %s 收到空参数，可能是流式 arguments 解析失败", tc.name
                    )

                # 通知外部：工具开始调用（携带 step 分组与工具序号，供前端穿插展示）
                _tool_start = time.monotonic()
                if self.on_tool_event is not None:
                    await self.on_tool_event("tool_call", {
                        "id": tc.id or f"tc-{self.current_step}-{_tc_idx}",
                        "step": self.current_step,
                        "name": tc.name,
                        "args": tc.args,
                    })

                result = await self._dispatch(tc)
                _tool_elapsed = time.monotonic() - _tool_start
                result_text = _result_text(result)
                self.tool_trace.append({
                    "name": tc.name,
                    "args": tc.args,
                    "result": result_text,
                })

                # 通知外部：工具调用完成（携带 step 分组与工具序号）
                if self.on_tool_event is not None:
                    await self.on_tool_event("tool_result", {
                        "id": tc.id or f"tc-{self.current_step}-{_tc_idx}",
                        "step": self.current_step,
                        "name": tc.name,
                        "args": tc.args,
                        "result": result_text,
                        "success": isinstance(result, ToolResult) and result.success,
                        "elapsed": round(_tool_elapsed, 2),
                    })
                self.session.add_raw({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

                # 判断本次调用是否成功
                if isinstance(result, ToolResult) and result.success:
                    step_all_failed = False

            # 连续失败计数：如果本步所有工具调用都失败，递增计数
            if step_all_failed:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "连续 %d 步工具调用全部失败，强制终止以避免无限循环",
                        consecutive_failures,
                    )
                    self.session.add_raw({
                        "role": "assistant",
                        "content": f"工具调用连续 {consecutive_failures} 次失败，已自动终止。"
                                   "请检查工具参数是否正确、MCP 服务是否可用。",
                    })
                    self.session.save()
                    return f"工具调用连续 {consecutive_failures} 次失败，已自动终止。"
            else:
                consecutive_failures = 0  # 有成功调用，重置计数

        logger.warning("Agent 循环达到最大步数 %d", self.max_steps)
        # 达到最大步数：把中断原因作为系统消息注入会话并持久化，
        # 前端重建历史时（rebuildToolEvents）能读取该标记渲染为中断卡片。
        self.session.add_raw({
            "role": "system",
            "content": "已达到最大步数，循环被强制结束。",
        })
        self.session.save()
        return "已达到最大步数，循环被强制结束。"

    async def _call_llm(self, stream: bool) -> AssistantMessage:
        """调一次 LLM：stream=False 直接拿 AssistantMessage；stream=True 消费 chunk 累积。
        流式场景下 SSE 通常不带 usage，因此 usage 为零（CLI 显示降级到本地估算）。
        """
        messages = self.session.chat_messages()
        # ── 最终安全校验：清理孤儿 tool_calls，防止 API 400 ──
        messages = self._sanitize_tool_calls(messages)
        tools = self.registry.list_tool_schemas()
        if not stream:
            assert self.on_chunk is None
            return await self.adapter.chat(
                messages, tools=tools, stream=False, temperature=self.temperature,
            )

        # 流式：消费 chunk 拼成 AssistantMessage
        chunks_iter = self.adapter.stream_chat(
            messages, tools=tools, temperature=self.temperature,
        )
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        # 流式 tool_call：按 index 分组累积，支持 LLM 一次返回多个 tool_call
        # 每个 group 记录 id、name 和 arguments 片段列表
        tc_groups: dict[int, dict] = {}  # index -> {"id": str, "name": str, "args_parts": [str]}

        async for chunk in chunks_iter:
            # usage 通常在流末尾以独立 chunk 发送，必须在拼接内容时累积。
            self.accumulated_usage += chunk.usage
            # 把 chunk 喂给外部回调（CLI 实时打印用）
            if self.on_chunk is not None:
                await self.on_chunk(chunk)
            if chunk.content_delta:
                content_parts.append(chunk.content_delta)
            if chunk.reasoning_delta:
                reasoning_parts.append(chunk.reasoning_delta)
            # 处理 tool_call delta
            if chunk.tool_call_delta is not None:
                idx = chunk.tool_call_index if chunk.tool_call_index >= 0 else 0
                if idx not in tc_groups:
                    tc_groups[idx] = {"id": "", "name": "", "args_parts": []}
                if chunk.tool_call_delta.id:
                    tc_groups[idx]["id"] = chunk.tool_call_delta.id
                if chunk.tool_call_delta.name:
                    tc_groups[idx]["name"] = chunk.tool_call_delta.name
            # arguments 片段累积（同一个 index 的跨 chunk 拼接）
            if chunk.tool_call_args_delta:
                idx = chunk.tool_call_index if chunk.tool_call_index >= 0 else 0
                if idx not in tc_groups:
                    tc_groups[idx] = {"id": "", "name": "", "args_parts": []}
                tc_groups[idx]["args_parts"].append(chunk.tool_call_args_delta)

        content = "".join(content_parts)
        reasoning_content = "".join(reasoning_parts)

        # 按 index 顺序拼装最终的 tool_calls
        tool_calls: list[ToolCall] = []
        for idx in sorted(tc_groups.keys()):
            g = tc_groups[idx]
            if not g["name"] and not g["args_parts"]:
                continue  # 空的 group，跳过
            args_str = "".join(g["args_parts"]).strip()
            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                logger.warning(
                    "流式 tool_call[%d] (%s) arguments JSON 解析失败，原始片段：%s",
                    idx, g["name"], args_str[:200],
                )
                args = {}
            tool_calls.append(ToolCall(id=g["id"], name=g["name"], args=args))

        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage=UsageInfo(),  # usage 已在消费 chunk 时累积到 AgentLoop
            reasoning_content=reasoning_content,
        )

    def _ensure_fresh_system(self) -> None:
        """确保会话中的 system 消息为最新版本（skill 清单 / 系统模板 / 记忆均不过期）。

        策略：
        - 无 system 消息 → 直接新建并注入（写入版本元数据）。
        - 有 system 消息但版本/签名过期 → 重建 system 并替换原位，保留会话其他历史。
        - 有 system 消息且最新 → 不做任何改动（避免每轮重写增加 token 开销）。
        替换后不调用 session.save()——由 run() 后续流程统一持久化（终态回复处 save）。
        """
        messages = self.session.get_messages()
        current_sig = _skills_signature(self.skills)
        for i, m in enumerate(messages):
            if m.get("role") != "system":
                continue
            meta = m.get(_SYSTEM_META_KEY) or {}
            ver = meta.get(_SYSTEM_VERSION_KEY)
            sig = meta.get(_SKILLS_SIG_KEY)
            # 1) 旧格式 system（无版本元数据）→ 视为过期，重建一次
            # 2) 版本或 skill 签名不匹配 → 过期，重建
            if ver == _SYSTEM_PROMPT_VERSION and sig == current_sig:
                return  # 已是最新，无需处理
            logger.info(
                "system 提示过期：ver=%s sig=%s → 重建（当前 ver=%s）",
                ver, sig, _SYSTEM_PROMPT_VERSION,
            )
            new_content = self._build_system()
            updated = dict(m)
            updated["content"] = new_content
            updated[_SYSTEM_META_KEY] = {
                _SYSTEM_VERSION_KEY: _SYSTEM_PROMPT_VERSION,
                _SKILLS_SIG_KEY: current_sig,
            }
            self.session.set_messages(messages[:i] + [updated] + messages[i + 1:])
            return
        # 无 system 消息：注入全新 system
        self.session.add_raw({
            "role": "system",
            "content": self._build_system(),
            _SYSTEM_META_KEY: {
                _SYSTEM_VERSION_KEY: _SYSTEM_PROMPT_VERSION,
                _SKILLS_SIG_KEY: current_sig,
            },
        })

    def _build_system(self) -> str:
        skills_summary = "\n".join(
            f"- {s.name}: {s.description}\n  SKILL.md: {s.source_dir / 'SKILL.md'}"
            for s in self.skills.values()
        ) or "（暂无可用 Skill）"
        # 平台信息放在最前面，确保 LLM 从第一行就知道当前运行环境
        platform_prompt = build_platform_prompt()
        base = f"{platform_prompt}\n\n{SYSTEM_PROMPT}\n\n{VIBE_CODING_PROMPT}\n\n可用 Skill：\n{skills_summary}"
        # 注入当前会话的工作目录提示
        if self.workdir:
            base = f"{base}\n\n## 当前工作目录\n{self.workdir}\n文件操作和 Shell 命令限定在此目录及白名单目录内。"
        if self.extra_system_prompt:
            base = f"{base}\n\n# 智能体指令\n{self.extra_system_prompt}"
        if self.memory_manager is not None:
            try:
                mem = self.memory_manager.memory_text()
                if mem:
                    base = f"{base}\n\n{mem}"
            except Exception as e:  # noqa: BLE001
                logger.warning("记忆注入失败：%s", e)
        # memory_text() 已以 "# 全局记忆" 开头，直接拼接避免重复标题
        return base

    def _tool_has_required_params(self, name: str) -> bool:
        """检查工具是否有必填参数（用于空参数告警过滤）。"""
        target = self.registry.resolve(name)
        if target is None:
            return False
        schema = target.to_schema()
        params = schema.get("function", {}).get("parameters", {})
        required = params.get("required", [])
        return len(required) > 0

    async def _dispatch(self, tc) -> ToolResult | str:
        target = self.registry.resolve(tc.name)
        if target is None:
            return ToolResult(success=False, error=f"未知工具：{tc.name}")
        # 内置工具：若目标重写了 async_run（Memory 工具），走异步；否则同步 execute
        if hasattr(target, "execute") and callable(target.execute):
            try:
                if type(target).async_run is not BaseTool.async_run:
                    return await target.async_run(**tc.args)
                return target.execute(**tc.args)
            except Exception as e:  # noqa: BLE001
                return ToolResult(success=False, error=f"工具异常：{e}")
        # MCP 工具
        if hasattr(target, "call"):
            try:
                return await target.call(tc.args)
            except Exception as e:  # noqa: BLE001
                return ToolResult(success=False, error=f"MCP 异常：{e}")
        return ToolResult(success=False, error="目标无可用执行入口")

    def _get_model_name(self) -> str:
        """获取当前模型名称（用于上下文窗口检测）"""
        if hasattr(self.adapter, "model"):
            return self.adapter.model or ""
        return ""

    @staticmethod
    def _sanitize_tool_calls(messages: list[dict]) -> list[dict]:
        """
        发送给 LLM 前的最终安全校验：确保每个 assistant(tool_calls) 消息
        后面都有对应的 tool 响应消息。缺失的 tool_calls 被剥除，避免 API 400。

        这是压缩、持久化、加载等所有环节之后的最后一道防线。
        """
        # 收集所有 tool_call_id 和 tool 响应 id
        call_ids: set[str] = set()
        for m in messages:
            for tc in m.get("tool_calls", []) or []:
                tc_id = tc.get("id")
                if tc_id:
                    call_ids.add(tc_id)

        result_ids: set[str] = set()
        for m in messages:
            if m.get("role") == "tool" and m.get("tool_call_id"):
                result_ids.add(m["tool_call_id"])

        orphan_call_ids = call_ids - result_ids  # 有 calls 但无响应
        orphan_result_ids = result_ids - call_ids  # 有响应但无 calls

        if not orphan_call_ids and not orphan_result_ids:
            return messages

        logger.warning(
            "sanitize_tool_calls: found %d orphan tool_calls, %d orphan tool_results — cleaning",
            len(orphan_call_ids), len(orphan_result_ids),
        )

        cleaned = []
        for m in messages:
            # 删除无对应 tool_calls 的 tool 结果
            if m.get("role") == "tool" and m.get("tool_call_id") in orphan_result_ids:
                continue
            # 处理带孤儿 tool_calls 的 assistant 消息
            if m.get("role") == "assistant" and m.get("tool_calls"):
                surviving = [
                    tc for tc in m["tool_calls"]
                    if tc.get("id") not in orphan_call_ids
                ]
                if len(surviving) < len(m["tool_calls"]):
                    if not surviving:
                        # 全部孤儿：去掉 tool_calls，保留 content
                        m_copy = {k: v for k, v in m.items() if k != "tool_calls"}
                        if not m_copy.get("content"):
                            m_copy["content"] = ""
                        cleaned.append(m_copy)
                        continue
                    else:
                        # 部分孤儿：只保留有配对的 tool_calls
                        m_copy = dict(m)
                        m_copy["tool_calls"] = surviving
                        cleaned.append(m_copy)
                        continue
            cleaned.append(m)

        return cleaned

    def get_context_snapshot(self) -> ContextSnapshot | None:
        """
        获取当前上下文快照（供 CLI /context 命令和 API 使用）。

        如果没有压缩器或尚未生成快照，返回 None。
        """
        if self.last_context_snapshot is not None:
            return self.last_context_snapshot
        # 主动构建一次快照
        if self.compressor is not None:
            _, snapshot = self.compressor.should_compress(
                messages=self.session.chat_messages(),
                tool_schemas=self.registry.list_tool_schemas(),
                model_name=self._get_model_name(),
            )
            self.last_context_snapshot = snapshot
            return snapshot
        return None


def _result_text(result) -> str:
    if isinstance(result, ToolResult):
        if result.success:
            return result.content or ""
        return f"ERROR: {result.error}"
    return str(result)
