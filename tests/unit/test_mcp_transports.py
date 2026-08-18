"""MCP transport 基础测试。

为避免引入真实 MCP server，本测试仅覆盖 transport 接口契约与一个
端到端 fake server 流程（stdio）。
"""
import asyncio
import json
import sys

import pytest

from open_fox.config import McpServerConfig
from open_fox.core.mcp.transports.stdio import StdioTransport


# 用一个小 Python 脚本模拟 MCP server（仅本测试）
FAKE_SERVER = r"""
import json, sys

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

# 收到 initialize
line = sys.stdin.readline()
req = json.loads(line)
send({"jsonrpc": "2.0", "id": req["id"], "result": {"serverInfo": {"name": "fake"}}})

# 收到 initialized 通知（不需响应）
line = sys.stdin.readline()

# 收到 tools/list
line = sys.stdin.readline()
req = json.loads(line)
send({"jsonrpc": "2.0", "id": req["id"], "result": {
    "tools": [{
        "name": "echo",
        "description": "echo",
        "inputSchema": {"type": "object", "properties": {"x": {"type": "string"}}}
    }]
}})

# 收到 tools/call
line = sys.stdin.readline()
req = json.loads(line)
send({"jsonrpc": "2.0", "id": req["id"], "result": {
    "content": [{"type": "text", "text": "echoed"}]
}})
"""


@pytest.mark.asyncio
async def test_stdio_transport_end_to_end(tmp_path):
    server_script = tmp_path / "fake_server.py"
    server_script.write_text(FAKE_SERVER, encoding="utf-8")

    cfg = McpServerConfig(
        name="fake", transport="stdio",
        command=f"{sys.executable} {server_script}",
    )
    t = StdioTransport(cfg)
    try:
        await t.connect()
        tools = await t.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"
        result = await t.call_tool("echo", {"x": "hi"})
        assert result["content"][0]["text"] == "echoed"
    finally:
        await t.close()