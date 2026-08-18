"""MCP transport 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class McpTransport(ABC):
    """MCP transport 抽象。"""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接，必要时做 initialize 握手。"""

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """列出该 server 提供的工具 schema。"""

    @abstractmethod
    async def call_tool(self, name: str, args: dict) -> dict:
        """调用指定工具，返回 MCP 标准结果。"""

    @abstractmethod
    async def close(self) -> None:
        """关闭连接。"""