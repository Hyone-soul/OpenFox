"""SKILL.md 解析器。

SKILL.md 格式：
---
name: <name>            # 必填
description: <desc>     # 必填
tools: [tool1, tool2]   # 可选
scripts:                # 可选
  - id: <id>
    lang: python|shell|node
    entry: <relative path>
    timeout: <seconds>
    description: <desc>
---
<Markdown 正文>
"""

from __future__ import annotations

from pathlib import Path

import yaml

from open_fox.core.skills.models import ScriptSpec, Skill


class SkillParseError(ValueError):
    """SKILL.md 解析失败。"""


def parse_skill_md(path: Path) -> Skill:
    """解析单个 SKILL.md 文件，返回 Skill 对象。"""
    return parse_skill_md_text(path.read_text(encoding="utf-8"), source_dir=path.parent.resolve())


def parse_skill_md_text(text: str, source_dir: Path | None = None) -> Skill:
    """从文本解析 SKILL.md 内容（不依赖文件路径，供进化校验等场景复用）。"""
    if not text.startswith("---"):
        raise SkillParseError("缺少 YAML frontmatter")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillParseError("frontmatter 格式错误")

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        raise SkillParseError(f"YAML 解析失败：{e}") from e

    if "name" not in meta:
        raise SkillParseError("缺少 name 字段")
    if "description" not in meta:
        raise SkillParseError("缺少 description 字段")

    scripts = [
        ScriptSpec(
            id=s["id"],
            lang=s["lang"],
            entry=s["entry"],
            timeout=s.get("timeout", 30),
            description=s.get("description", ""),
        )
        for s in meta.get("scripts", [])
    ]

    try:
        version = int(meta.get("version", 1))
    except (TypeError, ValueError):
        # 容错：语义化版本字符串 "1.0.0" → 取主版本号 1
        raw = meta.get("version", 1)
        if isinstance(raw, str):
            major = raw.split(".")[0]
            try:
                version = int(major)
            except (TypeError, ValueError):
                raise SkillParseError(f"version 字段非法：{raw!r}") from None
        else:
            raise SkillParseError(f"version 字段非法：{raw!r}") from None

    return Skill(
        name=meta["name"],
        description=meta["description"],
        tools=meta.get("tools", []),
        scripts=scripts,
        body=parts[2].strip(),
        source_dir=source_dir or Path("."),
        version=version,
        deprecated=bool(meta.get("deprecated", False)),
        trigger=str(meta.get("trigger", "")),
    )