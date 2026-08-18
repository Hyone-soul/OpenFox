"""MCP streamable-http transport。

通过 mcp SDK 的 streamable_http_client 建立连接。
与 SSE 的区别在于通信通过普通 HTTP body 流式返回（非 SSE 事件流），
但 JSON-RPC 消息交互逻辑相同，因此复用 SSETransport 基类。

同样通过 asyncio.create_task 隔离 anyio TaskGroup 的 cancel scope。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack

from mcp.client.streamable_http import streamable_http_client

from open_fox.config import McpServerConfig
from open_fox.core.mcp.transports.sse import SSETransport

logger = logging.getLogger(__name__)


class StreamableHttpTransport(SSETransport):
    """通过 mcp SDK streamable_http_client 与 MCP 服务器通信。"""

    async def connect(self) -> None:
        if not self._cfg.url:
            raise ValueError("streamable-http transport 需要 url 字段")

        # 在独立 task 中运行 streamable_http_client，隔离 cancel scope
        result = await asyncio.create_task(self._connect_inner_http())
        self._exit_stack = result["exit_stack"]
        self._read_stream = result["read_stream"]
        self._write_stream = result["write_stream"]

        # initialize 握手
        await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "openfox", "version": "0.1.0"},
        })
        # initialized 通知
        await self._notify("notifications/initialized", {})

    async def _connect_inner_http(self) -> dict:
        """在独立 task 中建立 Streamable HTTP 连接。"""
        stack = AsyncExitStack()
        read_stream, write_stream = await stack.enter_async_context(
            streamable_http_client(url=self._cfg.url)
        )
        return {
            "exit_stack": stack,
            "read_stream": read_stream,
            "write_stream": write_stream,
        }
