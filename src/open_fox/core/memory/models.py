from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entry:
    content: str
    meta: str
    confidence: str = ""   # 高/中/低（显式记忆为空）

@dataclass
class ImplicitSection:
    name: str
    entries: list[Entry] = field(default_factory=list)

@dataclass
class MemoryDocument:
    explicit: list[Entry] = field(default_factory=list)
    implicit: list[ImplicitSection] = field(default_factory=list)
    archive: list[Entry] = field(default_factory=list)
    lock_token: str = ""
