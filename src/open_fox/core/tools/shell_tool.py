"""Shell 命令执行工具。

⚠️ 安全风险提示：本工具执行任意 Shell 命令，存在命令注入与破坏性操作的
风险。LLM 应仅在 PathGuard 白名单内操作，且应优先使用 Skill 脚本而非
直接 shell 命令。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from open_fox.core.exceptions import DangerousCommand, ScriptTimeout
from open_fox.core.security.command_blacklist import check_command, check_dangerous
from open_fox.core.tools.base import BaseTool, ToolResult

# 当前进程 PID（启动时获取，防止 LLM 通过 shell 命令杀死自身）
_SELF_PID = os.getpid()


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

        # 2. 危险命令确认：命中 DANGEROUS_PATTERNS 则返回 confirm_required，
        #    由 AgentLoop 推送 tool_confirm 事件等待用户确认。
        #    确认通过后 shell_tool 会被再次调用，此时 cmd 不再触发确认
        #    （因为 kwargs 中带 _confirmed=True）
        if not kwargs.get("_confirmed") and check_dangerous(cmd):
            return ToolResult(
                success=False,
                error="",
                confirm_required=True,
                confirm_cmd=cmd,
            )

        # 3. 自身进程保护：禁止杀死当前 OpenFox 后端进程
        pid_str = str(_SELF_PID)
        if pid_str in cmd:
            return ToolResult(
                success=False,
                error=f"禁止杀死当前进程（PID: {pid_str}），该命令已被拦截",
            )

        # 4. 执行
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
