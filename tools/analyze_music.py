#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_music.py — 音乐分析（Phira 制谱前置步骤）

用法：
    python3 tools/analyze_music.py song.mp3 -o analysis.json --plot analysis.png
    python3 tools/analyze_music.py song.mp3 --bpm 112.5

输出（JSON）：
    duration / bpm / beats / onsets / energy / spectral / vocal / structure

说明：
    * BPM 检测有约 ±1.5 的误差，可用 --bpm 手动指定做校准
    * vocal 区段是"近似估计"，精确分离请用 demucs
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import numpy as np

try:
    import librosa
except ImportError:
    print("缺少 librosa：pip install --break-system-packages librosa", file=sys.stderr)
    sys.exit(2)


def load_audio(path: str, duration: float | None = None):
    y, sr = librosa.load(path, sr=22050, mono=True, duration=duration)
    if y.size == 0:
        raise ValueError("音频为空或格式不支持")
    return y, sr


def detect_bpm(y, sr, manual: float | None = None) -> Dict[str, Any]:
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, units="time")
    tempo_val = float(np.atleast_1d(tempo)[0])
    beat_times = [float(t) for t in np.atleast_1d(beats)]

    dynamic = []
    try:
        d_tempo, _ = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr, units="time", trim=False
        )
        dynamic = [float(np.atleast_1d(d_tempo)[0])]
    except Exception:
        dynamic = [tempo_val]

    avg_interval = 0.0
    if len(beat_times) > 1:
        avg_interval = float(np.mean(np.diff(beat_times)))

    return {
        "static": round(manual if manual else tempo_val, 2),
        "detected": round(tempo_val, 2),
        "rounded": int(round(manual if manual else tempo_val)),
        "dynamic_min": round(min(dynamic), 2),
        "dynamic_max": round(max(dynamic), 2),
        "avg_beat_interval_seconds": round(avg_interval, 4),
        "beat_times_sample": [round(t, 3) for t in beat_times[:10]],
        "beat_count": len(beat_times),
    }


def detect_onsets(y, sr) -> Dict[str, Any]:
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    default = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, backtrack=True, units="time"
    )

    superflux = []
    try:
        sf_env = librosa.onset.onset_strength_multi(
            y=y, sr=sr, channels=[0, -1], lag=2, max_size=3
        )
        superflux = librosa.onset.onset_detect(
            onset_envelope=sf_env[0], sr=sr, backtrack=True, units="time"
        )
    except Exception:
        superflux = default

    y_h, y_p = librosa.effects.hpss(y)
    drum = librosa.onset.onset_detect(y=y_p, sr=sr, backtrack=True, units="time")

    return {
        "default_count": int(len(default)),
        "superflux_count": int(len(superflux)),
        "drum_peaks": int(len(drum)),
        "default_times_sample": [round(float(t), 3) for t in default[:20]],
        "drum_times_sample": [round(float(t), 3) for t in drum[:20]],
    }


def analyze_energy(y, sr) -> Dict[str, Any]:
    rms = librosa.feature.rms(y=y)[0]
    db = librosa.amplitude_to_db(rms, ref=np.max)
    times = librosa.frames_to_time(np.arange(len(db)), sr=sr)

    thresh = np.percentile(db, 85)
    mask = db >= thresh
    sections = _runs(times, mask)

    silence_thresh = np.percentile(db, 5)
    silence = _runs(times, db <= silence_thresh)

    return {
        "rms_db_max": round(float(db.max()), 2),
        "rms_db_mean": round(float(db.mean()), 2),
        "high_energy_threshold_db": round(float(thresh), 2),
        "high_energy_sections": len(sections),
        "silence_sections": len(silence),
        "high_energy_ranges": [[round(a, 2), round(b, 2)] for a, b in sections[:10]],
        "silence_ranges": [[round(a, 2), round(b, 2)] for a, b in silence[:10]],
        "energy_curve_100": [round(float(x), 2) for x in _resample(db, 100)],
    }


def _runs(times, mask, min_len: int = 4):
    runs = []
    start = None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if i - start >= min_len:
                runs.append((times[start], times[i - 1]))
            start = None
    if start is not None and len(mask) - start >= min_len:
        runs.append((times[start], times[-1]))
    return runs


def _resample(arr, n: int):
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return np.zeros(n)
    idx = np.linspace(0, arr.size - 1, n).astype(int)
    return arr[idx]


def analyze_spectral(y, sr) -> Dict[str, Any]:
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    return {
        "centroid_mean_hz": round(float(centroid.mean()), 1),
        "centroid_min_hz": round(float(centroid.min()), 1),
        "centroid_max_hz": round(float(centroid.max()), 1),
        "bandwidth_mean_hz": round(float(bandwidth.mean()), 1),
        "rolloff_mean_hz": round(float(rolloff.mean()), 1),
        "centroid_curve_100": [round(float(x), 1) for x in _resample(centroid, 100)],
    }


