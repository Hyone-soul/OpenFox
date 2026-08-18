"""模型配置读写 config.yaml 的 models 段。

与 AgentStore 对称：负责 config.yaml 中 models 列表的 CRUD，
不涉及内存中的 adapter 同步（由 server.py 端点处理）。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


class ModelStore:
    """模型配置读写 config.yaml 的 models 段。"""

    def __init__(self, config_path: str | Path):
        self._path = Path(config_path)
        if not self._path.exists():
            self._path.write_text("models: []\n", encoding="utf-8")

    def _load(self) -> dict:
        return yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}

    def _save(self, raw: dict) -> None:
        self._path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _resolve_api_key(entry: dict) -> str:
        """从条目解析密钥：优先 api_key 字段，其次从 api_key_env 环境变量读取。"""
        key = entry.get("api_key", "")
        if key:
            return key
        env_name = entry.get("api_key_env", "")
        if env_name:
            return os.environ.get(env_name, "")
        return ""

    def list(self) -> list[dict]:
        """返回模型完整配置列表（含解析后的 api_key，供管理页面展示/编辑）。"""
        raw = self._load()
        result = []
        for m in raw.get("models", []):
            entry = dict(m)
            # 统一输出 api_key 字段（兼容旧 api_key_env 配置）
            entry["api_key"] = self._resolve_api_key(m)
            result.append(entry)
        return result

    def get(self, name: str) -> dict | None:
        for m in self.list():
            if m.get("name") == name:
                return m
        return None

    def create(self, data: dict) -> dict:
        """新增模型配置。name 不可重复。"""
        raw = self._load()
        models = raw.get("models", [])
        name = data.get("name", "").strip()
        if not name:
            raise ValueError("模型 name 不能为空")
        if any(m.get("name") == name for m in models):
            raise ValueError(f"模型 '{name}' 已存在")
        entry = {
            "name": name,
            "base_url": data.get("base_url", ""),
            "model": data.get("model", ""),
            "api_key": data.get("api_key", ""),
            "temperature": data.get("temperature"),
            "max_tokens": data.get("max_tokens"),
            "retry_count": data.get("retry_count"),
        }
        models.append(entry)
        raw["models"] = models
        self._save(raw)
        return entry

    def update(self, name: str, data: dict) -> dict:
        """更新模型配置（name 不可改，可改 base_url/model/api_key/temperature/max_tokens/retry_count）。

        旧配置含 api_key_env 时，更新后会统一改为 api_key 明文存储。
        """
        raw = self._load()
        models = raw.get("models", [])
        target = None
        for m in models:
            if m.get("name") == name:
                target = m
                break
        if target is None:
            raise ValueError(f"模型 '{name}' 不存在")
        for k in ("base_url", "model", "api_key", "temperature", "max_tokens", "retry_count"):
            if k in data:
                target[k] = data[k]
        # 更新后清理旧的 api_key_env，统一为 api_key 明文
        target.pop("api_key_env", None)
        self._save(raw)
        return target

    def delete(self, name: str) -> None:
        raw = self._load()
        models = raw.get("models", [])
        if len(models) <= 1:
            raise ValueError("至少保留一个模型，不允许删除最后一个模型")
        if not any(m.get("name") == name for m in models):
            raise ValueError(f"模型 '{name}' 不存在")
        raw["models"] = [m for m in models if m.get("name") != name]
        self._save(raw)

    def set_active_model(self, name: str) -> None:
        """持久化 active_model 到 config.yaml 顶层字段。

        校验模型存在性；同时清理已删除模型残留的 active_model。
        """
        raw = self._load()
        models = raw.get("models", [])
        if not any(m.get("name") == name for m in models):
            raise ValueError(f"模型 '{name}' 不存在")
        raw["active_model"] = name
        self._save(raw)
