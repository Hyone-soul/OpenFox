"""Session 测试。"""
from open_fox.core.session import Session
from open_fox.core.storage.memory import MemoryStorage


def test_session_basic():
    s = Session(session_id="u1")
    s.add_message("user", "hi")
    s.add_message("assistant", "hello")
    msgs = s.get_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "hello"


def test_session_persistence():
    storage = MemoryStorage()
    s = Session(session_id="u1", storage=storage)
    s.add_message("user", "hi")
    s.save()

    s2 = Session(session_id="u1", storage=storage)
    s2.load()
    assert s2.get_messages() == [{"role": "user", "content": "hi"}]


def test_add_raw_message():
    s = Session(session_id="u1")
    s.add_raw({"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]})
    assert s.get_messages()[0]["tool_calls"] == [{"id": "1"}]


def test_meta_roundtrip():
    s = Session(session_id="s1")
    s.set_meta(agent_id="demo", title="会话1", model="m1", temperature=0.5)
    assert s.get_meta()["agent_id"] == "demo"
    assert s.get_meta()["title"] == "会话1"


def test_chat_messages_filters_meta():
    s = Session(session_id="s1")
    s.set_meta(agent_id="demo", title="t")
    s.add_message("user", "hello")
    assert s.chat_messages() == [{"role": "user", "content": "hello"}]


def test_meta_not_broken_after_load(tmp_path):
    from open_fox.core.storage.json_store import JsonStorage
    storage = JsonStorage(tmp_path)
    s = Session(session_id="x", storage=storage)
    s.set_meta(agent_id="demo", title="t")
    s.add_message("user", "hi")
    s.save()
    s2 = Session(session_id="x", storage=storage)
    s2.load()
    assert s2.get_meta()["agent_id"] == "demo"
    assert [m for m in s2.chat_messages() if m["role"] != "__meta__"]