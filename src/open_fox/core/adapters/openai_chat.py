"""OpenAI Chat Completions API 适配器。

兼容任何遵循该接口规范的模型服务（OpenAI、DeepSeek、Azure OpenAI、
本地 vLLM、Ollama 等）。响应统一归一化为内部 AssistantMessage。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import httpx

from open_fox.config import ModelConfig
from open_fox.core.adapters.base import (
    AssistantMessage,
    ChatChunk,
    ModelAdapter,
    ToolCall,
    UsageInfo,
)
from open_fox.core.exceptions import (
    InvalidAssistantMessage,
    ModelAPIError,
    StreamInterrupted,
)

logger = logging.getLogger(__name__)


def _enrich_messages_with_reasoning(messages: list[dict]) -> list[dict]:
    """把 assistant 消息里的 reasoning_content 透传给 API，并确保 content 不为 None。

    DeepSeek-R1 等推理模型要求：上一轮的 reasoning_content 必须原样回传，
    否则 API 报 400。透传的同时保留其他字段。返回新列表，不修改入参。

    同时做防御性清理：部分 API（如 DeepSeek）要求 messages[].content 必须是
    string 或 list，不能是 null。session 从存储加载或旧版本写入的消息可能
    存在 content=None，统一替换为空字符串。

    另外会剥离内部元数据键 `_meta`（system 消息携带的版本/skill 签名标记，
    用于 agent_loop 判断 system 是否过期）。该键仅供框架内部使用，
    不得发送给模型 API（避免未知字段导致 400）。
    """
    out: list[dict] = []
    for m in messages:
        new_m = {k: v for k, v in m.items() if k != "_meta" and k != "_compressed"}
        # 防御性清理：content=None → ""
        if new_m.get("content") is None:
            new_m["content"] = ""
        reasoning = m.get("reasoning_content")
        if reasoning:
            new_m["reasoning_content"] = reasoning
        out.append(new_m)
    return out


class OpenAIChatAdapter(ModelAdapter):
    """OpenAI Chat Completions 兼容适配器。"""

    def __init__(self, models: list[ModelConfig]):
        if not models:
            raise ValueError("至少需要一个模型配置")
        self._models = {m.name: m for m in models}
        self._active = next(iter(self._models))

    @property
    def active(self) -> str:
        return self._active

    def list_models(self) -> list[str]:
        return list(self._models.keys())

    def set_active(self, name: str) -> None:
        if name not in self._models:
            raise ValueError(f"未知模型：{name}")
        self._active = name

    def _current(self) -> ModelConfig:
        return self._models[self._active]

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        temperature: float | None = None,
    ) -> AssistantMessage:
        """非流式对话调用。失败自动重试 3 次（指数退避）。

        流式调用请使用 stream_chat()。本方法始终返回协程，调用方需 await。
        """
        cfg = self._current()
        payload: dict = {
            "model": cfg.model,
            "messages": _enrich_messages_with_reasoning(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        # temperature 优先用调用方传入的，其次用模型配置的默认值
        eff_temp = temperature if temperature is not None else cfg.temperature
        if eff_temp is not None:
            payload["temperature"] = eff_temp
        # max_tokens：模型配置了就透传
        if cfg.max_tokens is not None:
            payload["max_tokens"] = cfg.max_tokens

        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }

        retries = cfg.retry_count if cfg.retry_count is not None else 3
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{cfg.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                if resp.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    last_exc = ModelAPIError(429, resp.text)
                    continue
                if resp.status_code >= 400:
                    raise ModelAPIError(resp.status_code, resp.text)
                return self._parse_non_stream(resp.json())
            except (httpx.HTTPError, ModelAPIError) as e:
                last_exc = e
                await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """流式对话调用。返回异步迭代器，调用方直接 async for，无需 await。

        与 chat() 的区别：stream_chat 始终返回异步迭代器；chat 始终返回协程。
        """
        cfg = self._current()
        payload: dict = {
            "model": cfg.model,
            "messages": _enrich_messages_with_reasoning(messages),
            "stream": True,
            # OpenAI-compatible API 会在流末尾返回真实 usage；不支持的 provider 通常会忽略该字段。
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
        # temperature 优先用调用方传入的，其次用模型配置的默认值
        eff_temp = temperature if temperature is not None else cfg.temperature
        if eff_temp is not None:
            payload["temperature"] = eff_temp
        # max_tokens：模型配置了就透传
        if cfg.max_tokens is not None:
            payload["max_tokens"] = cfg.max_tokens

        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }

        return self._stream_chat(cfg.base_url, payload, headers)

    def _parse_non_stream(self, data: dict) -> AssistantMessage:
        try:
            choice = data["choices"][0]
            msg = choice["message"]
        except (KeyError, IndexError) as e:
            raise InvalidAssistantMessage(str(data)) from e

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            raw_args = tc.get("function", {}).get("arguments", "")
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                logger.warning(
                    "非流式 tool_call arguments JSON 解析失败，原始片段：%s", raw_args[:200]
                )
                args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                args=args,
            ))
        # 读取上游 API 真实 usage（不再用本地估算）
        from open_fox.core.adapters.base import UsageInfo
        usage = UsageInfo.from_openai_usage(data.get("usage"))
        # reasoning_content：DeepSeek-R1 等推理模型返回；多轮必须回传
        reasoning = msg.get("reasoning_content") or ""
        return AssistantMessage(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            usage=usage,
            reasoning_content=reasoning,
        )

    def _stream_chat(
        self,
        base_url: str,
        payload: dict,
        headers: dict,
    ) -> AsyncIterator[ChatChunk]:
        """流式调用，逐 chunk 产出。

        返回 AsyncIterator[ChatChunk]。部分 provider 会在流末尾发送独立
        usage chunk，由 ChatChunk 携带并交给 AgentLoop 累积。
        """
        async def gen() -> AsyncIterator[ChatChunk]:
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as resp:
                        if resp.status_code >= 400:
                            raise ModelAPIError(resp.status_code, await resp.aread())
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                yield ChatChunk(finish_reason="stop")
                                return
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            chunk = self._parse_stream_chunk(data)
                            if chunk:
                                yield chunk
            except httpx.HTTPError as e:
                raise StreamInterrupted(str(e)) from e

        return gen()

    def _parse_stream_chunk(self, data: dict) -> ChatChunk | None:
        usage = UsageInfo.from_openai_usage(data.get("usage"))
        # usage chunk 通常没有 choices，只承载最终 token 统计。
        if not data.get("choices"):
            return ChatChunk(usage=usage) if data.get("usage") else None
        try:
            choice = data["choices"][0]
            delta = choice.get("delta", {})
        except (KeyError, IndexError):
            return None
        content = delta.get("content") or ""
        # reasoning_content（DeepSeek-R1 等推理模型流式返回的思考增量）
        reasoning = delta.get("reasoning_content") or ""

        # 流式 tool_calls：OpenAI 规范中通过 index 区分多个 tool_call
        # 每个 chunk 可能携带不同 index 的 id/name/arguments 片段
        tc_delta = None
        args_delta = ""
        tc_index = -1
        if delta.get("tool_calls"):
            tcd = delta["tool_calls"][0]  # 每个 chunk 通常只带一个 tool_call 的 delta
            tc_index = tcd.get("index", 0)
            args_delta = tcd.get("function", {}).get("arguments", "")
            tc_delta = ToolCall(
                id=tcd.get("id", ""),
                name=tcd.get("function", {}).get("name", ""),
                args={},
            )

        return ChatChunk(
            content_delta=content,
            tool_call_delta=tc_delta,
            tool_call_index=tc_index,
            finish_reason=choice.get("finish_reason"),
            reasoning_delta=reasoning,
            tool_call_args_delta=args_delta,
            usage=usage,
        )
