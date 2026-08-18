"""配置加载：YAML + 环境变量 + CLI 覆盖。

加载优先级（后者覆盖前者）：
1. 内置默认值
2. YAML 文件
3. 环境变量替换 ${VAR} 占位符
4. CLI 参数覆盖
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelConfig:
    """单个模型配置。"""

    name: str
    base_url: str
    model: str
    api_key: str = ""             # 直接填写的密钥（优先）
    api_key_env: str = ""         # 密钥环境变量名（兼容旧配置，为空则忽略）
    temperature: float | None = None   # 默认采样温度（None = 用上游默认）
    max_tokens: int | None = None      # 单次回复最大 token 数（None = 不限制）
    retry_count: int | None = None    # 失败重试次数（None = 用默认值 3）


@dataclass
class McpServerConfig:
    """MCP 服务器配置。"""

    name: str
    transport: str  # stdio | sse | streamable-http
    command: str | None = None
    url: str | None = None
    headers: dict = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 30
    tool_allowlist: list[str] = field(default_factory=list)
    tool_denylist: list[str] = field(default_factory=list)
    permissions: dict = field(default_factory=dict)
    source_file: str = ""


@dataclass
class StorageConfig:
    """存储后端配置。"""

    backend: str = "memory"  # memory | json | mysql
    json_dir: str = "./data/sessions"
    mysql_url: str = ""


@dataclass
class SkillEvolutionConfig:
    """Skill 自我进化系统配置。"""

    enabled: bool = True
    require_confirmation: bool = True  # 写盘前必须用户确认
    min_failures: int = 2              # 分支A：同 skill 失败阈值
    min_repeats: int = 2               # 分支B：同会话签名重复阈值
    cooldown_turns: int = 20           # 冷却：修复/拒绝后抑制再触发
    data_dir: Path = Path("./data/evolution")


@dataclass
class ContextCompressionConfig:
    """上下文压缩配置。"""

    enabled: bool = True
    threshold: float = 0.5              # 触发阈值 = effective_budget × threshold
    target_ratio: float = 0.2           # 压缩目标 = effective_budget × target_ratio
    protect_first_n: int = 3            # 保护头部 N 条消息
    protect_last_n: int = 20            # 保护尾部 N 条消息
    max_attempts: int = 3               # 最大压缩重试次数
    anti_thrash_threshold: float = 0.1  # 反抖动：连续两次压缩收益 <10% 则熔断
    cooldown_seconds: float = 30.0      # 压缩失败冷却期（秒）
    context_window: int | None = None   # 手动指定上下文窗口（None = 自动检测）


@dataclass
class AppConfig:
    """应用全局配置。"""

    skills_dir: Path = Path("./skills")
    workspace_dir: Path = Path("./workspace")
    logs_dir: Path = Path("./logs")
    max_agent_steps: int = 500
    script_default_timeout: int = 30
    mcp_call_timeout: int = 60
    models: list[ModelConfig] = field(default_factory=list)
    active_model: str = ""
    storage: StorageConfig = field(default_factory=StorageConfig)
    custom_tools_dir: Path = Path("./tools")
    mcps_dir: Path = Path("./mcps")
    skill_evolution: SkillEvolutionConfig = field(default_factory=SkillEvolutionConfig)
    compression: ContextCompressionConfig = field(default_factory=ContextCompressionConfig)


_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _substitute_env(value):
    """递归替换字符串中的 ${VAR} 占位符。"""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def _load_dotenv():
    """自动加载 .env 文件（不覆盖已有系统环境变量）。

    若 python-dotenv 未安装则静默跳过（不影响其他功能）。
    """
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
    except ImportError:
        pass


def load_config(path: str | None = None, cli_overrides: dict | None = None) -> AppConfig:
    """加载并合并配置。

    配置加载顺序（后者覆盖前者）：
    1. 内置默认值
    2. .env 文件（不覆盖系统环境变量）
    3. YAML 文件（默认 ./config.yaml，存在则加载）
    4. CLI 参数
    """
    _load_dotenv()

    if path is None:
        # 默认加载 ./config.yaml（存在则加载，不存在也不报错）
        default_path = Path("config.yaml")
        if default_path.exists():
            path = str(default_path)

    raw: dict = {}
    if path:
        config_path = Path(path)
        if config_path.exists():
            with config_path.open(encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}

    raw = _substitute_env(raw)

    cfg = AppConfig()

    # 基础字段
    if "skills_dir" in raw:
        cfg.skills_dir = Path(raw["skills_dir"])
    if "workspace_dir" in raw:
        cfg.workspace_dir = Path(raw["workspace_dir"])
    if "logs_dir" in raw:
        cfg.logs_dir = Path(raw["logs_dir"])
    if "max_agent_steps" in raw:
        cfg.max_agent_steps = int(raw["max_agent_steps"])
    if "script_default_timeout" in raw:
        cfg.script_default_timeout = int(raw["script_default_timeout"])
    if "mcp_call_timeout" in raw:
        cfg.mcp_call_timeout = int(raw["mcp_call_timeout"])

    # 自定义工具 / MCP 配置目录
    if "custom_tools_dir" in raw:
        cfg.custom_tools_dir = Path(raw["custom_tools_dir"])
    if "mcps_dir" in raw:
        cfg.mcps_dir = Path(raw["mcps_dir"])

    # 模型列表
    for m in raw.get("models", []):
        mc = ModelConfig(**m)
        # 优先用直接填写的 api_key；否则从 api_key_env 环境变量解析
        if not mc.api_key and mc.api_key_env:
            mc.api_key = os.environ.get(mc.api_key_env, "")
        cfg.models.append(mc)

    # 存储
    if "storage" in raw:
        cfg.storage = StorageConfig(**raw["storage"])

    # Skill 进化
    if "skill_evolution" in raw:
        se = SkillEvolutionConfig(**raw["skill_evolution"])
        se.data_dir = Path(se.data_dir)
        cfg.skill_evolution = se

    # 上下文压缩
    if "compression" in raw:
        cd = raw["compression"]
        cfg.compression = ContextCompressionConfig(
            enabled=cd.get("enabled", cfg.compression.enabled),
            threshold=float(cd.get("threshold", cfg.compression.threshold)),
            target_ratio=float(cd.get("target_ratio", cfg.compression.target_ratio)),
            protect_first_n=int(cd.get("protect_first_n", cfg.compression.protect_first_n)),
            protect_last_n=int(cd.get("protect_last_n", cfg.compression.protect_last_n)),
            max_attempts=int(cd.get("max_attempts", cfg.compression.max_attempts)),
            anti_thrash_threshold=float(cd.get("anti_thrash_threshold", cfg.compression.anti_thrash_threshold)),
            cooldown_seconds=float(cd.get("cooldown_seconds", cfg.compression.cooldown_seconds)),
            context_window=int(cd["context_window"]) if "context_window" in cd else None,
        )

    # 默认激活第一个模型
    if cfg.models and not cfg.active_model:
        cfg.active_model = cfg.models[0].name

    # CLI 覆盖
    if cli_overrides:
        if "model" in cli_overrides:
            cfg.active_model = cli_overrides["model"]
        if "skills_dir" in cli_overrides:
            cfg.skills_dir = Path(cli_overrides["skills_dir"])

    return cfg
