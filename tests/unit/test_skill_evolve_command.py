"""CLI /skill-evolve 命令解析单元测试 + confirm rescan 联动 smoke test。"""
import io

import pytest
from rich.console import Console

from open_fox.cli import _run_skill_evolve, parse_skill_evolve_args
from open_fox.config import SkillEvolutionConfig
from open_fox.core.evolution.detector import EvolutionTriggerDetector
from open_fox.core.evolution.generator import EvolutionTask
from open_fox.core.evolution.manager import SkillEvolutionManager
from open_fox.core.evolution.pending import PendingQueue
from open_fox.core.evolution.stats import SkillInvocationTracker
from open_fox.core.skills.loader import SkillLoader


def test_parse_list():
    assert parse_skill_evolve_args("list") == ("list", "")


def test_parse_confirm_with_id():
    assert parse_skill_evolve_args("confirm evo-abc123") == ("confirm", "evo-abc123")


def test_parse_reject_with_reason():
    assert parse_skill_evolve_args("reject evo-abc 原因") == ("reject", "evo-abc 原因")


def test_parse_empty():
    assert parse_skill_evolve_args("") == ("", "")


# ---- confirm 写盘 + loader.rescan 联动 smoke test ----

class _NoopChat:
    """EvolutionTask 只在 _generate 时用 chat，confirm 路径不走 LLM，留空实现。"""

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        raise RuntimeError("confirm 路径不应调 LLM")


def _build_evolution_task(skills_dir, data_dir):
    """最小 EvolutionTask 构造：仅提供 queue / manager 即可供 _run_skill_evolve 使用。"""
    cfg = SkillEvolutionConfig(min_failures=2, min_repeats=2)
    manager = SkillEvolutionManager(skills_dir, data_dir)
    tracker = SkillInvocationTracker(data_dir)
    detector = EvolutionTriggerDetector(cfg, tracker, lambda: set())
    queue = PendingQueue(data_dir / "pending.json")
    return EvolutionTask(
        cfg, manager, tracker, detector, queue, _NoopChat(),
        existing_skills=lambda: set(),
        get_skill_md=lambda n: "x",
    )


@pytest.mark.asyncio
async def test_confirm_writes_skill_and_rescan(tmp_path):
    """confirm 子命令应落盘 + 立即 rescan loader，状态改为 confirmed。"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    loader = SkillLoader(skills_dir=skills_dir)
    task = _build_evolution_task(skills_dir, data_dir)
    pending = task.queue
    await pending.load()

    skill_name = "smoke-skill"
    content = (
        "---\n"
        "name: smoke-skill\n"
        "description: smoke 测试 skill\n"
        "---\n\n"
        "# smoke 正文\n"
    )
    item = await pending.enqueue(
        action="create", skill_name=skill_name, reason="smoke", content=content,
    )

    console = Console(file=io.StringIO(), force_terminal=False)
    await _run_skill_evolve(console, task, loader, "confirm", item.id)

    # 1) 文件已落盘
    assert (skills_dir / skill_name / "SKILL.md").exists()
    # 2) loader.rescan() 已生效 → loader.all() 含新 skill
    assert skill_name in loader.all()
    # 3) 队列状态已切到 confirmed
    assert pending.get(item.id).status == "confirmed"
    # 4) 变更日志完整（create + version 1）
    changelog = (data_dir / "changelog.log").read_text(encoding="utf-8")
    assert "[Skill新增]" in changelog
    assert skill_name in changelog
    assert "version 1" in changelog


@pytest.mark.asyncio
async def test_confirm_rejects_unknown_id(tmp_path):
    """不存在的 id 应走错误分支，不抛异常、不修改队列。"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    data_dir = tmp_path / "data"

    loader = SkillLoader(skills_dir=skills_dir)
    task = _build_evolution_task(skills_dir, data_dir)
    pending = task.queue
    await pending.load()

    console = Console(file=io.StringIO(), force_terminal=False)
    await _run_skill_evolve(console, task, loader, "confirm", "evo-doesnotexist")

    # 队列仍为空（无任何候选被处理）
    assert pending.list("pending") == []
    assert pending.list("confirmed") == []
    # loader 仍空（不存在的 id 不会触发任何 rescan 副作用）
    assert loader.all() == {}
