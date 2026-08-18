"""pytest 全局 fixture。"""
from pathlib import Path

import pytest


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """提供隔离的 workspace 目录。"""
    p = tmp_path / "workspace"
    p.mkdir()
    return p


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """提供隔离的 skills 目录。"""
    p = tmp_path / "skills"
    p.mkdir()
    return p