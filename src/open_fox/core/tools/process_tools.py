"""长进程管理工具集：start_process / read_process / stop_process / list_processes。

用于后台启动 dev server、FastAPI 等长期运行的服务进程，不阻塞 Agent 执行流。
进程信息存储在内存中（全局 dict），不持久化，重启后端后清空。
所有启动命令均经过命令黑名单检查。
"""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from open_fox.core.exceptions import DangerousCommand
from open_fox.core.security.command_blacklist import check_command
from open_fox.core.tools.base import BaseTool, ToolResult


# ── 全局进程注册表 ──────────────────────────────────────

class _ProcessEntry:
    """单个后台进程的运行时信息。"""

    __slots__ = (
        "pid", "cmd", "cwd", "start_time", "popen",
        "stdout_lines", "stderr_lines",
        "stdout_lock", "stderr_lock",
        "stdout_pos", "stderr_pos",
        "status", "exit_code",
    )

    def __init__(self, pid: int, cmd: str, cwd: str, popen: subprocess.Popen):
        self.pid = pid
        self.cmd = cmd
        self.cwd = cwd
        self.start_time = datetime.now().isoformat()
        self.popen = popen
        self.stdout_lines: list[str] = []
        self.stderr_lines: list[str] = []
        self.stdout_lock = threading.Lock()
        self.stderr_lock = threading.Lock()
        self.stdout_pos = 0          # read_process 下次读取的起始索引
        self.stderr_pos = 0
        self.status = "running"      # running / exited / crashed / stopped
        self.exit_code: int | None = None


# 全局进程表（PID -> _ProcessEntry），仅存在于内存
_processes: dict[int, _ProcessEntry] = {}
_registry_lock = threading.Lock()

# 每个输出流最多保留的行数，超出时丢弃最旧行
_MAX_BUFFER_LINES = 5000


def _reader_thread(pipe, buf: list[str], lock: threading.Lock):
    """后台逐行读取管道输出到缓冲区。

    当进程退出或管道关闭时，readline 返回空字符串，循环自然结束。
    """
    try:
        for line in iter(pipe.readline, ""):
            with lock:
                buf.append(line)
                if len(buf) > _MAX_BUFFER_LINES:
                    del buf[: len(buf) - _MAX_BUFFER_LINES]
    except (ValueError, OSError):
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _poll_status(entry: _ProcessEntry):
    """检查进程是否已退出，若已退出则更新 status / exit_code。"""
    if entry.status != "running":
        return
    rc = entry.popen.poll()
    if rc is not None:
        entry.exit_code = rc
        entry.status = "exited" if rc == 0 else "crashed"


# ── 工具 1: start_process ───────────────────────────────

class StartProcessTool(BaseTool):
    """后台启动长进程。"""

    name = "start_process"
    description = (
        "后台启动一个长期运行的命令（如 dev server、FastAPI），不阻塞执行流。"
        "返回进程 PID，后续可用 read_process 读取输出、stop_process 停止。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "完整命令字符串"},
            "cwd": {"type": "string",
                    "description": "工作目录（默认使用工具绑定的 cwd）"},
        },
        "required": ["cmd"],
    }

    _MAX_CMD_LENGTH = 5000

    def __init__(self, cwd: Path):
        self._cwd = cwd

    def execute(self, **kwargs) -> ToolResult:
        cmd = kwargs["cmd"]

        # 0. 命令长度上限
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

        # 2. 工作目录
        cwd = kwargs.get("cwd") or str(self._cwd)

        # 3. 启动进程
        try:
            popen = subprocess.Popen(
                cmd,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # 行缓冲，配合 readline
            )
        except OSError as e:
            return ToolResult(success=False, error=f"启动失败：{e}")

        pid = popen.pid
        entry = _ProcessEntry(pid, cmd, cwd, popen)

        # 4. 启动后台读取线程（daemon，随主进程退出）
        t_out = threading.Thread(
            target=_reader_thread,
            args=(popen.stdout, entry.stdout_lines, entry.stdout_lock),
            daemon=True,
        )
        t_err = threading.Thread(
            target=_reader_thread,
            args=(popen.stderr, entry.stderr_lines, entry.stderr_lock),
            daemon=True,
        )
        t_out.start()
        t_err.start()

        with _registry_lock:
            _processes[pid] = entry

        return ToolResult(
            success=True,
            content=f"进程已启动（PID: {pid}）\n命令: {cmd}\n工作目录: {cwd}",
            metadata={"pid": pid},
        )


