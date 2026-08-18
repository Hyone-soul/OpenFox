"""会话状态：消息列表、当前模型、可选持久化。"""

from __future__ import annotations

from open_fox.core.storage.base import Storage


class Session:
    """单个会话的状态。"""

    def __init__(
        self,
        session_id: str,
        storage: Storage | None = None,
        active_model: str = "",
    ):
        self.session_id = session_id
        self._storage = storage
        self.active_model = active_model
        self._messages: list[dict] = []

    def add_message(self, role: str, content: str, **extra) -> None:
        msg = {"role": role, "content": content, **extra}
        self._messages.append(msg)

    def add_raw(self, message: dict) -> None:
        """追加已构造好的消息（用于 tool_calls 等复杂结构）。"""
        self._messages.append(dict(message))

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def set_messages(self, messages: list[dict]) -> None:
        self._messages = [dict(m) for m in messages]

    def save(self) -> None:
        if self._storage:
            self._storage.save(self.session_id, self._messages)

    def load(self) -> None:
        if self._storage:
            msgs = self._storage.load(self.session_id)
            if msgs is not None:
                self._messages = msgs

    _META_ROLE = "__meta__"

    def set_meta(self, **kwargs) -> None:
        """写入/更新会话元数据（存于消息首部 __meta__ 消息）。"""
        for m in self._messages:
            if m.get("role") == self._META_ROLE:
                m.update(kwargs)
                return
        self._messages.insert(0, {"role": self._META_ROLE, **kwargs})

    def get_meta(self) -> dict:
        for m in self._messages:
            if m.get("role") == self._META_ROLE:
                return {k: v for k, v in m.items() if k != "role"}
        return {}

    def chat_messages(self) -> list[dict]:
        """返回发给 LLM 的消息（过滤掉 __meta__）。"""
        return [m for m in self._messages if m.get("role") != self._META_ROLE]