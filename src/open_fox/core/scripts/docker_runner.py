"""Docker 后端脚本执行器（可选）。

⚠️ 依赖 Docker，请确保宿主机已安装并启动 Docker Desktop / dockerd。
若 Docker 不可用，请使用默认 subprocess 后端。
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from open_fox.core.exceptions import ScriptTimeout
from open_fox.core.scripts.runner import ScriptResult
from open_fox.core.skills.models import ScriptSpec


_IMAGES = {
    "python": "python:3.13-slim",
    "shell": "bash:alpine",
    "node": "node:20-alpine",
}


class DockerScriptRunner:
    """通过 docker run 在临时容器中执行脚本。

    容器以只读方式挂载 skill 目录，cwd 设为 /skill。
    """

    def run(
        self,
        spec: ScriptSpec,
        source_dir: Path,
        args: list[str],
    ) -> ScriptResult:
        image = _IMAGES.get(spec.lang)
        if image is None:
            raise ValueError(f"未知脚本语言：{spec.lang}")

        script_rel = spec.entry  # 相对路径
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{source_dir.resolve()}:/skill:ro",
            "-w", "/skill",
            "--network=none",  # 默认禁止网络
            image,
            *_interp_cmd(spec.lang, script_rel, args),
        ]

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                timeout=spec.timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            raise ScriptTimeout(command=" ".join(cmd), timeout=float(spec.timeout)) from e
        except FileNotFoundError:
            # Docker 未安装，调用方应捕获并降级
            raise

        return ScriptResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            duration=time.time() - start,
        )


def _interp_cmd(lang: str, script_rel: str, args: list[str]) -> list[str]:
    if lang == "python":
        return ["python", script_rel, *args]
    if lang == "shell":
        return ["bash", script_rel, *args]
    if lang == "node":
        return ["node", script_rel, *args]
    raise ValueError(lang)
