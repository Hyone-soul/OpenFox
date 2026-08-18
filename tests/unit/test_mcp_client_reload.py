"""McpClient.reload 测试。"""

import pytest

from open_fox.config import McpServerConfig
from open_fox.core.mcp.client import McpClient


@pytest.mark.asyncio
async def test_reload_calls_stop_then_start(monkeypatch):
    calls: list[str] = []

    async def fake_stop(self):
        calls.append("stop")
    async def fake_start(self):
        calls.append("start")
    monkeypatch.setattr(McpClient, "stop_all", fake_stop)
    monkeypatch.setattr(McpClient, "start_all", fake_start)

    c = McpClient([McpServerConfig(name="x", transport="stdio", command="e")])
    await c.reload()
    assert calls == ["stop", "start"]
