#!/usr/bin/env bash
# 打包 Phira 谱面工程为可导入的 zip（扁平结构）
#
# 用法：
#   bash tools/package_chart.sh <工程目录> [--skip-validate]
#
# 例：
#   bash tools/package_chart.sh examples/minimal
#   → examples/minimal.zip

set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  echo "用法: bash tools/package_chart.sh <工程目录> [--skip-validate]" >&2
  exit 2
fi

DIR="${DIR%/}"
if [[ ! -d "$DIR" ]]; then
  echo "目录不存在: $DIR" >&2
  exit 2
fi

if [[ ! -f "$DIR/info.yml" ]]; then
  echo "缺少 info.yml（必须在工程根目录）: $DIR" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${2:-}" != "--skip-validate" ]]; then
  echo "[1/2] 校验中..."
  if ! python3 "$SCRIPT_DIR/validate_chart.py" "$DIR"; then
    echo "" >&2
    echo "校验未通过，已中止打包。修完再试，或加 --skip-validate 强制打包。" >&2
    exit 1
  fi
else
  echo "[1/2] 跳过校验"
fi

PARENT="$(cd "$DIR/.." && pwd)"
NAME="$(basename "$DIR")"
OUT="$PARENT/$NAME.zip"
rm -f "$OUT"

echo "[2/2] 打包 → $OUT"
(
  cd "$DIR"
  zip -r -q "$OUT" . \
    -x '.*' \
    -x '__MACOSX/*' \
    -x '*.DS_Store' \
    -x 'README*' \
    -x '*.zip'
)

echo "[ok] 完成：$OUT"
echo "     把 zip 传到 Phira 即可导入。"
