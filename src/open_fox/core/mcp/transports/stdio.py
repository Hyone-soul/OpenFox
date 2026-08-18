"""MCP stdio transport。

通过子进程 stdin/stdout 交换 JSON-RPC 消息。
每个请求一个 JSON object + \\n，响应格式相同。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from open_fox.config import McpServerConfig
from open_fox.core.mcp.transports.base import McpTransport

logger = logging.getLogger(__name__)


class StdioTransport(McpTransport):
    """通过子进程与 MCP server 通信。"""

    def __init__(self, cfg: McpServerConfig):
        self._cfg = cfg
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def connect(self) -> None:
        if not self._cfg.command:
            raise ValueError("stdio transport 需要 command 字段")
        self._proc = await asyncio.create_subprocess_shell(
            self._cfg.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # initialize 握手
        await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "openfox", "version": "0.1.0"},
        })
        await self._notify("notifications/initialized", {})

    async def list_tools(self) -> list[dict]:
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, args: dict) -> dict:
        return await self._request("tools/call", {"name": name, "arguments": args})

    async def close(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                await self._proc.wait()
            except ProcessLookupError:
                pass
            self._proc = None

    async def _request(self, method: str, params: dict) -> dict:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            raise RuntimeError("transport 未连接")
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        self._proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

        # 读取一行响应（忽略 notifications）
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server 关闭")
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def _notify(self, method: str, params: dict) -> None:
        if not self._proc or not self._proc.stdin:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self._proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()