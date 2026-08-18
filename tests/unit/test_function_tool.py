"""FunctionTool 类测试。"""
import asyncio

from open_fox.core.tools.base import ToolResult
from open_fox.tools.decorator import FunctionTool


def _ft(func, name="t", desc="d", params=None):
    return FunctionTool(func, name=name, description=desc, parameters=params or {})


def test_execute_normalizes_string_return():
    ft = _ft(lambda x: f"got {x}")
    r = ft.execute(x="a")
    assert isinstance(r, ToolResult)
    assert r.success is True
    assert r.content == "got a"


def test_execute_normalizes_tool_result():
    ft = _ft(lambda: ToolResult(success=False, error="e"))
    r = ft.execute()
    assert r.success is False and r.error == "e"


def test_execute_catches_exception():
    def boom():
        raise RuntimeError("nope")
    r = _ft(boom).execute()
    assert r.success is False
    assert r.error.startswith("本地工具异常：")
    assert "nope" in r.error


def test_async_run_dispatches_async_function():
    async def af(x):
        return x * 2
    ft = _ft(af)
    r = asyncio.run(ft.async_run(x=3))
    assert r.success is True and r.content == "6"


def test_async_run_catches_async_exception():
    async def af():
        raise ValueError("bad")
    r = asyncio.run(_ft(af).async_run())
    assert r.success is False and "bad" in r.error
