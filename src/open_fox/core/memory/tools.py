# src/open_fox/core/memory/tools.py
from __future__ import annotations

from open_fox.core.memory.manager import MemoryManager, MemoryManagerPool, get_current_user
from open_fox.core.registry import Registry
from open_fox.core.tools.base import BaseTool, ToolResult


class _MemoryTool(BaseTool):
    """池感知记忆工具基类：持有 MemoryManagerPool 引用，
    执行时根据当前上下文用户名解析对应的 MemoryManager。
    """

    def __init__(self, pool: MemoryManagerPool):
        self._pool = pool
        self.parameters = {
            "type": "object",
            "properties": self.properties(),
            "required": self.required(),
        }

    async def _get_manager(self) -> MemoryManager:
        """根据上下文用户名获取对应的 MemoryManager（懒加载）。"""
        username = get_current_user()
        if hasattr(self._pool, "get"):
            return await self._pool.get(username)
        # 兼容 CLI/单元测试直接注入 MemoryManager 的旧接口。
        return self._pool

    def properties(self) -> dict:
        return {}

    def required(self) -> list:
        return []

    def execute(self, **kwargs) -> ToolResult:
        # Memory 工具走 async_run；同步 execute 只是兜底（正常不会被调）
        raise NotImplementedError("Memory 工具通过 async_run 执行")

    async def async_run(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class MemoryAddTool(_MemoryTool):
    name = "memory_add"
    description = "新增一条全局记忆。memory_type=explicit（用户显式）或 implicit（自动提炼）；content 为精简结论。"

    def properties(self) -> dict:
        return {
            "memory_type": {"type": "string", "enum": ["explicit", "implicit"], "description": "记忆类型"},
            "section": {"type": "string", "description": "记忆板块名"},
            "content": {"type": "string", "description": "精简后的记忆内容"},
            "confidence": {"type": "string", "enum": ["高", "中", "低"], "description": "置信度"},
        }

    def required(self) -> list:
        return ["memory_type", "section", "content"]

    async def async_run(self, **kwargs) -> ToolResult:
        try:
            manager = await self._get_manager()
            msg = await manager.add(
                kwargs["memory_type"], kwargs.get("section", ""),
                kwargs.get("content", ""), kwargs.get("confidence", "低"),
            )
            return ToolResult(success=True, content=msg)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=str(e))


class MemoryQueryTool(_MemoryTool):
    name = "memory_query"
    description = "查询全局记忆。keyword 可空（查全部）；memory_type 可空（查全部）。"

    def properties(self) -> dict:
        return {
            "keyword": {"type": "string", "description": "检索关键词"},
            "memory_type": {"type": "string", "enum": ["explicit", "implicit", "archive", ""], "description": "记忆类型过滤"},
        }

    def required(self) -> list:
        return []

    async def async_run(self, **kwargs) -> ToolResult:
        try:
            manager = await self._get_manager()
            rows = await manager.query(kwargs.get("keyword", ""), kwargs.get("memory_type", ""))
            return ToolResult(success=True, content="\n".join(rows) if rows else "（无匹配记忆）")
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=str(e))


class MemoryUpdateTool(_MemoryTool):
    name = "memory_update"
    description = "更新一条记忆：target_content 旧内容 → new_content 新内容；旧内容自动移入归档。"

    def properties(self) -> dict:
        return {
            "target_content": {"type": "string", "description": "要更新的旧内容"},
            "new_content": {"type": "string", "description": "新内容"},
            "memory_type": {"type": "string", "enum": ["explicit", "implicit", ""], "description": "记忆类型"},
        }

    def required(self) -> list:
        return ["target_content", "new_content"]

    async def async_run(self, **kwargs) -> ToolResult:
        try:
            manager = await self._get_manager()
            msg = await manager.update(
                kwargs["target_content"], kwargs["new_content"], kwargs.get("memory_type", ""),
            )
            return ToolResult(success=True, content=msg)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=str(e))


class MemoryDeleteTool(_MemoryTool):
    name = "memory_delete"
    description = "删除一条记忆。archive=true 移入归档（默认）；archive=false 物理删除。显式记忆不可自动删除。"

    def properties(self) -> dict:
        return {
            "target_content": {"type": "string", "description": "要删除的记忆内容"},
            "archive": {"type": "boolean", "description": "是否归档而非物理删除"},
        }

    def required(self) -> list:
        return ["target_content"]

    async def async_run(self, **kwargs) -> ToolResult:
        try:
            manager = await self._get_manager()
            msg = await manager.delete(kwargs["target_content"], kwargs.get("archive", True))
            return ToolResult(success=True, content=msg)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=str(e))


def register_memory_tools(registry: Registry, pool: MemoryManagerPool) -> None:
    """注册池感知记忆工具（执行时根据上下文自动解析当前用户的 MemoryManager）。"""
    registry.register_tool(MemoryAddTool(pool))
    registry.register_tool(MemoryQueryTool(pool))
    registry.register_tool(MemoryUpdateTool(pool))
    registry.register_tool(MemoryDeleteTool(pool))
