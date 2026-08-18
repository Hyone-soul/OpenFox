"""目录与文件管理工具：list_dir / make_dir / copy_file / move_file。

所有路径通过 PathGuard 校验，确保只能在白名单内操作。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.base import BaseTool, ToolResult


class ListDirTool(BaseTool):
    """列出目录内容。"""

    name = "list_dir"
    description = "列出指定目录下的文件和子目录，显示名称、类型和大小。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认为工作区根"},
            "recursive": {"type": "boolean", "description": "是否递归列出子目录，默认 false"},
        },
        "required": [],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        root_str = kwargs.get("path", ".")
        try:
            root = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        if not root.is_dir():
            return ToolResult(success=False, error=f"不是目录：{root}")

        recursive = kwargs.get("recursive", False)
        lines = []

        if recursive:
            for dirpath, dirnames, filenames in _os_walk(root):
                rel_dir = Path(dirpath).relative_to(root)
                for d in sorted(dirnames):
                    lines.append(f"  {rel_dir / d}/")
                for f in sorted(filenames):
                    fp = Path(dirpath) / f
                    size = _safe_size(fp)
                    lines.append(f"  {rel_dir / f}  ({size})")
        else:
            try:
                entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError as e:
                return ToolResult(success=False, error=f"无权限：{e}")
            for p in entries:
                if p.is_dir():
                    lines.append(f"  {p.name}/")
                else:
                    lines.append(f"  {p.name}  ({_safe_size(p)})")

        if not lines:
            return ToolResult(success=True, content="（空目录）")
        return ToolResult(success=True, content="\n".join(lines))


class MakeDirTool(BaseTool):
    """创建目录（含父目录）。"""

    name = "make_dir"
    description = "创建目录，如果父目录不存在则自动创建。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要创建的目录路径"},
        },
        "required": ["path"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            p = self._guard.resolve(kwargs["path"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return ToolResult(success=False, error=f"创建失败：{e}")
        return ToolResult(success=True, content=f"目录已创建：{p}")


class CopyFileTool(BaseTool):
    """复制文件或目录。"""

    name = "copy_file"
    description = "复制文件或目录到目标路径。目标已存在则覆盖。"
    parameters = {
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "源路径"},
            "dst": {"type": "string", "description": "目标路径"},
        },
        "required": ["src", "dst"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            src = self._guard.resolve(kwargs["src"])
            dst = self._guard.resolve(kwargs["dst"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        if not src.exists():
            return ToolResult(success=False, error=f"源不存在：{src}")
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        except OSError as e:
            return ToolResult(success=False, error=f"复制失败：{e}")
        return ToolResult(success=True, content=f"已复制：{src} → {dst}")


class MoveFileTool(BaseTool):
    """移动/重命名文件或目录。"""

    name = "move_file"
    description = "移动或重命名文件和目录。"
    parameters = {
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "源路径"},
            "dst": {"type": "string", "description": "目标路径"},
        },
        "required": ["src", "dst"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            src = self._guard.resolve(kwargs["src"])
            dst = self._guard.resolve(kwargs["dst"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        if not src.exists():
            return ToolResult(success=False, error=f"源不存在：{src}")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except OSError as e:
            return ToolResult(success=False, error=f"移动失败：{e}")
        return ToolResult(success=True, content=f"已移动：{src} → {dst}")


# ---- 辅助函数 ----

import os as _os

def _os_walk(root: Path):
    return _os.walk(root)


def _safe_size(p: Path) -> str:
    try:
        s = p.stat().st_size
        if s >= 1024 * 1024:
            return f"{s / (1024 * 1024):.1f} MB"
        if s >= 1024:
            return f"{s / 1024:.1f} KB"
        return f"{s} B"
    except OSError:
        return "?"
