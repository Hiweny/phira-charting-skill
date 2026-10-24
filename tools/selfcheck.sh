#!/usr/bin/env bash
# Phira 谱面一键自检：结构校验 + 量化统计 + 视觉联系表
#
#   ./tools/selfcheck.sh <工程目录或 zip> [输出目录]
#
# 产出（默认 _selfcheck/<工程名>/）：
#   validate.txt      结构校验结果（退出码非 0 会中止）
#   stats.json        量化指标
#   contact_sheet.png 12 帧联系表（先看这张判断舞台是否成立）
#   summary.md        汇总报告
set -euo pipefail

CHART="${1:?用法: selfcheck.sh <工程目录或 zip> [输出目录]}"
NAME="$(basename "${CHART%/}")"
NAME="${NAME%.zip}"
OUT="${2:-_selfcheck/$NAME}"
mkdir -p "$OUT"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== L1 结构校验 =="
if python3 "$ROOT/tools/validate_chart.py" "$CHART" | tee "$OUT/validate.txt"; then
  :
else
  echo "校验失败，先修格式再谈视觉。" >&2
  exit 1
fi

echo "== L2 量化统计 =="
python3 "$ROOT/tools/preview_render.py" "$CHART" --stats > "$OUT/stats.json"
python3 - "$OUT/stats.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print(f"时长 {d['duration']}s | 线 {d['lines']} | 音符 {d['notes']} | 平均 NPS {d['avg_nps']} | 峰值 {d['peak_nps_1s']}")
print(f"X 覆盖 {d['x_range']} | 线 X 覆盖 {d['line_x_cover']}")
print(f"隐藏音符 {d['hidden_notes']} | 命中越界 {d['offscreen_hit_notes']} | 提前可见率 {d['approach_visible_ratio']}")
PY

echo "== L2.5 视觉联系表 =="
python3 "$ROOT/tools/preview_render.py" "$CHART" --contact-sheet "$OUT/contact_sheet.png"

{
  echo "# 自检报告：$NAME"
  echo
  echo "## 结构校验"
  echo '```'
  cat "$OUT/validate.txt"
  echo '```'
  echo
  echo "## 量化指标"
  echo '```json'
  cat "$OUT/stats.json"
  echo '```'
  echo
  echo "## 视觉联系表"
  echo "![contact sheet](contact_sheet.png)"
  echo
  echo "> 逐帧检查：音符下落方向是否一致、有没有黏线/闪现、判定线是否覆盖全屏、高潮段是否明显更密。"
} > "$OUT/summary.md"

echo
echo "完成：$OUT/summary.md"