def estimate_vocal(y, sr) -> Dict[str, Any]:
    """近似人声区段：400~4000Hz 能量占比 + 整体能量。"""
    spec = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    band = (freqs >= 400) & (freqs <= 4000)
    band_energy = spec[band, :].sum(axis=0)
    total_energy = spec.sum(axis=0) + 1e-9
    ratio = band_energy / total_energy
    times = librosa.frames_to_time(np.arange(ratio.size), sr=sr)

    rms = librosa.feature.rms(y=y)[0]
    rms_norm = rms / (rms.max() + 1e-9)

    mask = (ratio > np.percentile(ratio, 60)) & (rms_norm > 0.12)
    sections = _runs(times, mask, min_len=8)

    return {
        "method": "band-energy estimate (400-4000Hz); use demucs for accuracy",
        "vocal_sections": len(sections),
        "vocal_ranges": [[round(a, 2), round(b, 2)] for a, b in sections[:20]],
        "vocal_ratio_mean": round(float(ratio.mean()), 3),
    }


def analyze_structure(y, sr, k: int = 8) -> Dict[str, Any]:
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        bounds_frames = librosa.segment.agglomerative(chroma, k=k)
        bounds = librosa.frames_to_time(bounds_frames, sr=sr)
        bounds = sorted(set([0.0] + [float(b) for b in bounds]))
    except Exception as e:
        return {"segments": 0, "boundaries": [], "error": str(e)}

    duration = float(librosa.get_duration(y=y, sr=sr))
    segs = []
    for i, b in enumerate(bounds):
        end = bounds[i + 1] if i + 1 < len(bounds) else duration
        segs.append([round(b, 2), round(end, 2)])

    rms = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(np.arange(rms.size), sr=sr)
    labels = []
    for a, b in segs:
        m = (times >= a) & (times < b)
        e = float(rms[m].mean()) if m.any() else 0.0
        labels.append("high" if e > 0.12 else ("mid" if e > 0.05 else "low"))

    return {
        "segments": len(segs),
        "boundaries": segs,
        "energy_labels": labels,
    }


def plot(y, sr, out: str, bpm_info: Dict[str, Any]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[warn] 缺少 matplotlib，跳过绘图", file=sys.stderr)
        return

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)

    t = np.arange(y.size) / sr
    axes[0].plot(t, y, linewidth=0.3, color="#4a90d9")
    axes[0].set_ylabel("Waveform")

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    ot = librosa.frames_to_time(np.arange(onset_env.size), sr=sr)
    axes[1].plot(ot, onset_env, linewidth=0.6, color="#d9534f")
    axes[1].set_ylabel("Onset")

    rms = librosa.feature.rms(y=y)[0]
    db = librosa.amplitude_to_db(rms, ref=np.max)
    rt = librosa.frames_to_time(np.arange(db.size), sr=sr)
    axes[2].plot(rt, db, linewidth=0.8, color="#5cb85c")
    axes[2].set_ylabel("RMS (dB)")

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    axes[3].plot(rt[:centroid.size], centroid, linewidth=0.8, color="#f0ad4e")
    axes[3].set_ylabel("Centroid (Hz)")
    axes[3].set_xlabel("seconds")

    fig.suptitle(f"Music Analysis — BPM {bpm_info['static']}")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(f"[ok] 图表已保存：{out}")


def main() -> int:
    ap = argparse.ArgumentParser(description="音乐分析（librosa）")
    ap.add_argument("audio", help="音频文件（mp3/wav/ogg/flac）")
    ap.add_argument("-o", "--output", default="analysis.json", help="输出 JSON")
    ap.add_argument("--plot", default=None, help="输出可视化 PNG")
    ap.add_argument("--bpm", type=float, default=None, help="手动指定 BPM（校准）")
    ap.add_argument("--duration", type=float, default=None, help="只分析前 N 秒")
    ap.add_argument("--segments", type=int, default=8, help="结构分割段数")
    args = ap.parse_args()

    y, sr = load_audio(args.audio, args.duration)
    duration = float(librosa.get_duration(y=y, sr=sr))

    bpm_info = detect_bpm(y, sr, args.bpm)
    beats = {
        "total": bpm_info["beat_count"],
        "avg_interval_seconds": bpm_info["avg_beat_interval_seconds"],
        "first_10_beats": bpm_info["beat_times_sample"],
        "downbeats": max(1, bpm_info["beat_count"] // 4),
    }

    result = {
        "file": args.audio,
        "duration_seconds": round(duration, 2),
        "duration_minutes": round(duration / 60, 2),
        "sample_rate": sr,
        "bpm": {
            "static": bpm_info["static"],
            "detected": bpm_info["detected"],
            "rounded": bpm_info["rounded"],
            "dynamic_min": bpm_info["dynamic_min"],
            "dynamic_max": bpm_info["dynamic_max"],
        },
        "beats": beats,
        "onsets": detect_onsets(y, sr),
        "energy": analyze_energy(y, sr),
        "spectral": analyze_spectral(y, sr),
        "vocal": estimate_vocal(y, sr),
        "structure": analyze_structure(y, sr, args.segments),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[ok] BPM {result['bpm']['static']} | 时长 {result['duration_seconds']}s "
          f"| onset {result['onsets']['default_count']} | 段 {result['structure']['segments']}")
    print(f"[ok] 结果已保存：{args.output}")

    if args.plot:
        plot(y, sr, args.plot, bpm_info)

    if abs(result["bpm"]["detected"] - result["bpm"]["static"]) > 2:
        print("[warn] 检测 BPM 与你指定的值差异较大，建议用 --bpm 再跑一次校准", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
