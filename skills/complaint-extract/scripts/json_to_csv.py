# -*- coding: utf-8 -*-
"""把 complaint-extract 的抽取结果 JSON 转成 CSV。

输入 JSON 可以是单个对象或对象数组，字段固定为：
投诉人姓名、投诉人联系方式、投诉事由、处理诉求。

用法：
    python skills/complaint-extract/scripts/json_to_csv.py <input.json> <output.csv>

编码用 utf-8-sig（带 BOM），保证 Excel 直接打开中文不乱码。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

FIELDS = ["投诉人姓名", "投诉人联系方式", "投诉事由", "处理诉求"]


def main() -> int:
    if len(sys.argv) != 3:
        print("用法: python json_to_csv.py <input.json> <output.csv>")
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    if not in_path.exists():
        print(f"错误：输入文件不存在 {in_path}")
        return 1

    try:
        data = json.loads(in_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误：JSON 解析失败（文件里只能有纯 JSON，不能包 Markdown 代码块）：{e}")
        return 1

    records = data if isinstance(data, list) else [data]
    if not records:
        print("错误：JSON 数组为空")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序号"] + FIELDS)
        for i, rec in enumerate(records, start=1):
            if not isinstance(rec, dict):
                print(f"警告：第 {i} 条不是对象，已跳过")
                continue
            writer.writerow([i] + [str(rec.get(k, "")).strip() for k in FIELDS])

    print(f"已生成 {out_path}，共 {len(records)} 条记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
