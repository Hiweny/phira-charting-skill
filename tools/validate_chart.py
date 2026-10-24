#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_chart.py — Phira / RPE 谱面校验器

用法：
    python3 tools/validate_chart.py <工程目录 | chart.json | *.zip> [--report]

退出码：
    0 = 无 error（可能有 warning）
    1 = 存在 error
    2 = 无法读取输入

检查范围见 docs/06-qc/01-self-check.md。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

ERRORS: List[str] = []
WARNINGS: List[str] = []

LINE_KEYS = [
    "Group", "Name", "Texture", "bpmfactor", "eventLayers", "extended",
    "father", "isCover", "numOfNotes", "posControl", "sizeControl",
    "skewControl", "yControl", "alphaControl", "zOrder",
]
LINE_OPTIONAL = ["anchor", "isGif", "notes"]  # Phira 有默认值，真实谱面可能省略
NOTE_KEYS = [
    "type", "startTime", "endTime", "positionX", "speed", "above",
    "isFake", "alpha", "size", "visibleTime", "yOffset",
]
EVENT_CORE = ["startTime", "endTime", "start", "end"]
EVENT_OPTIONAL = [
    "easingType", "easingLeft", "easingRight", "bezier", "bezierPoints",
    "linkgroup",
]
LAYER_KEYS = ["alphaEvents", "moveXEvents", "moveYEvents", "rotateEvents", "speedEvents"]
INFO_REQUIRED = [
    "name", "difficulty", "level", "charter", "composer", "illustrator",
    "chart", "music", "illustration", "offset", "previewStart",
    "aspectRatio", "backgroundDim", "lineLength", "tags", "intro",
    "holdPartialCover", "noteUniformScale", "forceAspectRatio", "useAttachUiFix",
]
# Phira 同时接受旧版 Phi 大写字段的 info.yml（Name/Song/Picture/Chart...）
LEGACY_INFO_MAP = {
    "name": "Name", "music": "Song", "illustration": "Picture",
    "chart": "Chart", "level": "Level", "composer": "Composer",
    "charter": "Charter", "illustrator": "Illustrator",
}
LEGACY_INFO_REQUIRED = ["Name", "Song", "Picture", "Chart", "Level", "Composer", "Charter"]


def is_legacy_info(info: Optional[dict]) -> bool:
    return isinstance(info, dict) and "Name" in info and "name" not in info


def info_get(info: Optional[dict], key: str) -> Any:
    """同时支持 RPE 小写和旧版大写 info.yml。"""
    if not isinstance(info, dict):
        return None
    if key in info:
        return info[key]
    legacy = LEGACY_INFO_MAP.get(key)
    return info.get(legacy) if legacy else None


