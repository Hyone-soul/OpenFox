"""MySQL 存储实现（可选）。

依赖 SQLAlchemy + PyMySQL（`pip install -e ".[mysql]"`）。
若未安装依赖，import 时将抛 ImportError 由上层处理。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from open_fox.core.storage.base import Storage

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class MysqlStorage(Storage):
    """基于 MySQL 的会话存储，使用单表 sessions(id, messages)。"""

    def __init__(self, url: str):
        try:
            from sqlalchemy import create_engine
        except ImportError as e:
            raise ImportError(
                "请先安装 MySQL 依赖：pip install -e \".[mysql]\""
            ) from e
        self._engine: Engine = create_engine(url)
        self._ensure_table()

    def _ensure_table(self) -> None:
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "  id VARCHAR(64) PRIMARY KEY,"
                "  messages JSON NOT NULL"
                ")"
            ))

    def save(self, session_id: str, messages: list[dict]) -> None:
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "REPLACE INTO sessions (id, messages) VALUES (:id, :msgs)"
                ),
                {"id": session_id, "msgs": json.dumps(messages, ensure_ascii=False)},
            )

    def load(self, session_id: str) -> list[dict] | None:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT messages FROM sessions WHERE id = :id"),
                {"id": session_id},
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list_ids(self) -> list[str]:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            rows = conn.execute(text("SELECT id FROM sessions")).fetchall()
        return [r[0] for r in rows]

    def delete(self, session_id: str) -> None:
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sessions WHERE id = :id"),
                {"id": session_id},
            )