"""Skill 进化写入口单元测试。"""
import pytest

from open_fox.core.evolution.manager import (
    SkillEvolutionManager,
    SkillValidationError,
)

NEW_MD = "---\nname: evo-demo\ndescription: 进化测试\n---\n正文"
NEW_MD_STRIP_VER = ("---\nname: evo-demo\ndescription: 进化测试\n"
                    "version: 99\n---\n正文")  # version 由系统管理，LLM 写的应被覆盖
FIX_MD = "---\nname: evo-demo\ndescription: 修复后\n---\n修复正文"


@pytest.fixture
def mgr(tmp_path):
    return SkillEvolutionManager(skills_dir=tmp_path / "skills",
                                 data_dir=tmp_path / "data")


@pytest.mark.asyncio
async def test_create_writes_skill(mgr, tmp_path):
    summary = await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    assert "Skill新增" in summary
    md = (tmp_path / "skills" / "evo-demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "version: 1" in md  # 新建固定 version 1


@pytest.mark.asyncio
async def test_create_rejects_existing(mgr):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    with pytest.raises(SkillValidationError):
        await mgr.apply_candidate("create", "evo-demo", NEW_MD)


@pytest.mark.asyncio
async def test_update_bumps_version_and_snapshots(mgr, tmp_path):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    summary = await mgr.apply_candidate("fix", "evo-demo", FIX_MD)
    assert "1 -> 2" in summary
    md = (tmp_path / "skills" / "evo-demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "version: 2" in md
    # 旧版已快照到 .versions/v1
    snap = tmp_path / "skills" / "evo-demo" / ".versions" / "v1" / "SKILL.md"
    assert snap.exists()
    assert "修复前" not in md and "正文" in md


@pytest.mark.asyncio
async def test_update_overrides_llm_version(mgr, tmp_path):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD_STRIP_VER)
    md = (tmp_path / "skills" / "evo-demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "version: 1" in md
    assert "version: 99" not in md


@pytest.mark.asyncio
async def test_invalid_name_rejected(mgr):
    with pytest.raises(SkillValidationError):
        await mgr.apply_candidate("create", "../evil", NEW_MD)
    with pytest.raises(SkillValidationError):
        await mgr.apply_candidate("create", "大写名字", NEW_MD)


@pytest.mark.asyncio
async def test_name_mismatch_rejected(mgr):
    with pytest.raises(SkillValidationError):
        await mgr.apply_candidate(
            "create", "other-name",
            "---\nname: mismatch\ndescription: d\n---\n正文",
        )


@pytest.mark.asyncio
async def test_invalid_action_rejected(mgr):
    """apply_candidate 只接受 create/fix，其他操作类型抛 SkillValidationError。"""
    with pytest.raises(SkillValidationError, match="非法操作类型"):
        await mgr.apply_candidate("delete", "evo-demo", NEW_MD)
    with pytest.raises(SkillValidationError, match="非法操作类型"):
        await mgr.apply_candidate("whatever", "evo-demo", NEW_MD)


@pytest.mark.asyncio
async def test_fix_nonexistent_rejected(mgr):
    """fix 一个不存在的 skill 应抛 SkillValidationError（与确认端点契约一致）。"""
    with pytest.raises(SkillValidationError, match="Skill 不存在"):
        await mgr.apply_candidate(
            "fix", "no-such-skill",
            "---\nname: no-such-skill\ndescription: 修复\n---\n正文",
        )


@pytest.mark.asyncio
async def test_deprecate_marks_frontmatter(mgr, tmp_path):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    summary = await mgr.deprecate("evo-demo")
    assert "Skill废弃" in summary
    md = (tmp_path / "skills" / "evo-demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "deprecated: true" in md


@pytest.mark.asyncio
async def test_rollback_restores_previous(mgr, tmp_path):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    await mgr.apply_candidate("fix", "evo-demo", FIX_MD)
    summary = await mgr.rollback("evo-demo")
    assert "v1" in summary
    md = (tmp_path / "skills" / "evo-demo" / "SKILL.md").read_text(encoding="utf-8")
    assert "进化测试" in md  # 恢复 v1 的 description
    assert "version: 1" in md


@pytest.mark.asyncio
async def test_changelog_appended(mgr, tmp_path):
    await mgr.apply_candidate("create", "evo-demo", NEW_MD)
    log = (tmp_path / "data" / "changelog.log").read_text(encoding="utf-8")
    assert "Skill新增" in log
