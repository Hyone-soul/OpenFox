"""内存存储测试。"""
from open_fox.core.storage.memory import MemoryStorage


def test_save_and_load():
    s = MemoryStorage()
    msgs = [{"role": "user", "content": "hi"}]
    s.save("u1", msgs)
    assert s.load("u1") == msgs


def test_load_missing_returns_none():
    s = MemoryStorage()
    assert s.load("nope") is None


def test_list_ids():
    s = MemoryStorage()
    s.save("a", [])
    s.save("b", [])
    assert sorted(s.list_ids()) == ["a", "b"]


def test_delete():
    s = MemoryStorage()
    s.save("a", [{"role": "user", "content": "x"}])
    s.delete("a")
    assert s.load("a") is None
    assert s.list_ids() == []


def test_overwrite():
    s = MemoryStorage()
    s.save("a", [{"role": "user", "content": "v1"}])
    s.save("a", [{"role": "user", "content": "v2"}])
    assert s.load("a") == [{"role": "user", "content": "v2"}]