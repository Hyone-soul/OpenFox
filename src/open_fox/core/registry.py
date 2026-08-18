"""统一注册表：内置工具、MCP 工具。

Skill 脚本不在此注册 —— 按官方 Agent Skills 渐进披露规范，skill 脚本由 agent
读到 SKILL.md 后用 run_shell 按需执行（cwd 为项目根），不需要也不应该出现在
function calling 工具列表里。
"""

from __future__ import annotations

from open_fox.core.mcp.tool_adapter import McpToolAdapter
from open_fox.core.tools.base import BaseTool


class Registry:
    """按名字索引所有可被 Agent 调用的事物。

    命名空间：
    - 内置工具：直接使用其 name
    - MCP 工具：<server>__<tool>
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._mcp_tools: dict[str, McpToolAdapter] = {}

    def register_tool(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def unregister_tool(self, name: str) -> None:
        self._tools.pop(name, None)

    def register_mcp_tool(self, adapter: McpToolAdapter) -> None:
        self._mcp_tools[adapter.name] = adapter

    def get_tool(self, name: str):
        return self._tools.get(name)

    def resolve(self, name: str) -> BaseTool | McpToolAdapter | None:
        return self._tools.get(name) or self._mcp_tools.get(name)

    def list_tool_schemas(self) -> list[dict]:
        schemas = [t.to_schema() for t in self._tools.values()]
        schemas.extend(a.to_schema() for a in self._mcp_tools.values())
        return schemas