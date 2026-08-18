"""工具基类与结果数据类。

所有内置工具必须继承 BaseTool 并提供 name / description / parameters。
LLM 通过 OpenAI 兼容的 function calling schema 调用工具。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class ToolResult:
    """工具执行结果。

    始终返回结构化结果而非抛异常，确保 Agent 循环不会被工具错误击穿。
    """

    success: bool
    content: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
    # 确认机制：True 表示该命令需要用户确认才能执行，
    # AgentLoop 检测到此标志后推送 tool_confirm 事件，等待用户操作。
    confirm_required: bool = False
    # 待确认的原始命令（confirm_required=True 时必填）
    confirm_cmd: str = ""


class BaseTool(ABC):
    """工具抽象基类。"""

    name: str = ""
    description: str = ""
    # ClassVar 标注：参数 schema 是类级共享属性，避免可变默认值的告警
    parameters: ClassVar[dict] = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑，返回 ToolResult。"""

    async def async_run(self, **kwargs) -> ToolResult:
        """可选异步执行。默认回退到同步 execute；子类可重写（如 Memory 工具）。"""
        return self.execute(**kwargs)

    def to_schema(self) -> dict:
        """转换为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }