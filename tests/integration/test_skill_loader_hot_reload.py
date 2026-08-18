"""Skill 热加载集成测试。"""
import time
from pathlib import Path

from open_fox.core.skills.loader import SkillLoader


def _write_skill(skill_dir: Path, name: str, description: str):
    sd = skill_dir / name
    sd.mkdir(exist_ok=True)
    (sd / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n正文",
        encoding="utf-8",
    )


def test_initial_load(tmp_path: Path):
    _write_skill(tmp_path, "alpha", "A")
    _write_skill(tmp_path, "beta", "B")

    received: list[dict] = []
    loader = SkillLoader(skills_dir=tmp_path, on_change=received.append)
    loader.rescan()

    skills = loader.all()
    assert set(skills.keys()) == {"alpha", "beta"}
    loader.stop()


def test_hot_reload_on_new_skill(tmp_path: Path):
    received: list[dict] = []
    loader = SkillLoader(skills_dir=tmp_path, on_change=received.append)
    loader.start()
    try:
        _write_skill(tmp_path, "gamma", "G")
        # 等待 watchdog 事件传播（最多 3 秒）
        deadline = time.time() + 3
        while time.time() < deadline:
            if "gamma" in loader.all():
                break
            time.sleep(0.1)
        assert "gamma" in loader.all()
    finally:
        loader.stop()


def test_hot_reload_on_modification(tmp_path: Path):
    _write_skill(tmp_path, "delta", "old")
    received: list[dict] = []
    loader = SkillLoader(skills_dir=tmp_path, on_change=received.append)
    loader.start()
    try:
        # 修改 description
        (tmp_path / "delta" / "SKILL.md").write_text(
            "---\nname: delta\ndescription: new\n---\n正文",
            encoding="utf-8",
        )
        deadline = time.time() + 3
        while time.time() < deadline:
            if loader.all().get("delta") and loader.all()["delta"].description == "new":
                break
            time.sleep(0.1)
        assert loader.all()["delta"].description == "new"
    finally:
        loader.stop()


def test_invalid_skill_skipped(tmp_path: Path, caplog):
    # 一个目录无 SKILL.md：应被忽略
    (tmp_path / "no-skill-here").mkdir()
    # 一个 SKILL.md 缺 name
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
    # 一个合法 Skill
    _write_skill(tmp_path, "good", "ok")

    loader = SkillLoader(skills_dir=tmp_path, on_change=lambda _: None)
    loader.rescan()
    assert "good" in loader.all()
    assert "bad" not in loader.all()
    loader.stop()


def test_versions_dir_excluded(tmp_path):
    _write_skill(tmp_path, "alpha", "A")
    ver = tmp_path / "alpha" / ".versions" / "v1"
    ver.mkdir(parents=True)
    (ver / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: 旧版\n---\n旧正文",
        encoding="utf-8",
    )
    loader = SkillLoader(skills_dir=tmp_path, on_change=lambda _: None)
    loader.rescan()
    skills = loader.all()
    assert set(skills.keys()) == {"alpha"}
    # 顶层版本生效，.versions 里的历史版本不覆盖
    assert skills["alpha"].description == "A"
    loader.stop()