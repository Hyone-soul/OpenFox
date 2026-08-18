# src/open_fox/usage_store.py
"""用量存储：按月 JSON 文件持久化每次对话的 token 消耗。

文件路径：data/usage/<username>/YYYY-MM.json
每条记录包含：时间、模型、prompt/completion/total token、缓存命中、推理 token 等。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class UsageStore:
    def __init__(self, base_dir: str | Path = "./data/usage"):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    # ---- 内部路径 ----
    def _user_dir(self, username: str) -> Path:
        d = self._base / username
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _month_path(self, username: str, year: int, month: int) -> Path:
        return self._user_dir(username) / f"{year:04d}-{month:02d}.json"

    # ---- 写入 ----
    def record(
        self,
        username: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cache_hit_tokens: int = 0,
        reasoning_tokens: int = 0,
        session_id: str = "",
        agent_id: str = "",
        request_count: int = 1,
    ) -> dict:
        """追加一条用量记录，返回记录 dict。"""
        now = datetime.now(timezone.utc)
        entry = {
            "id": uuid.uuid4().hex[:12],
            "username": username,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cache_hit_tokens": cache_hit_tokens,
            "reasoning_tokens": reasoning_tokens,
            "session_id": session_id,
            "agent_id": agent_id,
            "request_count": request_count,
            "created_at": now.isoformat(),
        }

        path = self._month_path(username, now.year, now.month)
        records = []
        if path.exists():
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                records = []
        records.append(entry)
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return entry

    # ---- 读取 ----
    def _load_month(self, username: str, year: int, month: int) -> list[dict]:
        path = self._month_path(username, year, month)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def list_records(
        self,
        username: str,
        start_date: str = "",   # YYYY-MM-DD
        end_date: str = "",     # YYYY-MM-DD
        model: str = "",
        agent_id: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """按条件查询用量记录，返回 (records, total_count)。"""
        # 确定需要扫描的月份范围
        months: list[tuple[int, int]] = []
        if start_date and end_date:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            y, m = sd.year, sd.month
            ey, em = ed.year, ed.month
            while (y, m) <= (ey, em):
                months.append((y, m))
                m += 1
                if m > 12:
                    m = 1
                    y += 1
        else:
            # 默认查最近 3 个月
            now = datetime.now(timezone.utc)
            for i in range(3):
                d = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
                if i > 0:
                    # 回退 i 个月
                    y2, m2 = now.year, now.month
                    for _ in range(i):
                        m2 -= 1
                        if m2 == 0:
                            m2 = 12
                            y2 -= 1
                    months.append((y2, m2))
                else:
                    months.append((y2 := now.year, m2 := now.month))
            # 去重并排序
            months = sorted(set(months))

        all_records: list[dict] = []
        for y, m in months:
            all_records.extend(self._load_month(username, y, m))

        # 过滤
        filtered = all_records
        if start_date:
            filtered = [r for r in filtered if r.get("created_at", "")[:10] >= start_date]
        if end_date:
            filtered = [r for r in filtered if r.get("created_at", "")[:10] <= end_date]
        if model:
            filtered = [r for r in filtered if r.get("model") == model]
        if agent_id:
            filtered = [r for r in filtered if r.get("agent_id") == agent_id]

        # 按时间倒序
        filtered.sort(key=lambda r: r.get("created_at", ""), reverse=True)

        total = len(filtered)
        page = filtered[offset: offset + limit]
        return page, total

    def get_summary(
        self,
        username: str,
        start_date: str = "",
        end_date: str = "",
    ) -> dict:
        """汇总统计：总量、按模型分组、按日期分组。"""
        records, _ = self.list_records(
            username, start_date, end_date, limit=99999,
        )

        total_prompt = 0
        total_completion = 0
        total_tokens = 0
        total_cache_hit = 0
        total_reasoning = 0
        total_requests = 0

        by_model: dict[str, dict] = {}
        by_date: dict[str, dict] = {}

        for r in records:
            pt = r.get("prompt_tokens", 0)
            ct = r.get("completion_tokens", 0)
            tt = r.get("total_tokens", 0)
            ch = r.get("cache_hit_tokens", 0)
            rt = r.get("reasoning_tokens", 0)
            rc = r.get("request_count", 1)

            total_prompt += pt
            total_completion += ct
            total_tokens += tt
            total_cache_hit += ch
            total_reasoning += rt
            total_requests += rc

            # 按模型
            m = r.get("model", "unknown")
            if m not in by_model:
                by_model[m] = {"prompt_tokens": 0, "completion_tokens": 0,
                               "total_tokens": 0, "request_count": 0}
            by_model[m]["prompt_tokens"] += pt
            by_model[m]["completion_tokens"] += ct
            by_model[m]["total_tokens"] += tt
            by_model[m]["request_count"] += rc

            # 按日期
            d = r.get("created_at", "")[:10]
            if d not in by_date:
                by_date[d] = {"prompt_tokens": 0, "completion_tokens": 0,
                              "total_tokens": 0, "request_count": 0}
            by_date[d]["prompt_tokens"] += pt
            by_date[d]["completion_tokens"] += ct
            by_date[d]["total_tokens"] += tt
            by_date[d]["request_count"] += rc

        return {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_cache_hit_tokens": total_cache_hit,
            "total_reasoning_tokens": total_reasoning,
            "total_requests": total_requests,
            "by_model": by_model,
            "by_date": by_date,
        }
