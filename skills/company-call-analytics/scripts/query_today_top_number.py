#!/usr/bin/env python3
"""Return the phone number(s) with the most completed calls for a company/date."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path


QUERY = """
WITH call_counts AS (
    SELECT
        c.name AS company,
        p.number AS phone_number,
        p.label AS label,
        COUNT(*) AS call_count
    FROM call_records AS r
    JOIN companies AS c ON c.id = r.company_id
    JOIN phone_numbers AS p
      ON p.id = r.phone_number_id AND p.company_id = r.company_id
    WHERE c.name = ?
      AND substr(r.started_at, 1, 10) = ?
      AND r.status = 'completed'
    GROUP BY c.id, c.name, p.id, p.number, p.label
), ranked AS (
    SELECT
        company,
        phone_number,
        label,
        call_count,
        DENSE_RANK() OVER (ORDER BY call_count DESC) AS ranking
    FROM call_counts
)
SELECT company, phone_number, label, call_count
FROM ranked
WHERE ranking = 1
ORDER BY phone_number;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="查询企业在指定日期通话次数最多的号码"
    )
    parser.add_argument("--db", required=True, type=Path, help="SQLite 数据库路径")
    parser.add_argument("--company", required=True, help="企业名称（精确匹配）")
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="业务日期，格式 YYYY-MM-DD；默认使用本机日期",
    )
    return parser.parse_args()


def validate_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("--date 必须是 YYYY-MM-DD 格式") from exc


def query_top_numbers(db_path: Path, company: str, business_date: str) -> dict:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(QUERY, (company, business_date)).fetchall()
        company_exists = connection.execute(
            "SELECT 1 FROM companies WHERE name = ? LIMIT 1", (company,)
        ).fetchone()

    if not company_exists:
        raise LookupError(f"未找到企业：{company}")

    return {
        "company": company,
        "date": business_date,
        "metric": "completed_call_count",
        "results": [
            {
                "phone_number": phone_number,
                "label": label,
                "call_count": call_count,
            }
            for _, phone_number, label, call_count in rows
        ],
    }


def main() -> int:
    args = parse_args()
    try:
        business_date = validate_date(args.date)
        payload = query_top_numbers(args.db, args.company, business_date)
    except (OSError, sqlite3.Error, LookupError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
