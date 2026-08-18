"""Skill 进化唯一写入口：校验 + 版本快照 + 原子写 + 变更日志 + deprecated + rollback。"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from open_fox.core.skills.parser import parse_skill_md, parse_skill_md_text

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_VERSIONS_DIR = ".versions"


class SkillValidationError(ValueError):
    """Skill 内容校验失败。"""


class SkillEvolutionManager:
    def __init__(self, skills_dir: Path, data_dir: Path):
        self._skills_dir = Path(skills_dir)
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._changelog = self._data_dir / "changelog.log"
        self._lock = asyncio.Lock()

    def validate_candidate(self, action: str, skill_name: str, content: str) -> None:
        """校验候选内容；不通过抛 SkillValidationError。"""
        if not _NAME_RE.match(skill_name):
            raise SkillValidationError(f"非法 Skill 名：{skill_name}")
        if not content.strip().startswith("---"):
            raise SkillValidationError("SKILL.md 缺少 YAML frontmatter")
        try:
            skill = parse_skill_md_text(content)
        except Exception as e:
            raise SkillValidationError(f"SKILL.md 解析失败：{e}") from e
        if skill.name != skill_name:
            raise SkillValidationError(
                f"frontmatter name={skill.name} 与目标名 {skill_name} 不一致")
        if action == "create" and (self._skills_dir / skill_name).exists():
            raise SkillValidationError(f"Skill 已存在：{skill_name}（如需修改请用 fix）")

    async def apply_candidate(self, action: str, skill_name: str, content: str) -> str:
        """校验并落盘。create → 新建（version 1）；fix → 更新（快照 + 版本递增）。"""
        async with self._lock:
            if action not in ("create", "fix"):
                raise SkillValidationError(f"非法操作类型：{action}")
            self.validate_candidate(action, skill_name, content)
            if action == "create":
                return self._create_locked(skill_name, content)
            return self._update_locked(skill_name, content)

    def _create_locked(self, skill_name: str, content: str) -> str:
        skill_dir = self._skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=False)
        self._atomic_write(skill_dir / "SKILL.md", self._ensure_version(content, 1))
        self._append_changelog(f"[Skill新增] {skill_name} | version 1 | 确认人：user")
        return f"[Skill新增] {skill_name} | version 1"

    def _update_locked(self, skill_name: str, content: str) -> str:
        skill_dir = self._skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise SkillValidationError(f"Skill 不存在：{skill_name}")
        try:
            current = parse_skill_md(skill_md).version
        except Exception as e:
            raise SkillValidationError(
                f"读取/解析现有 SKILL.md 失败：{skill_name}（{e}）") from e
        self._snapshot(skill_dir, current)
        next_version = current + 1
        self._atomic_write(skill_md, self._ensure_version(content, next_version))
        self._append_changelog(
            f"[Skill更新] {skill_name} | {current} -> {next_version} | 确认人：user")
        return f"[Skill更新] {skill_name} | {current} -> {next_version}"

    def _ensure_version(self, content: str, version: int) -> str:
        """把 frontmatter 的 version 字段强制设为指定值（覆盖 LLM 输出）。"""
        lines = content.splitlines()
        if not (lines and lines[0].strip() == "---"):
            return content
        close = 1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        meta = [l for l in lines[1:close] if not l.strip().startswith("version:")]
        meta.append(f"version: {version}")
        return "\n".join(["---", *meta, *lines[close:]])

    def _snapshot(self, skill_dir: Path, version: int) -> None:
        """把当前 skill 目录（排除 .versions）快照到 .versions/vN/。"""
        dst = skill_dir / _VERSIONS_DIR / f"v{version}"
        if dst.exists():
            return
        shutil.copytree(skill_dir, dst, ignore=shutil.ignore_patterns(_VERSIONS_DIR))

    def _atomic_write(self, path: Path, text: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _append_changelog(self, line: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
        with self._changelog.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")

    async def deprecate(self, skill_name: str) -> str:
        """标记 deprecated: true（不删除）。"""
        async with self._lock:
            skill_md = self._skills_dir / skill_name / "SKILL.md"
            if not skill_md.exists():
                raise SkillValidationError(f"Skill 不存在：{skill_name}")
            try:
                text = skill_md.read_text(encoding="utf-8")
            except Exception as e:
                raise SkillValidationError(
                    f"读取 SKILL.md 失败：{skill_name}（{e}）") from e
            if "deprecated: true" in text:
                return f"已处于废弃状态：{skill_name}"
            lines = text.splitlines()
            close = 1
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    close = i
                    break
            meta = [l for l in lines[1:close] if not l.strip().startswith("deprecated:")]
            meta.append("deprecated: true")
            self._atomic_write(skill_md, "\n".join(["---", *meta, *lines[close:]]))
            self._append_changelog(f"[Skill废弃] {skill_name} | 确认人：user")
            return f"[Skill废弃] {skill_name}"

    async def rollback(self, skill_name: str) -> str:
        """恢复 .versions/ 中版本号最大的快照（轻量回滚，保留历史）。"""
        async with self._lock:
            skill_dir = self._skills_dir / skill_name
            versions_dir = skill_dir / _VERSIONS_DIR
            if not versions_dir.exists():
                raise SkillValidationError(f"无历史版本可回滚：{skill_name}")
            snaps = sorted(
                (p for p in versions_dir.iterdir() if p.is_dir()),
                key=lambda p: int(p.name.lstrip("v")) if p.name[1:].isdigit() else -1,
            )
            if not snaps:
                raise SkillValidationError(f"无历史版本可回滚：{skill_name}")
            latest = snaps[-1]
            shutil.copytree(latest, skill_dir, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(_VERSIONS_DIR))
            self._append_changelog(f"[Skill回滚] {skill_name} -> {latest.name} | 确认人：user")
            return f"[Skill回滚] {skill_name} -> {latest.name}"

    def load_sync(self) -> None:
        """预留：manager 无需要加载的持久化状态（changelog 只追加）。"""
        return
