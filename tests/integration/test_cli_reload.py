"""CLI /reload 命令 + build_app 8-tuple 集成测试。"""
import pytest

from open_fox.cli import build_app
from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.custom_tools.reload import reload_all
from open_fox.core.mcp.client import McpClient
from open_fox.core.registry import Registry


def test_build_app_returns_loader():
    """build_app 应返回 8 元组（含 custom_tools_loader）。"""
    _cfg, _adapter, _registry, _loader, _mcp, _memory_manager, _evolution_task, custom_tools_loader = build_app("./config.yaml")
    assert custom_tools_loader is not None
    assert isinstance(custom_tools_loader, CustomToolsLoader)


@pytest.mark.asyncio
async def test_reload_command_logic_runs_reload_all(tmp_path):
    """/reload 命令核心逻辑：调用 reload_all 返回报告。"""
    (tmp_path / "tools").mkdir()
    (tmp_path / "mcps").mkdir()
    reg = Registry()
    custom = CustomToolsLoader(tmp_path / "tools", reg)
    mcp = McpClient([])

    report = await reload_all(reg, custom, mcp, tmp_path / "mcps")
    assert report["custom_tools"] == []
    assert report["mcp_servers"] == []
    assert report["errors"] == []

    (tmp_path / "tools" / "h.py").write_text(
        "from open_fox.tools import tool\n"
        "@tool(name='h', description='x')\n"
        "def h(): return 'ok'\n",
        encoding="utf-8",
    )
    report = await reload_all(reg, custom, mcp, tmp_path / "mcps")
    assert "h" in report["custom_tools"]
    assert "h" in reg._tools
