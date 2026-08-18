"""危险命令安全策略。

分两层：
- DEFAULT_BLACKLIST：直接禁止的命令（格式化、关机、注册表等破坏性操作）
- DANGEROUS_PATTERNS：需要用户确认才能执行的命令（杀进程、递归删除等）
  命中此列表的命令不会被执行，而是返回 confirm_required，前端弹窗让用户确认。

⚠️ 安全风险提示：本策略只能降低已知风险，不能完全消除命令执行带来的
安全威胁。请只允许来自可信来源的 Skill 执行 Shell 命令，并尽可能使用
路径白名单、超时控制等额外约束。
"""

from __future__ import annotations

import re

from open_fox.core.exceptions import DangerousCommand


# 黑名单模式（正则），匹配即拦截——无需确认，直接拒绝
DEFAULT_BLACKLIST: list[str] = [
    # --- Linux / 通用 ---
    r"\bmkfs(\.[a-z0-9]+)?\s+/dev/",                      # 格式化磁盘
    r"\bshutdown\b",                                       # 关机
    r"\breboot\b",                                         # 重启
    r"\bdd\s+.*of=/dev/",                                  # dd 写设备
    r":\(\)\s*\{.*:\|:.*&\s*\};:",                          # fork bomb
    r"\bchmod\s+(-[a-zA-Z]*\s+)*0?777\s+/",                # 全局可写 /
    r"\bmv\s+/(\s|$|\*)",                                 # 移动根目录
    # --- Windows ---
    r"\bformat\b\s+[A-Z]:",                               # format C:
    r"\breg\s+delete\s+HKLM\\",                           # reg delete HKLM
    r"\bdiskpart\b",                                      # 磁盘分区操作
    r"\bnet\s+(user|localgroup)\s+/",                     # net user /add 等
    r"\bpowershell\s+.*-enc\b",                           # PS 编码命令（混淆注入）
    r"\bcmd\s+/c\s+.*&\s*",                               # cmd 链式执行
    r"\breg\s+add\s+HKLM\\",                              # 修改注册表启动项
]

# 危险命令模式（正则），匹配则需要用户确认才能执行
# 不在黑名单中（不直接拒绝），而是返回 confirm_required 让前端弹窗
DANGEROUS_PATTERNS: list[str] = [
    # --- 杀进程 ---
    r"\btaskkill\b",                                       # Windows 杀进程
    r"\bStop-Process\b",                                   # PowerShell 杀进程
    r"\bkill\s+-9\b",                                      # Linux 强杀
    # --- 递归删除 ---
    r"\brm\s+(-[a-zA-Z]*[rRfF][a-zA-Z]*\s+)+/",           # rm -rf /, rm -fr /etc
    r"\bdel\s+(/[sq]\s+)*[A-Z]:\\",                       # del /f /s C:\
    r"\brmdir\s+(/[sq]\s+)*[A-Z]:\\",                     # rmdir /s /q C:\
]


def check_command(cmd: str) -> None:
    """检查命令是否命中黑名单，命中则抛 DangerousCommand。

    参数:
        cmd: 完整命令字符串
    """
    for pattern in DEFAULT_BLACKLIST:
        if re.search(pattern, cmd):
            raise DangerousCommand(cmd)


def check_dangerous(cmd: str) -> str | None:
    """检查命令是否命中危险模式，命中则返回提示信息，否则返回 None。

    命中时调用方应返回 confirm_required 让前端弹窗确认。

    参数:
        cmd: 完整命令字符串
    返回:
        命中时返回提示信息（如"杀进程命令"），未命中返回 None
    """
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return f"该命令被标记为危险操作，需要用户确认后才能执行"
    return None