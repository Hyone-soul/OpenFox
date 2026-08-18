import pytest

from open_fox.core.custom_tools.reload import _is_builtin_tool, reload_all
from open_fox.core.registry import Registry
from open_fox.core.tools.base import ToolResult


def test_is_builtin_tool_protects_core():
    for n in ["read_file", "write_file", "edit_file", "run_shell"]:
        assert _is_builtin_tool(n) is True


def test_is_builtin_tool_protects_memory_prefix():
    assert _is_builtin_tool("memory_save") is True
    assert _is_builtin_tool("memory_list") is True
    assert _is_builtin_tool("not_memory") is False


def test_is_builtin_tool_allows_custom():
    assert _is_builtin_tool("my_custom_tool") is False
    assert _is_builtin_tool("foo__bar") is False


@pytest.mark.asyncio
async def test_reload_all_does_not_unregister_builtin(tmp_path):
    """集成测试：注册 builtin + memory mock 后跑 reload_all，验证不被清。"""
    from open_fox.core.custom_tools.loader import CustomToolsLoader
    from open_fox.core.mcp.client import McpClient

    reg = Registry()

    class FakeBuiltin:
        name = "read_file"
        description = ""
        parameters = {}  # noqa: RUF012

        def execute(self, **kw):
            return ToolResult(success=True, content="x")

        async def async_run(self, **kw):
            return self.execute(**kw)

    reg.register_tool(FakeBuiltin())

    class FakeMemory:
        name = "memory_save"
        description = ""
        parameters = {}  # noqa: RUF012

        def execute(self, **kw):
            return ToolResult(success=True)

        async def async_run(self, **kw):
            return self.execute(**kw)

    reg.register_tool(FakeMemory())

    custom = CustomToolsLoader(tmp_path / "tools", reg)
    custom.rescan()
    mcp = McpClient([])

    from open_fox.tools.decorator import FunctionTool

    def myfn():
        return "x"

    reg.register_tool(FunctionTool(myfn, name="custom_one", description="x", parameters={}))
    assert "custom_one" in reg._tools

    report = await reload_all(reg, custom, mcp, tmp_path / "mcps")

    assert "read_file" in reg._tools, "builtin 不应被清"
    assert "memory_save" in reg._tools, "memory_* 不应被清"
    assert "custom_one" not in reg._tools, "自定义工具应被清"
    assert report["custom_tools"] == []
    assert report["mcp_servers"] == []
    assert report["errors"] == []