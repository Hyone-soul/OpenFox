"""MCP 客户端：管理多个 server 连接并对外暴露统一工具列表。"""

from __future__ import annotations

import asyncio
import logging

from open_fox.config import McpServerConfig
from open_fox.core.mcp.tool_adapter import McpToolAdapter
from open_fox.core.mcp.transports.base import McpTransport
from open_fox.core.mcp.transports.sse import SSETransport
from open_fox.core.mcp.transports.stdio import StdioTransport
from open_fox.core.mcp.transports.streamable_http import StreamableHttpTransport

logger = logging.getLogger(__name__)


def _make_transport(cfg: McpServerConfig) -> McpTransport:
    if cfg.transport == "stdio":
        return StdioTransport(cfg)
    if cfg.transport == "sse":
        return SSETransport(cfg)
    if cfg.transport == "streamable-http":
        return StreamableHttpTransport(cfg)
    raise ValueError(f"未知 MCP transport：{cfg.transport}")


class McpClient:
    """管理多个 MCP server 生命周期。"""

    def __init__(self, configs: list[McpServerConfig]):
        self._configs = configs
        self._transports: dict[str, McpTransport] = {}
        self._tools: list[McpToolAdapter] = []

    async def start_all(self) -> None:
        for cfg in self._configs:
            if not cfg.enabled:
                logger.info("MCP '%s' 已禁用（%s）", cfg.name, cfg.source_file)
                continue
            try:
                t = _make_transport(cfg)
                await t.connect()
                tools_meta = await t.list_tools()
                tools_meta = self._apply_filters(tools_meta, cfg)
                self._transports[cfg.name] = t
                for tm in tools_meta:
                    self._tools.append(McpToolAdapter(
                        server_name=cfg.name, transport=t,
                        tool_name=tm["name"],
                        description=tm.get("description", ""),
                        input_schema=tm.get("inputSchema", {}),
                    ))
                logger.info("MCP '%s' 已连接，提供 %d 个工具（%s）",
                            cfg.name, len(tools_meta), cfg.source_file)
            except Exception as e:
                logger.warning("MCP '%s' 连接失败（%s）：%s",
                               cfg.name, cfg.source_file, e)

    async def get_tools(self) -> list[McpToolAdapter]:
        return list(self._tools)

    async def reload(self) -> None:
        await self.stop_all()
        await self.start_all()

    async def stop_all(self) -> None:
        for name, t in self._transports.items():
            try:
                await t.close()
            except Exception as e:
                logger.warning("关闭 MCP '%s' 失败：%s", name, e)
        self._transports.clear()
        self._tools.clear()

    def _apply_filters(self, tools_meta: list[dict], cfg) -> list[dict]:
        """allowlist ∩ ¬denylist"""
        if cfg.tool_allowlist:
            allow = set(cfg.tool_allowlist)
            tools_meta = [m for m in tools_meta if m["name"] in allow]
        if cfg.tool_denylist:
            deny = set(cfg.tool_denylist)
            tools_meta = [m for m in tools_meta if m["name"] not in deny]
        return tools_meta