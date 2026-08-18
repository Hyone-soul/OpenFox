"""Skill 数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class ScriptSpec:
    """Skill 内部脚本声明。"""

    id: str
    lang: Literal["python", "shell", "node"]
    entry: str
    timeout: int = 30
    description: str = ""


@dataclass
class Skill:
    """单个 Skill 的完整描述。"""

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    scripts: list[ScriptSpec] = field(default_factory=list)
    body: str = ""
    source_dir: Path = Path(".")
    version: int = 1
    deprecated: bool = False
    trigger: str = ""