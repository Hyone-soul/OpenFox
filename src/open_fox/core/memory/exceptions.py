class MemoryError(Exception):
    """记忆系统通用错误。"""

class MemoryParseError(MemoryError):
    """OPENFOX.md 解析失败。"""

class MemoryPermissionError(MemoryError):
    """无权限操作（如删除显式记忆）。"""
