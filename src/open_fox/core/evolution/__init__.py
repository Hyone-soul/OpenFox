"""Skill 自我进化系统。"""
from __future__ import annotations

from pathlib import Path

from open_fox.core.evolution.detector import EvolutionTriggerDetector
from open_fox.core.evolution.generator import EvolutionTask
from open_fox.core.evolution.manager import SkillEvolutionManager
from open_fox.core.evolution.pending import PendingQueue
from open_fox.core.evolution.stats import SkillInvocationTracker


def _existing_skill_names(skills_dir: Path):
    def _names() -> set[str]:
        return {d.name for d in Path(skills_dir).iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()}
    return _names


def _skill_reader(skills_dir: Path):
    def _read(name: str) -> str:
        return (Path(skills_dir) / name / "SKILL.md").read_text(encoding="utf-8")
    return _read


def build_evolution(cfg, adapter, skills_dir: Path):
    """构造进化组件（不加载持久化，由调用方 load/load_sync）。

    返回 (manager, tracker, detector, queue, task)。
    """
    evo = cfg.skill_evolution
    manager = SkillEvolutionManager(skills_dir=skills_dir, data_dir=evo.data_dir)
    tracker = SkillInvocationTracker(data_dir=evo.data_dir)
    queue = PendingQueue(evo.data_dir / "pending.json")
    detector = EvolutionTriggerDetector(evo, tracker, _existing_skill_names(skills_dir))
    task = EvolutionTask(
        evo, manager, tracker, detector, queue, adapter,
        existing_skills=_existing_skill_names(skills_dir),
        get_skill_md=_skill_reader(skills_dir),
    )
    return manager, tracker, detector, queue, task
