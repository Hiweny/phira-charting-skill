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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# ---------------------------------------------------------------- 常量

RPE_W, RPE_H = 1350.0, 900.0        # RPE 坐标系（x ∈ ±675，y ∈ ±450）
HALF_W, HALF_H = RPE_W / 2, RPE_H / 2

# prpr 源码 prpr/src/parse/rpe.rs：const SPEED_RATIO = 10 / 45 / HEIGHT_RATIO
HEIGHT_RATIO = 0.83175
SPEED_RATIO = 10.0 / 45.0 / HEIGHT_RATIO   # ≈ 0.2671

NOTE_COLORS = {
    1: (96, 210, 255),     # Tap  青
    2: (255, 214, 92),     # Hold 黄
    3: (255, 92, 110),     # Flick 红
    4: (255, 176, 60),     # Drag 橙
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
    p = max(0.0, min(1.0, p))
    if kind in (0,):
        return 0.0 if p < 1 else 1.0
    if kind == 1:
        return p
    if kind == 2:
        return 1 - math.cos(p * math.pi / 2)
    if kind == 3:
        return math.sin(p * math.pi / 2)
    if kind == 4:
        return p * p
    if kind == 5:
        return 1 - (1 - p) * (1 - p)
    if kind == 6:
        return -(math.cos(math.pi * p) - 1) / 2
    if kind == 7:
        return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2
    if kind == 8:
        return p ** 3
    if kind == 9:
        return 1 - (1 - p) ** 3
    if kind == 10:
        return p ** 4
    if kind == 11:
        return 1 - (1 - p) ** 4
    if kind == 12:
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if kind == 13:
        return 8 * p ** 4 if p < 0.5 else 1 - (-2 * p + 2) ** 4 / 2
    return p


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

    DEFAULT = {"pos": 0.0, "alpha": 1.0, "y": 0.0, "size": 1.0, "skew": 0.0}

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


def _layers_alpha(line: dict, t: float, timing: Timing) -> float:
    """RPE 的多个 eventLayer 是**叠加**关系（与 prpr 的 AnimFloat::chain 一致）。

    没有 alphaEvents 的图层不参与计算；有事件的图层把 0~255 归一化后相加，
    最后 clamp 到 1。若所有图层都没有 alpha 事件，视为不透明。
    """
    vals = []
    for lay in line.get("eventLayers") or []:
        if isinstance(lay, dict) and lay.get("alphaEvents"):
            v = _events_value(lay.get("alphaEvents"), t, timing, 255.0)
            vals.append(max(0.0, min(1.0, v / 255.0 if v > 1.5 else v)))
    if not vals:
        return 1.0
    return max(0.0, min(1.0, sum(vals)))


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
                        }
                    )
                except Exception:  # noqa: BLE001
                    continue
        self.notes.sort(key=lambda n: n["t"])
        self.effects = self._parse_effects(proj.extra)

    # -- 状态求值 --
    def line_state(self, L: dict, t: float):
        x = Ctl.value(L.get("posControl"), "pos", t, self.timing)
        y = Ctl.value(L.get("yControl"), "y", t, self.timing)
        size = Ctl.value(L.get("sizeControl"), "size", t, self.timing) or 1.0
        base_alpha = Ctl.value(L.get("alphaControl"), "alpha", t, self.timing)
        x += _layers_sum(L, "moveXEvents", t, self.timing)
        y += _layers_sum(L, "moveYEvents", t, self.timing)
        rot = -_layers_sum(L, "rotateEvents", t, self.timing)
        if base_alpha > 1.5:
            base_alpha /= 255.0
        alpha = max(0.0, min(1.0, base_alpha)) * _layers_alpha(L, t, self.timing)
        return x, y, rot, alpha, abs(size)

    def note_pos(self, ni: int, t: float, st, hit_t: float | None = None):
        """t = 当前画面时间；hit_t = 该 note（或 Hold 尾）的判定时间。"""
        n = self.notes[ni]
        lx, ly, rot, la, lsize = st
        H = self._speed[n["line"]]
        hit = n["t"] if hit_t is None else hit_t
        dist = (H.H(hit) - H.H(t)) * HALF_H * n["speed"] * self.speed_mul
        sign = 1.0 if n["above"] >= 1 else -1.0
        rel_x = n["x"] - lx
        rel_y = sign * max(0.0, dist) + n["yoff"]
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
        draw = ImageDraw.Draw(img, "RGBA")

        # 判定线
        states = [self.line_state(L, t) for L in self.lines]
        order = sorted(range(len(self.lines)), key=lambda i: self.lines[i].get("zOrder", 0))
        for li in order:
            x, y, rot, a, size = states[li]
            if a <= 0.01:
                continue
            length = RPE_W * max(0.05, size)
            dx, dy = _rot(length / 2, 0, rot)
            cx, cy = (HALF_W + x) * self.sx, (HALF_H - y) * self.sy
            col = (200, 220, 255, int(170 * a))
            draw.line([(cx - dx * self.sx, cy + dy * self.sy), (cx + dx * self.sx, cy - dy * self.sy)],
                      fill=col, width=max(2, int(3 * self.sy)))

        # 音符（先画 Hold 体，再画头）
        for ni, n in enumerate(self.notes):
            # 未到判定前 3s 内才进入画面；Tap/Flick/Drag 判定后立即消失，Hold 持续到尾
            t_end = n["te"] + 0.35 if n["type"] == 2 else n["t"] + 0.06
            if not (n["t"] - 3.0 <= t <= t_end):
                continue
            st = states[n["line"]]
            px, py, rot, la, lsize, _dist = self.note_pos(ni, t, st)
            if px < -200 or px > self.w + 200 or py < -300 or py > self.h + 300:
                continue
            a = max(0.0, min(1.0, n["alpha"] * la))
            if a <= 0.02:
                continue
            if n["fake"]:
                a *= 0.45
            col = NOTE_COLORS.get(n["type"], (255, 255, 255))
            if n["fake"]:
                col = (150, 150, 160)
            sz = 18.0 * max(0.4, n["size"]) * self.sy

            if n["type"] == 2 and n["te"] > n["t"]:
                ex, ey, _, _, _, _ = self.note_pos(ni, t, st, hit_t=n["te"])
                draw.line([(px, py), (ex, ey)], fill=col + (int(70 * a),), width=max(2, int(sz * 0.55)))

            if n["type"] == 1:
                draw.rounded_rectangle([px - sz, py - sz * 0.72, px + sz, py + sz * 0.72],
                                       radius=int(sz * 0.45), fill=col + (int(255 * a),))
            elif n["type"] == 2:
                draw.rounded_rectangle([px - sz, py - sz * 0.6, px + sz, py + sz * 0.6],
                                       radius=int(sz * 0.3), fill=col + (int(255 * a),))
            elif n["type"] == 3:
                draw.polygon([(px, py - sz), (px + sz * 0.9, py + sz * 0.7), (px - sz * 0.9, py + sz * 0.7)],
                             fill=col + (int(255 * a),))
            else:
                draw.ellipse([px - sz * 0.55, py - sz * 0.55, px + sz * 0.55, py + sz * 0.55],
                             fill=col + (int(230 * a),))
                draw.ellipse([px - sz * 0.25, py - sz * 0.25, px + sz * 0.25, py + sz * 0.25],
                             fill=(255, 255, 255, int(200 * a)))

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
                })
            except Exception:  # noqa: BLE001
                continue
        out.sort(key=lambda x: x["t0"])
        return out

    def active_effects(self, t: float):
        return [e["shader"] for e in self.effects if e["t0"] <= t <= e["t1"]]

    def apply_effects(self, img: Image.Image, t: float) -> Image.Image:
        act = self.active_effects(t)
        if not act:
            return img
        for name in act:
            if "grayscale" in name:
                img = ImageEnhance.Color(img).enhance(0.15)
            elif "chromatic" in name:
                r, g, b = img.split()
                img = Image.merge("RGB", (r.transform(r.size, Image.AFFINE, (1, 0, 4, 0, 1, 0)),
                                          g,
                                          b.transform(b.size, Image.AFFINE, (1, 0, -4, 0, 1, 0))))
            elif "glitch" in name:
                d = ImageDraw.Draw(img, "RGBA")
                rnd = random.Random(int(t * 30))
                for _ in range(6):
                    y = rnd.randrange(0, self.h)
                    hh = rnd.randrange(2, 14)
                    x = rnd.randrange(-40, 40)
                    strip = img.crop((0, y, img.width, min(self.h, y + hh)))
                    img.paste(strip, (x, y))
                d.rectangle([0, 0, self.w, self.h], outline=(255, 0, 80, 10))
            elif "vignette" in name:
                v = Image.new("L", (self.w, self.h), 0)
                vd = ImageDraw.Draw(v)
                vd.ellipse([-self.w * 0.25, -self.h * 0.25, self.w * 1.25, self.h * 1.25], fill=255)
                v = v.filter(ImageFilter.GaussianBlur(120))
                black = Image.new("RGB", (self.w, self.h), (0, 0, 0))
                img = Image.composite(img, black, v)
            elif "shockwave" in name:
                e = next((x for x in self.effects if x["t0"] <= t <= x["t1"] and "shockwave" in x["shader"]), None)
                if e:
                    p = (t - e["t0"]) / max(1e-3, e["t1"] - e["t0"])
                    rad = 60 + p * self.w * 0.9
                    d = ImageDraw.Draw(img, "RGBA")
                    d.ellipse([self.w / 2 - rad, self.h / 2 - rad, self.w / 2 + rad, self.h / 2 + rad],
                              outline=(255, 255, 255, int(120 * (1 - p))), width=3)
            elif "snow" in name:
                d = ImageDraw.Draw(img, "RGBA")
                rnd = random.Random(int(t * 12))
                for _ in range(90):
                    x = rnd.randrange(0, self.w)
                    y = (rnd.randrange(0, self.h) + int(t * 40)) % self.h
                    d.ellipse([x, y, x + 2, y + 2], fill=(255, 255, 255, 140))
            elif "flare" in name:
                overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                d.ellipse([self.w * 0.5 - 220, self.h * 0.12, self.w * 0.5 + 220, self.h * 0.12 + 160],
                          fill=(255, 240, 200, 40))
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img

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
