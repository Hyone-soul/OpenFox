"""文件工具集：read_file / write_file / edit_file。

所有路径都通过 PathGuard 校验，确保只能访问白名单内的目录。
"""

from __future__ import annotations

from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation, ToolExecutionError
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """读取文本文件。"""

    name = "read_file"
    description = "读取白名单目录下的文本文件内容。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对或绝对路径"},
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
        if not p.exists():
            return ToolResult(success=False, error=f"文件不存在：{p}")
        try:
            content = p.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult(success=False, error=f"读取失败：{e}")
        return ToolResult(success=True, content=content)


class WriteFileTool(BaseTool):
    """创建或覆盖文本文件。"""

    name = "write_file"
    description = "在白名单目录下创建或覆盖一个文本文件。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            p = self._guard.resolve(kwargs["path"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(kwargs["content"], encoding="utf-8")
        except OSError as e:
            return ToolResult(success=False, error=f"写入失败：{e}")
        return ToolResult(success=True, content=f"已写入：{p}")


class EditFileTool(BaseTool):
    """精确字符串替换编辑文件。"""

    name = "edit_file"
    description = "在文件中精确替换一段字符串，old 不存在则报错。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old": {"type": "string", "description": "要被替换的原文本"},
            "new": {"type": "string", "description": "替换后的文本"},
        },
        "required": ["path", "old", "new"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            p = self._guard.resolve(kwargs["path"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        if not p.exists():
            return ToolResult(success=False, error=f"文件不存在：{p}")
        text = p.read_text(encoding="utf-8")
        old = kwargs["old"]
        new = kwargs["new"]
        if old not in text:
            return ToolResult(success=False, error=f"未找到待替换文本：{old!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolResult(success=True, content="已替换")