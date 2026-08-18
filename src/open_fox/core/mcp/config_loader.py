"""扫描 ./mcps/*.yaml|*.json 解析为 McpServerConfig[]。"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from open_fox.config import McpServerConfig, _substitute_env

logger = logging.getLogger(__name__)

_VALID_TRANSPORTS = {"stdio", "sse", "streamable-http"}


def load_mcp_configs(mcps_dir: Path) -> tuple[list[McpServerConfig], list[dict]]:
    if not mcps_dir.exists():
        return [], []
    configs: list[McpServerConfig] = []
    errors: list[dict] = []
    seen: set[str] = set()
    files = sorted(
        [*mcps_dir.glob("*.yaml"), *mcps_dir.glob("*.json")],
        key=lambda p: p.name,
    )
    for f in files:
        try:
            raw = (yaml.safe_load(f.read_text(encoding="utf-8"))
                   if f.suffix == ".yaml"
                   else json.loads(f.read_text(encoding="utf-8")))
            if not isinstance(raw, dict):
                raise ValueError("配置文件根必须是对象")  # noqa: TRY004
            cfg = _parse_one(raw, source_file=str(f))
            if cfg.transport not in _VALID_TRANSPORTS:
                raise ValueError(f"未知 transport：{cfg.transport}")
            if cfg.name in seen:
                raise ValueError(f"重复的 server name '{cfg.name}'")
            if cfg.transport == "stdio" and not cfg.command:
                raise ValueError("stdio transport 必须指定 command")
            if cfg.transport in ("sse", "streamable-http") and not cfg.url:
                raise ValueError(f"{cfg.transport} transport 必须指定 url")
            seen.add(cfg.name)
            configs.append(cfg)
        except Exception as e:  # noqa: BLE001
            errors.append({"source": str(f), "error": str(e)})
            logger.warning("MCP 配置 %s 跳过：%s", f, e)
    return configs, errors


def _parse_one(raw: dict, *, source_file: str) -> McpServerConfig:
    headers = raw.get("headers", {}) or {}
    headers = _substitute_env(headers)
    return McpServerConfig(
        name=str(raw["name"]),
        transport=str(raw["transport"]),
        command=raw.get("command"),
        url=raw.get("url"),
        headers=headers,
        enabled=bool(raw.get("enabled", True)),
        timeout=int(raw.get("timeout", 30)),
        tool_allowlist=list(raw.get("tool_allowlist", []) or []),
        tool_denylist=list(raw.get("tool_denylist", []) or []),
        permissions=dict(raw.get("permissions", {}) or {}),
        source_file=source_file,
    )
