"""存储抽象接口。

所有存储后端必须实现 save / load / list_ids / delete。
消息以可序列化的 dict 列表形式保存，便于 JSON / MySQL 通用。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Storage(ABC):
    """会话持久化抽象接口。"""

    @abstractmethod
    def save(self, session_id: str, messages: list[dict]) -> None:
        """保存会话消息。已存在的会话将被覆盖。"""

    @abstractmethod
    def load(self, session_id: str) -> list[dict] | None:
        """加载会话消息，不存在则返回 None。"""

    @abstractmethod
    def list_ids(self) -> list[str]:
        """返回所有已知会话 ID。"""

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """删除会话，幂等。"""