"""MCP SSE transport。

通过 mcp SDK 的 sse_client 建立 SSE 连接，自动处理端点发现
（GET /sse → 获取 message endpoint → POST 到该 endpoint）。

注意：sse_client 内部使用 anyio TaskGroup，会跨 task 传播异常。
为了避免与 Starlette BaseHTTPMiddleware 的 cancel scope 冲突，
connect() 通过独立的 asyncio task 来运行 sse_client，
确保 TaskGroup 在隔离的上下文中管理。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp.client.sse import sse_client

from open_fox.config import McpServerConfig
from open_fox.core.mcp.transports.base import McpTransport

logger = logging.getLogger(__name__)


class SSETransport(McpTransport):
    """通过 mcp SDK sse_client 与 MCP 服务器通信。"""

    def __init__(self, cfg: McpServerConfig):
        self._cfg = cfg
        self._exit_stack: AsyncExitStack | None = None
        self._read_stream: Any = None
        self._write_stream: Any = None
        self._next_id = 1

    async def connect(self) -> None:
        if not self._cfg.url:
            raise ValueError("sse transport 需要 url 字段")

        # 在独立 task 中运行 sse_client，隔离 anyio TaskGroup 的 cancel scope，
        # 避免与 Starlette BaseHTTPMiddleware 冲突
        result = await asyncio.create_task(self._connect_inner())
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

    async def _connect_inner(self) -> dict:
        """在独立 task 中建立 SSE 连接，返回流和 exit_stack。"""
        stack = AsyncExitStack()
        read_stream, write_stream = await stack.enter_async_context(
            sse_client(
                url=self._cfg.url,
                headers=dict(self._cfg.headers) if self._cfg.headers else None,
                timeout=self._cfg.timeout,
                sse_read_timeout=float(self._cfg.timeout * 10),
            )
        )
        return {
            "exit_stack": stack,
            "read_stream": read_stream,
            "write_stream": write_stream,
        }

    async def list_tools(self) -> list[dict]:
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, args: dict) -> dict:
        return await self._request("tools/call", {"name": name, "arguments": args})

    async def close(self) -> None:
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.debug("关闭 SSE transport 时出错（可忽略）：%s", e)
            self._exit_stack = None
            self._read_stream = None
            self._write_stream = None

    async def _request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC request 并等待对应 id 的响应。"""
        if not self._write_stream or not self._read_stream:
            raise RuntimeError("transport 未连接")

        req_id = self._next_id
        self._next_id += 1

        from mcp.types import JSONRPCRequest
        from mcp.shared.message import SessionMessage

        request_msg = JSONRPCRequest(
            jsonrpc="2.0",
            id=req_id,
            method=method,
            params=params,
        )
        await self._write_stream.send(SessionMessage(request_msg))

        # 从 read_stream 中读取匹配 id 的响应
        async for session_message in self._read_stream:
            if isinstance(session_message, Exception):
                raise session_message
            msg = session_message.message
            # 跳过通知，只处理有 id 的响应
            if hasattr(msg, "id") and msg.id == req_id:
                if hasattr(msg, "error") and msg.error:
                    raise RuntimeError(f"MCP 错误：{msg.error}")
                return getattr(msg, "result", {})

        raise RuntimeError("MCP 连接关闭，未收到响应")

    async def _notify(self, method: str, params: dict) -> None:
        """发送 JSON-RPC notification（无 id，不期望响应）。"""
        if not self._write_stream:
            raise RuntimeError("transport 未连接")

        from mcp.types import JSONRPCNotification
        from mcp.shared.message import SessionMessage

        notify_msg = JSONRPCNotification(
            jsonrpc="2.0",
            method=method,
            params=params,
        )
        await self._write_stream.send(SessionMessage(notify_msg))
