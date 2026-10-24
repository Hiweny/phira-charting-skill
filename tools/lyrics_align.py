#!/usr/bin/env python3
"""歌词时间轴 → beat 三元组（为 RPE 谱面提供落点表）。

把 LRC / 纯时间行转成"第几句、第几秒、第几拍、几个字、建议落点数"，
直接可以拿去排 note。

用法：
    # 最简单：固定 BPM
    python3 tools/lyrics_align.py lyrics.lrc --bpm 140 --offset 0

    # 读谱面的 BPMList（支持变速），并输出 JSON 给后续脚本用
    python3 tools/lyrics_align.py lyrics.lrc --chart my-chart/chart.json -o lyrics.json

    # 从 SRT 转（只需要每条的起始时间与文字）
    python3 tools/lyrics_align.py subs.srt --bpm 140

支持格式：
    LRC   [01:23.45] 文本
    LRC   [01:23.45][02:10.00] 文本      （多时间戳，取第一个）
    SRT   00:01:23,450 --> 00:01:26,000 （取每块的第一行时间与文本）

输出列：
    #   time(s)   beat      chars  notes   text
    notes = ceil(chars / 3)，即"2~3 个字取一个落点"的经验值。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

LRC_RE = re.compile(r"\[(\d{1,3}):(\d{1,2}(?:[.:]\d{1,3})?)\]")
SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _parse_lrc(text: str) -> List[Tuple[float, str]]:
    out: List[Tuple[float, str]] = []
    for line in text.splitlines():
        stamps = LRC_RE.findall(line)
        if not stamps:
            continue
        body = LRC_RE.sub("", line).strip()
        if not body:
            continue
        mm, ss = stamps[0]
        sec = int(mm) * 60 + float(ss.replace(":", "."))
        out.append((sec, body))
    return sorted(out)


def _parse_srt(text: str) -> List[Tuple[float, str]]:
    out: List[Tuple[float, str]] = []
    blocks = re.split(r"\r?\n\r?\n", text.strip())
    for b in blocks:
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        tline = next((ln for ln in lines if "-->" in ln), None)
        if not tline:
            continue
        m = SRT_TIME_RE.search(tline)
        if not m:
            continue
        h, mi, s, ms = m.group(1), m.group(2), m.group(3), m.group(4)
        start = int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0
        idx = lines.index(tline)
        body = " ".join(lines[idx + 1 :])
        if body:
            out.append((start, body))
    return sorted(out)


def _load_bpm_list(chart_path: str) -> Tuple[List[Tuple[float, float]], float]:
    """返回 [(开始秒, bpm)] 与谱面 offset（秒）。"""
    d = json.loads(Path(chart_path).read_text(encoding="utf-8"))
    offset_ms = 0
    if isinstance(d.get("offset"), (int, float)):
        offset_ms = d["offset"]
    elif isinstance(d.get("META", {}).get("offset"), (int, float)):
        offset_ms = d["META"]["offset"]
    offset = float(offset_ms) / 1000.0

    def triple_to_beat(t) -> float:
        if isinstance(t, (int, float)):
            return float(t)
        w, n, den = (list(t) + [0, 0, 1])[:3]
        return float(w) + (float(n) / float(den) if den else 0.0)

    bpm_list = d.get("BPMList") or d.get("bpmList") or []
    rows: List[Tuple[float, float]] = []
    for item in bpm_list:
        beat = triple_to_beat(item.get("startTime", [0, 0, 1]))
        rows.append((beat, float(item["bpm"])))
    if not rows:
        rows = [(0.0, 120.0)]
    # beat -> 秒 的积分起点
    acc = 0.0
    sec_rows: List[Tuple[float, float]] = []
    prev_beat, prev_bpm = rows[0][0], rows[0][1]
    start_sec = offset  # 第 0 拍在音频里的时间
    for beat, bpm in rows:
        acc += (beat - prev_beat) * 60.0 / prev_bpm
        sec_rows.append((start_sec + acc, bpm))
        prev_beat, prev_bpm = beat, bpm
    return sec_rows, offset


def _sec_to_beat(t: float, sec_rows: List[Tuple[float, float]]) -> float:
    beat = 0.0
    for i, (s0, bpm) in enumerate(sec_rows):
        s1 = sec_rows[i + 1][0] if i + 1 < len(sec_rows) else float("inf")
        if t >= s0:
            beat += (min(t, s1) - s0) * bpm / 60.0
            if t < s1:
                return beat
        else:
            break
    return beat


def main() -> int:
    ap = argparse.ArgumentParser(description="歌词时间轴 → beat 落点表")
    ap.add_argument("lyrics", help=".lrc 或 .srt 文件")
    ap.add_argument("--bpm", type=float, default=120.0, help="固定 BPM（未给 --chart 时生效）")
    ap.add_argument("--offset", type=float, default=0.0, help="谱面 offset（秒）")
    ap.add_argument("--chart", help="从 chart.json 读取 BPMList 与 offset（支持变速）")
    ap.add_argument("--chars-per-note", type=float, default=3.0, help="每几个字取一个落点（默认 3）")
    ap.add_argument("-o", "--json", help="同时输出 JSON")
    args = ap.parse_args()

    path = Path(args.lyrics)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    rows = _parse_srt(raw) if path.suffix.lower() == ".srt" else _parse_lrc(raw)
    if not rows:
        print("没有解析到任何带时间戳的歌词行。", file=sys.stderr)
        return 1

    if args.chart:
        sec_rows, offset = _load_bpm_list(args.chart)
        fixed_bpm = None
    else:
        sec_rows, offset = [(args.offset, args.bpm)], args.offset
        fixed_bpm = args.bpm

    table = []
    print(f"{'#':>3}  {'time':>8}  {'beat':>8}  {'chars':>5}  {'notes':>5}  text")
    for i, (t, body) in enumerate(rows, 1):
        beat = _sec_to_beat(t, sec_rows) if fixed_bpm is None else (t - offset) * fixed_bpm / 60.0
        chars = len(re.sub(r"\s+", "", body))
        notes = max(1, math.ceil(chars / max(0.5, args.chars_per_note)))
        table.append({"i": i, "time": round(t, 3), "beat": round(beat, 3),
                      "chars": chars, "notes": notes, "text": body})
        print(f"{i:>3}  {t:>8.2f}  {beat:>8.2f}  {chars:>5}  {notes:>5}  {body}")

    if args.json:
        payload = {"source": str(path), "bpm_mode": "chart" if args.chart else "fixed",
                   "offset": offset, "chars_per_note": args.chars_per_note, "lines": table}
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
