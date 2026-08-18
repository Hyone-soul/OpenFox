"""代码搜索工具：grep_search / glob_find。

在白名单目录下按正则搜索文件内容或按模式匹配文件名。
Windows 兼容，不依赖 grep/findstr 外部命令。
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.base import BaseTool, ToolResult

# 大文件跳过阈值（1 MB）
_MAX_FILE_SIZE = 1 * 1024 * 1024
# 最大结果条数
_MAX_RESULTS = 50


class GrepSearchTool(BaseTool):
    """在白名单目录下按正则搜索文件内容，返回匹配行及其位置。"""

    name = "grep_search"
    description = "在目录下按正则表达式搜索文件内容，返回匹配行及行号。类似 ripprep/grep 功能。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则表达式"},
            "path": {"type": "string", "description": "搜索根目录，默认为工作区根"},
            "include": {"type": "string", "description": "文件名过滤通配符，如 *.py、*.vue"},
            "max_results": {"type": "integer", "description": "最大返回条数，默认 50"},
        },
        "required": ["pattern"],
    }

    # 常见不需要搜索的目录
    _SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        ".env", "dist", "build", ".next", ".nuxt", ".ruff_cache",
        ".pytest_cache", ".mypy_cache",
    }
    _SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
                  ".webp", ".mp3", ".mp4", ".zip", ".gz", ".tar",
                  ".exe", ".dll", ".so", ".woff", ".woff2", ".ttf", ".eot"}

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            regex = re.compile(kwargs["pattern"], re.IGNORECASE)
        except re.error as e:
            return ToolResult(success=False, error=f"正则语法错误：{e}")

        # 防御性转换：LLM 可能传入非字符串 path（如整数），统一转 str
        root_str = str(kwargs.get("path", "."))
        try:
            root = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))

        max_results = min(kwargs.get("max_results", _MAX_RESULTS), _MAX_RESULTS)

        # path 指向文件：直接搜索该文件内容
        if root.is_file():
            return self._search_single_file(root, regex, max_results)
        if not root.is_dir():
            return ToolResult(success=False, error=f"路径不存在：{root}")

        include = kwargs.get("include", "")
        results = []

        for path in self._walk(root):
            if include and not fnmatch.fnmatch(path.name, include):
                continue
            if path.suffix.lower() in self._SKIP_EXTS:
                continue
            try:
                if path.stat().st_size > _MAX_FILE_SIZE:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = path.relative_to(root)
                    results.append(f"{rel}:{i}: {line.strip()}")
                    if len(results) >= max_results:
                        return ToolResult(
                            success=True,
                            content="\n".join(results),
                            metadata={"truncated": True},
                        )

        if not results:
            return ToolResult(success=True, content="未找到匹配项")
        return ToolResult(success=True, content="\n".join(results))

    def _search_single_file(self, file_path: Path, regex: re.Pattern, max_results: int) -> ToolResult:
        """搜索单个文件内容，用于 path 指向文件而非目录的场景。"""
        if file_path.suffix.lower() in self._SKIP_EXTS:
            return ToolResult(success=True, content="未找到匹配项（文件类型已跳过）")
        try:
            if file_path.stat().st_size > _MAX_FILE_SIZE:
                return ToolResult(success=True, content="文件过大，已跳过")
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ToolResult(success=False, error=f"读取文件失败：{e}")
        results = []
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                results.append(f"{file_path.name}:{i}: {line.strip()}")
                if len(results) >= max_results:
                    break
        if not results:
            return ToolResult(success=True, content="未找到匹配项")
        return ToolResult(success=True, content="\n".join(results))

    def _walk(self, root: Path):
        for dirpath, dirnames, filenames in os_walk(root):
            # 就地过滤跳过的目录，避免递归进入
            dirnames[:] = [d for d in dirnames if d not in self._SKIP_DIRS]
            for fn in filenames:
                yield dirpath / fn


class GlobFindTool(BaseTool):
    """在白名单目录下按通配符匹配文件名。"""

    name = "glob_find"
    description = "按通配符模式搜索文件名，如 **/*.py、src/**/*.vue。类似 find/glob 功能。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "通配符模式，如 **/*.py、src/**/*.vue"},
            "path": {"type": "string", "description": "搜索根目录，默认为工作区根"},
            "max_results": {"type": "integer", "description": "最大返回条数，默认 50"},
        },
        "required": ["pattern"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        # 防御性转换：LLM 可能传入非字符串 path
        root_str = str(kwargs.get("path", "."))
        try:
            root = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        # glob_find 语义上需要目录作为根，但 path 指向文件时给出明确提示
        if root.is_file():
            return ToolResult(success=False, error=f"path 指向文件而非目录：{root}，如需搜索文件内容请使用 grep_search")
        if not root.is_dir():
            return ToolResult(success=False, error=f"路径不存在：{root}")

        pattern = kwargs["pattern"]
        max_results = min(kwargs.get("max_results", _MAX_RESULTS), _MAX_RESULTS)

        try:
            matches = sorted(root.glob(pattern))
        except ValueError as e:
            return ToolResult(success=False, error=f"模式语法错误：{e}")

        # 安全校验：过滤掉白名单外的路径
        lines = []
        for p in matches[:max_results]:
            if self._guard.is_allowed(p):
                rel = p.relative_to(root)
                kind = "/" if p.is_dir() else ""
                lines.append(f"{rel}{kind}")

        if not lines:
            return ToolResult(success=True, content="未找到匹配文件")
        return ToolResult(
            success=True,
            content="\n".join(lines),
            metadata={"total": len(lines), "truncated": len(matches) > max_results},
        )


# 兼容 Windows 的 os.walk 封装
import os as _os

def os_walk(root: Path):
    return _os.walk(root)
