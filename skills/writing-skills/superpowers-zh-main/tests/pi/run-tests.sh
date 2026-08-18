#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 扩展是 TypeScript（仅 `import type`，运行时无类型依赖）。Node 22.6–23.5
# 需要 --experimental-strip-types 才能 import .ts；23.6+ 默认开启，该 flag 仍兼容。
node --experimental-strip-types "$SCRIPT_DIR/test-pi-extension.mjs"
