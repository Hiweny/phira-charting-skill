#!/usr/bin/env python3
"""谱面横向基准统计：一次算出一张谱的"体检表"，用于对比与拆解精品谱。

用法：
    python3 tools/chart_stats.py <谱面目录或 json> [--json]
    python3 tools/chart_stats.py samples/*            # 批量出 Markdown 表格

输出指标设计原则：每一项都要能回答一个"作者在为什么花时间"的问题。
    lines          -> 舞台规模
    tex_lines      -> 有多少精力花在美术上
    shaders        -> 有多少精力花在特效上
    kp             -> 事件总量（编排密度）
    kp_per_note    -> 每个音符背后的演出量（"这是动画还是谱面"）
    nps / peak_nps -> 演奏强度
    hold/flick     -> 手感构成
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

NOTE_TYPES = {1: "tap", 2: "drag", 3: "hold", 4: "flick"}


def find_chart(path: str) -> str:
    if os.path.isfile(path):
        return path
    cands = []
    for f in os.listdir(path):
        if f.lower().endswith(".json") and f.lower() not in ("extra.json", "info.json"):
            cands.append(os.path.join(path, f))
    if not cands:
        raise SystemExit(f"没找到谱面 json: {path}")
    # 优先文件名是纯数字的（RPE 惯例）
    cands.sort(key=lambda p: (not os.path.basename(p).split(".")[0].isdigit(),
                              -os.path.getsize(p)))
    return cands[0]


def count_events(events) -> int:
    if not isinstance(events, list):
        return 0
    return sum(1 for e in events if isinstance(e, dict))


def bpm_segments(data: dict) -> list[tuple[float, float]]:
    """读取 BPM 分段：RPE 用 `BPMList`，少数谱用 `bpmList`。返回 [(起始拍, bpm)]。"""
    lst = data.get("BPMList") or data.get("bpmList") or []
    segs: list[tuple[float, float]] = []
    for it in lst:
        if not isinstance(it, dict):
            continue
        st = it.get("startTime") or [0, 0, 1]
        beat = st[0] + st[1] / (st[2] if len(st) > 2 and st[2] else 1)
        segs.append((float(beat), float(it.get("bpm") or 120.0)))
    segs.sort()
    return segs or [(0.0, 120.0)]


def beat_to_sec(beat: float, segs: list[tuple[float, float]]) -> float:
    """把拍号换算成秒。变速曲按分段累加，别用单一 BPM 硬除。"""
    if beat <= segs[0][0]:
        return (beat - segs[0][0]) * 60.0 / segs[0][1]
    sec = 0.0
    for i, (b, bpm) in enumerate(segs):
        nxt = segs[i + 1][0] if i + 1 < len(segs) else float("inf")
        if beat <= b:
            break
        span = min(beat, nxt) - b
        sec += span * 60.0 / bpm
    return sec


def analyze(path: str) -> dict:
    chart_path = find_chart(path)
    with open(chart_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    lines = data.get("judgeLineList") or []
    fmt = "RPE"
    if not lines:
        fmt = "PEC/PGR"
        raise SystemExit(f"{chart_path}: 目前只支持 RPE(JSON) 格式")

    notes = Counter()
    nps_bins = Counter()
    x_min, x_max = 1e9, -1e9
    y_min, y_max = 1e9, -1e9
    all_t = []
    kp = 0
    chan = Counter()
    tex = set()
    tex_lines = 0
    rot_lines = 0
    incline_lines = 0
    layers_total = 0
    speed_events = 0

    for ln in lines:
        texname = (ln.get("Texture") or "").strip()
        if texname and texname != "line.png":
            tex.add(texname)
            tex_lines += 1
        for ns in (ln.get("notes") or []):
            t = ns.get("type")
            notes[NOTE_TYPES.get(t, f"t{t}")] += 1
            st = ns.get("startTime")
            if isinstance(st, dict):
                beat = st.get("beat", [0, 0, 1])
            else:  # 少数谱把 startTime 直接写成 beat 数组
                beat = st if isinstance(st, list) else [0, 0, 1]
            all_t.append(beat if (beat and len(beat) >= 2) else [0, 0, 1])
            x = ns.get("positionX", 0)
            x_min, x_max = min(x_min, x), max(x_max, x)

        for ly in (ln.get("eventLayers") or []):
            if not isinstance(ly, dict):
                continue
            layers_total += 1
            for k, v in ly.items():
                if not isinstance(v, list):
                    continue
                n = count_events(v)
                if not n:
                    continue
                kp += n
                chan[k] += n
                if k == "rotateEvents" and any(
                        abs(e.get("start", 0)) > 1e-3 or abs(e.get("end", 0)) > 1e-3
                        for e in v if isinstance(e, dict)):
                    rot_lines += 1
        ex = ln.get("extended") or {}
        if any(abs(e.get("start", 0)) > 1e-3 or abs(e.get("end", 0)) > 1e-3
               for e in (ex.get("inclineEvents") or []) if isinstance(e, dict)):
            incline_lines += 1
        speed_events += count_events(ln.get("speedEvents"))

    total_notes = sum(notes.values())
    segs = bpm_segments(data)
    # 关键：拍号 → 秒。直接拿 beat 当秒会让 NPS 和峰值翻倍
    seconds = [beat_to_sec(b[0] + (b[1] / b[2] if len(b) > 2 and b[2] else 0), segs)
               for b in all_t]
    dur = (max(seconds) - min(seconds)) if seconds else 0.0
    # 峰值 NPS：1 秒滑动窗口
    peak = 0
    if seconds:
        s = sorted(seconds)
        j = 0
        for i in range(len(s)):
            while s[i] - s[j] > 1.0:
                j += 1
            peak = max(peak, i - j + 1)

    # 音乐时长：优先 ffprobe（mutagen 对部分 mp3 会读出约 2 倍时长）
    audio = 0.0
    for f in os.listdir(os.path.dirname(chart_path) or "."):
        if f.lower().endswith((".ogg", ".mp3", ".wav")):
            ap = os.path.join(os.path.dirname(chart_path), f)
            try:
                import subprocess
                out = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", ap],
                    capture_output=True, text=True, timeout=20).stdout.strip()
                audio = float(out)
            except Exception:
                audio = 0.0
            if not audio:
                try:
                    from mutagen import File as MFile  # 兜底
                    audio = MFile(ap).info.length
                except Exception:
                    audio = 0.0
            break

    off = data.get("offset", 0)
    return {
        "name": os.path.basename(os.path.dirname(chart_path)) or os.path.basename(chart_path),
        "format": fmt,
        "seconds": round(audio or dur, 1),
        "lines": len(lines),
        "tex_lines": tex_lines,
        "textures": len(tex),
        "shaders": len(data.get("effectObjects") or []) or sum(
            1 for f in os.listdir(os.path.dirname(chart_path) or ".")
            if f.lower().endswith(".glsl")),
        "notes": total_notes,
        "tap": notes["tap"], "drag": notes["drag"],
        "hold": notes["hold"], "flick": notes["flick"],
        "nps": round(total_notes / dur, 2) if dur else 0,
        "peak_nps": peak,
        "x_span": [round(x_min, 0), round(x_max, 0)] if total_notes else [0, 0],
        "kp": kp,
        "kp_per_s": round(kp / (audio or dur), 1) if (audio or dur) else 0,
        "kp_per_note": round(kp / total_notes, 1) if total_notes else 0,
        "layers": layers_total,
        "rot_lines": rot_lines,
        "incline_lines": incline_lines,
        "speed_events": speed_events,
        "hold_ratio": round(notes["hold"] / total_notes, 2) if total_notes else 0,
        "offset": off,
        "channels": dict(chan.most_common(6)),
    }


def fmt_table(rows: list[dict]) -> str:
    cols = [("name", "谱面"), ("seconds", "时长s"), ("lines", "判定线"),
            ("tex_lines", "非默认贴图线"), ("textures", "贴图"), ("shaders", "shader"),
            ("notes", "音符"), ("nps", "均NPS"), ("peak_nps", "峰NPS"),
            ("hold_ratio", "Hold%"), ("kp", "事件帧"), ("kp_per_s", "帧/秒"),
            ("kp_per_note", "帧/音符"), ("rot_lines", "旋转线"),
            ("incline_lines", "3D线")]
    out = ["| " + " | ".join(c[1] for c in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c[0], "")) for c in cols) + " |")
    return "\n".join(out)


def timeline(path: str, step: float = 10.0) -> str:
    """按时间分桶的事件密度，用于识别"平均指标骗人"的情况。"""
    chart_path = find_chart(path)
    with open(chart_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    segs = bpm_segments(data)
    buckets: Counter = Counter()
    for ln in (data.get("judgeLineList") or []):
        for ly in (ln.get("eventLayers") or []):
            if not isinstance(ly, dict):
                continue
            for v in ly.values():
                if not isinstance(v, list):
                    continue
                for e in v:
                    st = e.get("startTime") if isinstance(e, dict) else None
                    if not isinstance(st, list) or len(st) < 2:
                        continue
                    beat = st[0] + st[1] / (st[2] if len(st) > 2 and st[2] else 1)
                    t = beat_to_sec(beat, segs)
                    buckets[int(t // step) * int(step)] += 1
    if not buckets:
        return "（无事件）"
    peak = max(buckets.values())
    lines_out = [f"{'起(s)':>6} {'帧数':>6}  密度"]
    for b in sorted(buckets):
        n = buckets[b]
        bar = "█" * max(1, round(n / peak * 40))
        lines_out.append(f"{b:>6} {n:>6}  {bar}")
    return "\n".join(lines_out)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if "--timeline" in sys.argv:
        for a in args:
            print(f"## {a}\n{timeline(a)}")
        return
    rows = []
    for a in args:
        try:
            rows.append(analyze(a))
        except SystemExit as e:
            print(f"! {a}: {e}", file=sys.stderr)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(fmt_table(rows))


if __name__ == "__main__":
    main()
