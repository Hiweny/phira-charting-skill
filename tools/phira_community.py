#!/usr/bin/env python3
"""Phira 社区谱面工具（搜索 / 详情 / 下载 / 批量取样）。

数据源：https://api.phira.cn （Phira 官方社区后端，公开只读接口）

用法：
    # 搜索
    python3 tools/phira_community.py search "探窗" -n 10
    python3 tools/phira_community.py search "BPM 200" --tag regular --sort rating

    # 详情（含 file 直链）
    python3 tools/phira_community.py info 61048

    # 下载并解压到一个目录（zip 内含 chart.json / 音乐 / 曲绘 / info.yml）
    python3 tools/phira_community.py download 61048 -o samples/tanchuang

    # 按评分取样前 N 张（用于批量学习）
    python3 tools/phira_community.py top -n 5 -o samples/

说明：
    * 接口无需登录，请保持低频访问（默认每次请求间隔 0.4s）。
    * `search` 的排序参数 `--sort rating` 为好评度降序；不传则按最新。
    * 下载到的工程可以直接交给 tools/validate_chart.py 与 tools/preview_render.py。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.phira.cn"
UA = "phira-charting-skill/1.0 (+https://github.com/Hiweny/phira-charting-skill)"
DEFAULT_DELAY = 0.4


def _get(url: str, retries: int = 3) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 + i)
    raise RuntimeError(f"请求失败：{url}\n{last}")


def _json(url: str) -> dict:
    return json.loads(_get(url).decode("utf-8"))


def cmd_search(args) -> int:
    q = {"page": args.page}
    if args.query:
        q["search"] = args.query
    if args.sort:
        q["sort"] = args.sort
    if args.tag:
        q["tag"] = args.tag
    url = f"{API}/chart?" + urllib.parse.urlencode(q)
    data = _json(url)
    rows = data.get("results", [])
    print(f"# 共 {data.get('count', '?')} 张，本页 {len(rows)} 张  ({url})")
    print(f"{'id':>8}  {'rating':>6}  {'难度':<10}  {'谱师':<16}  曲名")
    for r in rows[: args.n]:
        print(
            f"{r['id']:>8}  {(r.get('rating') or 0.0):>6.3f}  {str(r.get('level', '')):<10}  "
            f"{str(r.get('charter', ''))[:16]:<16}  {r.get('name', '')}"
        )
    return 0


def cmd_info(args) -> int:
    d = _json(f"{API}/chart/{args.chart_id}")
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    keys = [
        "id", "name", "level", "difficulty", "charter", "composer", "illustrator",
        "rating", "ratingCount", "uploader", "tags", "description", "created",
        "file", "illustration", "preview",
    ]
    for k in keys:
        if k in d:
            print(f"{k:>12}: {d[k]}")
    return 0


def cmd_download(args) -> int:
    meta = _json(f"{API}/chart/{args.chart_id}")
    out = Path(args.output or f"chart_{args.chart_id}")
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"_chart_{args.chart_id}.zip"
    print(f"下载 {meta.get('name')} (id={meta['id']}) → {zip_path}")
    zip_path.write_bytes(_get(meta["file"]))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out)
    zip_path.unlink()
    print(f"已解压到 {out}/")
    for p in sorted(out.iterdir()):
        print(f"  {p.name:40s} {p.stat().st_size:>10,d} B")
    print("\n下一步：")
    print(f"  python3 tools/validate_chart.py {out}")
    print(f"  python3 tools/preview_render.py {out} --contact-sheet {out}/sheet.png")
    return 0


def cmd_top(args) -> int:
    data = _json(f"{API}/chart?page=1&sort=rating")
    rows = data.get("results", [])[: args.n]
    base = Path(args.output or "samples")
    base.mkdir(parents=True, exist_ok=True)
    print(f"# 取评分前 {len(rows)} 张 → {base}/")
    for r in rows:
        rid = r["id"]
        dest = base / f"{rid}"
        if dest.exists() and any(dest.iterdir()):
            print(f"跳过已存在：{dest}")
            continue
        dest.mkdir(exist_ok=True)
        try:
            (dest / f"_c{rid}.zip").write_bytes(_get(r["file"]))
            with zipfile.ZipFile(dest / f"_c{rid}.zip") as z:
                z.extractall(dest)
            (dest / f"_c{rid}.zip").unlink()
            print(f"✓ {rid:>6}  {(r.get('rating') or 0.0):.3f}  {r.get('name', '')}")
        except Exception as e:  # noqa: BLE001
            print(f"✗ {rid}: {e}")
            continue
        time.sleep(DEFAULT_DELAY)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phira 社区谱面检索 / 下载")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="搜索谱面")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("-n", type=int, default=16)
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--sort", choices=["rating"], help="rating = 好评度降序")
    s.add_argument("--tag", help="标签过滤，如 regular / 明日方舟")
    s.set_defaults(func=cmd_search)

    i = sub.add_parser("info", help="查看谱面详情")
    i.add_argument("chart_id", type=int)
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    d = sub.add_parser("download", help="下载并解压谱面")
    d.add_argument("chart_id", type=int)
    d.add_argument("-o", "--output")
    d.set_defaults(func=cmd_download)

    t = sub.add_parser("top", help="批量取样高评分谱面")
    t.add_argument("-n", type=int, default=5)
    t.add_argument("-o", "--output")
    t.set_defaults(func=cmd_top)

    args = ap.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
