"""JSON 文件存储实现。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from open_fox.core.storage.base import Storage

# session_id 白名单：仅允许字母数字与 ._-，防止 ../ 路径穿越越界写文件
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class JsonStorage(Storage):
    """每个会话保存为 <base_dir>/<session_id>.json。

    session_id 中的 .json 后缀会被自动去除，避免重复。
    """

    def __init__(self, base_dir: str | Path):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        sid = session_id[:-5] if session_id.endswith(".json") else session_id
        # 白名单过滤：非法字符（如 ../）直接抛错，防止路径穿越越界写文件
        if not _SAFE_ID.match(sid) or sid in (".", ".."):
            raise ValueError(f"非法 session_id: {session_id!r}")
        return self._base / f"{sid}.json"

    def save(self, session_id: str, messages: list[dict]) -> None:
        self._path(session_id).write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, session_id: str) -> list[dict] | None:
        p = self._path(session_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def list_ids(self) -> list[str]:
        return [p.stem for p in self._base.glob("*.json")]

    def delete(self, session_id: str) -> None:
        p = self._path(session_id)
        if p.exists():
            p.unlink()