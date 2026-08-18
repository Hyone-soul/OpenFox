"""
Token Estimator — 统一的 token 估算工具

采用 chars÷4 粗略估算（与 Hermes 一致），非精确 tokenizer。
这是整个上下文管理体系的度量基础——先量化，再治理。
"""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str | None) -> int:
    """估算单个文本的 token 数（chars÷4，最少 0）"""
    if not text:
        return 0
    # 粗略估算：4 字符 ≈ 1 token（中英文混合场景的经验值）
    # 实际中文约 1.5-2 字符/token，英文约 4 字符/token，取折中
    return max(0, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """
    估算消息列表的总 token 数。

    包含：
    - 每条消息的 role 开销（~4 token）
    - content 字段
    - tool_calls 的函数名 + 参数 JSON
    - reasoning_content
    - tool_call_id / name 等元数据
    """
    total = 0
    for msg in messages:
        # 每条消息的基础开销（role、格式化等）
        total += 4

        # content
        total += estimate_tokens(msg.get("content"))

        # reasoning_content（推理模型的思考链）
        total += estimate_tokens(msg.get("reasoning_content"))

        # tool_calls（assistant 消息中的工具调用）
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                total += estimate_tokens(func.get("name"))
                total += estimate_tokens(func.get("arguments"))
                # tool_call id 和 type
                total += 2

        # tool 消息的元数据
        if msg.get("tool_call_id"):
            total += 2
        if msg.get("name"):
            total += estimate_tokens(msg.get("name"))

    return total


def estimate_tool_schemas_tokens(tools: list[dict]) -> int:
    """
    估算工具定义（JSON Schema）的 token 数。

    每个工具约 50-200 token（取决于参数复杂度），
    这里用 JSON 序列化后 chars÷4 来估算。
    """
    if not tools:
        return 0
    # 将整个工具列表序列化为 JSON 后估算
    return estimate_tokens(json.dumps(tools, ensure_ascii=False))


def estimate_system_prompt_tokens(system_prompt: str | None) -> int:
    """估算系统提示的 token 数"""
    return estimate_tokens(system_prompt)


# ════════════════════════════════════════════
# 常见模型的上下文窗口大小参考
# ════════════════════════════════════════════

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-v4-flash": 1_000_000,
    "deepseek-reasoner": 64_000,
    "deepseek-r1": 64_000,
    # Anthropic
    "claude-sonnet-4-20250514": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    # MiniMax
    "MiniMax-M1": 1_000_000,
    # Qwen
    "qwen-max": 32_000,
    "qwen-plus": 131_072,
    # 默认
    "default": 32_000,
}


def get_model_context_window(model_name: str) -> int:
    """
    根据模型名获取上下文窗口大小。

    支持模糊匹配（model_name 包含 key 即可），
    找不到则返回 default (32k)。
    """
    if not model_name:
        return MODEL_CONTEXT_WINDOWS["default"]

    model_lower = model_name.lower()

    # 精确匹配
    if model_name in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_name]

    # 模糊匹配（模型名中包含 key）
    for key, window in MODEL_CONTEXT_WINDOWS.items():
        if key != "default" and key.lower() in model_lower:
            return window

    return MODEL_CONTEXT_WINDOWS["default"]
