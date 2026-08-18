"""把 MCP 工具适配为 Registry 可调用的对象。"""

from __future__ import annotations

from open_fox.core.mcp.transports.base import McpTransport
from open_fox.core.tools.base import ToolResult


class McpToolAdapter:
    """单个 MCP 工具的适配器。"""

    def __init__(self, server_name: str, transport: McpTransport,
                 tool_name: str, description: str, input_schema: dict):
        self._server_name = server_name
        self._transport = transport
        self._tool_name = tool_name
        self._description = description
        self._schema = input_schema

    @property
    def name(self) -> str:
        # 命名空间：<server>__<tool>
        return f"{self._server_name}__{self._tool_name}"

    async def call(self, args: dict) -> ToolResult:
        try:
            result = await self._transport.call_tool(self._tool_name, args)
        except Exception as e:
            return ToolResult(success=False, error=f"MCP 调用失败：{e}")
        # MCP 结果中 content 列表第一个 text 段作为输出
        contents = result.get("content", [])
        text = "\n".join(c.get("text", "") for c in contents if c.get("type") == "text")
        return ToolResult(success=True, content=text or json_dumps(result))

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._description,
                "parameters": self._schema,
            },
        }


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)