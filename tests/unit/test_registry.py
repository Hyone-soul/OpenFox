"""Registry 测试。"""
import pytest

from open_fox.core.registry import Registry
from open_fox.core.tools.base import BaseTool, ToolResult


class FakeTool(BaseTool):
    name = "fake"
    description = "fake tool"
    parameters = {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="fake")


def test_register_and_resolve_tool():
    r = Registry()
    t = FakeTool()
    r.register_tool(t)
    assert r.resolve("fake") is t


def test_resolve_unknown_returns_none():
    r = Registry()
    assert r.resolve("nope") is None


def test_overwrite_tool_with_same_name():
    r = Registry()
    a = FakeTool()
    b = FakeTool()
    r.register_tool(a)
    r.register_tool(b)
    assert r.resolve("fake") is b


def test_list_tool_schemas_combines_tools_and_mcp():
    r = Registry()
    r.register_tool(FakeTool())
    schemas = r.list_tool_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "fake"