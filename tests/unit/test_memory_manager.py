# tests/unit/test_memory_manager.py
import asyncio

import pytest

from open_fox.core.memory.exceptions import MemoryPermissionError
from open_fox.core.memory.manager import MemoryManager
from open_fox.core.memory.models import Entry, ImplicitSection


@pytest.fixture
def tmp_mem(tmp_path):
    return tmp_path / "OPENFOX.md"


@pytest.mark.asyncio
async def test_load_creates_template_if_missing(tmp_mem):
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    assert tmp_mem.exists()
    assert "OpenFox 全局记忆" in tmp_mem.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_add_explicit_roundtrip(tmp_mem):
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.add("explicit", "用户显式记忆", "我用 FastAPI")
    found = await m.query(keyword="FastAPI")
    assert any("FastAPI" in x for x in found)


@pytest.mark.asyncio
async def test_add_implicit_dedup(tmp_mem):
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    r1 = await m.add("implicit", "用户编码与风格偏好", "项目用 ruff", "中")
    r2 = await m.add("implicit", "用户编码与风格偏好", "项目用 ruff", "中")
    assert "已存在" in r2
    assert "已存在" not in r1


@pytest.mark.asyncio
async def test_delete_explicit_raises(tmp_mem):
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.add("explicit", "用户显式记忆", "别删我")
    with pytest.raises(MemoryPermissionError):
        await m.delete("别删我")


@pytest.mark.asyncio
async def test_update_no_match_does_not_deadlock(tmp_mem):
    """C1：update 无匹配退化新增，不得在持锁状态下二次加锁死锁。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    result = await asyncio.wait_for(
        m.update("不存在的旧记忆", "替代的新内容"),
        timeout=2.0,
    )
    assert "已写入隐式记忆" in result


@pytest.mark.asyncio
async def test_update_no_match_fallback_uses_default_section(tmp_mem):
    """I1：update 退化新增路由到默认子板块，而不是把旧内容当 section。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.update("不存在的旧记忆", "新记忆内容")
    found = await m.query(keyword="新记忆内容", memory_type="implicit")
    assert any("用户编码与风格偏好" in x for x in found)


@pytest.mark.asyncio
async def test_update_match_archives_old(tmp_mem):
    """update 命中后覆盖并归档旧记忆。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.add("implicit", "用户编码与风格偏好", "旧内容")
    r = await m.update("旧内容", "新内容")
    assert "已更新并归档旧记忆" in r
    assert any("旧内容" in x for x in await m.query(keyword="旧内容", memory_type="archive"))
    assert any("新内容" in x for x in await m.query(keyword="新内容", memory_type="implicit"))


@pytest.mark.asyncio
async def test_add_explicit_over_500_allowed(tmp_mem):
    """I2：显式记忆强制入库不受 500 字上限；隐式仍受上限约束。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    long_content = "长" * 600
    r = await m.add("explicit", "用户显式记忆", long_content)
    assert "已写入用户显式记忆" in r
    r2 = await m.add("implicit", "用户编码与风格偏好", long_content)
    assert "已拒绝" in r2


@pytest.mark.asyncio
async def test_update_empty_new_content_rejected(tmp_mem):
    """M3：update 匹配路径对空 new_content 做保护。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.add("implicit", "用户编码与风格偏好", "原内容")
    r = await m.update("原内容", "   ")
    assert "内容为空" in r


@pytest.mark.asyncio
async def test_delete_implicit_archives_and_removes_all(tmp_mem):
    """M1：delete 隐式记忆会归档并删除全部副本，归档不累积重复。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    await m.add("implicit", "用户编码与风格偏好", "旧内容")
    await m.add("implicit", "项目约束与配置规范", "旧内容")  # 同一内容在另一子板块
    r = await m.delete("旧内容")
    assert "已删除（归档）" in r
    assert await m.query(keyword="旧内容", memory_type="implicit") == []
    # 归档去重：两处副本只归档一条
    assert len(await m.query(keyword="旧内容", memory_type="archive")) == 1
    # 再次删除 → 命中归档区物理删除
    r2 = await m.delete("旧内容")
    assert "已删除" in r2
    assert await m.query(keyword="旧内容", memory_type="archive") == []


@pytest.mark.asyncio
async def test_memory_text_over_budget_sorts_by_confidence_and_updated(tmp_mem):
    """I1：注入超 2000 字预算时，隐式条目按 (confidence desc, updated desc) 取前 N 条，
    explicit 恒保留、总长不超过 2000 字。"""
    m = MemoryManager(tmp_path=tmp_mem.parent)
    await m.load()
    # 显式记忆恒保留
    await m.add("explicit", "用户显式记忆", "必须保留的显式记忆")
    # 直接构造隐式条目：两条低置信度条目，新日期(08-01)应排在填充之前、旧日期(01-01)在填充之后
    m._doc.implicit.append(ImplicitSection(name="用户编码与风格偏好", entries=[
        Entry(content="新更新条目", meta="置信度：低｜更新时间：2026-08-01", confidence="低"),
        Entry(content="旧更新条目", meta="置信度：低｜更新时间：2026-01-01", confidence="低"),
    ]))
    # 大量同置信度填充条目（updated 介于新旧之间，撑爆 2000 字预算）
    for i in range(30):
        m._doc.implicit.append(ImplicitSection(name="项目约束与配置规范", entries=[
            Entry(content=f"低置信填充 {i}：" + "长" * 100,
                  meta="置信度：低｜更新时间：2026-06-01", confidence="低"),
        ]))
    # 高置信度条目应被优先保留（confidence desc）
    m._doc.implicit.append(ImplicitSection(name="工具与系统使用偏好", entries=[
        Entry(content="关键高置信记忆", meta="置信度：高｜更新时间：2026-05-01", confidence="高"),
    ]))

    text = m.memory_text()
    assert len(text) <= 2000
    assert "必须保留的显式记忆" in text
    assert "关键高置信记忆" in text
    # 同置信度下新日期优先（updated desc）：新更新条目被保留、旧更新条目被裁掉
    assert "新更新条目" in text
    assert "旧更新条目" not in text
    # 末尾的填充条目被裁掉
    assert "低置信填充 29" not in text
