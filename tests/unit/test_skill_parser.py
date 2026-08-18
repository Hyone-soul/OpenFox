"""SKILL.md 解析测试。"""
from pathlib import Path

import pytest

from open_fox.core.skills.parser import (
    SkillParseError,
    parse_skill_md,
    parse_skill_md_text,
)


def test_parse_full_skill(tmp_path: Path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "lint.py").write_text("print('ok')")
    md = skill_dir / "SKILL.md"
    md.write_text(
        "---\n"
        "name: my-skill\n"
        "description: 一个示例技能\n"
        "tools: [read_file, run_shell]\n"
        "scripts:\n"
        "  - id: lint\n"
        "    lang: python\n"
        "    entry: scripts/lint.py\n"
        "    timeout: 30\n"
        "    description: lint 检查\n"
        "---\n"
        "# 正文\n"
        "这是 Markdown 正文。\n",
        encoding="utf-8",
    )
    skill = parse_skill_md(md)
    assert skill.name == "my-skill"
    assert skill.description == "一个示例技能"
    assert skill.tools == ["read_file", "run_shell"]
    assert len(skill.scripts) == 1
    s = skill.scripts[0]
    assert s.id == "lint"
    assert s.lang == "python"
    assert s.timeout == 30
    assert skill.body.startswith("# 正文")
    assert skill.source_dir == skill_dir.resolve()


def test_parse_minimal_skill(tmp_path: Path):
    skill_dir = tmp_path / "mini"
    skill_dir.mkdir()
    md = skill_dir / "SKILL.md"
    md.write_text(
        "---\nname: mini\ndescription: 最小技能\n---\n正文",
        encoding="utf-8",
    )
    skill = parse_skill_md(md)
    assert skill.tools == []
    assert skill.scripts == []
    assert skill.body == "正文"


def test_missing_frontmatter(tmp_path: Path):
    md = tmp_path / "SKILL.md"
    md.write_text("正文无 frontmatter", encoding="utf-8")
    with pytest.raises(SkillParseError):
        parse_skill_md(md)


def test_missing_required_field(tmp_path: Path):
    md = tmp_path / "SKILL.md"
    md.write_text("---\ndescription: 缺 name\n---\n正文", encoding="utf-8")
    with pytest.raises(SkillParseError):
        parse_skill_md(md)


def test_parse_version_deprecated_trigger(tmp_path: Path):
    skill_dir = tmp_path / "vskill"
    skill_dir.mkdir()
    md = skill_dir / "SKILL.md"
    md.write_text(
        "---\n"
        "name: vskill\n"
        "description: 带版本\n"
        "version: 3\n"
        "deprecated: true\n"
        "trigger: 用户提到 PDF\n"
        "---\n正文",
        encoding="utf-8",
    )
    skill = parse_skill_md(md)
    assert skill.version == 3
    assert skill.deprecated is True
    assert skill.trigger == "用户提到 PDF"


def test_parse_skill_md_text():
    skill = parse_skill_md_text(
        "---\nname: t\ndescription: 文本解析\n---\n正文",
        source_dir=Path("."),
    )
    assert skill.name == "t"
    assert skill.version == 1


def test_invalid_version_raises_skill_parse_error():
    """坏 version 字段应抛 SkillParseError，而不是原始 ValueError（供 rescan 热加载容忍）。"""
    with pytest.raises(SkillParseError):
        parse_skill_md_text("---\nname: vbad\ndescription: d\nversion: v3\n---\n正文")


def test_invalid_version_raises_skill_parse_error_for_non_int():
    """version 为数字字符串也应统一抛 SkillParseError。"""
    with pytest.raises(SkillParseError):
        parse_skill_md_text("---\nname: vbad\ndescription: d\nversion: 'abc'\n---\n正文")