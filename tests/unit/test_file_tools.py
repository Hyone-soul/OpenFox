"""文件工具测试。"""
from pathlib import Path

import pytest

from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.file_tools import (
    EditFileTool,
    ReadFileTool,
    WriteFileTool,
)


@pytest.fixture
def guard(tmp_path):
    skills = tmp_path / "skills"
    workspace = tmp_path / "workspace"
    skills.mkdir()
    workspace.mkdir()
    # ⚠️ 关键：传入 base_dir=tmp_path，否则相对路径会解析到 cwd
    return PathGuard(allowed_roots=[skills, workspace], base_dir=tmp_path)


def test_read_file_success(guard, tmp_path):
    f = tmp_path / "workspace" / "x.txt"
    f.write_text("hello", encoding="utf-8")
    tool = ReadFileTool(path_guard=guard)
    r = tool.execute(path="workspace/x.txt")
    assert r.success is True
    assert r.content == "hello"


def test_read_file_outside_blocked(guard):
    tool = ReadFileTool(path_guard=guard)
    r = tool.execute(path="/etc/passwd")
    assert r.success is False
    assert "路径" in r.error or "Path" in r.error


def test_read_file_missing(guard, tmp_path):
    tool = ReadFileTool(path_guard=guard)
    r = tool.execute(path="workspace/nope.txt")
    assert r.success is False


def test_write_file_creates_file(guard, tmp_path):
    tool = WriteFileTool(path_guard=guard)
    r = tool.execute(path="workspace/new.txt", content="data")
    assert r.success is True
    assert (tmp_path / "workspace" / "new.txt").read_text(encoding="utf-8") == "data"


def test_write_file_overwrites(guard, tmp_path):
    (tmp_path / "workspace" / "x.txt").write_text("old", encoding="utf-8")
    tool = WriteFileTool(path_guard=guard)
    r = tool.execute(path="workspace/x.txt", content="new")
    assert r.success is True
    assert (tmp_path / "workspace" / "x.txt").read_text(encoding="utf-8") == "new"


def test_edit_file_replaces(guard, tmp_path):
    f = tmp_path / "workspace" / "x.txt"
    f.write_text("hello world", encoding="utf-8")
    tool = EditFileTool(path_guard=guard)
    r = tool.execute(path="workspace/x.txt", old="world", new="python")
    assert r.success is True
    assert f.read_text(encoding="utf-8") == "hello python"


def test_edit_file_old_not_found(guard, tmp_path):
    f = tmp_path / "workspace" / "x.txt"
    f.write_text("hello", encoding="utf-8")
    tool = EditFileTool(path_guard=guard)
    r = tool.execute(path="workspace/x.txt", old="zzz", new="new")
    assert r.success is False


def test_path_traversal_blocked(guard):
    tool = ReadFileTool(path_guard=guard)
    r = tool.execute(path="workspace/../../../etc/passwd")
    assert r.success is False