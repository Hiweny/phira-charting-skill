#!/usr/bin/env python3
"""Phira/RPE 谱面离屏预览渲染器（自检用，不依赖 Phira 客户端）。

用途：把 chart.json 直接画成"接近 Phigros 观感"的画面，输出截图 / 联系表 / 视频，
用来回答四个问题：

  1. 音符有没有黏在判定线上？（音符下落是否正常）
  2. 有没有看不见的音符？（越界 / alpha 隐藏 / 被线遮挡）
  3. 判定线到底在动吗？动得够不够开？（覆盖范围 / 事件密度）
  4. 高潮段和安静段的画面差异是否成立？（NPS / 线运动 / 特效）

注意：这是**近似渲染**（不含官方资源包贴图、不含自定义 shader、不含 3D 透视），
用于设计自检；最终判定仍以 Phira 实机为准。精确渲染见
docs/06-qc/02-visual-selfcheck.md（phichain-renderer / prpr-render / phira-render）。

用法：
    # 单帧
    python3 tools/preview_render.py my-chart --frame 42.5 -o shot.png

    # 联系表（12 帧，一眼看全曲的舞台变化）
    python3 tools/preview_render.py my-chart --contact-sheet sheet.png

    # 导出视频（含音频，需要 ffmpeg）
    python3 tools/preview_render.py my-chart --video out.mp4 --from 30 --to 60 --fps 30

    # 量化统计（JSON）
    python3 tools/preview_render.py my-chart --stats
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# ---------------------------------------------------------------- 常量

RPE_W, RPE_H = 1350.0, 900.0        # RPE 坐标系（x ∈ ±675，y ∈ ±450）
HALF_W, HALF_H = RPE_W / 2, RPE_H / 2

# prpr 源码 prpr/src/parse/rpe.rs：const SPEED_RATIO = 10 / 45 / HEIGHT_RATIO
HEIGHT_RATIO = 0.83175
SPEED_RATIO = 10.0 / 45.0 / HEIGHT_RATIO   # ≈ 0.2671

TEXT_PX = 26.0                     # 文字线字号（逻辑像素，prpr 固定不可调）

# prpr/src/core.rs: NOTE_WIDTH_RATIO_BASE = 0.13175016
# draw_center 的 dest_size = 2 * scale，所以音符全宽约 0.2635 个世界单位。
NOTE_W_WORLD = 0.2635
LINE_LEN_DEFAULT = 6.0             # info.yml lineLength 缺省值（世界单位）

NOTE_COLORS = {
    1: (75, 160, 229),     # Tap  默认皮肤 click.png
    2: (228, 238, 250),    # Hold 默认皮肤 hold.png（近白）
    3: (213, 30, 30),      # Flick 默认皮肤 flick.png
    4: (228, 196, 66),     # Drag 默认皮肤 drag.png
}
NOTE_NAMES = {1: "Tap", 2: "Hold", 3: "Flick", 4: "Drag"}


# ---------------------------------------------------------------- 时间系统


def tri(v) -> float:
    """[whole, num, den] → beat。den 必须 ≥ 1。"""
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return 0.0
    w, n, d = v
    if d == 0:
        return float(w)
    return float(w) + float(n) / float(d)


class Timing:
    """beat ↔ 秒。支持多 BPM 段。"""

    def __init__(self, bpm_items: list[dict]):
        items = sorted(
            ((tri(it.get("startTime")), float(it.get("bpm", 120))) for it in bpm_items or []),
            key=lambda x: x[0],
        )
        if not items:
            items = [(0.0, 120.0)]
        self.items = items
        # 段起始秒
        self.seg_sec = [0.0]
        for i in range(1, len(items)):
            b0, bpm = items[i - 1]
            b1, _ = items[i]
            self.seg_sec.append(self.seg_sec[-1] + (b1 - b0) * 60.0 / bpm)

    def beat_at(self, sec: float) -> float:
        idx = 0
        for i, t0 in enumerate(self.seg_sec):
            if sec >= t0:
                idx = i
            else:
                break
        b0, bpm = self.items[idx]
        return b0 + (sec - self.seg_sec[idx]) * bpm / 60.0

    def sec(self, beat: float) -> float:
        idx = 0
        for i, (b0, _) in enumerate(self.items):
            if beat >= b0:
                idx = i
            else:
                break
        b0, bpm = self.items[idx]
        return self.seg_sec[idx] + (beat - b0) * 60.0 / bpm

    @property
    def max_bpm(self):
        return max(b for _, b in self.items)


# ---------------------------------------------------------------- 缓动

def ease(kind: int, p: float) -> float:
    """RPE easingType，严格对齐 Phira 官方表

    https://teamflos.github.io/phira-docs/en/chart-standard/chart-format/rpe/extend.html
    1 Linear · 2 OutSine · 3 InSine · 4 OutQuad · 5 InQuad · 6 InOutSine
    7 InOutQuad · 8 OutCubic · 9 InCubic · 10 OutQuart · 11 InQuart
    12 InOutCubic · 13 InOutQuart · 14 OutQuint · 15 InQuint
    16 OutExpo · 17 InExpo · 18 OutCirc · 19 InCirc · 20 OutBack
    21 InBack · 22 InOutCirc · 23 InOutBack · 24 OutElastic
    25 InElastic · 26 OutBounce · 27 InBounce · 28 InOutBounce · 29 InOutElastic
    """
    p = max(0.0, min(1.0, p))
    if kind <= 0:                                            # fixed
        return 0.0 if p < 1 else 1.0
    if kind == 1:
        return p                                             # Linear
    if kind == 2:
        return math.sin(p * math.pi / 2)                     # OutSine
    if kind == 3:
        return 1 - math.cos(p * math.pi / 2)                 # InSine
    if kind == 4:
        return 1 - (1 - p) ** 2                              # OutQuad
    if kind == 5:
        return p ** 2                                        # InQuad
    if kind == 6:
        return -(math.cos(math.pi * p) - 1) / 2              # InOutSine
    if kind == 7:
        return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2
    if kind == 8:
        return 1 - (1 - p) ** 3                              # OutCubic
    if kind == 9:
        return p ** 3                                        # InCubic
    if kind == 10:
        return 1 - (1 - p) ** 4                              # OutQuart
    if kind == 11:
        return p ** 4                                        # InQuart
    if kind == 12:
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if kind == 13:
        return 8 * p ** 4 if p < 0.5 else 1 - (-2 * p + 2) ** 4 / 2
    if kind == 14:
        return 1 - (1 - p) ** 5                              # OutQuint
    if kind == 15:
        return p ** 5                                        # InQuint
    if kind == 16:
        return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)         # OutExpo
    if kind == 17:
        return 0.0 if p <= 0 else 2 ** (10 * p - 10)         # InExpo
    if kind == 18:
        return math.sqrt(max(0.0, 1 - (p - 1) ** 2))         # OutCirc
    if kind == 19:
        return 1 - math.sqrt(max(0.0, 1 - p * p))            # InCirc
    if kind == 20:
        return 1 + 2.70158 * (p - 1) ** 3 + 1.70158 * (p - 1) ** 2   # OutBack
    if kind == 21:
        return 2.70158 * p ** 3 - 1.70158 * p ** 2           # InBack
    if kind == 22:
        if p < 0.5:
            return (1 - math.sqrt(max(0.0, 1 - (2 * p) ** 2))) / 2
        return (math.sqrt(max(0.0, 1 - (-2 * p + 2) ** 2)) + 1) / 2
    if kind == 23:
        if p < 0.5:
            return ((2 * p) ** 2 * ((2.5949095 + 1) * 2 * p - 2.5949095)) / 2
        return ((2 * p - 2) ** 2 * ((2.5949095 + 1) * (p * 2 - 2) + 2.5949095) + 2) / 2
    if kind == 24:
        if p in (0.0, 1.0):
            return p
        return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi / 3)) + 1
    if kind == 25:
        if p in (0.0, 1.0):
            return p
        return -2 ** (10 * p - 10) * math.sin((p * 10 - 10.75) * (2 * math.pi / 3))
    if kind == 26:
        return _bounce(p)                                    # OutBounce
    if kind == 27:
        return 1 - _bounce(1 - p)                            # InBounce
    if kind == 28:
        if p < 0.5:
            return (1 - _bounce(1 - 2 * p)) / 2
        return (1 + _bounce(2 * p - 1)) / 2
    if kind == 29:
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            return 1.0
        if p < 0.5:
            return -(2 ** (20 * p - 10) * math.sin((20 * p - 11.125) * (2 * math.pi / 4.5))) / 2
        return (2 ** (-20 * p + 10) * math.sin((20 * p - 11.125) * (2 * math.pi / 4.5))) / 2 + 1
    return p


def _bounce(t: float) -> float:
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


def lerp(a, b, p):
    return a + (b - a) * p


# ---------------------------------------------------------------- 读取工程


@dataclass
class Project:
    root: Path
    info: dict
    chart: dict
    music: Path | None = None
    illustration: Path | None = None
    extra: dict | None = None
    chart_path: Path | None = None


def _find_chart(root: Path, info: dict) -> Path:
    name = info.get("chart") or info.get("Chart")
    if name and (root / name).exists():
        return root / name
    cands = [p for p in root.glob("*.json") if p.name.lower() not in ("extra.json",)]
    if not cands:
        raise FileNotFoundError(f"{root} 下找不到谱面 JSON")
    cands.sort(key=lambda p: p.stat().st_size, reverse=True)
    return cands[0]


def load_project(path: str | Path) -> Project:
    src = Path(path)
    tmp = None
    if src.is_file() and src.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="phira_preview_"))
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        root = tmp
    elif src.is_dir():
        root = src
    else:
        raise FileNotFoundError(f"找不到工程：{src}")

    info: dict = {}
    for n in ("info.yml", "info.yaml"):
        if (root / n).exists():
            info = yaml.safe_load((root / n).read_text(encoding="utf-8")) or {}
            break
    if not info:
        # 旧版 Phira/Phi info.txt（大写字段）
        p = root / "info.txt"
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if ":" in line and not line.startswith("#"):
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()

    chart_path = _find_chart(root, info)
    chart = json.loads(chart_path.read_text(encoding="utf-8"))

    def _res(key: str) -> Path | None:
        v = info.get(key) or info.get(key.capitalize())
        if v and (root / v).exists():
            return root / v
        return None

    music = _res("music") or _res("song")
    illustration = _res("illustration") or _res("picture")
    if illustration is None:
        for p in root.iterdir():
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                illustration = p
                break

    extra = None
    for n in ("extra.json",):
        if (root / n).exists():
            try:
                extra = json.loads((root / n).read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                extra = None

    return Project(root, info, chart, music, illustration, extra, chart_path)


# ---------------------------------------------------------------- 谱面求值


def _bpm_list(chart: dict) -> list[dict]:
    for k in ("bpmList", "BPMList"):
        if chart.get(k):
            return chart[k]
    return []


def _line_list(chart: dict) -> list[dict]:
    for k in ("judgeLineList", "JudgeLineList"):
        if chart.get(k):
            return chart[k]
    return []


def _meta(chart: dict) -> dict:
    return chart.get("META") or chart.get("meta") or {}


def _duration(chart: dict, proj: Project) -> float:
    m = _meta(chart)
    for v in (m.get("duration"), proj.info.get("length")):
        try:
            if float(v) > 0:
                return float(v)
        except (TypeError, ValueError):
            pass
    # 回退：最后一个音符/事件
    last = 0.0
    for L in _line_list(chart):
        for n in L.get("notes") or []:
            last = max(last, tri(n.get("endTime")) if n.get("type") == 2 else tri(n.get("startTime")))
        for lay in L.get("eventLayers") or []:
            if not isinstance(lay, dict):
                continue
            for k in ("alphaEvents", "moveXEvents", "moveYEvents", "rotateEvents", "speedEvents"):
                for e in lay.get(k) or []:
                    last = max(last, tri(e.get("endTime")))
    return last


class Ctl:
    """posControl / alphaControl / yControl / sizeControl / skewControl 求值。"""

    DEFAULT = {"pos": 1.0, "alpha": 1.0, "y": 1.0, "size": 1.0, "skew": 0.0}

    @staticmethod
    def at_x(entries: list[dict] | None, key: str, x: float) -> float:
        """按 note 的行进高度（RPE 像素）求值，而不是按时间。

        prpr 的 `CtrlObject::set_height` 把 alpha/size/pos/y 控制事件绑在
        **音符离判定线的距离**上：越远的 note 用越靠后的关键帧。
        这正是"距离雾 / 透视缩放 / 扇阵收放"能实现的原因。
        """
        d = Ctl.DEFAULT.get(key, 1.0)
        if not entries:
            return d
        pts = []
        for e in entries:
            kx = float(e.get("x", 0))
            if kx > 9e6:
                continue
            pts.append((kx, float(e.get(key, d)), int(e.get("easing", 1))))
        if not pts:
            return d
        pts.sort(key=lambda p: p[0])
        if x <= pts[0][0]:
            return pts[0][1]
        for i in range(len(pts) - 1):
            x0, v0, es = pts[i]
            x1, v1, _ = pts[i + 1]
            if x0 <= x <= x1:
                if x1 - x0 <= 1e-9:
                    return v1
                return lerp(v0, v1, ease(es, (x - x0) / (x1 - x0)))
        return pts[-1][1]

    @staticmethod
    def value(entries: list[dict] | None, key: str, t_sec: float, timing: Timing) -> float:
        d = Ctl.DEFAULT.get(key, 0.0)
        if not entries:
            return d
        pts = []
        for e in entries:
            x = float(e.get("x", 0))
            if x > 9e6:
                continue
            v = float(e.get(key, d))
            pts.append((x, v, int(e.get("easing", 1))))
        if not pts:
            return d
        # Ex-Phiedit / RPE 导出常用 [0, 9999999] + 值 1.0 表示"未设置"，回落到默认值
        if len(pts) == 1 and abs(pts[0][1] - 1.0) < 1e-6:
            return d
        # x 若像秒就按秒，否则按 beat（真实谱面两种都有）
        beat_mode = max(x for x, _, _ in pts) < 1e6 and max(x for x, _, _ in pts) > 4.0
        pts = [(timing.sec(x) if beat_mode else x, v, es) for x, v, es in pts]
        pts.sort(key=lambda p: p[0])
        if t_sec <= pts[0][0]:
            return pts[0][1]
        for i in range(len(pts) - 1):
            t0, v0, es = pts[i]
            t1, v1, _ = pts[i + 1]
            if t0 <= t_sec <= t1:
                if t1 - t0 <= 1e-9:
                    return v1
                p = (t_sec - t0) / (t1 - t0)
                return lerp(v0, v1, ease(es, p))
        return pts[-1][1]


def _events_value(events: list[dict] | None, t_sec: float, timing: Timing, default: float = 0.0) -> float:
    if not events:
        return default
    evs = []
    for e in events:
        evs.append(
            (
                timing.sec(tri(e.get("startTime"))),
                timing.sec(tri(e.get("endTime"))),
                float(e.get("start", default)),
                float(e.get("end", default)),
                int(e.get("easingType", 1)),
            )
        )
    evs.sort(key=lambda x: x[0])
    # 多个事件首尾相接时取当前生效的那个；空档保持上一个 end
    cur = default
    for t0, t1, v0, v1, es in evs:
        if t_sec < t0:
            return cur
        if t1 <= t0:
            cur = v1
            continue
        if t_sec <= t1:
            return lerp(v0, v1, ease(es, (t_sec - t0) / (t1 - t0)))
        cur = v1
    return cur


def _layers_sum(line: dict, key: str, t: float, timing: Timing, factor: float = 1.0) -> float:
    total = 0.0
    for lay in line.get("eventLayers") or []:
        if isinstance(lay, dict):
            total += _events_value(lay.get(key), t, timing) * factor
    return total


def _blank_alpha(events) -> bool:
    """编辑器写的空白占位：全部关键帧都是 0 -> 0，等价于"这个通道没设过"。

    RPE 保存时经常给没用到的图层写上 `{"start":0,"end":0}`。
    如果当成真的 0，整条线（以及挂在上面的所有 note）都会消失。
    """
    if not events:
        return True
    for e in events:
        if not isinstance(e, dict):
            return False
        if float(e.get("start", 0) or 0) != 0.0 or float(e.get("end", 0) or 0) != 0.0:
            return False
    return True


def _layers_alpha(line: dict, t: float, timing: Timing) -> float:
    """RPE 的多个 eventLayer 是**叠加**关系（与 prpr 的 AnimFloat::chain 一致）。

    没有 alphaEvents 的图层不参与计算；全 0 占位的事件同样不参与
    （见 `_blank_alpha`）。有事件的图层把 0~255 归一化后相加，最后 clamp 到 1。
    """
    vals = []
    for lay in line.get("eventLayers") or []:
        if isinstance(lay, dict) and lay.get("alphaEvents"):
            if _blank_alpha(lay.get("alphaEvents")):
                continue
            v = _events_value(lay.get("alphaEvents"), t, timing, 255.0)
            vals.append(max(0.0, min(1.0, v / 255.0 if v > 1.5 else v)))
    if not vals:
        return 1.0
    return max(0.0, min(1.0, sum(vals)))


def _ext_scalar(line: dict, key: str, t: float, timing: Timing, default: float = 1.0) -> float:
    """RPE 1.6 扩展事件（scaleX / scaleY / incline / gif）求值。

    与普通 *Control 不同，扩展事件直接内联在 `line["extended"]` 里，
    元素形如 {"startTime":[..], "endTime":[..], "start":0.7, "end":0.7}。
    """
    ev = (line.get("extended") or {}).get(key)
    if not ev:
        return default
    return _events_value(ev, t, timing, default)


def _ext_color(line: dict, t: float, timing: Timing) -> tuple[float, float, float]:
    """colorEvents 求值（RGB 0~255）。多个关键帧之间线性插值。"""
    ev = (line.get("extended") or {}).get("colorEvents")
    if not ev:
        return (1.0, 1.0, 1.0)

    def _c(v):
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            return [float(x) / 255.0 for x in v[:3]]
        if isinstance(v, (int, float)):
            return [float(v)] * 3
        return [1.0, 1.0, 1.0]

    pts = []
    for e in ev:
        try:
            pts.append((tri(e["startTime"]), _c(e.get("start"))))
        except (KeyError, TypeError, ValueError):
            continue
    if not pts:
        return (1.0, 1.0, 1.0)
    pts.sort(key=lambda p: p[0])
    beat = timing.beat_at(t)
    if beat <= pts[0][0]:
        return tuple(pts[0][1])
    for i in range(len(pts) - 1):
        b0, c0 = pts[i]
        b1, c1 = pts[i + 1]
        if b0 <= beat <= b1:
            p = 0.0 if b1 == b0 else (beat - b0) / (b1 - b0)
            return (c0[0] + (c1[0] - c0[0]) * p,
                    c0[1] + (c1[1] - c0[1]) * p,
                    c0[2] + (c1[2] - c0[2]) * p)
    return tuple(pts[-1][1])


# 文字线字体：优先 CJK，保证中日文不糊成方块
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto-cjk-otf/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf",
)
_FONT_CACHE: dict = {}


def _load_font(px: int):
    if px in _FONT_CACHE:
        return _FONT_CACHE[px]
    font = None
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, px)
                break
            except Exception:  # noqa: BLE001
                continue
    if font is None:
        try:
            font = ImageFont.load_default(px)
        except Exception:  # noqa: BLE001
            font = None
    _FONT_CACHE[px] = font
    return font


def _ext_text(line: dict, t: float, timing: Timing) -> str:
    """textEvents 求值：字符串不插值，而是按进度"逐字显现"。

    RPE/prpr 里 `start` 与 `end` 是同一段文本的两个状态：
    `start: ""` → 打字机；`start == end` → 静态显示。
    事件结束后保持最后一段文本（与其它通道的 hold 语义一致）。
    """
    ev = (line.get("extended") or {}).get("textEvents")
    if not ev:
        return ""
    cur = ""
    for e in sorted(ev, key=lambda x: tri(x.get("startTime"))):
        try:
            b0 = tri(e.get("startTime"))
            b1 = tri(e.get("endTime"))
        except (KeyError, TypeError, ValueError):
            continue
        s = str(e.get("start") or "")
        d = str(e.get("end") or "")
        beat = timing.beat_at(t)
        if beat < b0:
            break
        if b1 <= b0 or beat >= b1:
            cur = d
            continue
        p = (beat - b0) / (b1 - b0)
        if s == d:
            cur = d
        elif not s:                      # 打字机
            n = int(round(p * len(d)))
            cur = d[:n]
        else:                            # 有初值：按目标长度逐字覆盖
            n = int(round(p * len(d)))
            cur = d[:n] or s
    return cur


class SpeedField:
    """把 speedEvents 积分成"下落高度场" H(t)。

    RPE 的默认速度是 10（编辑器默认值），prpr 里统一乘 SPEED_RATIO 转成
    "单位/秒"。这里用固定步长数值积分，保证没有 speedEvents 的线也有正常下落。
    """

    DEFAULT_RAW_SPEED = 10.0

    def __init__(self, line: dict, timing: Timing, end: float):
        self.timing = timing
        self.end = max(1.0, end)
        segs = []
        for lay in line.get("eventLayers") or []:
            if not isinstance(lay, dict):
                continue
            for e in lay.get("speedEvents") or []:
                t0 = timing.sec(tri(e.get("startTime")))
                t1 = timing.sec(tri(e.get("endTime")))
                segs.append((t0, t1, float(e.get("start", self.DEFAULT_RAW_SPEED)),
                             float(e.get("end", self.DEFAULT_RAW_SPEED))))
        segs.sort(key=lambda x: x[0])
        self.segs = [s for s in segs if s[1] > s[0]]
        self.dt = 1.0 / 120.0
        self.h = [0.0]
        steps = int((self.end + 2.0) / self.dt) + 2
        h = 0.0
        for i in range(steps):
            t = i * self.dt
            h += self._raw_speed(t) * SPEED_RATIO * self.dt
            self.h.append(h)

    def _raw_speed(self, t: float) -> float:
        cur = self.DEFAULT_RAW_SPEED
        for t0, t1, v0, v1 in self.segs:
            if t < t0:
                break
            if t <= t1:
                p = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                return lerp(v0, v1, p)
            cur = v1
        return cur

    def H(self, t: float) -> float:
        if t <= 0:
            return 0.0
        i = t / self.dt
        i0 = int(i)
        if i0 + 1 >= len(self.h):
            return self.h[-1]
        frac = i - i0
        return lerp(self.h[i0], self.h[i0 + 1], frac)


def _nofly(line: dict, timing: Timing, end: float) -> SpeedField:
    return SpeedField(line, timing, end)


# ---------------------------------------------------------------- 绘制


def _fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    iw, ih = img.size
    s = max(w / iw, h / ih)
    img = img.resize((int(iw * s) + 1, int(ih * s) + 1), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _fit_screen(img: Image.Image, w: int, h: int, mode: str) -> Image.Image:
    """prpr ScaleType：cropCenter=铺满裁剪；inside=完整放入；fit=拉伸铺满。"""
    mode = (mode or "cropCenter").lower()
    if mode == "fit":
        return img.resize((w, h), Image.LANCZOS)
    iw, ih = img.size
    if mode == "inside":
        s = min(w / iw, h / ih)
        out = img.resize((max(1, int(iw * s)), max(1, int(ih * s))), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        canvas.paste(out, ((w - out.width) // 2, (h - out.height) // 2))
        return canvas
    return _fit_cover(img, w, h)


def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


class Renderer:
    def __init__(self, proj: Project, width=1350, height=900, hud=True, speed_mul=1.0):
        self.proj = proj
        self.speed_mul = speed_mul
        self.w, self.h = width, height
        self.sx, self.sy = width / RPE_W, height / RPE_H
        self.hud = hud
        chart = proj.chart
        self.timing = Timing(_bpm_list(chart))
        self.lines = _line_list(chart)
        m = _meta(chart)
        self.duration = _duration(chart, proj)
        self.offset = float(m.get("offset") or proj.info.get("offset") or 0.0) / 1000.0
        self.bg_dim = float(proj.info.get("backgroundDim") or 0.6)
        self.line_len = float(proj.info.get("lineLength") or LINE_LEN_DEFAULT)
        self.bg = None
        if proj.illustration and proj.illustration.exists():
            try:
                self.bg = _fit_cover(Image.open(proj.illustration).convert("RGB"), width, height)
            except Exception:  # noqa: BLE001
                self.bg = None
        self._speed = [_nofly(L, self.timing, self.duration + 2) for L in self.lines]
        # note 预处理
        self.notes = []
        for li, L in enumerate(self.lines):
            for n in L.get("notes") or []:
                try:
                    self.notes.append(
                        {
                            "line": li,
                            "t": self.timing.sec(tri(n.get("startTime"))),
                            "te": self.timing.sec(tri(n.get("endTime"))),
                            "x": float(n.get("positionX", 0)),
                            "type": int(n.get("type", 1)),
                            "above": int(n.get("above", 1)),
                            "alpha": float(n.get("alpha", 255)) / 255.0,
                            "fake": int(n.get("isFake", 0)),
                            "size": float(n.get("size", 1.0)) or 1.0,
                            "speed": float(n.get("speed", 1.0)) or 1.0,
                            "yoff": float(n.get("yOffset", 0)) or 0.0,
                            "visible": float(n.get("visibleTime", 999999)) or 999999.0,
                        }
                    )
                except Exception:  # noqa: BLE001
                    continue
        self.notes.sort(key=lambda n: n["t"])
        self.effects = self._parse_effects(proj.extra)
        # RPE 1.7 也会把 effects 写在 chart.json 顶层；两处合并去重
        for e in self._parse_effects({"effects": (chart or {}).get("effects") or []}):
            if not any(abs(e["t0"] - o["t0"]) < 1e-6 and e["shader"] == o["shader"] for o in self.effects):
                self.effects.append(e)
        self.effects.sort(key=lambda x: x["t0"])
        self._tex_cache: dict[str, Image.Image | None] = {}
        self._tex_scaled: dict[tuple, Image.Image] = {}
        self.videos = self._parse_videos(proj.extra)
        self._vid_cache: dict[tuple, Image.Image | None] = {}
        self.texture_lines = sum(1 for L in self.lines if (L.get("Texture") or "").strip())

    # -- 贴图（RPE 1.6 图片判定线）--
    def tex_image(self, name: str, frame: int = 0):
        """加载贴图（带缓存）。贴图的像素尺寸与逻辑坐标 1:1 对应。

        GIF 会缓存全部帧；`frame` 选定帧序号（由 `gifEvents` 的进度决定）。
        """
        key = (name, frame) if name.lower().endswith(".gif") else name
        if key in self._tex_cache:
            return self._tex_cache[key]
        path = self.proj.root / name
        img = None
        if path.exists():
            try:
                im = Image.open(path)
                n = getattr(im, "n_frames", 1)
                if n > 1:
                    im.seek(max(0, min(n - 1, int(frame))))
                img = im.convert("RGBA")
            except Exception:  # noqa: BLE001
                img = None
        self._tex_cache[key] = img
        return img

    def gif_frame_index(self, line: dict, t: float) -> int:
        """`gifEvents` 的值是 0~1 的播放进度，换算成帧序号。"""
        tex = (line.get("Texture") or "")
        if not tex.lower().endswith(".gif"):
            return 0
        path = self.proj.root / tex
        n = 1
        try:
            if path.exists():
                im = Image.open(path)
                n = max(1, getattr(im, "n_frames", 1))
        except Exception:  # noqa: BLE001
            n = 1
        p = _ext_scalar(line, "gifEvents", t, self.timing, -1.0)
        if p < 0:
            p = 0.0
        return int(round(max(0.0, min(1.0, p)) * (n - 1)))

    # -- 视频图层（extra.json videos，prpr feature=video）--
    def _parse_videos(self, extra: dict | None) -> list[dict]:
        out = []
        for v in (extra or {}).get("videos") or []:
            try:
                t0 = self.timing.sec(v.get("time") or [0, 0, 1])
            except Exception:  # noqa: BLE001
                t0 = 0.0
            st = (v.get("scale") or "cropCenter")
            if isinstance(st, dict):
                st = st.get("type", "cropCenter")
            out.append({"path": v.get("path") or "", "t0": t0, "scale": st,
                        "alpha": v.get("alpha", 1.0), "dim": v.get("dim", 0.0),
                        "attach": v.get("attach")})
        return out

    def _anim_value(self, v, t: float, default: float) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return Ctl.value(v, "value", t, self.timing)
        return default

    def video_frame(self, path: str, rel_t: float):
        """用 ffmpeg 按需抽帧（0.1s 缓存）；没有 ffmpeg 则返回 None。"""
        key = (path, round(rel_t, 1))
        if key in self._vid_cache:
            return self._vid_cache[key]
        if len(self._vid_cache) > 120:
            self._vid_cache.clear()
        src = self.proj.root / path
        img = None
        if src.exists() and shutil.which("ffmpeg"):
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp = f.name
                r = subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, rel_t):.3f}",
                     "-i", str(src), "-frames:v", "1", tmp],
                    capture_output=True, timeout=20,
                )
                if r.returncode == 0:
                    img = Image.open(tmp).convert("RGB")
                os.unlink(tmp)
            except Exception:  # noqa: BLE001
                img = None
        self._vid_cache[key] = img
        return img

    def draw_videos(self, img: Image.Image, t: float) -> Image.Image:
        """videos：attach 为空时全屏；attach=线号时跟随该线的位姿（近似）。"""
        if not self.videos:
            return img
        for v in self.videos:
            rel = t - v["t0"]
            if rel < 0:
                continue
            frame = self.video_frame(v["path"], rel)
            if frame is None:
                continue
            mode = str(v.get("scale") or "cropCenter")
            if v.get("attach") is not None:
                try:
                    li = int(v["attach"])
                except (TypeError, ValueError):
                    li = -1
                if 0 <= li < len(self.lines):
                    x, y, rot, _a, size = self.line_state(self.lines[li], t)
                    layer = _fit_screen(frame, self.w, self.h, mode)
                    k = max(0.05, size)
                    layer = layer.resize((max(1, int(self.w * k)), max(1, int(self.h * k))), Image.BILINEAR)
                    layer = layer.rotate(rot, resample=Image.BICUBIC, expand=False,
                                         center=(layer.width / 2, layer.height / 2))
                    base = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
                    cx, cy = (HALF_W + x) * self.sx, (HALF_H - y) * self.sy
                    base.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)
                    frame = base.convert("RGB")
                else:
                    frame = _fit_screen(frame, self.w, self.h, mode)
            else:
                frame = _fit_screen(frame, self.w, self.h, mode)
            alpha = max(0.0, min(1.0, self._anim_value(v.get("alpha"), t, 1.0)))
            dim = max(0.0, min(1.0, self._anim_value(v.get("dim"), t, 0.0)))
            if alpha <= 0.01:
                continue
            arr = frame.convert("RGB")
            if dim > 0:
                arr = Image.blend(arr, Image.new("RGB", arr.size, (0, 0, 0)), dim)
            img = Image.blend(img.convert("RGB"), arr, alpha)
        return img

    def _scaled_tex(self, name: str, sx: float, sy: float, frame: int = 0):
        src = self.tex_image(name, frame)
        if src is None:
            return None
        w = max(1, int(round(src.width * abs(sx))))
        h = max(1, int(round(src.height * abs(sy))))
        if w > 4096 or h > 4096:
            w = min(w, 4096)
            h = min(h, 4096)
        key = (name, w, h, frame)
        out = self._tex_scaled.get(key)
        if out is None:
            out = src.resize((w, h), Image.LANCZOS if (w * h) < 4_000_000 else Image.BILINEAR)
            self._tex_scaled[key] = out
        return out

    def draw_paint(self, img: Image.Image, L: dict, st, t: float) -> bool:
        """Paint 线：整屏被一个圆形填满/收束（iris 转场），无需贴图。

        `paintEvents` 的值是**像素半径**，`-1` 为编辑器写下的"未设置"哨兵。
        """
        r = _ext_scalar(L, "paintEvents", t, self.timing, -1.0)
        if r <= 0:
            return False
        x, y, _rot, a, _size = st
        cx, cy = (HALF_W + x) * self.sx, (HALF_H - y) * self.sy
        cr, cg, cb = _ext_color(L, t, self.timing)
        col = (int(cr * 255), int(cg * 255), int(cb * 255), int(255 * a))
        rr = r * self.sy
        draw = ImageDraw.Draw(img, "RGBA")
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
        return True

    def draw_text(self, img: Image.Image, L: dict, st, t: float) -> bool:
        """Text 线：居中渲染，字号固定，排版只能靠空格与换行。"""
        s = _ext_text(L, t, self.timing)
        if not s:
            return False
        x, y, _rot, a, _size = st
        if a <= 0.01:
            return False
        cr, cg, cb = _ext_color(L, t, self.timing)
        col = (int(cr * 255), int(cg * 255), int(cb * 255), int(255 * min(1.0, a)))
        px = max(8, int(round(TEXT_PX * self.sy)))
        font = _load_font(px)
        if font is None:
            return False
        cx, cy = (HALF_W + x) * self.sx, (HALF_H - y) * self.sy
        lines = s.split("\n")
        lh = px * 1.32
        top = cy - lh * (len(lines) - 1) / 2.0
        draw = ImageDraw.Draw(img, "RGBA")
        for i, line in enumerate(lines):
            draw.text((cx, top + i * lh), line, font=font, fill=col, anchor="mm")
        return True

    def draw_texture(self, img: Image.Image, L: dict, st, t: float):
        """把判定线当图片图层画出来：位置/旋转/缩放/裁切/染色/透明度。"""
        name = (L.get("Texture") or "").strip()
        if not name:
            return False
        x, y, rot, a, size = st
        gframe = self.gif_frame_index(L, t)
        # prpr：贴图线 scale = 事件值 * 2 / RPE_WIDTH（世界单位）；
        # 世界单位 → 预览像素是 w/2，所以源图像素 × w/1350。
        k = self.w / RPE_W
        sx = _ext_scalar(L, "scaleXEvents", t, self.timing, 1.0)
        sy = _ext_scalar(L, "scaleYEvents", t, self.timing, 1.0)
        sprite = self._scaled_tex(name, size * k, sy * k, gframe)
        if sprite is None:
            return False

        # incline：水平剪切（角度制）
        inc = _ext_scalar(L, "inclineEvents", t, self.timing, 0.0)
        if abs(inc) > 0.01:
            k = math.tan(math.radians(max(-80.0, min(80.0, inc))))
            sprite = sprite.transform(sprite.size, Image.AFFINE, (1, k, -k * sprite.height / 2, 0, 1, 0))

        # 染色
        r, g, b = _ext_color(L, t, self.timing)
        if abs(r - 1) > 0.01 or abs(g - 1) > 0.01 or abs(b - 1) > 0.01:
            tint = Image.new("RGB", sprite.size, (int(r * 255), int(g * 255), int(b * 255)))
            rgb = ImageChops.multiply(sprite.convert("RGB"), tint)
            sprite = Image.merge("RGBA", (*rgb.split(), sprite.getchannel("A")))

        if a < 0.999:
            al = sprite.getchannel("A").point(lambda v: int(v * a))
            sprite = sprite.copy()
            sprite.putalpha(al)

        if abs(rot) > 0.01:
            sprite = sprite.rotate(rot, resample=Image.BICUBIC, expand=True)

        ax, ay = (L.get("anchor") or [0.5, 0.5])[:2]
        cx = (HALF_W + x) * self.sx
        cy = (HALF_H - y) * self.sy
        ox = (ax - 0.5) * sprite.width
        oy = (ay - 0.5) * sprite.height
        left = int(cx - sprite.width / 2 - ox)
        top = int(cy - sprite.height / 2 - oy)
        if left > self.w or top > self.h or left + sprite.width < 0 or top + sprite.height < 0:
            return True
        img.paste(sprite, (left, top), sprite)
        return True

    # -- 状态求值 --
    def line_state(self, L: dict, t: float):
        """线的位姿。

        RPE 的 posControl / sizeControl / alphaControl / yControl **不是线的属性**，
        而是"线上所有音符"的属性（按音符行进距离求值，见 Ctl.at_x），
        这里绝不能拿来改线本身，否则整条线会错误平移/缩放。
        """
        x = _layers_sum(L, "moveXEvents", t, self.timing)
        y = _layers_sum(L, "moveYEvents", t, self.timing)
        rot = -_layers_sum(L, "rotateEvents", t, self.timing)
        size = abs(_ext_scalar(L, "scaleXEvents", t, self.timing, 1.0))
        alpha = _layers_alpha(L, t, self.timing)
        return x, y, rot, alpha, size

    def note_ctrl(self, ni: int, dist: float) -> tuple[float, float, float, float]:
        """按距离求 ctrl：返回 (alpha, size, pos, y)。"""
        L = self.lines[self.notes[ni]["line"]]
        a = Ctl.at_x(L.get("alphaControl"), "alpha", abs(dist))
        s = Ctl.at_x(L.get("sizeControl"), "size", abs(dist))
        p = Ctl.at_x(L.get("posControl"), "pos", abs(dist))
        yy = Ctl.at_x(L.get("yControl"), "y", abs(dist))
        return a, s, p, (yy if abs(yy) > 1e-6 else 1.0)

    def note_pos(self, ni: int, t: float, st, hit_t: float | None = None):
        """t = 当前画面时间；hit_t = 该 note（或 Hold 尾）的判定时间。"""
        n = self.notes[ni]
        lx, ly, rot, la, lsize = st
        H = self._speed[n["line"]]
        hit = n["t"] if hit_t is None else hit_t
        raw = (H.H(hit) - H.H(t)) * HALF_H * n["speed"]
        _ca, _cs, cpos, cy = self.note_ctrl(ni, raw * self.speed_mul)
        dist = raw / cy * self.speed_mul
        # RPE 的 positionX 是相对判定线中心的坐标；prpr 里先平移到 (x, height)
        # 再叠加线自身的平移与旋转。这里不能减去线坐标（那会二次平移）。
        rel_x = n["x"] * cpos
        # above 在 Phira 的 RPE 解析里只影响粒子朝向，不影响下落方向。
        rel_y = max(0.0, dist) + n["yoff"]
        rx, ry = _rot(rel_x, rel_y, rot)
        wx, wy = lx + rx, ly + ry
        px = (HALF_W + wx) * self.sx
        py = (HALF_H - wy) * self.sy
        return px, py, rot, la, lsize, dist

    # -- 画一帧 --
    def frame(self, t_audio: float) -> Image.Image:
        t = t_audio + self.offset   # 谱面时间
        img = Image.new("RGB", (self.w, self.h), (8, 10, 16))
        if self.bg:
            img.paste(self.bg)
            img = ImageEnhance.Brightness(img).enhance(max(0.05, 1.0 - self.bg_dim))
        # videos 在 prpr 里先于判定线与音符绘制
        img = self.draw_videos(img, t)
        draw = ImageDraw.Draw(img, "RGBA")

        # 判定线（有 Texture 的按图片图层画，其余画线）
        states = [self.line_state(L, t) for L in self.lines]
        order = sorted(range(len(self.lines)), key=lambda i: self.lines[i].get("zOrder", 0))
        for li in order:
            x, y, rot, a, size = states[li]
            if a <= 0.01:
                continue
            L = self.lines[li]
            ex = L.get("extended") or {}
            tex = (L.get("Texture") or "").strip()
            if tex in ("", "line.png"):
                # prpr 语义：line.png 时 paint > text > 普通线
                if ex.get("paintEvents") and self.draw_paint(img, L, states[li], t):
                    continue
                if ex.get("textEvents") and self.draw_text(img, L, states[li], t):
                    continue
            elif self.draw_texture(img, L, states[li], t):
                continue
            length = self.line_len * HALF_W * max(0.05, size) * 2
            dx, dy = _rot(length / 2, 0, rot)
            cx, cy = (HALF_W + x) * self.sx, (HALF_H - y) * self.sy
            # 默认判定线色 = respack.info.color_perfect（0xe1ffec9f）→ 暖白；
            # colorEvents 支持时直接覆盖线色（prpr parse: line.color）。
            if ex.get("colorEvents"):
                _cr, _cg, _cb = _ext_color(L, t, self.timing)
                col = (int(255 * _cr), int(255 * _cg), int(255 * _cb), int(255 * a))
            else:
                col = (255, 236, 159, int(225 * a))
            thick = 0.0076 if abs(size - 1.0) > 1e-4 else 0.01
            draw.line([(cx - dx * self.sx, cy + dy * self.sy), (cx + dx * self.sx, cy - dy * self.sy)],
                      fill=col, width=max(2, int(thick * HALF_W * self.sx)))
        draw = ImageDraw.Draw(img, "RGBA")   # paste 会失效旧的 draw 句柄

        # 音符（先画 Hold 体，再画头）
        for ni, n in enumerate(self.notes):
            # visibleTime 是"提前多少秒出现"；999999 表示常显。
            # 判定后 Tap/Flick/Drag 立即消失，Hold 持续到尾。
            t_end = n["te"] + 0.35 if n["type"] == 2 else n["t"] + 0.06
            appear = n["t"] - min(3.0, max(0.0, n["visible"]))
            if not (appear <= t <= t_end):
                continue
            st = states[n["line"]]
            px, py, rot, la, lsize, dist = self.note_pos(ni, t, st)
            if px < -300 or px > self.w + 300 or py < -300 or py > self.h + 300:
                continue
            # RPE/Phira：判定线 alpha 只影响线本身，音符 alpha 独立。
            # 早期版本这里乘了 la，导致"透明线上的音符"在预览里假性消失，
            # 与实机（音符照常显示、照常判定）不一致。
            ca, cs, _cpos, _cy = self.note_ctrl(ni, abs(dist))
            a = max(0.0, min(1.0, n["alpha"] * ca))
            # visibleTime 生效时 Phira 会在出现点淡入
            if n["visible"] < 999999:
                fade = min(1.0, max(0.0, (t - appear) / 0.12))
                a *= fade
            if a <= 0.02:
                continue
            col = NOTE_COLORS.get(n["type"], (255, 255, 255))
            # prpr draw_center：dest_size = 2 * (NOTE_WIDTH_RATIO_BASE * size)
            nw = NOTE_W_WORLD * HALF_W * self.sx * max(0.05, n["size"] * cs)
            nwy = NOTE_W_WORLD * HALF_H * self.sy * max(0.05, n["size"] * cs)
            nh = {"1": 0.10, "2": 0.10, "3": 0.172, "4": 0.053}.get(str(n["type"]), 0.10)
            rot_deg = -rot

            if n["type"] == 2 and n["te"] > n["t"]:
                ex, ey, _, _, _, _ = self.note_pos(ni, t, st, hit_t=n["te"])
                # 长条本体：与头同宽的竖直条带，双端略收
                ddx, ddy = ex - px, ey - py
                ln = math.hypot(ddx, ddy)
                if ln > 1:
                    ux, uy = ddx / ln, ddy / ln
                    nx, ny = -uy, ux
                    hw = nw * 0.46
                    body = [(px + nx * hw, py + ny * hw), (ex + nx * hw, ey + ny * hw),
                            (ex - nx * hw, ey - ny * hw), (px - nx * hw, py - ny * hw)]
                    draw.polygon(body, fill=col + (int(58 * a),))
                    draw.line([(px + nx * hw, py + ny * hw), (ex + nx * hw, ey + ny * hw)],
                              fill=(235, 245, 255, int(130 * a)), width=max(1, int(2 * self.sy)))

            if n["type"] == 3:
                # flick：宽三角 / 箭头，指向下落方向（flick.png 比例约 172:998）
                hh = nwy * nh
                tri_pts = [(0, -hh * 1.05), (nw * 0.5, hh * 0.95), (0, hh * 0.35), (-nw * 0.5, hh * 0.95)]
                rs = [_rot(x, y, rot_deg) for x, y in tri_pts]
                draw.polygon([(px + x, py + y) for x, y in rs], fill=col + (int(255 * a),))
            else:
                hh = nwy * nh
                rect = [(px - nw / 2, py - hh / 2), (px + nw / 2, py - hh / 2),
                        (px + nw / 2, py + hh / 2), (px - nw / 2, py + hh / 2)]
                if abs(rot_deg) > 0.2:
                    rect = [(px + _rot(x - px, y - py, rot_deg)[0], py + _rot(x - px, y - py, rot_deg)[1])
                            for x, y in rect]
                draw.polygon(rect, fill=col + (int(255 * a),))
                if n["type"] == 2:
                    # Hold 头：中间加亮
                    draw.line([(px - nw * 0.42, py), (px + nw * 0.42, py)],
                              fill=(255, 255, 255, int(150 * a)), width=max(1, int(2 * self.sy)))

        img = self.apply_effects(img, t_audio)

        if self.hud:
            self.draw_hud(img, ImageDraw.Draw(img, "RGBA"), t_audio)
        return img

    # -- 特效（近似） --
    def _parse_effects(self, extra):
        out = []
        if not extra:
            return out
        for e in extra.get("effects") or []:
            try:
                out.append({
                    "t0": self.timing.sec(tri(e.get("start"))),
                    "t1": self.timing.sec(tri(e.get("end"))),
                    "shader": (e.get("shader") or "").lower(),
                    "vars": e.get("vars") or {},
                    "line": int(e.get("line") or 0),
                })
            except Exception:  # noqa: BLE001
                continue
        out.sort(key=lambda x: x["t0"])
        return out

    def active_effects(self, t: float):
        return [e["shader"] for e in self.effects if e["t0"] <= t <= e["t1"]]

    def _ev(self, eff: dict, key: str, t: float, default: float) -> float:
        """取 shader 变量的当前值（vars 里每个键都是一条事件轴）。"""
        arr = (eff.get("vars") or {}).get(key)
        if not arr:
            return default
        return _events_value(arr, t, self.timing, default)

    def _fx_grayscale(self, img, eff, t):
        f = max(0.0, min(1.0, self._ev(eff, "factor", t, 1.0)))
        if f <= 0.01:
            return img
        return Image.blend(img, img.convert("L").convert("RGB"), f)

    def _fx_glow(self, img, eff, t):
        """glow_effect：按亮度阈值取亮部 → 模糊 → screen 叠加。"""
        inten = max(0.0, self._ev(eff, "intensity", t, 0.6))
        thr = self._ev(eff, "threshold", t, 0.3)
        if inten <= 0.01:
            return img
        lum = img.convert("L")
        lo = int(max(0.0, min(1.0, thr)) * 255)
        mask = lum.point(lambda v: 255 if v >= lo else 0)
        r = max(2, int(self.h * 0.018))
        bloom = img.filter(ImageFilter.GaussianBlur(r))
        bloom = Image.composite(bloom, Image.new("RGB", img.size, (0, 0, 0)), mask.filter(ImageFilter.GaussianBlur(r)))
        bloom = ImageEnhance.Brightness(bloom).enhance(min(2.0, inten * 1.6))
        return ImageChops.screen(img, bloom)

    def _fx_rain(self, img, eff, t):
        n = int(max(0, min(600, self._ev(eff, "density", t, 0))))
        if n <= 0:
            return img
        hfrac = max(0.005, self._ev(eff, "height", t, 0.03))
        wpx = max(1.0, self._ev(eff, "width", t, 0.0008) * self.w * 4)
        speed = self._ev(eff, "speed", t, 1.0)
        col = (int(0.70 * 255), int(0.80 * 255), int(0.90 * 255), int(0.60 * 255))
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        rnd = random.Random(20240601)
        seeds = [(rnd.random(), rnd.random(), 0.7 + rnd.random() * 0.8) for _ in range(n)]
        ln = max(4, int(hfrac * self.h))
        for sx, sy, sp in seeds:
            x = sx * self.w
            y = ((sy + t * 0.35 * speed * sp) % 1.0) * self.h
            d.line([(x, y), (x - wpx * 3, y + ln)], fill=col, width=max(1, int(wpx)))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _fx_snow(self, img, eff, t):
        n = int(max(0, min(800, self._ev(eff, "snowCount", t, 0))))
        if n <= 0:
            return img
        size = max(1.0, self._ev(eff, "size", t, 0.01) * self.h)
        vx = self._ev(eff, "speedx", t, 20.0) / self.h
        vy = self._ev(eff, "speedy", t, 60.0) / self.h
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        rnd = random.Random(20240602)
        for i in range(n):
            bx, by, sp = rnd.random(), rnd.random(), 0.5 + rnd.random()
            x = ((bx + t * vx * sp) % 1.0) * self.w
            y = ((by + t * vy * sp) % 1.0) * self.h
            d.ellipse([x - size, y - size, x + size, y + size], fill=(255, 255, 255, 190))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _fx_chromatic(self, img, eff, t):
        """prpr chromatic.glsl：以屏幕中心为原点做径向 RGB 分离。"""
        power = max(0.0, self._ev(eff, "power", t, 0.01))
        if power <= 1e-5:
            return img
        try:
            import numpy as np
        except ImportError:
            d = int(power * self.w * 0.5)
            r, g, b = img.split()
            return Image.merge("RGB", (
                r.transform(r.size, Image.AFFINE, (1, 0, d, 0, 1, 0)),
                g,
                b.transform(b.size, Image.AFFINE, (1, 0, -d, 0, 1, 0)),
            ))
        a = np.asarray(img, dtype=np.float32)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        out = a.copy()
        for ch, k in ((0, 1.0 + power), (2, 1.0 - power)):
            sx = cx + (xx - cx) * k
            sy = cy + (yy - cy) * k
            sx0 = np.clip(np.floor(sx).astype(np.int32), 0, w - 1)
            sy0 = np.clip(np.floor(sy).astype(np.int32), 0, h - 1)
            out[..., ch] = a[sy0, sx0, ch]
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    def _fx_vignette(self, img, eff, t):
        """prpr vignette.glsl：从 radius 开始，向外 extend 渐变到指定颜色。"""
        radius = max(0.0, self._ev(eff, "radius", t, 15.0)) / 100.0
        extend = max(1e-3, self._ev(eff, "extend", t, 0.25))
        try:
            import numpy as np
        except ImportError:
            return img
        a = np.asarray(img, dtype=np.float32)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
        m = np.clip((d - radius) / extend, 0.0, 1.0)[..., None]
        col = np.array([self._ev(eff, "r", t, 0.0), self._ev(eff, "g", t, 0.0),
                        self._ev(eff, "b", t, 0.0)], dtype=np.float32) * 255.0
        out = a * (1.0 - m) + col * m
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    def _fx_circle_blur(self, img, eff, t):
        """circle_blur.glsl：圆形邻域取最亮像素（近似为 MaxFilter）。"""
        size = int(max(0, min(16, self._ev(eff, "size", t, 10.0))))
        if size <= 0:
            return img
        return img.filter(ImageFilter.MaxFilter(size * 2 + 1))

    def _fx_shockwave(self, img, eff, t):
        """shockwave.glsl：一圈随时间扩散的环形折射。"""
        span = max(1e-3, eff["t1"] - eff["t0"])
        prog = max(0.001, min(0.999, (t - eff["t0"]) / span))
        width = max(0.01, self._ev(eff, "width", t, 0.1))
        dist_k = max(0.0, self._ev(eff, "distortion", t, 0.8))
        expand = max(0.1, self._ev(eff, "expand", t, 10.0))
        cx = self._ev(eff, "centerX", t, 0.5) * self.w
        cy = self._ev(eff, "centerY", t, 0.5) * self.h
        try:
            import numpy as np
        except ImportError:
            return img
        a = np.asarray(img, dtype=np.float32)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx, dy = xx - cx, yy - cy
        d = np.sqrt(dx * dx + dy * dy) / max(w, h)
        ring = np.abs(d - prog) < width
        scale = 1.0 - np.power(np.clip(np.abs(d - prog) * expand, 0, 1), dist_k)
        k = np.where(ring, 1.0 + 0.35 * scale, 1.0)
        sx = np.clip(cx + dx * k, 0, w - 1).astype(np.int32)
        sy = np.clip(cy + dy * k, 0, h - 1).astype(np.int32)
        out = a[sy, sx]
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

    def _fx_radial_blur(self, img, eff, t):
        """radial_blur.glsl：向中心做缩放模糊。"""
        power = max(0.0, min(0.2, self._ev(eff, "power", t, 0.02)))
        n = int(max(2, min(12, self._ev(eff, "sampleCount", t, 6))))
        cx = self._ev(eff, "centerX", t, 0.5) * self.w
        cy = self._ev(eff, "centerY", t, 0.5) * self.h
        base = img
        acc = None
        for i in range(n):
            k = 1.0 - power * i
            w2, h2 = max(1, int(self.w * k)), max(1, int(self.h * k))
            z = base.resize((w2, h2), Image.BILINEAR)
            canvas = Image.new("RGB", (self.w, self.h), (0, 0, 0))
            canvas.paste(z, (int(cx - cx * k), int(cy - cy * k)))
            acc = canvas if acc is None else Image.blend(acc, canvas, 1.0 / (i + 1))
        return acc or img

    def _fx_pixel(self, img, eff, t):
        """pixel.glsl：按块大小做马赛克。"""
        size = max(1.0, self._ev(eff, "size", t, 10.0))
        sw = max(1, int(self.w / size))
        sh = max(1, int(self.h / size))
        return img.resize((sw, sh), Image.BILINEAR).resize((self.w, self.h), Image.NEAREST)

    def _fx_noise(self, img, eff, t):
        """noise.glsl：按 seed 做逐像素偏移。"""
        power = max(0.0, self._ev(eff, "power", t, 0.03))
        seed = self._ev(eff, "seed", t, 81.0)
        try:
            import numpy as np
        except ImportError:
            return img
        a = np.asarray(img, dtype=np.uint8)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sin((xx + seed) * 12.9898 + yy * 78.233) * 43758.5453
        r = r - np.floor(r)
        sx = np.clip((xx + (r - 0.5) * 6.0).astype(np.int32), 0, w - 1)
        sy = np.clip((yy + (r - 0.5) * 6.0).astype(np.int32), 0, h - 1)
        return Image.fromarray(a[sy, sx])

    def _fx_fisheye(self, img, eff, t):
        """fisheye.glsl：桶形/枕形畸变。"""
        power = self._ev(eff, "power", t, -0.1)
        if abs(power) < 1e-4:
            return img
        try:
            import numpy as np
        except ImportError:
            return img
        a = np.asarray(img, dtype=np.uint8)
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx = (xx - w / 2) / (h / 2)
        ny = (yy - h / 2) / (h / 2)
        r = np.sqrt(nx * nx + ny * ny)
        if power > 0:
            f = np.tan(np.minimum(r * power, 1.4)) / np.maximum(r, 1e-5) * (r / max(1e-5, np.tan(min(1.4, power))))
        else:
            f = np.arctan(r * -power * 10.0) / np.maximum(r, 1e-5) / max(1e-5, np.arctan(-power * 10.0))
        sx = np.clip(nx * f * (h / 2) + w / 2, 0, w - 1).astype(np.int32)
        sy = np.clip(ny * f * (h / 2) + h / 2, 0, h - 1).astype(np.int32)
        return Image.fromarray(a[sy, sx])

    def apply_effects(self, img: Image.Image, t: float) -> Image.Image:
        act = [e for e in self.effects if e["t0"] <= t <= e["t1"]]
        if not act:
            return img
        for eff in act:
            name = eff["shader"]
            if "grayscale" in name:
                img = self._fx_grayscale(img, eff, t)
            elif "glow" in name:
                img = self._fx_glow(img, eff, t)
            elif "rain" in name:
                img = self._fx_rain(img, eff, t)
            elif "snow" in name:
                img = self._fx_snow(img, eff, t)
            elif "chromatic" in name:
                img = self._fx_chromatic(img, eff, t)
            elif "glitch" in name:
                img = self._fx_glitch(img, eff, t)
            elif "vignette" in name:
                img = self._fx_vignette(img, eff, t)
            elif "circle" in name and "blur" in name:
                img = self._fx_circle_blur(img, eff, t)
            elif "radial" in name and "blur" in name:
                img = self._fx_radial_blur(img, eff, t)
            elif "shockwave" in name:
                img = self._fx_shockwave(img, eff, t)
            elif "pixel" in name:
                img = self._fx_pixel(img, eff, t)
            elif "noise" in name:
                img = self._fx_noise(img, eff, t)
            elif "fisheye" in name:
                img = self._fx_fisheye(img, eff, t)
            elif "flare" in name:
                overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                d.ellipse([self.w * 0.5 - 220, self.h * 0.12, self.w * 0.5 + 220, self.h * 0.12 + 160],
                          fill=(255, 240, 200, 40))
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img

    def _fx_glitch(self, img, eff, t):
        """glitch.glsl：随机行块位移 + RGB 错位。"""
        power = max(0.0, self._ev(eff, "power", t, 0.03))
        rate = max(0.0, min(1.0, self._ev(eff, "rate", t, 0.6)))
        speed = max(0.1, self._ev(eff, "speed", t, 5.0))
        blocks = max(2.0, self._ev(eff, "blockCount", t, 30.5))
        color_rate = max(0.0, self._ev(eff, "colorRate", t, 0.01))
        rnd = random.Random(int(t * speed * 1000))
        if rnd.random() > rate:
            return img
        out = img.copy()
        d = ImageDraw.Draw(out, "RGBA")
        band_h = max(2, int(self.h / blocks))
        for i in range(int(blocks)):
            if rnd.random() > rate * 0.5:
                continue
            y = i * band_h
            shift = int((rnd.random() - 0.5) * power * self.w * 2)
            if shift == 0:
                continue
            strip = img.crop((0, y, self.w, min(self.h, y + band_h)))
            out.paste(strip, (shift, y))
        r, g, b = out.split()
        dx = max(1, int(color_rate * self.w))
        return Image.merge("RGB", (
            r.transform(r.size, Image.AFFINE, (1, 0, dx, 0, 1, 0)),
            g,
            b.transform(b.size, Image.AFFINE, (1, 0, -dx, 0, 1, 0)),
        ))

    def draw_hud(self, img, draw, t):
        b = self.timing.beat_at(t)
        act = ",".join(self.active_effects(t)) or "-"
        vis = sum(1 for n in self.notes if abs(n["t"] - t) <= 1.5)
        txt = f"t={t:7.2f}s  beat={b:7.2f}  NPS~{vis/3.0:4.2f}  fx={act[:38]}"
        draw.rectangle([0, 0, self.w, 26], fill=(0, 0, 0, 150))
        draw.text((10, 6), txt, fill=(210, 230, 255, 230))


# ---------------------------------------------------------------- 统计


def build_stats(r: Renderer) -> dict:
    notes = r.notes
    dur = r.duration or (max((n["t"] for n in notes), default=0) + 1)
    per_sec = {}
    for n in notes:
        k = int(n["t"])
        per_sec[k] = per_sec.get(k, 0) + 1
    nps = [per_sec.get(i, 0) for i in range(int(dur) + 1)]
    peak = max(nps) if nps else 0
    types = {1: 0, 2: 0, 3: 0, 4: 0}
    for n in notes:
        types[n["type"]] = types.get(n["type"], 0) + 1
    xs = [n["x"] for n in notes] or [0]

    line_notes = {}
    for n in notes:
        line_notes[n["line"]] = line_notes.get(n["line"], 0) + 1
    event_count = {}
    for i, L in enumerate(r.lines):
        c = 0
        for lay in L.get("eventLayers") or []:
            if isinstance(lay, dict):
                for k in ("alphaEvents", "moveXEvents", "moveYEvents", "rotateEvents", "speedEvents"):
                    c += len(lay.get(k) or [])
        event_count[i] = c

    # 舞台覆盖（采样）
    xs_cover = []
    t = 0.0
    while t < dur:
        for L in r.lines:
            x, y, rot, a, size = r.line_state(L, t)
            if a > 0.05:
                xs_cover.append(x)
        t += 0.5

    # 可见性检查：命中瞬间是否被隐藏 / 越界；提前 0.4s 是否已出现在画面内
    hidden = offscreen_hit = approach_ok = 0
    approach_dist = []
    for ni, n in enumerate(r.notes):
        st = r.line_state(r.lines[n["line"]], n["t"])
        if st[3] < 0.05:
            hidden += 1
        hx, hy, _, _, _, _ = r.note_pos(ni, n["t"], st)
        if not (0 <= hx <= r.w and 0 <= hy <= r.h):
            offscreen_hit += 1
        st2 = r.line_state(r.lines[n["line"]], n["t"] - 0.4)
        ax, ay, _, al, _, d = r.note_pos(ni, n["t"] - 0.4, st2)
        approach_dist.append(d)
        if 0 <= ax <= r.w and 0 <= ay <= r.h and al > 0.05:
            approach_ok += 1

    return {
        "duration": round(dur, 2),
        "lines": len(r.lines),
        "lines_with_notes": len(line_notes),
        "notes": len(notes),
        "types": {NOTE_NAMES.get(k, str(k)): v for k, v in types.items()},
        "avg_nps": round(len(notes) / dur, 2) if dur else 0,
        "peak_nps_1s": peak,
        "x_range": [round(min(xs), 1), round(max(xs), 1)],
        "x_std": round((sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / len(xs)) ** 0.5, 1),
        "line_x_cover": [round(min(xs_cover), 1), round(max(xs_cover), 1)] if xs_cover else [0, 0],
        "hidden_notes": hidden,
        "offscreen_hit_notes": offscreen_hit,
        "approach_visible_ratio": round(approach_ok / len(notes), 3) if notes else 0,
        "approach_dist_median": round(sorted(approach_dist)[len(approach_dist) // 2], 1) if approach_dist else 0,
        "top_event_lines": sorted(event_count.items(), key=lambda kv: -kv[1])[:5],
        "effects": len(r.effects),
        "note_density_by_line": dict(sorted(line_notes.items(), key=lambda kv: -kv[1])[:8]),
    }


# ---------------------------------------------------------------- 输出


def save_contact_sheet(r: Renderer, out: Path, n=12, times=None):
    if times is None:
        dur = r.duration
        times = [dur * (i + 0.5) / n for i in range(n)]
    cols, rows = 4, math.ceil(len(times) / 4)
    tw, th = 480, 320
    sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (12, 12, 18))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        fr = r.frame(t).resize((tw, th), Image.LANCZOS)
        x = (i % cols) * tw
        y = (i // cols) * (th + 22)
        sheet.paste(fr, (x, y))
        d.text((x + 6, y + th + 5), f"#{i+1}  t={t:.2f}s", fill=(220, 230, 250))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"联系表：{out}  ({len(times)} 帧)")


def render_video(r: Renderer, out: Path, t0: float, t1: float, fps: int, audio: bool = True):
    out.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, int((t1 - t0) * fps))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{r.w}x{r.h}", "-r", str(fps),
        "-i", "-",
    ]
    audio_in = None
    if audio and r.proj.music and r.proj.music.exists():
        audio_in = r.proj.music
        cmd += ["-ss", f"{t0:.3f}", "-i", str(audio_in), "-map", "0:v:0", "-map", "1:a:0",
                "-shortest", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert p.stdin is not None
    for i in range(n):
        t = t0 + i / fps
        p.stdin.write(r.frame(t).tobytes())
    p.stdin.close()
    code = p.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg 退出码 {code}")
    print(f"视频：{out}  {n} 帧 @ {fps}fps")


def main() -> int:
    ap = argparse.ArgumentParser(description="Phira 谱面离屏预览 / 自检")
    ap.add_argument("path", help="工程目录或 zip")
    ap.add_argument("--frame", type=float, help="渲染单帧（秒）")
    ap.add_argument("-o", "--output", help="单帧输出路径 / 视频路径")
    ap.add_argument("--contact-sheet", metavar="PNG", help="生成联系表")
    ap.add_argument("--times", help="联系表时间点，逗号分隔（秒）")
    ap.add_argument("--video", metavar="MP4", help="导出视频")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--width", type=int, default=1350)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--no-hud", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--speed-mul", type=float, default=1.0,
                    help="下落速度倍数（只影响预览观感，默认 1.0 接近 Phira）")
    args = ap.parse_args()

    proj = load_project(args.path)
    r = Renderer(proj, args.width, args.height, hud=not args.no_hud, speed_mul=args.speed_mul)
    if args.t1 is None:
        args.t1 = r.duration

    if args.stats:
        print(json.dumps(build_stats(r), ensure_ascii=False, indent=2))
        return 0

    if args.frame is not None:
        out = Path(args.output or f"frame_{args.frame:.2f}.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        r.frame(args.frame).save(out)
        print(f"截图：{out}")
        return 0

    if args.contact_sheet:
        times = None
        if args.times:
            times = [float(x) for x in args.times.split(",") if x.strip()]
        save_contact_sheet(r, Path(args.contact_sheet), times=times)
        return 0

    if args.video:
        render_video(r, Path(args.video), args.t0, args.t1, args.fps)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        raise SystemExit(1)
