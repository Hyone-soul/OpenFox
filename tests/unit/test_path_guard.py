"""路径守卫测试 - 防止路径穿越与越界访问。"""
import pytest

from open_fox.core.exceptions import PathGuardViolation
from open_fox.core.security.path_guard import PathGuard


@pytest.fixture
def guard(tmp_path):
    allowed = [tmp_path / "skills", tmp_path / "workspace"]
    for p in allowed:
        p.mkdir()
    return PathGuard(allowed_roots=allowed, base_dir=tmp_path)


def test_resolve_inside_allowed(guard, tmp_path):
    p = guard.resolve("skills/foo.md")
    assert p == (tmp_path / "skills" / "foo.md").resolve()


def test_resolve_absolute_inside_allowed(guard, tmp_path):
    p = guard.resolve(str(tmp_path / "workspace" / "x.txt"))
    assert p == (tmp_path / "workspace" / "x.txt").resolve()


def test_path_traversal_blocked(guard):
    with pytest.raises(PathGuardViolation):
        guard.resolve("skills/../../../etc/passwd")


def test_path_outside_allowed_blocked(guard, tmp_path):
    with pytest.raises(PathGuardViolation):
        guard.resolve(str(tmp_path / "etc" / "passwd"))


def test_relative_outside_blocked(guard):
    with pytest.raises(PathGuardViolation):
        guard.resolve("../outside.txt")


def test_is_allowed_returns_bool(guard, tmp_path):
    inside = (tmp_path / "skills" / "x").resolve()
    outside = (tmp_path / "outside").resolve()
    assert guard.is_allowed(inside) is True
    assert guard.is_allowed(outside) is False