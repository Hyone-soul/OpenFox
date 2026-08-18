"""项目存储层：JSON 文件存储，类似 Session 存储。

每个项目对应 data/projects/{project_id}.json。
一个 workdir 只能对应一个 project（重复创建返回已有 project）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class ProjectStore:
    """Project JSON 文件存储。"""

    def __init__(self, base_dir: str | Path = "./data/projects"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, pid: str) -> Path:
        return self._base_dir / f"{pid}.json"

    def create(self, workdir: str, name: str | None = None,
               owner: str = "Ciel") -> dict:
        """创建项目。若 workdir 已有对应项目，直接返回已有项目。"""
        existing = self._find_by_workdir(workdir)
        if existing:
            return existing

        pid = f"p-{uuid.uuid4().hex[:12]}"
        project_name = name or Path(workdir).name
        project = {
            "id": pid,
            "name": project_name,
            "workdir": str(Path(workdir).resolve()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner": owner,
            "pinned": False,
        }
        self._save(pid, project)
        return project

    def list(self, owner: str | None = None) -> list[dict]:
        """列出所有项目（可按 owner 过滤）。"""
        projects = []
        for f in self._base_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if owner and data.get("owner", "Ciel") != owner:
                    continue
                projects.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        # 置顶优先，然后按创建时间排序
        projects.sort(key=lambda p: (
            not p.get("pinned", False),
            p.get("created_at", ""),
        ))
        return projects

    def get(self, pid: str) -> dict | None:
        """获取单个项目。"""
        p = self._path(pid)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, pid: str) -> bool:
        """删除项目（不删会话，会话的 project_id 由调用方清空）。"""
        p = self._path(pid)
        if p.exists():
            p.unlink()
            return True
        return False

    def rename(self, pid: str, new_name: str) -> dict | None:
        """重命名项目。"""
        project = self.get(pid)
        if project is None:
            return None
        project["name"] = new_name
        self._save(pid, project)
        return project

    def set_pinned(self, pid: str, pinned: bool) -> dict | None:
        """设置项目置顶状态。"""
        project = self.get(pid)
        if project is None:
            return None
        project["pinned"] = pinned
        self._save(pid, project)
        return project

    def _find_by_workdir(self, workdir: str) -> dict | None:
        """通过 workdir 查找已有项目。"""
        resolved = str(Path(workdir).resolve())
        for p in self._base_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("workdir") == resolved:
                    return data
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def _save(self, pid: str, data: dict) -> None:
        self._path(pid).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
