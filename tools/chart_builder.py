#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chart_builder.py — Phira / RPE 谱面构建库

设计目标：
    让调用者永远不需要手写 JSON 字段，从而绕开 90% 的格式错误。

核心保证：
    * beat 三元组永远是整数（自动 Fraction 转换）
    * 每个 note 都带 endTime / positionX 等 11 个白名单字段
    * eventLayers 每层都是完整的 5 事件数组
    * control 字段永远是数组

用法：
    from chart_builder import Chart, bt

    c = Chart(bpm=128, song="song.mp3", name="曲名", charter="谱师")
    line = c.add_line("Main", group=0)
    line.add_note(1, bt(4), x=0)
    line.add_note(2, bt(4.5), bt(6), x=-200)
    line.movex([(bt(0), 0), (bt(4), 120)])
    line.speed([(bt(0), 10.0)])
    c.save("chart.json")
    c.save_info("info.yml")
    c.save_extra("extra.json")
"""

from __future__ import annotations

import json
import math
import os
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "bt",
    "note",
    "event",
    "anim",
    "Line",
    "Chart",
    "oscillation_events",
    "damped_shake_events",
    "parse_bt",
]

MAX_DEN = 64  # 最大细分分母（1/64 拍）


# --------------------------------------------------------------------------
# 时间系统
# --------------------------------------------------------------------------
def bt(*args: Any) -> List[int]:
    """把拍值转成 RPE 的 beat 三元组 [whole, numerator, denominator]。

    支持两种调用：
        bt(3.5)          -> [3, 1, 2]
        bt(4)            -> [4, 0, 1]
        bt(3, 1, 2)      -> [3, 1, 2]

    全部输出整数；小数用 Fraction 精确转换，绝不产生浮点。
    """
    if len(args) == 1:
        return _bt_from_number(args[0])
    if len(args) == 2:
        whole, num = args
        den = 1
    elif len(args) == 3:
        whole, num, den = args
    else:
        raise TypeError("bt() 接受 1~3 个参数")

    whole, num, den = int(whole), int(num), int(den)
    if den == 0:
        raise ValueError(
            "分母必须 ≥ 1：整数拍请写 bt(4)（得到 [4,0,1]），不能写 [4,0,0]"
        )
    # 规范化：[3, 2, 2] -> [4, 0, 1]
    f = Fraction(whole * den + num, den)
    w = int(f)
    n = f.numerator - w * f.denominator
    d = f.denominator
    return [w, n if n else 0, d]


def _bt_from_number(value: Any) -> List[int]:
    if isinstance(value, (list, tuple)):
        return bt(*value)
    f = Fraction(value if isinstance(value, (int, Fraction)) else float(value))
    f = f.limit_denominator(MAX_DEN)
    w = int(f)
    n = f.numerator - w * f.denominator
    d = f.denominator
    return [w, n if n else 0, d]


def parse_bt(triplet: Sequence[int]) -> float:
    """三元组 -> 拍值（float），仅用于计算/校验。"""
    if len(triplet) != 3:
        raise ValueError(f"beat 三元组必须 3 个元素，得到 {triplet}")
    w, n, d = (int(x) for x in triplet)
    if d == 0:
        raise ValueError(
            f"非法三元组 {triplet}：分母为 0（整数拍应写 [bar, 0, 1]）"
        )
    return w + n / d


def beat_to_seconds(beat: float, bpm_list: Sequence[Tuple[float, float]]) -> float:
    """按 BPM 分段累加，把拍值转秒。bpm_list = [(start_beat, bpm), ...]"""
    bpm_list = sorted(bpm_list)
    total = 0.0
    for i, (start, bpm) in enumerate(bpm_list):
        nxt = bpm_list[i + 1][0] if i + 1 < len(bpm_list) else float("inf")
        if beat <= start:
            break
        span = min(beat, nxt) - start
        total += span * 60.0 / bpm
        if beat <= nxt:
            return total
    return total


# --------------------------------------------------------------------------
# 音符
# --------------------------------------------------------------------------
_TYPE_NAMES = {1: "Tap", 2: "Hold", 3: "Flick", 4: "Drag"}


def note(
    note_type: int,
    start: Any,
    end: Any = None,
    x: Any = 0,
    speed: float = 1.0,
    above: int = 1,
    is_fake: int = 0,
    alpha: int = 255,
    size: float = 1.0,
    visible_time: float = 999999.0,
    y_offset: Any = 0,
) -> Dict[str, Any]:
    """构造一个 Phira note。

    note_type: 1=Tap 2=Hold 3=Flick 4=Drag
    非 Hold/Drag 的 end 会自动写成 [0,0,1] 占位。
    """
    if note_type not in _TYPE_NAMES:
        raise ValueError(f"note type 必须是 1~4，得到 {note_type}")

    n = {
        "type": int(note_type),
        "startTime": bt(start),
        "endTime": bt(end) if (end is not None and note_type in (2, 4)) else [0, 0, 1],
        "positionX": _as_int(x),
        "speed": float(speed),
        "above": int(above),
        "isFake": int(is_fake),
        "alpha": max(0, min(255, int(alpha))),
        "size": float(size),
        "visibleTime": float(visible_time),
        "yOffset": _as_number(y_offset),
    }
    if note_type in (2, 4) and parse_bt(n["endTime"]) < parse_bt(n["startTime"]):
        raise ValueError(f"Hold/Drag 的 endTime 早于 startTime: {n}")
    return n


def _as_int(v: Any) -> int:
    if isinstance(v, (list, tuple)):
        raise TypeError("这里需要数字，不是三元组")
    return int(round(float(v)))


def _as_number(v: Any):
    f = float(v)
    return int(f) if f.is_integer() else f


# --------------------------------------------------------------------------
# 事件
# --------------------------------------------------------------------------
def event(start: Any, end: Any, start_value: float, end_value: float,
          easing: int = 1, linkgroup: int = 0) -> Dict[str, Any]:
    """构造一个标准事件（10 字段全齐）。"""
    return {
        "startTime": bt(start),
        "endTime": bt(end),
        "start": _event_value(start_value),
        "end": _event_value(end_value),
        "easingType": int(easing),
        "easingLeft": 0.0,
        "easingRight": 1.0,
        "bezier": 0,
        "bezierPoints": [0.0, 0.0, 0.0, 0.0],
        "linkgroup": int(linkgroup),
    }


def _event_value(v: Any):
    if isinstance(v, (list, tuple)):
        return [float(x) for x in v]
    f = float(v)
    return int(f) if f.is_integer() else f


def anim(start: Any, end: Any, start_value: float, end_value: float,
         easing: int = 1) -> Dict[str, Any]:
    """extra.json 的动画变量（无 linkgroup / bezier 字段）。"""
    return {
        "startTime": bt(start),
        "endTime": bt(end),
        "start": _event_value(start_value),
        "end": _event_value(end_value),
        "easingType": int(easing),
    }


# --------------------------------------------------------------------------
# 编舞工具
# --------------------------------------------------------------------------
def oscillation_events(start: float, end: float, period: float = 2.0,
                       amp: float = 10.0, step: float = 0.125) -> List[Tuple[Any, float]]:
    """正弦振荡关键帧：返回 [(bt, value), ...]，配合 line.movex() 使用。

    step=0.125 即 1/8 拍。
    """
    out: List[Tuple[Any, float]] = []
    b = start
    while b < end:
        v = amp * math.sin(2 * math.pi * (b - start) / period)
        out.append((bt(b), v))
        b += step
    return out


def damped_shake_events(start: float, amp: float = 5.0, k: float = 0.35,
                        step: float = 0.125, min_amp: float = 0.02):
    """阻尼振荡：模拟"被敲击后抖动 → 静止"。返回 [(bt, value), ...]"""
    out = []
    b, i = start, 0
    while amp * math.exp(-k * i) > min_amp:
        a = amp * math.exp(-k * i)
        out.append((bt(b), a))
        out.append((bt(b + step / 2), -a))
        b += step
        i += 1
    out.append((bt(b), 0.0))
    return out


def _points_to_events(points: Iterable[Any], easing: int) -> List[Dict[str, Any]]:
    """[(bt, value), ...] -> 一串首尾相接的线性事件。"""
    pts = list(points)
    evs = []
    for i in range(len(pts) - 1):
        t0, v0 = pts[i]
        t1, v1 = pts[i + 1]
        if parse_bt(t0) == parse_bt(t1):
            continue
        evs.append(event(t0, t1, v0, v1, easing=easing))
    return evs


# --------------------------------------------------------------------------
# 判定线
# --------------------------------------------------------------------------
class Line:
    """一条判定线。"""

    def __init__(self, name: str, group: int = 0, father: int = -1,
                 texture: str = "line.png", z_order: int = 0,
                 anchor: Tuple[float, float] = (0.5, 0.5),
                 bpm_factor: float = 1.0):
        self.name = name
        self.group = int(group)
        self.father = int(father)
        self.texture = texture
        self.z_order = int(z_order)
        self.anchor = [float(anchor[0]), float(anchor[1])]
        self.bpm_factor = float(bpm_factor)
        self.notes: List[Dict[str, Any]] = []
        self.extended: Dict[str, Any] = {}
        self.is_gif = False
        self.is_cover = 0
        self.default_end: Any = 3600  # 单点事件的默认结束时间（拍）

        self._alpha: List[Dict[str, Any]] = []
        self._movex: List[Dict[str, Any]] = []
        self._movey: List[Dict[str, Any]] = []
        self._rotate: List[Dict[str, Any]] = []
        self._speed: List[Dict[str, Any]] = []

    # ---- note ----
    def add_note(self, note_type: int, start: Any, end: Any = None, x: Any = 0,
                 **kw) -> Dict[str, Any]:
        n = note(note_type, start, end, x, **kw)
        self.notes.append(n)
        return n

    def tap(self, start, x=0, **kw):
        return self.add_note(1, start, None, x, **kw)

    def hold(self, start, end, x=0, **kw):
        return self.add_note(2, start, end, x, **kw)

    def flick(self, start, x=0, **kw):
        return self.add_note(3, start, None, x, **kw)

    def drag(self, start, end, x=0, **kw):
        return self.add_note(4, start, end, x, **kw)

    # ---- 事件 ----
    def _append(self, bucket: List[Dict[str, Any]], events: Iterable) -> None:
        bucket.extend(events)

    def alpha(self, events: Iterable) -> "Line":
        self._alpha.extend(_normalize_events(events, alpha=True, default_end=self.default_end))
        return self

    def movex(self, events: Iterable) -> "Line":
        self._movex.extend(_normalize_events(events, default_end=self.default_end))
        return self

    def movey(self, events: Iterable) -> "Line":
        self._movey.extend(_normalize_events(events, default_end=self.default_end))
        return self

    def rotate(self, events: Iterable) -> "Line":
        self._rotate.extend(_normalize_events(events, default_end=self.default_end))
        return self

    def speed(self, events: Iterable) -> "Line":
        self._speed.extend(_normalize_events(events, default_end=self.default_end))
        return self

    # ---- 扩展 ----
    def add_text(self, start, end, text: str, font: str = "",
                 easing: int = 1) -> "Line":
        ev = {
            "startTime": bt(start),
            "endTime": bt(end),
            "start": str(text),
            "end": str(text),
            "font": font,
            "easingType": int(easing),
            "easingLeft": 0.0,
            "easingRight": 1.0,
            "bezier": 0,
            "bezierPoints": [0.0, 0.0, 0.0, 0.0],
            "linkgroup": 0,
        }
        self.extended.setdefault("textEvents", []).append(ev)
        return self

    def scale(self, x: float = 1.0, y: float = 1.0, start=0, end=None) -> "Line":
        """固定纹理缩放（生成一个恒定事件）。"""
        if end is None:
            end = start
        self.extended.setdefault("scaleXEvents", []).append(event(start, end, x, x))
        self.extended.setdefault("scaleYEvents", []).append(event(start, end, y, y))
        return self

    # ---- 输出 ----
    def to_dict(self) -> Dict[str, Any]:
        return {
            "Group": self.group,
            "Name": self.name,
            "Texture": self.texture,
            "anchor": self.anchor,
            "bpmfactor": self.bpm_factor,
            "eventLayers": [{
                "alphaEvents": self._alpha,
                "moveXEvents": self._movex,
                "moveYEvents": self._movey,
                "rotateEvents": self._rotate,
                "speedEvents": self._speed,
            }],
            "extended": self.extended,
            "father": self.father,
            "isCover": self.is_cover,
            "isGif": bool(self.is_gif),
            "notes": self.notes,
            "numOfNotes": len(self.notes),
            "posControl": [],
            "sizeControl": [],
            "skewControl": [],
            "yControl": [],
            "alphaControl": [
                {"alpha": 1.0, "easing": 1, "x": 0.0},
                {"alpha": 1.0, "easing": 1, "x": 9999999.0},
            ],
            "zOrder": self.z_order,
        }


def _normalize_events(events: Iterable, alpha: bool = False,
                      default_end: Optional[Any] = None) -> List[Dict[str, Any]]:
    """接受多种写法：
        [(t0, v0), (t1, v1), ...]                 自动首尾相接
        [(t0, t1, v0, v1), ...]
        [{...完整事件...}, ...]
    """
    evs: List[Dict[str, Any]] = []
    items = list(events)
    if not items:
        return evs
    if isinstance(items[0], dict):
        evs = list(items)
        if alpha:
            for e in evs:
                e["start"] = int(round(float(e["start"])))
                e["end"] = int(round(float(e["end"])))
        return evs

    first = items[0]
    if isinstance(first, (list, tuple)) and len(first) == 2:
        pts = list(items)
        if len(pts) == 1:
            # 单点 = 从该时刻起保持恒定值（持续到 default_end）
            t0, v0 = pts[0]
            evs.append(event(t0, default_end if default_end is not None else t0, v0, v0))
        for i in range(len(pts) - 1):
            t0, v0 = pts[i]
            t1, v1 = pts[i + 1]
            if parse_bt(bt(t0)) == parse_bt(bt(t1)):
                continue
            evs.append(event(t0, t1, v0, v1))
    else:
        for it in items:
            if len(it) == 3:
                t0, t1, v = it
                evs.append(event(t0, t1, v, v))
            elif len(it) == 4:
                t0, t1, v0, v1 = it
                evs.append(event(t0, t1, v0, v1))
            elif len(it) == 5:
                t0, t1, v0, v1, e = it
                evs.append(event(t0, t1, v0, v1, easing=e))
            else:
                raise ValueError(f"无法解析事件元组: {it}")
    if alpha:
        for e in evs:
            e["start"] = int(round(float(e["start"])))
            e["end"] = int(round(float(e["end"])))
    return evs


# --------------------------------------------------------------------------
# 谱面
# --------------------------------------------------------------------------
class Chart:
    def __init__(self, bpm: float, song: str, name: str, charter: str,
                 level: str = "IN 13", difficulty: float = 13.0,
                 composer: str = "Unknown", illustrator: str = "Unknown",
                 duration: float = 120.0, offset_ms: int = 0,
                 rpe_version: int = 170, chart_id: str = "chart"):
        self.lines: List[Line] = []
        self.groups: List[str] = ["Default"]
        self.effects: List[Dict[str, Any]] = []
        self.bpm_list: List[Dict[str, Any]] = [{"bpm": float(bpm), "startTime": bt(0)}]
        self.meta = {
            "RPEVersion": int(rpe_version),
            "background": "illustration.png",
            "charter": charter,
            "composer": composer,
            "duration": float(duration),
            "id": str(chart_id),
            "level": level,
            "name": name,
            "offset": int(offset_ms),
            "song": song,
            "illustration": "illustration.png",
        }
        self.duration = float(duration)
        self.name = name
        self.charter = charter
        self.level = level
        self.difficulty = float(difficulty)
        self.song = song
        self.composer = composer
        self.illustrator = illustrator
        self.offset_s = offset_ms / 1000.0
        self._extra_bpm = self.bpm_list

    # ---- 构建 ----
    def add_group(self, name: str) -> int:
        if name not in self.groups:
            self.groups.append(name)
        return self.groups.index(name)

    def add_line(self, name: str, group: Any = 0, father: int = -1,
                 texture: str = "line.png", z_order: int = 0, **kw) -> Line:
        if isinstance(group, str):
            group = self.add_group(group)
        real_father = (len(self.lines) - 1) if father == "auto" else int(father)
        ln = Line(name, group=group, father=real_father,
                  texture=texture, z_order=z_order, **kw)
        base_bpm = float(self.bpm_list[0]["bpm"])
        ln.default_end = max(3600.0, self.duration * base_bpm / 60.0)
        self.lines.append(ln)
        return ln

    def add_bpm_change(self, beat: Any, bpm: float) -> None:
        self.bpm_list.append({"bpm": float(bpm), "startTime": bt(beat)})

    def add_effect(self, shader: str, start: Any, end: Any,
                   vars: Optional[Dict[str, Any]] = None,
                   global_: bool = False) -> Dict[str, Any]:
        eff = {
            "shader": shader,
            "start": bt(start),
            "end": bt(end),
            "global": bool(global_),
        }
        if vars:
            eff["vars"] = vars
        self.effects.append(eff)
        return eff

    # ---- 统计 ----
    def stats(self) -> Dict[str, Any]:
        types = {1: 0, 2: 0, 3: 0, 4: 0}
        xs = []
        for ln in self.lines:
            for n in ln.notes:
                types[n["type"]] += 1
                xs.append(n["positionX"])
        total = sum(types.values())
        return {
            "lines": len(self.lines),
            "notes": total,
            "types": types,
            "x_min": min(xs) if xs else 0,
            "x_max": max(xs) if xs else 0,
            "duration": self.duration,
            "avg_nps": round(total / self.duration, 2) if self.duration else 0,
        }

    # ---- 输出 ----
    def to_dict(self) -> Dict[str, Any]:
        return {
            "BPMList": sorted(self.bpm_list, key=lambda x: parse_bt(x["startTime"])),
            "META": dict(self.meta),
            "chartTime": float(self.duration),
            "judgeLineGroup": list(self.groups),
            "judgeLineList": [ln.to_dict() for ln in self.lines],
            "multiLineString": "",
            "multiScale": 1.0,
        }

    def save(self, path: str = "chart.json") -> str:
        _write_json(path, self.to_dict())
        return path

    def save_extra(self, path: str = "extra.json") -> Optional[str]:
        if not self.effects:
            return None
        _write_json(path, {
            "bpm": [{"time": e["startTime"], "bpm": e["bpm"]} for e in self.bpm_list],
            "effects": self.effects,
        })
        return path

    def save_info(self, path: str = "info.yml", **overrides) -> str:
        data = {
            "id": overrides.get("id", 88001),
            "uploader": overrides.get("uploader", 1233),
            "name": self.name,
            "difficulty": self.difficulty,
            "level": self.level,
            "charter": self.charter,
            "composer": self.composer,
            "illustrator": self.illustrator,
            "chart": overrides.get("chart", "chart.json"),
            "format": None,
            "music": self.song,
            "illustration": overrides.get("illustration", "illustration.png"),
            "unlockVideo": None,
            "previewStart": overrides.get("previewStart", 0.0),
            "previewEnd": None,
            "aspectRatio": overrides.get("aspectRatio", 1.0),
            "backgroundDim": overrides.get("backgroundDim", 0.6),
            "lineLength": overrides.get("lineLength", 6.0),
            "offset": self.offset_s,
            "tip": overrides.get("tip", ""),
            "tags": overrides.get("tags", ["Phira"]),
            "intro": overrides.get("intro", ""),
            "holdPartialCover": False,
            "noteUniformScale": False,
            "forceAspectRatio": False,
            "useRpe170Speed": None,
            "useAttachUiFix": True,
        }
        _write_yaml(path, data)
        return path


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _write_yaml(path: str, data: Dict[str, Any]) -> None:
    try:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False)
    except ImportError:
        with open(path, "w", encoding="utf-8") as f:
            for k, v in data.items():
                f.write(f"{k}: {_yaml_scalar(v)}\n")


def _yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#{}[]&*!|>'\"%@`") or s.strip() != s:
        return "'" + s.replace("'", "''") + "'"
    return s
