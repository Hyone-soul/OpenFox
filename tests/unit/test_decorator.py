"""@tool 装饰器测试。"""
import pytest

from open_fox.tools import tool
from open_fox.tools.decorator import _TOOL_INSTANCE, _TOOL_MARKER


def test_decorator_marks_function():
    @tool(name="hello", description="say hi")
    def hello(name: str) -> str:
        return f"hi {name}"

    assert getattr(hello, _TOOL_MARKER) is True
    ft = getattr(hello, _TOOL_INSTANCE)
    assert ft.name == "hello"
    assert ft.description.startswith("say hi")


def test_decorator_requires_name():
    with pytest.raises(ValueError, match="name"):
        tool(name="", description="x")(lambda: None)


def test_decorator_requires_description():
    with pytest.raises(ValueError, match="description"):
        tool(name="x", description="")(lambda: None)
