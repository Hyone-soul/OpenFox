"""工具基类测试。"""
import pytest

from open_fox.core.tools.base import BaseTool, ToolResult


class EchoTool(BaseTool):
    name = "echo"
    description = "回显输入"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content=kwargs["text"])


def test_execute_returns_tool_result():
    tool = EchoTool()
    r = tool.execute(text="hello")
    assert r.success is True
    assert r.content == "hello"


def test_to_schema_returns_openai_function_format():
    tool = EchoTool()
    schema = tool.to_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "echo"
    assert schema["function"]["description"] == "回显输入"
    assert "text" in schema["function"]["parameters"]["properties"]


def test_tool_result_error_field():
    r = ToolResult(success=False, error="oops")
    assert r.success is False
    assert r.error == "oops"
    assert r.content == ""