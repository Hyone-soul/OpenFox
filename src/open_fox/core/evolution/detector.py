"""进化触发判定：纯逻辑、无 LLM 调用。

- 分支A（修复）：本次 trace 涉及且累计失败 ≥ min_failures，且不在冷却期。
- 分支B（新建）：本次 trace 的粗化签名在会话内累计 ≥ min_repeats，且未被拒绝过。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from open_fox.config import SkillEvolutionConfig
from open_fox.core.evolution.stats import (
    SkillInvocationTracker,
    _coarse_signature,
    _extract_skill_refs,
)

logger = logging.getLogger(__name__)


@dataclass
class EvolutionTrigger:
    kind: Literal["fix", "create"]
    skill_name: str
    evidence: list[str]
    signature: str = ""  # 分支B 的粗化签名；分支A 为空


class EvolutionTriggerDetector:
    def __init__(
        self,
        config: SkillEvolutionConfig,
        tracker: SkillInvocationTracker,
        existing_skills: Callable[[], set[str]],
    ):
        self._config = config
        self._tracker = tracker
        self._existing = existing_skills
        self._rejected_signatures: set[str] = set()

    def mark_rejected(self, signature: str) -> None:
        """标记签名已处理（生成过/被拒绝过），避免同会话反复建议。"""
        self._rejected_signatures.add(signature)

    def evaluate(self, session_id: str, tool_trace: list[dict]) -> list[EvolutionTrigger]:
        if not self._config.enabled:
            return []
        self._tracker.record_trace(session_id, tool_trace)
        # 分支A：本次涉及且失败达阈值的 skill
        for skill in sorted(self._tracked_skills_in_trace(tool_trace)):
            if self._tracker.skill_failures(skill) >= self._config.min_failures:
                st = self._tracker.skill_stats(skill)
                if st.cooldown_until_turn <= self._tracker.turn():
                    return [EvolutionTrigger(
                        kind="fix", skill_name=skill,
                        evidence=list(st.error_samples), signature="",
                    )]
        # 分支B：本次签名在会话内重复达阈值
        for sig in self._signatures_in_trace(tool_trace):
            count = self._tracker.signature_count(session_id, sig)
            if count >= self._config.min_repeats and sig not in self._rejected_signatures:
                return [EvolutionTrigger(
                    kind="create", skill_name="",
                    evidence=[f"会话内相同流程重复 {count} 次：{sig}"],
                    signature=sig,
                )]
        return []

    def _tracked_skills_in_trace(self, tool_trace: list[dict]) -> set[str]:
        skills: set[str] = set()
        for entry in tool_trace:
            for ref in _extract_skill_refs(entry):
                skills.add(ref.split(":", 1)[1])
        return skills

    def _signatures_in_trace(self, tool_trace: list[dict]) -> list[str]:
        sigs: list[str] = []
        for entry in tool_trace:
            sig = _coarse_signature(entry)
            if sig:
                sigs.append(sig)
        return sigs
