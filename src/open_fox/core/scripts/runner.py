"""基于 subprocess 的脚本执行器。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from open_fox.core.exceptions import ScriptTimeout
from open_fox.core.skills.models import ScriptSpec


@dataclass
class ScriptResult:
    """脚本执行结果。"""

    stdout: str
    stderr: str
    exit_code: int
    duration: float


_INTERPRETERS = {
    "python": [sys.executable],
    "node": ["node"],
}


def _shell_interpreter() -> list[str]:
    """选择可用 shell；Windows 没有 Bash 时用 PowerShell 兼容基础脚本。"""
    if os.name == "nt":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    if shutil.which("bash"):
        return ["bash"]
    return ["sh"]


class ScriptRunner:
    """在 skill 目录下执行 SKILL.md 声明的脚本。

    后端可选：
    - subprocess：直接在本机子进程中执行（默认）
    - docker：通过 DockerRunner 在容器中执行
    """

    def __init__(self, backend: str = "subprocess"):
        if backend not in ("subprocess", "docker"):
            raise ValueError(f"未知后端：{backend}")
        self._backend = backend

    def run(
        self,
        spec: ScriptSpec,
        source_dir: Path,
        args: list[str] | None = None,
    ) -> ScriptResult:
        """执行脚本并返回结果。"""
        if self._backend == "docker":
            from open_fox.core.scripts.docker_runner import DockerScriptRunner
            return DockerScriptRunner().run(spec, source_dir, args or [])

        return self._run_subprocess(spec, source_dir, args or [])

    def _run_subprocess(
        self,
        spec: ScriptSpec,
        source_dir: Path,
        args: list[str],
    ) -> ScriptResult:
        interp = _shell_interpreter() if spec.lang == "shell" else _INTERPRETERS.get(spec.lang)
        if interp is None:
            raise ValueError(f"未知脚本语言：{spec.lang}")

        script_path = source_dir / spec.entry
        if not script_path.exists():
            raise FileNotFoundError(f"脚本不存在：{script_path}")

        # cwd 已锁定在 source_dir，用相对路径（避免 Windows 盘符路径在 bash 中被误解）
        if spec.lang == "shell" and os.name == "nt" and interp[-1] == "-File":
            # PowerShell -File 要求 .ps1 扩展名；Skill 仍可保持 .sh 文件名，
            # 通过读取并执行脚本内容兼容基础 shell 命令。
            literal = str(script_path).replace("'", "''")
            cmd = [*interp[:-1], "-Command", f"Get-Content -Raw -LiteralPath '{literal}' | Invoke-Expression"]
        else:
            cmd = [*interp, script_path.relative_to(source_dir).as_posix(), *args]

        # 安全：剥离敏感环境变量
        safe_env = {
            k: v for k, v in os.environ.items()
            if k not in ("OPENAI_API_KEY", "MCP_TOKEN", "AWS_SECRET_ACCESS_KEY")
        }

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(source_dir),          # ⚠️ cwd 锁在 skill 目录
                timeout=spec.timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=safe_env,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start
            raise ScriptTimeout(command=" ".join(cmd), timeout=float(spec.timeout)) from e

        return ScriptResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration=time.time() - start,
        )
