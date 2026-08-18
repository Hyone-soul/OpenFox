"""Skill 调用轨迹统计：解析 tool_trace，跨会话持久化。

信号分两类：
- 分支A：skill 目录引用（skills/<name>/）→ per-skill 调用/失败计数
- 分支B：粗化工具签名（run_shell 取脚本 basename、文件工具取 父目录:文件名）
  → 会话内重复流程检测（不限于已存在的 skill）

本模块为同步方法 + 原子写，无 await 间隙，事件循环内天然串行，不需要锁。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILL_PATH_RE = re.compile(r"skills[\\/]([A-Za-z0-9_-]+)")
_MAX_ERROR_SAMPLES = 5
_MAX_SESSIONS = 20


@dataclass
class SkillStats:
    invocations: int = 0
    failures: int = 0
    last_failed_at: str = ""
    last_success_at: str = ""
    error_samples: list[str] = field(default_factory=list)
    cooldown_until_turn: int = 0


def _extract_skill_refs(entry: dict) -> list[str]:
    """从一条 tool_trace 提取 skill 目录引用，如 'shell:pdf' / 'read:pdf'。"""
    name = entry.get("name", "")
    args = entry.get("args") or {}
    refs: list[str] = []
    if name == "run_shell":
        m = _SKILL_PATH_RE.search(str(args.get("cmd", "")))
        if m:
            refs.append(f"shell:{m.group(1)}")
    elif name == "read_file":
        path = str(args.get("path", ""))
        if path.endswith("SKILL.md"):
            m = _SKILL_PATH_RE.search(path)
            if m:
                refs.append(f"read:{m.group(1)}")
    return refs


def _coarse_signature(entry: dict) -> str | None:
    """粗化工具签名：同一流程重复执行（输入不同）应得到相同签名。"""
    name = entry.get("name", "")
    args = entry.get("args") or {}
    if name == "run_shell":
        cmd = str(args.get("cmd", ""))
        m = re.search(r"([\w./\\-]+\.(?:py|sh|js))", cmd)
        if m:
            return f"shell:{Path(m.group(1)).name}"
        first = cmd.split()[0] if cmd.split() else ""
        return f"shell:{first}" if first else None
    if name in ("read_file", "write_file", "edit_file"):
        p = Path(str(args.get("path", "")))
        if p.name:
            return f"{name}:{p.parent.name}:{p.name}"
    return None


class SkillInvocationTracker:
    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._data_dir / "stats.json"
        self._stats: dict[str, SkillStats] = {}
        self._session_signatures: dict[str, dict[str, int]] = {}
        self._session_lru: list[str] = []
        self._turn_count = 0

    # ---- 轮次（节流用，AgentLoop 每轮由 EvolutionTask.notify 调用）----
    def register_turn(self) -> None:
        self._turn_count += 1

    def turn(self) -> int:
        return self._turn_count

    # ---- 记录 ----
    def record_trace(self, session_id: str, tool_trace: list[dict]) -> None:
        """解析并累计本次 tool_trace（同步方法，事件循环内调用）。"""
        self._touch_session(session_id)
        sig_bucket = self._session_signatures.setdefault(session_id, {})
        for entry in tool_trace:
            # 分支A：skill 目录引用 → per-skill 计数
            for ref in _extract_skill_refs(entry):
                skill = ref.split(":", 1)[1]
                st = self._stats.setdefault(skill, SkillStats())
                st.invocations += 1
                result = str(entry.get("result", ""))
                if result.startswith("ERROR:"):
                    st.failures += 1
                    st.last_failed_at = str(date.today())  # noqa: DTZ011
                    if len(st.error_samples) < _MAX_ERROR_SAMPLES:
                        st.error_samples.append(result[:200])
                else:
                    st.last_success_at = str(date.today())  # noqa: DTZ011
            # 分支B：粗化签名 → 会话内重复计数
            sig = _coarse_signature(entry)
            if sig:
                sig_bucket[sig] = sig_bucket.get(sig, 0) + 1

    def _touch_session(self, session_id: str) -> None:
        if session_id in self._session_lru:
            self._session_lru.remove(session_id)
        self._session_lru.append(session_id)
        if len(self._session_lru) > _MAX_SESSIONS:
            drop = self._session_lru.pop(0)
            self._session_signatures.pop(drop, None)

    # ---- 查询 ----
    def skill_failures(self, skill_name: str) -> int:
        return self._stats.get(skill_name, SkillStats()).failures

    def skill_invocations(self, skill_name: str) -> int:
        return self._stats.get(skill_name, SkillStats()).invocations

    def skill_stats(self, skill_name: str) -> SkillStats:
        return self._stats.setdefault(skill_name, SkillStats())

    def signature_count(self, session_id: str, signature: str) -> int:
        return self._session_signatures.get(session_id, {}).get(signature, 0)

    # ---- 持久化 ----
    async def load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._stats = {k: SkillStats(**v) for k, v in data.get("stats", {}).items()}
            self._session_signatures = data.get("signatures", {})
            # 重建 LRU 列表，让恢复的会话桶参与淘汰，避免死会话无界增长
            self._session_lru = list(self._session_signatures.keys())
        except Exception as e:  # noqa: BLE001
            logger.warning("skill 统计加载失败，用空统计继续：%s", e)

    async def save(self) -> None:
        payload = {
            "stats": {k: vars(v) for k, v in self._stats.items()},
            "signatures": self._session_signatures,
        }
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def load_sync(self) -> None:
        asyncio.run(self.load())
