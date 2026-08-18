"""待确认候选队列：持久化 pending.json。

本模块为同步写 + 原子替换，无 await 间隙，事件循环内天然串行，不需要锁。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class PendingItem:
    id: str
    action: Literal["fix", "create"]
    skill_name: str
    reason: str
    content: str
    created_at: str
    status: str = "pending"  # pending | confirmed | rejected


class PendingQueue:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, PendingItem] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005

    async def load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._items = {i["id"]: PendingItem(**i) for i in data}
        except Exception as e:  # noqa: BLE001
            logger.warning("待确认队列加载失败，用空队列继续：%s", e)

    async def _save(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps([asdict(i) for i in self._items.values()],
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    async def enqueue(self, action: str, skill_name: str, reason: str, content: str) -> PendingItem:
        item = PendingItem(
            id=f"evo-{uuid.uuid4().hex[:8]}",
            action=action, skill_name=skill_name,
            reason=reason, content=content, created_at=self._now(),
        )
        self._items[item.id] = item
        await self._save()
        return item

    def get(self, item_id: str) -> PendingItem | None:
        return self._items.get(item_id)

    def list(self, status: str = "pending") -> list[PendingItem]:
        return [i for i in self._items.values() if i.status == status]

    async def mark_status(self, item_id: str, status: str) -> PendingItem | None:
        item = self._items.get(item_id)
        if item is None:
            return None
        item.status = status
        await self._save()
        return item

    def load_sync(self) -> None:
        asyncio.run(self.load())
