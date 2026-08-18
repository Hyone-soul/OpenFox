"""reload_all(): 重扫 tools/ 和 mcps/，保护内置工具。"""
from __future__ import annotations

import logging
from pathlib import Path

from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.mcp.client import McpClient
from open_fox.core.mcp.config_loader import load_mcp_configs
from open_fox.core.registry import Registry

logger = logging.getLogger(__name__)

_BUILTIN_TOOL_NAMES = {
    "read_file", "write_file", "edit_file", "run_shell",
    # 代码搜索
    "grep_search", "glob_find",
    # 目录与文件管理
    "list_dir", "make_dir", "copy_file", "move_file",
    # Git 操作
    "git_status", "git_diff", "git_commit", "git_log",
    # 浏览器
    "web_search", "web_fetch",
    # 代码理解
    "ast_parse",
    # 任务管理
    "todo_read", "todo_write",
}
_MEMORY_TOOL_PREFIX = "memory_"


def _is_builtin_tool(name: str) -> bool:
    return name in _BUILTIN_TOOL_NAMES or name.startswith(_MEMORY_TOOL_PREFIX)


async def reload_all(
    registry: Registry,
    custom_tools_loader: CustomToolsLoader,
    mcp_client: McpClient,
    mcps_dir: Path,
) -> dict:
    # 1. 清掉现有自定义工具和 MCP 工具（保留 builtin + memory_*）
    for name in [n for n in list(registry._tools) if not _is_builtin_tool(n)]:
        registry.unregister_tool(name)
    for name in list(registry._mcp_tools):
        registry._mcp_tools.pop(name, None)

    # 2. 重扫 tools/
    custom_errors = custom_tools_loader.rescan()

    # 3. 重扫 mcps/ + McpClient 重连
    new_configs, mcp_errors = load_mcp_configs(mcps_dir)
    mcp_client._configs = new_configs
    await mcp_client.reload()

    # 4. 重新注册 MCP tools
    for tool in await mcp_client.get_tools():
        registry.register_mcp_tool(tool)

    return {
        "custom_tools": list(custom_tools_loader.all()),
        "mcp_servers": [c.name for c in new_configs if c.enabled],
        "mcp_tools": list(registry._mcp_tools),
        "errors": custom_errors + mcp_errors,
    }