"""
用法：python scripts/migrate_mcp_config.py [--config config.yaml] [--out mcps/]
读 config.yaml 的 mcp_servers 段，按 server name 分文件写到 mcps/<name>.yaml。
迁移后用户自行删除 config.yaml 的 mcp_servers 段。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HEADER = """\
# 由 migrate_mcp_config.py 自动生成
# 迁移后请手动删除原 config.yaml 的 mcp_servers 段
# 提示：headers 里的 ${VAR} 占位符会在运行时替换
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 config.yaml 的 mcp_servers 到 mcps/ 目录")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default="mcps/")
    args = parser.parse_args()

    config_path = Path(args.config)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        print(f"未找到配置文件：{config_path}", file=sys.stderr)
        return 1

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    servers = raw.get("mcp_servers", [])
    if not servers:
        print("config.yaml 中未找到 mcp_servers 段，无可迁移项。")
        return 0

    written, skipped, failed = [], [], []
    for s in servers:
        name = s.get("name")
        if not name:
            failed.append({"source": str(s), "error": "缺少 name"})
            continue
        out_file = out_dir / f"{name}.yaml"
        if out_file.exists():
            skipped.append(str(out_file))
            continue
        try:
            content = {
                "name": name,
                "transport": s["transport"],
                "enabled": True,
                "timeout": 30,
                "tool_allowlist": [],
                "tool_denylist": [],
                "permissions": {},
                **({"command": s["command"]} if "command" in s else {}),
                **({"args": s["args"]} if "args" in s else {}),
                **({"url": s["url"]} if "url" in s else {}),
                **({"headers": s["headers"]} if "headers" in s else {}),
            }
            out_file.write_text(
                HEADER + yaml.safe_dump(content, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            written.append(str(out_file))
        except Exception as e:  # noqa: BLE001 - CLI 宽容捕获，统一记入 failed 报告
            failed.append({"source": str(s), "error": str(e)})

    print(f"已生成：{len(written)}")
    for w in written:
        print(f"  + {w}")
    if skipped:
        print(f"已存在跳过：{len(skipped)}")
        for s in skipped:
            print(f"  = {s}")
    if failed:
        print(f"失败：{len(failed)}")
        for f in failed:
            print(f"  ! {f['source']}: {f['error']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())