"""危险命令黑名单。

⚠️ 安全风险提示：本黑名单只能降低已知风险，不能完全消除命令执行带来的
安全威胁。请只允许来自可信来源的 Skill 执行 Shell 命令，并尽可能使用
路径白名单、超时控制等额外约束。
"""

from __future__ import annotations

import re

from open_fox.core.exceptions import DangerousCommand


# 黑名单模式（正则），匹配即拦截
DEFAULT_BLACKLIST: list[str] = [
    # --- Linux / 通用 ---
    r"rm\s+(-[a-zA-Z]*[rRfF][a-zA-Z]*\s+)+/",  # rm -rf /, rm -fr /etc
    r"\bmkfs(\.[a-z0-9]+)?\s+/dev/",                      # 格式化磁盘
    r"\bshutdown\b",                                       # 关机
    r"\breboot\b",                                         # 重启
    r"\bdd\s+.*of=/dev/",                                  # dd 写设备
    r":\(\)\s*\{.*:\|:.*&\s*\};:",                          # fork bomb
    r"\bchmod\s+(-[a-zA-Z]*\s+)*0?777\s+/",                # 全局可写 /
    r"\bmv\s+/(\s|$|\*)",                                 # 移动根目录
    # --- Windows ---
    r"\bformat\b\s+[A-Z]:",                               # format C:
    r"\bdel\s+(/[sq]\s+)*[A-Z]:\\",                       # del /f /s C:\
    r"\brmdir\s+(/[sq]\s+)*[A-Z]:\\",                     # rmdir /s /q C:\
    r"\breg\s+delete\s+HKLM\\",                           # reg delete HKLM
    r"\bdiskpart\b",                                      # 磁盘分区操作
    r"\bnet\s+(user|localgroup)\s+/",                     # net user /add 等
    r"\btaskkill\s+/(f|/pid)\b",                          # 强杀进程
    r"\bpowershell\s+.*-enc\b",                           # PS 编码命令（混淆注入）
    r"\bcmd\s+/c\s+.*&\s*",                               # cmd 链式执行
    r"\breg\s+add\s+HKLM\\",                              # 修改注册表启动项
]


def check_command(cmd: str) -> None:
    """检查命令是否命中黑名单，命中则抛 DangerousCommand。

    参数:
        cmd: 完整命令字符串
    """
    for pattern in DEFAULT_BLACKLIST:
        if re.search(pattern, cmd):
            raise DangerousCommand(cmd)