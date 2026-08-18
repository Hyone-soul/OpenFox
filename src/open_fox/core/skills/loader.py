"""Skill 加载器，支持 watchdog 热加载。

职责：
- 递归扫描 skills_dir 下所有 SKILL.md
- 监听文件系统事件（创建/修改/删除/移动）触发增量重扫
- 将变化通过 on_change 回调通知上层（通常是 Registry）

失败容忍：单个 Skill 解析失败不影响其他 Skill 的加载。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from open_fox.core.skills.models import Skill
from open_fox.core.skills.parser import SkillParseError, parse_skill_md

logger = logging.getLogger(__name__)


class SkillLoader:
    """扫描 skills_dir 并维护最新 Skill 集合。"""

    def __init__(
        self,
        skills_dir: Path,
        on_change: Callable[[dict[str, Skill]], None] | None = None,
    ):
        self._dir = Path(skills_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._on_change = on_change or (lambda _: None)
        self._skills: dict[str, Skill] = {}
        self._observer: Observer | None = None

    def all(self) -> dict[str, Skill]:
        """当前所有 Skill 的快照（浅拷贝）。"""
        return dict(self._skills)

    def rescan(self) -> None:
        """全量重扫。

        失败容忍：单个 SKILL.md 读取失败（被占用、临时权限问题）或解析失败都不影响
        其他 Skill 的加载，rescan 继续往下走。事件回调在 watchdog 线程里，
        异常不能冒泡，否则其他 Skill 也加载不到。
        """
        new_skills: dict[str, Skill] = {}
        for skill_md in self._dir.rglob("SKILL.md"):
            # 排除 .versions 目录下的版本快照，避免历史版本被误加载
            # （同名 last-wins 会选中旧版）
            if ".versions" in skill_md.parts:
                continue
            try:
                skill = parse_skill_md(skill_md)
                new_skills[skill.name] = skill
            except (SkillParseError, OSError) as e:
                logger.warning("跳过 Skill %s：%s", skill_md, e)
        self._skills = new_skills
        self._on_change(self._skills)

    def start(self) -> None:
        """启动 watchdog 监听。"""
        self.rescan()
        handler = _Handler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._dir), recursive=True)
        self._observer.start()
        logger.info("Skill 热加载监听已启动：%s", self._dir)

    def stop(self) -> None:
        """停止监听。"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def _on_event(self, event: FileSystemEvent) -> None:
        """文件系统事件回调：触发增量重扫。"""
        if event.is_directory and event.event_type in ("created", "deleted"):
            # 新增/删除目录：可能意味着新 Skill
            self.rescan()
            return
        if event.src_path.endswith("SKILL.md"):
            self.rescan()


class _Handler(FileSystemEventHandler):
    def __init__(self, loader: SkillLoader):
        self._loader = loader

    def on_any_event(self, event: FileSystemEvent) -> None:
        self._loader._on_event(event)