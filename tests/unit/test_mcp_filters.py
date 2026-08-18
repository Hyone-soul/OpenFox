"""MCP 客户端 _apply_filters 测试。"""

from open_fox.config import McpServerConfig
from open_fox.core.mcp.client import McpClient


def test_no_filter_returns_all():
    c = McpClient([])
    out = c._apply_filters(
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],
        McpServerConfig(name="x", transport="stdio", command="e"),
    )
    assert len(out) == 3


def test_allowlist_filters():
    c = McpClient([])
    cfg = McpServerConfig(name="x", transport="stdio", command="e",
                          tool_allowlist=["a", "c"])
    out = c._apply_filters([{"name": "a"}, {"name": "b"}, {"name": "c"}], cfg)
    assert [t["name"] for t in out] == ["a", "c"]


def test_denylist_filters():
    c = McpClient([])
    cfg = McpServerConfig(name="x", transport="stdio", command="e",
                          tool_denylist=["b"])
    out = c._apply_filters([{"name": "a"}, {"name": "b"}, {"name": "c"}], cfg)
    assert [t["name"] for t in out] == ["a", "c"]


def test_allow_and_deny_combined():
    c = McpClient([])
    cfg = McpServerConfig(name="x", transport="stdio", command="e",
                          tool_allowlist=["a", "b"], tool_denylist=["b"])
    out = c._apply_filters([{"name": "a"}, {"name": "b"}], cfg)
    assert [t["name"] for t in out] == ["a"]
