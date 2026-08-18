"""
Context Breakdown — 上下文分解与量化

将发给 API 的请求拆成 8 个可量化的类目（参考 Hermes agent/context_breakdown.py）：
  system_prompt / tool_definitions / rules / skills / mcp / subagent_definitions / memory / conversation

每个类目独立估算 token 数，构成上下文管理的度量基础。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .token_estimator import (
    estimate_tokens,
    estimate_messages_tokens,
    estimate_tool_schemas_tokens,
    get_model_context_window,
)


class ContextCategory(str, Enum):
    """上下文 8 大类目"""
    SYSTEM_PROMPT = "system_prompt"
    TOOL_DEFINITIONS = "tool_definitions"
    RULES = "rules"              # Agent system_prompt / extra rules
    SKILLS = "skills"            # 技能索引
    MCP = "mcp"                  # MCP 工具（含在 tool_definitions 中，但单独量化）
    SUBAGENT_DEFINITIONS = "subagent_definitions"  # 子智能体（预留）
    MEMORY = "memory"            # 全局记忆
    CONVERSATION = "conversation"  # 对话历史


@dataclass
class CategoryUsage:
    """单个类目的 token 用量"""
    category: ContextCategory
    tokens: int = 0
    detail: str = ""  # 可选的补充说明


@dataclass
class ContextSnapshot:
    """
    上下文快照——某一时刻所有类目的 token 占用全景。

    用法：
      snapshot = ContextSnapshot.capture(...)
      print(snapshot.summary())
      print(f"上下文占用率: {snapshot.usage_percent:.1f}%")
    """
    categories: list[CategoryUsage] = field(default_factory=list)
    context_window: int = 32_000
    max_tokens: int = 4_096  # 模型输出预留

    @property
    def total_tokens(self) -> int:
        """当前上下文总 token 数"""
        return sum(c.tokens for c in self.categories)

    @property
    def effective_budget(self) -> int:
        """有效输入预算 = 上下文窗口 − 模型输出预留"""
        return max(0, self.context_window - self.max_tokens)

    @property
    def usage_percent(self) -> float:
        """上下文占用率（相对于有效预算）"""
        budget = self.effective_budget
        if budget <= 0:
            return 100.0
        return (self.total_tokens / budget) * 100

    @property
    def remaining_tokens(self) -> int:
        """剩余可用 token 数"""
        return max(0, self.effective_budget - self.total_tokens)

    def get_category(self, cat: ContextCategory) -> CategoryUsage:
        """获取指定类目的用量"""
        for c in self.categories:
            if c.category == cat:
                return c
        return CategoryUsage(category=cat, tokens=0)

    def summary(self) -> str:
        """
        生成可视化摘要（类 CLI /context 输出）

        示例：
          ┌─ Context Status ─────────────────────────┐
          │  Window: 64,000  Budget: 59,592          │
          │  Used:   12,345  (20.7%)  Free: 47,247   │
          ├──────────────────────────────────────────┤
          │  system_prompt     1,234  ███░░░  2.1%   │
          │  tool_definitions    890  █░░░░░  1.5%   │
          │  conversation     10,221  ██████ 17.1%   │
          │  ...                                      │
          └──────────────────────────────────────────┘
        """
        lines = []
        lines.append("┌─ Context Status ──────────────────────────────────┐")
        lines.append(f"│  Window: {self.context_window:>7,}  "
                      f"Budget: {self.effective_budget:>7,}  "
                      f"MaxTokens: {self.max_tokens:>5,}     │")
        lines.append(f"│  Used:   {self.total_tokens:>7,}  "
                      f"({self.usage_percent:>5.1f}%)  "
                      f"Free: {self.remaining_tokens:>7,}          │")
        lines.append("├──────────────────────────────────────────────────────┤")

        budget = self.effective_budget
        for c in sorted(self.categories, key=lambda x: x.tokens, reverse=True):
            pct = (c.tokens / budget * 100) if budget > 0 else 0
            # 进度条（最多 10 格）
            bar_len = min(10, max(0, round(pct / 10)))
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(
                f"│  {c.category.value:<20s} {c.tokens:>7,}  {bar} {pct:>5.1f}% │"
            )

        lines.append("└──────────────────────────────────────────────────────┘")
        return "\n".join(lines)


class ContextBreakdown:
    """
    上下文分解器——将完整的 API 请求拆分为 8 个类目并量化。

    参考 Hermes 的 context_breakdown.py，给每一类算 token 数，
    于是每个时刻都知道"离上下文窗口还有多远"。
    """

    @staticmethod
    def capture(
        messages: list[dict],
        tool_schemas: list[dict] | None = None,
        skills: dict | list | None = None,
        model_name: str = "",
        context_window: int | None = None,
        max_tokens: int = 4096,
        memory_text: str = "",
    ) -> ContextSnapshot:
        """
        捕获当前上下文快照。

        参数：
          messages: 会话消息列表（含 system 消息）
          tool_schemas: 工具 JSON Schema 列表
          skills: 技能列表/字典
          model_name: 当前模型名（用于自动检测上下文窗口）
          context_window: 手动指定上下文窗口（优先于模型名检测）
          max_tokens: 模型输出预留 token 数
          memory_text: 全局记忆注入文本
        """
        categories: list[CategoryUsage] = []

        # ── 1. 从消息中分离各类目 ──

        system_tokens = 0
        conversation_tokens = 0
        rules_tokens = 0
        memory_tokens = 0
        skills_tokens = 0

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content") or ""

            if role == "system":
                # 系统提示是混合体，尝试拆分
                # 但实际存储是一整条 system 消息，所以先整体算
                system_tokens += estimate_tokens(content)
                system_tokens += 4  # role 开销

                # 尝试从内容中识别记忆部分
                if memory_text and memory_text in content:
                    # 记忆文本包含在 system 中，单独量化
                    mem_tokens = estimate_tokens(memory_text)
                    system_tokens -= mem_tokens
                    memory_tokens += mem_tokens

                # 尝试识别技能索引部分
                # 技能索引通常以 "可用 Skill：" 或 "Available Skills:" 开头
                skill_section_start = content.find("可用 Skill")
                if skill_section_start == -1:
                    skill_section_start = content.find("Available Skill")
                if skill_section_start >= 0:
                    skill_text = content[skill_section_start:]
                    skill_tk = estimate_tokens(skill_text)
                    system_tokens -= skill_tk
                    skills_tokens += skill_tk

            elif role in ("user", "assistant", "tool"):
                conversation_tokens += estimate_tokens(content)
                conversation_tokens += 4  # role 开销

                # reasoning_content
                rc = msg.get("reasoning_content")
                if rc:
                    conversation_tokens += estimate_tokens(rc)

                # tool_calls
                tcs = msg.get("tool_calls")
                if tcs:
                    for tc in tcs:
                        func = tc.get("function", {})
                        conversation_tokens += estimate_tokens(func.get("name"))
                        conversation_tokens += estimate_tokens(func.get("arguments"))
                        conversation_tokens += 2

                if msg.get("tool_call_id"):
                    conversation_tokens += 2

        # ── 2. 工具定义 ──
        tool_def_tokens = estimate_tool_schemas_tokens(tool_schemas or [])

        # ── 3. 记忆（如果不在 system 中单独量化）──
        if memory_text and memory_tokens == 0:
            memory_tokens = estimate_tokens(memory_text)

        # ── 4. 技能（如果不在 system 中单独量化）──
        if skills:
            if isinstance(skills, dict):
                for s in skills.values():
                    skills_tokens += estimate_tokens(getattr(s, "description", ""))
                    skills_tokens += estimate_tokens(getattr(s, "name", ""))
            elif isinstance(skills, list):
                for s in skills:
                    if isinstance(s, dict):
                        skills_tokens += estimate_tokens(s.get("description", ""))
                        skills_tokens += estimate_tokens(s.get("name", ""))

        # ── 构建类目列表 ──
        categories.append(CategoryUsage(ContextCategory.SYSTEM_PROMPT, system_tokens,
                                         "平台感知 + 工具使用规则 + Vibe Coding 提示"))
        categories.append(CategoryUsage(ContextCategory.TOOL_DEFINITIONS, tool_def_tokens,
                                         f"工具数量: {len(tool_schemas) if tool_schemas else 0}"))
        categories.append(CategoryUsage(ContextCategory.RULES, rules_tokens,
                                         "Agent 自定义 system_prompt"))
        categories.append(CategoryUsage(ContextCategory.SKILLS, skills_tokens,
                                         "技能索引（L1）"))
        categories.append(CategoryUsage(ContextCategory.MCP, 0, "MCP 工具（含在 tool_definitions 中）"))
        categories.append(CategoryUsage(ContextCategory.SUBAGENT_DEFINITIONS, 0, "子智能体定义（预留）"))
        categories.append(CategoryUsage(ContextCategory.MEMORY, memory_tokens,
                                         "全局记忆注入"))
        categories.append(CategoryUsage(ContextCategory.CONVERSATION, conversation_tokens,
                                         f"消息数: {sum(1 for m in messages if m.get('role') != '__meta__')}"))

        # ── 确定上下文窗口 ──
        window = context_window or get_model_context_window(model_name)

        return ContextSnapshot(
            categories=categories,
            context_window=window,
            max_tokens=max_tokens,
        )
