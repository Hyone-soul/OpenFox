"""待确认候选队列单元测试。"""
import pytest

from open_fox.core.evolution.pending import PendingQueue


@pytest.mark.asyncio
async def test_enqueue_and_list(tmp_path):
    q = PendingQueue(tmp_path / "pending.json")
    await q.load()
    item = await q.enqueue("create", "evo-demo", "测试候选",
                           "---\nname: evo-demo\ndescription: d\n---\n正文")
    assert item.status == "pending"
    pending = q.list("pending")
    assert len(pending) == 1
    assert pending[0].skill_name == "evo-demo"


@pytest.mark.asyncio
async def test_mark_status(tmp_path):
    q = PendingQueue(tmp_path / "pending.json")
    await q.load()
    item = await q.enqueue("fix", "pdf", "修复", "---\nname: pdf\ndescription: d\n---\n新正文")
    await q.mark_status(item.id, "confirmed")
    assert q.list("pending") == []
    got = q.get(item.id)
    assert got is not None and got.status == "confirmed"


@pytest.mark.asyncio
async def test_persistence_roundtrip(tmp_path):
    q = PendingQueue(tmp_path / "pending.json")
    await q.load()
    await q.enqueue("create", "a", "原因", "---\nname: a\ndescription: d\n---\n正文")
    q2 = PendingQueue(tmp_path / "pending.json")
    await q2.load()
    assert len(q2.list("pending")) == 1
