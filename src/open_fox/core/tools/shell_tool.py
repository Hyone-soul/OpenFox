"""Shell 命令执行工具。

⚠️ 安全风险提示：本工具执行任意 Shell 命令，存在命令注入与破坏性操作的
风险。LLM 应仅在 PathGuard 白名单内操作，且应优先使用 Skill 脚本而非
直接 shell 命令。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from open_fox.core.exceptions import DangerousCommand, ScriptTimeout
from open_fox.core.security.command_blacklist import check_command
from open_fox.core.tools.base import BaseTool, ToolResult


class RunShellTool(BaseTool):
    """在指定 cwd 下执行 Shell 命令。"""

    name = "run_shell"
    description = "在白名单工作目录下执行 Shell 命令，支持超时控制。"
    parameters = {
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "完整命令字符串"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 30"},
        },
        "required": ["cmd"],
    }

    def __init__(self, cwd: Path, default_timeout: int = 30):
        # cwd 不存在时回退到父目录（防止 LLM 误操作导致路径失效）
        if cwd.exists():
            self._cwd = cwd
        else:
            self._cwd = cwd.parent if cwd.parent.exists() else Path.cwd()
        self._default_timeout = default_timeout

    _MAX_CMD_LENGTH = 5000

    def execute(self, **kwargs) -> ToolResult:
        cmd = kwargs["cmd"]
        timeout = kwargs.get("timeout", self._default_timeout)

        # 0. 命令长度上限（防止超长命令注入）
        if len(cmd) > self._MAX_CMD_LENGTH:
            return ToolResult(
                success=False,
                error=f"命令过长（{len(cmd)}>{self._MAX_CMD_LENGTH} 字符），已拦截",
            )

        # 1. 黑名单检查
        try:
            check_command(cmd)
        except DangerousCommand as e:
            return ToolResult(success=False, error=str(e))

        # 2. 执行
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self._cwd),
                timeout=timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            return ToolResult(
                success=False,
                error=f"命令执行超时（>{timeout}s）：{cmd}",
            )
        except OSError as e:
            return ToolResult(success=False, error=f"执行失败：{e}")

        # 4. 构造结果
        if proc.returncode == 0:
            return ToolResult(
                success=True,
                content=proc.stdout,
                metadata={"stderr": proc.stderr, "exit_code": 0},
            )
        return ToolResult(
            success=False,
            content=proc.stdout,
            error=f"命令退出码 {proc.returncode}: {proc.stderr.strip()}",
            metadata={"exit_code": proc.returncode},
        )
