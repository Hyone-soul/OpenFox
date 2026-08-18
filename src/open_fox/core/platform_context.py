"""平台感知：检测运行环境并生成系统提示词片段，让 LLM 使用正确的平台命令。"""

from __future__ import annotations

import os
import platform
import shutil
import sys


def detect_platform() -> dict:
    """检测当前运行平台，返回结构化信息。"""
    is_windows = sys.platform.startswith("win")
    is_mac = sys.platform == "darwin"
    is_linux = sys.platform.startswith("linux")

    # 检测可用的 shell
    shell_name = "unknown"
    if is_windows:
        # shell=True 在 Windows 上走 cmd.exe，但系统中可能有 PowerShell
        if shutil.which("powershell"):
            shell_name = "cmd.exe（shell=True 默认）/ PowerShell 可用"
        else:
            shell_name = "cmd.exe"
    else:
        shell_name = os.environ.get("SHELL", "/bin/sh")

    # Python 命令名
    python_cmd = "python" if is_windows else (sys.executable.split("/")[-1] if not is_windows else "python3")
    if is_windows:
        python_cmd = "python"
    elif is_linux or is_mac:
        # 检查是 python3 还是 python
        python_cmd = "python3" if shutil.which("python3") else "python"

    return {
        "os": platform.system(),           # Windows / Darwin / Linux
        "os_version": platform.version(),
        "platform": sys.platform,           # win32 / darwin / linux
        "is_windows": is_windows,
        "is_mac": is_mac,
        "is_linux": is_linux,
        "shell": shell_name,
        "python_cmd": python_cmd,
        "path_sep": "\\" if is_windows else "/",
        "exe_suffix": ".exe" if is_windows else "",
        "arch": platform.machine(),        # AMD64 / arm64 / x86_64
    }


def build_platform_prompt() -> str:
    """生成注入系统提示词的平台感知片段。"""
    info = detect_platform()

    if info["is_windows"]:
        platform_block = f"""## 运行环境（重要）

**操作系统**：Windows {info["os_version"]}（{info["arch"]}）
**默认 Shell**：{info["shell"]}（run_shell 工具使用 shell=True，在 Windows 上实际走 cmd.exe）
**Python 命令**：`{info["python_cmd"]}`（不是 python3）
**路径分隔符**：`\\`（反斜杠）
**可执行文件后缀**：`{info["exe_suffix"]}`

### 必须遵守的 Windows 命令规范

使用 run_shell 工具时，**必须使用 Windows 命令**，不要使用 Linux/macOS 命令：

| 场景 | Windows 正确命令 | 错误（Linux） |
|------|------------------|---------------|
| 列出文件 | `dir` | ~~ls~~ |
| 查看文件内容 | `type file.txt` | ~~cat file.txt~~ |
| 搜索文本 | `findstr "pattern" file` | ~~grep "pattern" file~~ |
| 复制文件 | `copy src dst` | ~~cp src dst~~ |
| 移动/重命名 | `move src dst` 或 `ren src dst` | ~~mv src dst~~ |
| 删除文件 | `del file` | ~~rm file~~ |
| 删除目录 | `rmdir /s /q dir` | ~~rm -rf dir~~ |
| 创建目录 | `mkdir dir` | ~~mkdir -p dir~~ |
| 环境变量 | `%VAR%` | ~~$VAR~~ |
| 路径连接 | `;` | ~~:~~ |
| 管道符 | `\\|`（同 Linux） | - |
| 后台运行 | `start cmd` | ~~&~~ |
| 查看进程 | `tasklist` | ~~ps aux~~ |
| 终止进程 | `taskkill /pid 1234 /f` | ~~kill 1234~~ |
| 查看端口 | `netstat -ano` | ~~netstat -tlnp~~ |

### PowerShell 命令（如果指定使用 PowerShell）

如果需要 PowerShell 语法（如管道操作、对象处理），可以在 cmd 中调用：
`powershell -Command "Get-Process | Where-Object {{$_.CPU -gt 10}}"`

### 注意事项

1. **路径使用反斜杠**：`skills\\db-helper\\scripts\\query_db.py`，而非 `skills/db-helper/scripts/query_db.py`
2. **换行符**：Windows 使用 CRLF（`\\r\\n`）
3. **Python 脚本调用**：`{info["python_cmd"]} skills\\xxx\\scripts\\yyy.py`，而非 `python3 skills/xxx/scripts/yyy.py`
4. **多命令连接**：用 `&&` 连接（cmd 支持），不要用 `;`
5. **引号**：路径含空格时用双引号 `"C:\\Program Files\\app"`
"""
    elif info["is_mac"]:
        platform_block = f"""## 运行环境（重要）

**操作系统**：macOS {info["os_version"]}（{info["arch"]}）
**默认 Shell**：{info["shell"]}
**Python 命令**：`{info["python_cmd"]}`
**路径分隔符**：`/`

### 命令规范

使用 run_shell 工具时，请使用标准 Unix 命令（ls、cat、grep、cp、mv、rm 等）。
macOS 基于 BSD，部分命令参数与 GNU Linux 不同（如 `sed -i ''` 需要额外空参数）。
"""
    else:
        platform_block = f"""## 运行环境（重要）

**操作系统**：Linux {info["os_version"]}（{info["arch"]}）
**默认 Shell**：{info["shell"]}
**Python 命令**：`{info["python_cmd"]}`
**路径分隔符**：`/`

### 命令规范

使用 run_shell 工具时，请使用标准 Unix/Linux 命令（ls、cat、grep、cp、mv、rm 等）。
"""

    return platform_block
