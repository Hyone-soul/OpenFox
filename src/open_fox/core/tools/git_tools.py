"""Git 操作工具：git_status / git_diff / git_commit / git_log。

通过 subprocess 调用 git 命令，Windows 兼容（git.exe）。
所有操作在 PathGuard 白名单目录内执行。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.base import BaseTool, ToolResult

_GIT_TIMEOUT = 15


def _run_git(cwd: Path, args: list[str], timeout: int = _GIT_TIMEOUT) -> ToolResult:
    """通用 git 命令执行器。"""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return ToolResult(success=False, error="git 未安装或不在 PATH 中")
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"git 命令超时（>{timeout}s）")
    except OSError as e:
        return ToolResult(success=False, error=f"执行失败：{e}")

    if proc.returncode == 0:
        out = proc.stdout.strip()
        return ToolResult(success=True, content=out or "（无输出）")
    return ToolResult(
        success=False,
        error=f"git 返回码 {proc.returncode}: {proc.stderr.strip()}",
        content=proc.stdout.strip(),
    )


class GitStatusTool(BaseTool):
    """查看 git 仓库状态。"""

    name = "git_status"
    description = "查看当前仓库的 git 状态（修改、暂存、未跟踪等）。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "仓库根目录，默认为工作区"},
        },
        "required": [],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        root_str = kwargs.get("path", ".")
        try:
            cwd = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))
        return _run_git(cwd, ["status", "--short"])


class GitDiffTool(BaseTool):
    """查看 git diff。"""

    name = "git_diff"
    description = "查看工作区或暂存区的变更内容。默认显示未暂存的修改。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "仓库根目录，默认为工作区"},
            "staged": {"type": "boolean", "description": "是否查看已暂存的变更，默认 false"},
            "file": {"type": "string", "description": "限定查看某个文件的 diff"},
        },
        "required": [],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        root_str = kwargs.get("path", ".")
        try:
            cwd = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))

        args = ["diff"]
        if kwargs.get("staged", False):
            args.append("--staged")
        file = kwargs.get("file", "")
        if file:
            args.append("--")
            args.append(file)
        return _run_git(cwd, args, timeout=30)


class GitCommitTool(BaseTool):
    """执行 git add + commit。"""

    name = "git_commit"
    description = "将所有变更暂存并提交。自动执行 git add -A 然后 git commit。"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "提交信息"},
            "path": {"type": "string", "description": "仓库根目录，默认为工作区"},
        },
        "required": ["message"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        root_str = kwargs.get("path", ".")
        try:
            cwd = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))

        message = kwargs["message"]
        # git add -A
        add_result = _run_git(cwd, ["add", "-A"])
        if not add_result.success:
            return add_result
        # git commit
        # Windows: 用 -m 传消息，不依赖 shell 引号
        return _run_git(cwd, ["commit", "-m", message])


class GitLogTool(BaseTool):
    """查看 git 提交日志。"""

    name = "git_log"
    description = "查看 git 提交历史。默认最近 10 条，单行格式。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "仓库根目录，默认为工作区"},
            "count": {"type": "integer", "description": "显示条数，默认 10"},
            "verbose": {"type": "boolean", "description": "是否显示完整信息（含时间作者），默认 false"},
        },
        "required": [],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        root_str = kwargs.get("path", ".")
        try:
            cwd = self._guard.resolve(root_str)
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))

        count = kwargs.get("count", 10)
        verbose = kwargs.get("verbose", False)

        if verbose:
            args = ["log", f"-{count}", "--format=%h %ai %an: %s"]
        else:
            args = ["log", f"-{count}", "--oneline"]
        return _run_git(cwd, args)
