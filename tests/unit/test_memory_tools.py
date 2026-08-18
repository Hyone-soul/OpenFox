# tests/unit/test_memory_tools.py
import pytest

from open_fox.core.memory.manager import MemoryManager
from open_fox.core.memory.tools import register_memory_tools
from open_fox.core.registry import Registry


@pytest.mark.asyncio
async def test_register_and_schema(tmp_path):
    m = MemoryManager(tmp_path=tmp_path)
    await m.load()
    r = Registry()
    register_memory_tools(r, m)
    schemas = r.list_tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "memory_add" in names
    assert "memory_query" in names
    assert "memory_update" in names
    assert "memory_delete" in names
    assert len(names) == 4

@pytest.mark.asyncio
async def test_memory_add_tool_execute(tmp_path):
    m = MemoryManager(tmp_path=tmp_path)
    await m.load()
    r = Registry()
    register_memory_tools(r, m)
    tool = r.resolve("memory_add")
    result = await tool.async_run(memory_type="explicit", section="用户显式记忆", content="记住 FastAPI", confidence="高")
    assert result.success is True
    found = await m.query(keyword="FastAPI")
    assert any("FastAPI" in x for x in found)
