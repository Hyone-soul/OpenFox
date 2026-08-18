"""模型适配器抽象与消息数据类。

框架统一使用内部消息格式（role/content/tool_calls），各适配器负责把
外部 API（OpenAI、Anthropic 等）的请求/响应归一化到本格式。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class ToolCall:
    """LLM 发起的一次工具调用。"""

    id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class UsageInfo:
    """单次 LLM 调用的 token 统计（来自上游 API 真实 usage 字段）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # 缓存统计（部分 provider 支持，如 Anthropic prompt cache、OpenAI cached）
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    # 推理 token（如 DeepSeek-R1 的 thinking tokens，单独计费）
    reasoning_tokens: int = 0

    @classmethod
    def from_openai_usage(cls, usage: dict | None) -> "UsageInfo":
        """从 OpenAI Chat Completions usage dict 解析。"""
        if not usage:
            return cls()
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        prompt = int(usage.get("prompt_tokens", 0))
        completion = int(usage.get("completion_tokens", 0))
        # OpenAI 在 cached_tokens 字段返回缓存命中
        cache_hit = int(prompt_details.get("cached_tokens", 0))
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=int(usage.get("total_tokens", prompt + completion)),
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=max(0, prompt - cache_hit),
            reasoning_tokens=int(completion_details.get("reasoning_tokens", 0)),
        )

    def __iadd__(self, other: "UsageInfo") -> "UsageInfo":
        """累积：usage += other。"""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cache_hit_tokens += other.cache_hit_tokens
        self.cache_miss_tokens += other.cache_miss_tokens
        self.reasoning_tokens += other.reasoning_tokens
        return self


@dataclass
class AssistantMessage:
    """LLM 单轮 assistant 响应。"""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)  # 来自上游 API 真实 usage
    # 推理模型的中间思考内容（DeepSeek-R1 等需要）。多轮对话必须回传给 API。
    reasoning_content: str = ""


@dataclass
class ChatChunk:
    """流式响应中的一段内容。"""

    content_delta: str = ""
    tool_call_delta: ToolCall | None = None
    # 流式 tool_call 的 index（OpenAI 用 index 区分并发的多个 tool_call）
    tool_call_index: int = -1
    finish_reason: str | None = None
    # 推理模型的思考增量（流式 reasoning_content 片段），需在最终 AssistantMessage 里累积。
    reasoning_delta: str = ""
    # 流式 tool_call 的 arguments 原始字符串片段（不完整 JSON，跨 chunk 累积后再整体解析）。
    tool_call_args_delta: str = ""
    # 部分 OpenAI-compatible provider 会在流末尾发送独立 usage chunk。
    usage: UsageInfo = field(default_factory=UsageInfo)


class ModelAdapter(ABC):
    """模型适配器抽象。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        temperature: float | None = None,
    ) -> AssistantMessage | AsyncIterator[ChatChunk]:
        """发起一次对话调用。stream=True 时返回异步迭代器。"""

    @abstractmethod
    def list_models(self) -> list[str]:
        """返回所有已配置模型名。"""

    @abstractmethod
    def set_active(self, name: str) -> None:
        """切换当前激活模型。"""