# ── 工具 2: read_process ────────────────────────────────

class ReadProcessTool(BaseTool):
    """读取后台进程的最新输出。"""

    name = "read_process"
    description = (
        "读取指定 PID 后台进程的最新 stdout / stderr 输出。"
        "每次调用只返回自上次读取以来的新增行。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "进程 PID"},
            "lines": {"type": "integer",
                      "description": "最多返回行数（默认 50，0 表示不限制）"},
        },
        "required": ["pid"],
    }

    def execute(self, **kwargs) -> ToolResult:
        pid = kwargs["pid"]
        max_lines = kwargs.get("lines", 50)

        with _registry_lock:
            entry = _processes.get(pid)

        if entry is None:
            return ToolResult(success=False, error=f"找不到 PID {pid} 的进程")

        _poll_status(entry)

        # 读取 stdout（自上次读取以来的新增行）
        with entry.stdout_lock:
            pos = entry.stdout_pos
            if pos > len(entry.stdout_lines):
                pos = 0  # 缓冲区被裁剪，从头读
            new_stdout = entry.stdout_lines[pos:]
            entry.stdout_pos = len(entry.stdout_lines)

        # 读取 stderr
        with entry.stderr_lock:
            pos = entry.stderr_pos
            if pos > len(entry.stderr_lines):
                pos = 0
            new_stderr = entry.stderr_lines[pos:]
            entry.stderr_pos = len(entry.stderr_lines)

        # 截断到最大行数
        if max_lines and max_lines > 0:
            new_stdout = new_stdout[-max_lines:]
            new_stderr = new_stderr[-max_lines:]

        result = {
            "pid": pid,
            "status": entry.status,
            "exit_code": entry.exit_code,
            "stdout": "".join(new_stdout),
            "stderr": "".join(new_stderr),
        }
        return ToolResult(
            success=True,
            content=json.dumps(result, ensure_ascii=False),
            metadata={"pid": pid, "status": entry.status},
        )


# ── 工具 3: stop_process ────────────────────────────────

class StopProcessTool(BaseTool):
    """停止后台进程。"""

    name = "stop_process"
    description = (
        "停止指定 PID 的后台进程，先尝试 SIGTERM，5 秒后仍未退出则强制 SIGKILL。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "pid": {"type": "integer", "description": "进程 PID"},
        },
        "required": ["pid"],
    }

    def execute(self, **kwargs) -> ToolResult:
        pid = kwargs["pid"]

        with _registry_lock:
            entry = _processes.get(pid)

        if entry is None:
            return ToolResult(success=False, error=f"找不到 PID {pid} 的进程")

        if entry.status != "running":
            return ToolResult(
                success=True,
                content=f"进程 {pid} 已不在运行（状态: {entry.status}）",
            )

        popen = entry.popen

        # 先 SIGTERM
        try:
            popen.terminate()
        except OSError:
            pass

        # 等待最多 5 秒
        try:
            popen.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # 强制 SIGKILL
            try:
                popen.kill()
            except OSError:
                pass
            try:
                popen.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

        entry.exit_code = popen.returncode
        entry.status = "stopped"

        return ToolResult(
            success=True,
            content=f"进程 {pid} 已停止（退出码: {entry.exit_code}）",
            metadata={"pid": pid, "exit_code": entry.exit_code},
        )


# ── 工具 4: list_processes ──────────────────────────────

class ListProcessesTool(BaseTool):
    """列出所有后台进程。"""

    name = "list_processes"
    description = "列出所有后台进程的 PID、命令、状态和启动时间。"
    parameters = {
        "type": "object",
        "properties": {},
    }

    def execute(self, **kwargs) -> ToolResult:
        with _registry_lock:
            entries = list(_processes.values())

        result = []
        for entry in entries:
            _poll_status(entry)
            result.append({
                "pid": entry.pid,
                "cmd": entry.cmd,
                "cwd": entry.cwd,
                "status": entry.status,
                "exit_code": entry.exit_code,
                "start_time": entry.start_time,
            })

        return ToolResult(
            success=True,
            content=json.dumps(result, ensure_ascii=False),
            metadata={"count": len(result)},
        )