# --------------------------------------------------------------------------
# 基础判断
# --------------------------------------------------------------------------
def is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_triplet(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 3 and all(is_int(x) for x in v)


def triplet_error(v: Any) -> Optional[str]:
    if not isinstance(v, list):
        return f"不是数组（得到 {type(v).__name__}）"
    if len(v) != 3:
        return f"长度 {len(v)} != 3"
    for i, x in enumerate(v):
        if isinstance(x, bool) or not isinstance(x, int):
            return f"第 {i} 位不是整数（得到 {x!r}，类型 {type(x).__name__}）"
    if v[2] == 0:
        # RPE 换算公式为 bar + num/den；分母 0 即除零，任何情况下都不合法。
        if v[1] != 0:
            return "分母为 0 但分子非 0（整数拍请写 [bar, 0, 1]）"
        return "分母为 0（整数拍请写 [bar, 0, 1]，不能写 [bar, 0, 0]）"
    return None


def parse_bt(t: Sequence[int]) -> float:
    w, n, d = t
    if d == 0:
        return float(w)
    return w + n / d


# --------------------------------------------------------------------------
# 读取
# --------------------------------------------------------------------------
def _pick_chart_name(names: Sequence[str], info: Optional[dict]) -> Optional[str]:
    """从 info.yml 的 chart 字段或常见命名中找出谱面 JSON。

    Phira 导出的工程常把谱面命名为 <数字id>.json，而不是 chart.json，
    所以必须优先读取 info.yml 里的 chart 字段。
    """
    roots = [n for n in names if "/" not in n.strip("/")]
    want = info_get(info, "chart")
    if isinstance(want, str):
        want = want.strip().lstrip("./")
        for n in names:
            if n.strip("./") == want:
                return n
        for n in roots:
            if n == want:
                return n
    for pref in ("chart.json",):
        if pref in roots:
            return pref
    cands = [n for n in roots
             if n.endswith(".json") and n not in ("extra.json", "info.json")]
    return cands[0] if cands else None


def read_inputs(path: str) -> Tuple[Optional[dict], Optional[dict], Optional[dict], Optional[str]]:
    """返回 (info, chart, extra, error)。"""
    info = chart = extra = None

    if os.path.isdir(path):
        info = _load_yaml(os.path.join(path, "info.yml"))
        chart_name = _pick_chart_name(os.listdir(path), info)
        chart = _load_json(os.path.join(path, chart_name)) if chart_name else None
        extra = _load_json(os.path.join(path, "extra.json"))
        if chart is None:
            return None, None, None, f"目录中没有找到谱面 JSON：{path}"
        if info is None:
            ERRORS.append("缺少 info.yml 或解析失败")
        _check_files_exist(path, info, chart_name)
        return info, chart, extra, None

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            def rd(key):
                for n in names:
                    if n.strip("./") == key:
                        return z.read(n).decode("utf-8-sig")
                return None
            info_raw = rd("info.yml")
            info = _parse_yaml(info_raw) if info_raw else None
            chart_name = _pick_chart_name(names, info)
            chart_raw = rd(chart_name) if chart_name else None
            extra_raw = rd("extra.json")
        if info_raw is None:
            ERRORS.append("zip 根目录缺少 info.yml（Phira 不会扫描子目录）")
        if chart_name is None or chart_raw is None:
            return None, None, None, "zip 中没有找到谱面 JSON（检查 info.yml 的 chart 字段）"
        chart = _parse_json(chart_raw, chart_name)
        extra = _parse_json(extra_raw) if extra_raw else None
        _check_zip_files(names, info)
        return info, chart, extra, None

    if path.endswith((".json",)):
        return None, _load_json(path), None, None

    return None, None, None, f"无法识别的输入：{path}"


def _load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    return _parse_json(raw, path)


def _parse_json(raw: str, label: str = "") -> Optional[dict]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        ERRORS.append(f"{label or 'JSON'} 解析失败：{e}（常见原因：多个对象拼接 / BOM / 注释）")
        return None


def _load_yaml(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return _parse_yaml(f.read())


def _parse_yaml(raw: str) -> Optional[dict]:
    try:
        import yaml
    except ImportError:
        ERRORS.append("缺少 pyyaml：pip install pyyaml")
        return None
    try:
        return yaml.safe_load(raw)
    except Exception as e:
        ERRORS.append(f"info.yml 解析失败：{e}")
        return None


def _check_files_exist(directory: str, info: Optional[dict],
                       chart_name: Optional[str] = None) -> None:
    must = [chart_name or "chart.json"]
    if info:
        for k in ("chart", "music", "illustration"):
            v = info_get(info, k)
            if v:
                must.append(str(v))
    for m in must:
        if not os.path.exists(os.path.join(directory, m)):
            ERRORS.append(f"缺少文件：{m}")


def _check_zip_files(names: Sequence[str], info: Optional[dict]) -> None:
    """zip 内资源可以在子目录，但 info.yml 必须在根目录。"""
    flat = {n.strip("./") for n in names}
    if "info.yml" not in flat:
        return  # 已由 read_inputs 报告
    if info:
        for k in ("chart", "music", "illustration"):
            v = info_get(info, k)
            if not v:
                continue
            if str(v).strip("./") not in flat:
                ERRORS.append(f"zip 中缺少 info.yml 引用的文件：{v}")


# --------------------------------------------------------------------------
# info.yml
# --------------------------------------------------------------------------
def check_info(info: Optional[dict]) -> None:
    if info is None:
        return
    if not isinstance(info, dict):
        ERRORS.append("info.yml 顶层必须是映射")
        return

    if is_legacy_info(info):
        # 旧版 Phi info.yml：字段少但 Phira 仍可识别
        for k in LEGACY_INFO_REQUIRED:
            if k not in info:
                ERRORS.append(f"info.yml（旧版格式）缺少必需字段：{k}")
        for k in LEGACY_INFO_REQUIRED:
            if k in info and not isinstance(info[k], str):
                ERRORS.append(f"info.yml {k} 必须是字符串")
        return

    for k in INFO_REQUIRED:
        if k not in info:
            ERRORS.append(f"info.yml 缺少必需字段：{k}")

    # 社区下载的谱面常见 id: null / uploader: null（未上传），这是合法的
    if info.get("id") is not None and not is_int(info["id"]):
        ERRORS.append(f"info.yml id 必须是整数或 null，得到 {info['id']!r}")
    if info.get("uploader") is not None and not is_int(info["uploader"]):
        ERRORS.append(f"info.yml uploader 必须是整数或 null，得到 {info['uploader']!r}")
    if "difficulty" in info and not is_number(info["difficulty"]):
        ERRORS.append("info.yml difficulty 必须是数字")
    for k in ("offset", "previewStart", "aspectRatio", "backgroundDim", "lineLength"):
        if k in info and info[k] is not None and not is_number(info[k]):
            ERRORS.append(f"info.yml {k} 必须是数字")
    if "tags" in info and not isinstance(info["tags"], list):
        ERRORS.append("info.yml tags 必须是列表")
    for k in ("holdPartialCover", "noteUniformScale", "forceAspectRatio", "useAttachUiFix"):
        if k in info and info[k] is not None and not isinstance(info[k], bool):
            ERRORS.append(f"info.yml {k} 必须是布尔值")
    for k in ("name", "level", "charter", "chart", "music", "illustration"):
        if k in info and not isinstance(info[k], str):
            ERRORS.append(f"info.yml {k} 必须是字符串")


# --------------------------------------------------------------------------
# chart.json
# --------------------------------------------------------------------------
def check_chart(chart: dict) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "lines": 0, "playing_lines": 0, "notes": 0, "types": Counter(),
        "xs": [], "line_events": [], "speeds": [], "effects": 0,
        "hold_max_beats": 0.0, "duplicates": 0, "score_events": 0,
    }

    required_top = ("BPMList", "META", "judgeLineGroup", "judgeLineList")
    for key in required_top:
        if key not in chart:
            ERRORS.append(f"chart.json 缺少顶层字段：{key}")
    if "chartTime" not in chart:
        WARNINGS.append("chart.json 缺少 chartTime（部分 Phira 导出会省略，可接受）")
    if "judgeLineList" not in chart:
        return stats

    # BPM
    bpm_segments: List[Tuple[float, float]] = []
    bpm_list = chart.get("BPMList") or []
    if not isinstance(bpm_list, list) or not bpm_list:
        ERRORS.append("BPMList 必须是非空数组")
    else:
        for i, b in enumerate(bpm_list):
            if not isinstance(b, dict):
                ERRORS.append(f"BPMList[{i}] 不是对象")
                continue
            if "bpm" not in b:
                ERRORS.append(f"BPMList[{i}] 缺少 bpm（会导致加载阶段失败）")
            elif not is_number(b["bpm"]) or float(b["bpm"]) <= 0:
                ERRORS.append(f"BPMList[{i}].bpm 非法：{b.get('bpm')!r}")
            else:
                err = triplet_error(b.get("startTime"))
                if err:
                    ERRORS.append(f"BPMList[{i}].startTime {err}")
                else:
                    bpm_segments.append((parse_bt(b["startTime"]), float(b["bpm"])))
        bpm_segments.sort()
        for i in range(1, len(bpm_segments)):
            if bpm_segments[i][0] <= bpm_segments[i - 1][0]:
                WARNINGS.append("BPMList 存在重复/乱序的开始时间")

    # META
    meta = chart.get("META") or {}
    if not isinstance(meta, dict):
        ERRORS.append("META 必须是对象")
    else:
        for k in ("RPEVersion", "duration", "name", "charter"):
            if k not in meta:
                WARNINGS.append(f"META 缺少 {k}")
        if "RPEVersion" in meta and not is_int(meta["RPEVersion"]):
            ERRORS.append("META.RPEVersion 必须是整数")
        if "offset" in meta and not is_number(meta["offset"]):
            ERRORS.append("META.offset 必须是数字（毫秒）")

    # 时长：优先 META.duration（秒）；chartTime 在部分导出中为 0 或单位异常
    chart_time = chart.get("chartTime", 0)
    if not is_number(chart_time):
        ERRORS.append("chartTime 必须是数字")
        chart_time = 0
    meta_dur = meta.get("duration") if isinstance(meta, dict) else None
    if is_number(meta_dur) and float(meta_dur) > 0:
        duration = float(meta_dur)
    elif float(chart_time) > 0:
        duration = float(chart_time)
    else:
        duration = 0.0

    # groups
    groups = chart.get("judgeLineGroup") or []
    if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
        ERRORS.append("judgeLineGroup 必须是字符串数组")

    lines = chart["judgeLineList"]
    if not isinstance(lines, list):
        ERRORS.append("judgeLineList 必须是数组")
        return stats
    stats["lines"] = len(lines)
    if not lines:
        ERRORS.append("judgeLineList 为空")
        return stats

    notes_by_line: List[List[dict]] = []
    for li, line in enumerate(lines):
        if not isinstance(line, dict):
            ERRORS.append(f"judgeLineList[{li}] 不是对象")
            notes_by_line.append([])
            continue

        for k in LINE_KEYS:
            if k not in line:
                ERRORS.append(f"line[{li}] 缺少字段 {k}")
        if "notes" in line and not isinstance(line["notes"], list):
            ERRORS.append(f"line[{li}].notes 必须是数组")
        if "Group" in line:
            if not is_int(line["Group"]):
                ERRORS.append(f"line[{li}].Group 必须是整数")
            elif groups and not (0 <= line["Group"] < len(groups)):
                ERRORS.append(f"line[{li}].Group={line['Group']} 超出 judgeLineGroup 范围")
        if "father" in line and not is_int(line["father"]):
            ERRORS.append(f"line[{li}].father 必须是整数")
        elif is_int(line.get("father")) and not (-1 <= line["father"] < len(lines)):
            ERRORS.append(f"line[{li}].father={line['father']} 非法")
        if "isCover" in line and not is_int(line["isCover"]):
            ERRORS.append(f"line[{li}].isCover 必须是整数 0/1（不是布尔）")
        if "isGif" in line and not isinstance(line["isGif"], bool):
            ERRORS.append(f"line[{li}].isGif 必须是布尔值")
        for ctrl in ("posControl", "sizeControl", "skewControl", "yControl"):
            if ctrl in line and not isinstance(line[ctrl], list):
                ERRORS.append(f"line[{li}].{ctrl} 必须是数组 []（不能是对象 {{}}）")
        if "alphaControl" in line and not isinstance(line["alphaControl"], list):
            ERRORS.append(f"line[{li}].alphaControl 必须是数组")
        if "extended" in line and not isinstance(line["extended"], dict):
            ERRORS.append(f"line[{li}].extended 必须是对象")
        if "anchor" in line and not (isinstance(line["anchor"], list) and len(line["anchor"]) == 2):
            ERRORS.append(f"line[{li}].anchor 必须是 [x, y]")

        # layers（真实谱面会用 null 表示空图层，这是合法的）
        ev_counts = Counter()
        layers = line.get("eventLayers")
        if not isinstance(layers, list) or not layers:
            ERRORS.append(f"line[{li}].eventLayers 必须是非空数组")
        else:
            for ei, layer in enumerate(layers):
                if layer is None:
                    continue
                if not isinstance(layer, dict):
                    ERRORS.append(f"line[{li}].eventLayers[{ei}] 不是对象或 null")
                    continue
                # 真实谱面允许只写部分事件数组（如只有 moveXEvents），其余由 Phira 补默认值
                for k in LAYER_KEYS:
                    arr = layer.get(k)
                    if arr is None:
                        continue
                    if not isinstance(arr, list):
                        ERRORS.append(f"line[{li}].eventLayers[{ei}].{k} 必须是数组")
                        continue
                    ev_counts[k] = max(ev_counts[k], len(arr))
                    for ej, ev in enumerate(arr):
                        _check_event(li, k, ej, ev)
                        if k == "speedEvents" and isinstance(ev, dict) and is_number(ev.get("start")):
                            stats["speeds"].append(float(ev["start"]))
                            stats["speeds"].append(float(ev.get("end", ev["start"])))

        stats["line_events"].append({
            "name": line.get("Name", f"line{li}"),
            "notes": len(line.get("notes") or []),
            **dict(ev_counts),
        })

        # notes
        notes = line.get("notes") or []
        if not isinstance(notes, list):
            ERRORS.append(f"line[{li}].notes 必须是数组")
            notes = []
        # 注：numOfNotes 只是导出器的缓存字段，Phira 会自行统计，不参与校验
        if notes:
            stats["playing_lines"] += 1
        notes_by_line.append(notes)
        stats["notes"] += len(notes)

        for ni, n in enumerate(notes):
            _check_note(li, ni, n, stats)

    _check_duplicates(lines, notes_by_line, stats)
    stats["chart_time"] = duration
    if bpm_segments:
        if duration > 0:
            _check_overflow(lines, duration, bpm_segments, stats)
        _attach_timing_stats(lines, bpm_segments, stats)

    stats["bpm_segments"] = bpm_segments
    stats["groups"] = groups
    return stats


def _check_event(li: int, kind: str, ei: int, ev: Any) -> None:
    where = f"line[{li}].{kind}[{ei}]"
    if not isinstance(ev, dict):
        ERRORS.append(f"{where} 不是对象")
        return
    for k in EVENT_CORE:
        if k not in ev:
            ERRORS.append(f"{where} 缺少核心字段 {k}")
    for k in EVENT_OPTIONAL:
        if k not in ev:
            continue  # RPE 允许省略，Phira 有默认值
        if k == "easingType" and not is_int(ev[k]):
            ERRORS.append(f"{where}.easingType 必须是整数")
        if k == "linkgroup" and not is_int(ev[k]):
            ERRORS.append(f"{where}.linkgroup 必须是整数")
        if k in ("easingLeft", "easingRight") and not is_number(ev[k]):
            ERRORS.append(f"{where}.{k} 必须是数字")
        if k == "bezier" and not is_int(ev[k]):
            ERRORS.append(f"{where}.bezier 必须是整数")
        if k == "bezierPoints" and not (
            isinstance(ev[k], list) and len(ev[k]) == 4
        ):
            ERRORS.append(f"{where}.bezierPoints 必须是 4 个数字")
    for tk in ("startTime", "endTime"):
        if tk in ev:
            err = triplet_error(ev[tk])
            if err:
                ERRORS.append(f"{where}.{tk} {err}")
    if is_triplet(ev.get("startTime")) and is_triplet(ev.get("endTime")):
        if parse_bt(ev["endTime"]) < parse_bt(ev["startTime"]):
            ERRORS.append(f"{where} endTime 早于 startTime")
    if "start" not in ev or "end" not in ev:
        return
    if kind == "alphaEvents":
        for sk in ("start", "end"):
            v = ev.get(sk)
            if not is_int(v):
                ERRORS.append(f"{where}.{sk} 必须是整数（alpha）")
            elif not (-255 <= v <= 255):
                WARNINGS.append(f"{where}.{sk}={v} 超出 0~255")
    else:
        for sk in ("start", "end"):
            if not is_number(ev.get(sk)):
                ERRORS.append(f"{where}.{sk} 必须是数字")


def _check_note(li: int, ni: int, n: Any, stats: Dict[str, Any]) -> None:
    where = f"line[{li}].notes[{ni}]"
    if not isinstance(n, dict):
        ERRORS.append(f"{where} 不是对象")
        return
    missing = [k for k in NOTE_KEYS if k not in n]
    if missing:
        ERRORS.append(f"{where} 缺少字段 {missing}")
    # 真实 RPE 谱面还会带 judgeArea / tint 等字段，Phira 接受，不报警

    t = n.get("type")
    if not is_int(t) or t not in (1, 2, 3, 4):
        ERRORS.append(f"{where}.type 必须是 1~4，得到 {t!r}")
    for tk in ("startTime", "endTime"):
        err = triplet_error(n.get(tk))
        if err:
            ERRORS.append(f"{where}.{tk} {err}")

    px = n.get("positionX")
    if not is_number(px):
        ERRORS.append(f"{where}.positionX 必须是数字，得到 {px!r}")
    elif abs(float(px)) > 700:
        WARNINGS.append(f"{where}.positionX={px} 超出屏幕范围 ±675")
    else:
        stats["xs"].append(float(px))

    if "alpha" in n and (not is_int(n["alpha"]) or not (0 <= n["alpha"] <= 255)):
        ERRORS.append(f"{where}.alpha 必须是 0~255 的整数")
    if "speed" in n and not is_number(n["speed"]):
        ERRORS.append(f"{where}.speed 必须是数字")
    if "visibleTime" in n and is_number(n["visibleTime"]) and n["visibleTime"] < 2:
        WARNINGS.append(f"{where}.visibleTime={n['visibleTime']} 过小，note 可能一闪而过")
    if "size" in n and is_number(n["size"]) and float(n["size"]) <= 0:
        ERRORS.append(f"{where}.size 必须 > 0")

    if is_int(t):
        stats["types"][t] += 1
    if t in (2, 4) and is_triplet(n.get("startTime")) and is_triplet(n.get("endTime")):
        dur = parse_bt(n["endTime"]) - parse_bt(n["startTime"])
        if dur < 0:
            ERRORS.append(f"{where} Hold/Drag 的 endTime 早于 startTime")
        stats["hold_max_beats"] = max(stats["hold_max_beats"], dur)


def _check_duplicates(lines: List[dict], notes_by_line: List[List[dict]],
                      stats: Dict[str, Any]) -> None:
    for li, notes in enumerate(notes_by_line):
        seen = defaultdict(int)
        for n in notes:
            if not isinstance(n, dict):
                continue
            if not is_triplet(n.get("startTime")):
                continue
            key = (tuple(n["startTime"]), n.get("positionX"), n.get("type"))
            seen[key] += 1
        dup = sum(v - 1 for v in seen.values() if v > 1)
        if dup:
            stats["duplicates"] += dup
            WARNINGS.append(
                f"line[{li}] 存在 {dup} 个完全重叠的 note（同时间/同位置/同类型）"
            )


def _beat_to_seconds(beat: float, segs: List[Tuple[float, float]]) -> float:
    total = 0.0
    for i, (start, bpm) in enumerate(segs):
        nxt = segs[i + 1][0] if i + 1 < len(segs) else float("inf")
        if beat <= start:
            break
        total += (min(beat, nxt) - start) * 60.0 / bpm
        if beat <= nxt:
            return total
    return total


def _check_overflow(lines: List[dict], chart_time: float,
                    segs: List[Tuple[float, float]], stats: Dict[str, Any]) -> None:
    over = 0
    for line in lines:
        for n in line.get("notes") or []:
            if is_triplet(n.get("startTime")):
                if _beat_to_seconds(parse_bt(n["startTime"]), segs) > chart_time + 1.0:
                    over += 1
    if over:
        WARNINGS.append(f"有 {over} 个 note 的时间超出 chartTime")


def _attach_timing_stats(lines: List[dict], segs: List[Tuple[float, float]],
                         stats: Dict[str, Any]) -> None:
    times: List[float] = []
    for line in lines:
        for n in line.get("notes") or []:
            if is_triplet(n.get("startTime")):
                times.append(_beat_to_seconds(parse_bt(n["startTime"]), segs))
    if not times:
        return
    times.sort()
    duration = stats.get("chart_time") or (times[-1] or 1)
    stats["first_note"] = round(times[0], 2)
    stats["last_note"] = round(times[-1], 2)
    stats["avg_nps"] = round(len(times) / duration, 2) if duration > 0 else 0

    # 峰值 NPS：1 秒滑动窗口
    peak, peak_t = 0, 0.0
    j = 0
    for i in range(len(times)):
        while times[i] - times[j] > 1.0:
            j += 1
        if i - j + 1 > peak:
            peak = i - j + 1
            peak_t = times[i]
    stats["peak_nps"] = peak
    stats["peak_nps_at"] = round(peak_t, 2)


# --------------------------------------------------------------------------
# extra.json
# --------------------------------------------------------------------------
def check_extra(extra: Optional[dict], stats: Dict[str, Any]) -> None:
    if extra is None:
        return
    if not isinstance(extra, dict):
        ERRORS.append("extra.json 顶层必须是对象")
        return
    effects = extra.get("effects")
    if effects is None:
        return
    if not isinstance(effects, list):
        ERRORS.append("extra.json effects 必须是数组")
        return
    stats["effects"] = len(effects)
    for i, eff in enumerate(effects):
        where = f"effects[{i}]"
        if not isinstance(eff, dict):
            ERRORS.append(f"{where} 不是对象")
            continue
        if not isinstance(eff.get("shader"), str) or not eff.get("shader"):
            ERRORS.append(f"{where}.shader 必须是非空字符串")
        for tk in ("start", "end"):
            err = triplet_error(eff.get(tk))
            if err:
                ERRORS.append(f"{where}.{tk} {err}（必须是 beat 三元组，不能是秒数）")
        if is_triplet(eff.get("start")) and is_triplet(eff.get("end")):
            if parse_bt(eff["end"]) < parse_bt(eff["start"]):
                ERRORS.append(f"{where} end 早于 start")
        if "global" in eff and not isinstance(eff["global"], bool):
            ERRORS.append(f"{where}.global 必须是布尔值")
        vars_ = eff.get("vars")
        if vars_ is not None and not isinstance(vars_, dict):
            ERRORS.append(f"{where}.vars 必须是对象")
        elif isinstance(vars_, dict):
            for name, v in vars_.items():
                if isinstance(v, list):
                    # 两种合法形态：
                    #   动画  [{startTime, endTime, easingType, start, end}, ...]
                    #   静态  [r, g, b, a] 这样的纯数字数组（如 color）
                    if v and all(is_number(x) for x in v):
                        continue
                    for j, a in enumerate(v):
                        if not isinstance(a, dict):
                            ERRORS.append(
                                f"{where}.vars.{name}[{j}] 不是对象"
                                f"（静态值请写纯数字数组，动画请写对象数组）"
                            )
                            continue
                        for tk in ("startTime", "endTime"):
                            err = triplet_error(a.get(tk))
                            if err:
                                ERRORS.append(f"{where}.vars.{name}[{j}].{tk} {err}")
                elif not is_number(v):
                    WARNINGS.append(f"{where}.vars.{name} 类型可疑：{type(v).__name__}")


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def print_report(stats: Dict[str, Any], path: str) -> None:
    print("\n=== Chart Report ===")
    print(f"Input         : {path}")
    print(f"Lines         : {stats['lines']} (playing {stats['playing_lines']})")
    types = stats["types"]
    total = sum(types.values()) or 1
    parts = [f"{name} {types[t]} ({types[t]/total:.1%})"
             for t, name in ((1, "Tap"), (2, "Hold"), (3, "Flick"), (4, "Drag"))]
    print(f"Notes         : {stats['notes']}  " + " | ".join(parts))
    print(f"Duration      : {stats.get('chart_time', 0):.2f}s")
    if stats.get("avg_nps") is not None:
        print(f"Avg NPS       : {stats['avg_nps']}")
        print(f"Peak NPS      : {stats.get('peak_nps')} @ {stats.get('peak_nps_at')}s")
        print(f"First/Last    : {stats.get('first_note')}s / {stats.get('last_note')}s")
    if stats["xs"]:
        xs = stats["xs"]
        print(f"X range       : {min(xs)} ~ {max(xs)} (mean {sum(xs)/len(xs):.1f})")
    if stats["speeds"]:
        print(f"Speed range   : {min(stats['speeds']):.1f} ~ {max(stats['speeds']):.1f}")
    print(f"Max Hold      : {stats['hold_max_beats']:.2f} beats")
    print(f"Duplicates    : {stats['duplicates']}")
    print(f"Effects       : {stats['effects']}")
    if stats["line_events"]:
        print("Event density :")
        for e in stats["line_events"]:
            print(f"  {e['name']:<22} notes={e['notes']:<5} "
                  f"moveX={e.get('moveXEvents', 0):<5} moveY={e.get('moveYEvents', 0):<5} "
                  f"rot={e.get('rotateEvents', 0):<5} alpha={e.get('alphaEvents', 0):<5} "
                  f"speed={e.get('speedEvents', 0)}")
    if stats.get("groups"):
        print(f"Groups        : {', '.join(stats['groups'])}")
    print("====================\n")


def semantic_warnings(stats: Dict[str, Any]) -> None:
    total = sum(stats["types"].values()) or 1
    for t, name in ((1, "Tap"), (2, "Hold"), (3, "Flick"), (4, "Drag")):
        ratio = stats["types"][t] / total
        if ratio > 0.85:
            WARNINGS.append(f"{name} 占比 {ratio:.0%}，谱面可能过于单调")
    if stats["playing_lines"] == 1:
        WARNINGS.append("只有 1 条线承载音符，视觉表现可能单调")
    if stats["playing_lines"] > 6:
        WARNINGS.append("超过 6 条线承载音符，读谱难度可能过高")
    if stats.get("avg_nps") is not None and stats["avg_nps"] < 1:
        WARNINGS.append("平均 NPS < 1，可能过于稀疏")
    if stats["line_events"]:
        dense = [e for e in stats["line_events"]
                 if max(e.get("moveXEvents", 0), e.get("moveYEvents", 0),
                        e.get("rotateEvents", 0), e.get("alphaEvents", 0)) >= 100]
        if stats["playing_lines"] >= 2 and not dense:
            WARNINGS.append("没有任何线的事件数 ≥100，判定线表演可能过于死板")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Phira / RPE 谱面校验器")
    ap.add_argument("path", help="工程目录 / chart.json / zip")
    ap.add_argument("--report", action="store_true", help="打印统计报告")
    args = ap.parse_args()

    info, chart, extra, err = read_inputs(args.path)
    if err:
        print(f"[FATAL] {err}")
        _flush()
        return 2
    if chart is None:
        print("[FATAL] 无法读取谱面")
        _flush()
        return 2

    check_info(info)
    stats = check_chart(chart)
    check_extra(extra, stats)
    semantic_warnings(stats)

    if args.report:
        print_report(stats, args.path)

    _flush()
    return 1 if ERRORS else 0


def _flush() -> None:
    for e in ERRORS:
        print(f"[ERROR] {e}")
    for w in WARNINGS:
        print(f"[WARN ] {w}")
    print(f"\n结果：{len(ERRORS)} error, {len(WARNINGS)} warning")


if __name__ == "__main__":
    sys.exit(main())
