"""JSON 文件存储测试。"""
import json
from pathlib import Path

import pytest

from open_fox.core.storage.json_store import JsonStorage


def test_save_creates_file(tmp_path: Path):
    s = JsonStorage(base_dir=tmp_path / "sessions")
    msgs = [{"role": "user", "content": "hi"}]
    s.save("u1", msgs)
    f = tmp_path / "sessions" / "u1.json"
    assert f.exists()
    assert json.loads(f.read_text(encoding="utf-8")) == msgs


def test_load_round_trip(tmp_path: Path):
    s = JsonStorage(base_dir=tmp_path / "sessions")
    msgs = [{"role": "assistant", "content": "hello", "tool_calls": []}]
    s.save("u1", msgs)
    assert s.load("u1") == msgs


def test_load_missing(tmp_path: Path):
    s = JsonStorage(base_dir=tmp_path / "sessions")
    assert s.load("nope") is None


def test_list_ids(tmp_path: Path):
    s = JsonStorage(base_dir=tmp_path / "sessions")
    s.save("a", [])
    s.save("b", [])
    s.save("c.json", [])  # .json 后缀应当被去除
    assert sorted(s.list_ids()) == ["a", "b", "c"]


def test_delete(tmp_path: Path):
    s = JsonStorage(base_dir=tmp_path / "sessions")
    s.save("a", [{"role": "user", "content": "x"}])
    s.delete("a")
    assert not (tmp_path / "sessions" / "a.json").exists()


def test_session_id_path_traversal_raises(tmp_path: Path):
    """session_id 含 ../ 等非法字符应抛 ValueError，防止路径穿越越界写文件。"""
    s = JsonStorage(base_dir=tmp_path / "sessions")
    evil_ids = [
        "../../etc/passwd",
        "../sibling",
        "a/../b",
        "..",
        "a b",
        "a/b",
        "..\\sibling",
    ]
    for sid in evil_ids:
        with pytest.raises(ValueError):
            s._path(sid)
        with pytest.raises(ValueError):
            s.save(sid, [])
        with pytest.raises(ValueError):
            s.load(sid)
        with pytest.raises(ValueError):
            s.delete(sid)
    # 越界文件不应被写入
    assert not (tmp_path / "etc" / "passwd.json").exists()
    assert not (tmp_path / "sibling.json").exists()
    # 合法 id 不受影响（覆盖现有 data/sessions 中的命名模式）
    assert s._path("demo-session-001") == tmp_path / "sessions" / "demo-session-001.json"
    assert s._path("oai-0cd8ceff43e04397") == tmp_path / "sessions" / "oai-0cd8ceff43e04397.json"
    assert s._path("s-ae8d9896f4a2.json") == tmp_path / "sessions" / "s-ae8d9896f4a2.json"
    assert s._path("test-session-multi-turn") == tmp_path / "sessions" / "test-session-multi-turn.json"