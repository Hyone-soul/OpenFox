"""内存存储实现（默认后端）。"""

from __future__ import annotations

from open_fox.core.storage.base import Storage


class MemoryStorage(Storage):
    """基于内存字典的会话存储，进程重启即清空。"""

    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    def save(self, session_id: str, messages: list[dict]) -> None:
        # 深拷贝以避免外部修改影响存储
        self._store[session_id] = [dict(m) for m in messages]

    def load(self, session_id: str) -> list[dict] | None:
        msgs = self._store.get(session_id)
        return [dict(m) for m in msgs] if msgs is not None else None

    def list_ids(self) -> list[str]:
        return list(self._store.keys())

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)