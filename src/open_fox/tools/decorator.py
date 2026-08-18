"""@tool 装饰器与 FunctionTool 包装类。"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from open_fox.core.custom_tools.schema_builder import (
    build_schema_from_signature,
    parse_docstring_args,
    parse_docstring_summary,
)
from open_fox.core.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_TOOL_MARKER = "_is_openfox_tool"
_TOOL_INSTANCE = "_openfox_tool"


def tool(*, name: str, description: str):
    """标记函数为 OpenFox 工具，挂载 FunctionTool 实例。"""
    if not name or not isinstance(name, str):
        raise ValueError("@tool 必须提供非空 name")
    if not description:
        raise ValueError("@tool 必须提供 description")

    def decorator(func: Callable) -> Callable:
        params = _build_schema(func)
        doc_desc = parse_docstring_summary(func.__doc__)
        full_desc = description + ("\n\n" + doc_desc if doc_desc else "")
        ft = FunctionTool(
            func, name=name, description=full_desc, parameters=params,
        )
        setattr(func, _TOOL_MARKER, True)
        setattr(func, _TOOL_INSTANCE, ft)
        return func
    return decorator


class FunctionTool(BaseTool):
    """装饰器包装后的 BaseTool 子类。"""

    def __init__(self, func: Callable, *, name: str, description: str, parameters: dict):
        self._func = func
        self.name = name
        self.description = description
        self.parameters = parameters
        self._is_async = asyncio.iscoroutinefunction(func)

    def execute(self, **kwargs) -> ToolResult:
        try:
            return _coerce(self._func(**kwargs))
        except Exception as e:
            logger.exception("本地工具 %s 异常", self.name)
            return ToolResult(success=False, error=f"本地工具异常：{e}")

    async def async_run(self, **kwargs) -> ToolResult:
        if not self._is_async:
            return self.execute(**kwargs)
        try:
            return _coerce(await self._func(**kwargs))
        except Exception as e:
            logger.exception("本地工具 %s 异常", self.name)
            return ToolResult(success=False, error=f"本地工具异常：{e}")


def _coerce(ret) -> ToolResult:
    if isinstance(ret, ToolResult):
        return ret
    if isinstance(ret, str):
        return ToolResult(success=True, content=ret)
    return ToolResult(success=True, content=str(ret))


# 基于签名 + 类型注解 + docstring 的真实 schema 生成（Task 3 接入 schema_builder）
def _build_schema(func) -> dict:
    schema = build_schema_from_signature(func)
    args_desc = parse_docstring_args(func.__doc__)
    for name, desc in args_desc.items():
        if name in schema.get("properties", {}):
            schema["properties"][name]["description"] = desc
    return schema
