"""智能体配置模型：Web 端创建的智能体定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import yaml


@dataclass
class AgentConfig:
    """单个智能体的完整配置。"""

    id: str
    name: str
    description: str = ""
    model: str = ""                    # 绑定模型（空 = 全局 active）
    system_prompt: str = ""            # 智能体专属系统提示词
    tools: list[str] = field(default_factory=list)    # 空 = 全部
    skills: list[str] = field(default_factory=list)   # 空 = 全部
    temperature: float | None = None   # 采样温度（None = 用上游默认）
    max_steps: int = 500
    owner: str = ""                     # 所属用户（空 = 全局 / 旧数据兼容）
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        # 只取已知字段，忽略未知键（兼容未来扩展）
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)


def validate_agent(agent: AgentConfig, available_models: list[str]) -> list[str]:
    """校验智能体配置，返回错误列表（空 = 通过）。"""
    errors: list[str] = []
    if not agent.id.strip():
        errors.append("id 不能为空")
    if not agent.name.strip():
        errors.append("name 不能为空")
    if agent.model and agent.model not in available_models:
        errors.append(f"model 字段: 模型 '{agent.model}' 不在可用模型列表中")
    return errors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    """智能体配置读写 config.yaml 的 agents 段。"""

    def __init__(self, config_path: str | Path):
        self._path = Path(config_path)
        if not self._path.exists():
            self._path.write_text("agents: []\n", encoding="utf-8")

    def _load(self) -> dict:
        return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}

    def _save(self, raw: dict) -> None:
        self._path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def list(self) -> list[AgentConfig]:
        raw = self._load()
        return [AgentConfig.from_dict(a) for a in raw.get("agents", [])]

    def get(self, agent_id: str) -> AgentConfig | None:
        for a in self.list():
            if a.id == agent_id:
                return a
        return None

    def create(self, agent: AgentConfig) -> AgentConfig:
        if self.get(agent.id):
            raise ValueError(f"智能体 '{agent.id}' 已存在")
        now = _now()
        agent.created_at = now
        agent.updated_at = now
        self._upsert(agent)
        return agent

    def update(self, agent_id: str, data: dict) -> AgentConfig:
        existing = self.get(agent_id)
        if existing is None:
            raise ValueError(f"智能体 '{agent_id}' 不存在")
        for k, v in data.items():
            if k in AgentConfig.__dataclass_fields__:
                setattr(existing, k, v)
        existing.updated_at = _now()
        self._upsert(existing)
        return existing

    def delete(self, agent_id: str) -> None:
        raw = self._load()
        agents = raw.get("agents", [])
        raw["agents"] = [a for a in agents if a.get("id") != agent_id]
        self._save(raw)

    def _upsert(self, agent: AgentConfig) -> None:
        raw = self._load()
        agents = raw.get("agents", [])
        agents = [a for a in agents if a.get("id") != agent.id]
        agents.append(agent.to_dict())
        raw["agents"] = agents
        self._save(raw)

