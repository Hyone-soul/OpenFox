"""按智能体配置过滤工具与技能。"""

from __future__ import annotations

from open_fox.agents import AgentConfig
from open_fox.core.registry import Registry
from open_fox.core.skills.models import Skill


def filter_registry(agent: AgentConfig, registry: Registry) -> Registry:
    """按智能体配置过滤出可用的工具。空列表 = 全部。"""
    filtered = Registry()
    if not agent.tools:
        for schema in registry.list_tool_schemas():
            name = schema["function"]["name"]
            # resolve 同时解析内置工具与 MCP 工具（get_tool 只查内置工具）
            tool = registry.resolve(name)
            if tool is not None:
                filtered.register_tool(tool)
        return filtered
    for name in agent.tools:
        # resolve 支持 MCP 工具的 <server>__<tool> 命名
        tool = registry.resolve(name)
        if tool is not None:
            filtered.register_tool(tool)
    return filtered


def filter_skills(agent: AgentConfig, skills: dict[str, Skill]) -> dict[str, Skill]:
    """按智能体配置过滤出可用的技能。空列表 = 全部。"""
    if not agent.skills:
        return dict(skills)
    return {k: v for k, v in skills.items() if k in agent.skills}
