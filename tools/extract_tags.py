#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_tags.py — 从音频文件里挖出「自带的歌词与封面」。

制谱时最容易被忽略的一件事：**歌本身就带着歌词和曲绘**。
用户发来一个 .mp3，里面常常已经嵌了 LRC 歌词（甚至带中文翻译）和封面图，
不必再去网上找、也不必跑 ASR。

支持：
    * FLAC  —— VORBIS_COMMENT 的 LYRICS / UNSYNCEDLYRICS，PICTURE(type 6) 块
    * MP3   —— ID3v2 TXXX:LYRICS / USLT / SYLT，APIC 封面
    * M4A   —— ©lyr 歌词、covr 封面（MP4 box 解析）
    * 兜底  —— 文件头是 fLaC 但扩展名写着 .mp3 时按内容判断（很常见）

用法：
    python3 tools/extract_tags.py song.mp3 -o out/            # 写 lyrics.lrc / cover.jpg
    python3 tools/extract_tags.py song.mp3 --json             # 只打印元信息
    python3 tools/extract_tags.py song.mp3 --check            # 同时报告"文件真实格式"

输出：
    lyrics.lrc   逐行 [mm:ss.xxx]，可直接给 lyrics_align.py
    lyrics.zh.txt  若歌词里有 [TLYRIC] / [翻译] 段，单独拆出来
    cover.jpg    第一张图片
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys


# ---------------------------------------------------------------- FLAC
def read_flac(f):
    magic = f.read(4)
    if magic != b'fLaC':
        return None
    out = {'format': 'flac', 'tags': {}, 'pictures': []}
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        last, btype = hdr[0] >> 7, hdr[0] & 0x7f
        length = int.from_bytes(hdr[1:4], 'big')
        data = f.read(length)
        if btype == 4:                      # VORBIS_COMMENT
            j = 0
            vlen = struct.unpack('<I', data[j:j + 4])[0]; j += 4 + vlen
            cnt = struct.unpack('<I', data[j:j + 4])[0]; j += 4
            for _ in range(cnt):
                l = struct.unpack('<I', data[j:j + 4])[0]; j += 4
                kv = data[j:j + l].decode('utf-8', 'replace'); j += l
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    out['tags'][k.upper()] = v
        elif btype == 6:                    # PICTURE
            j = 4                            # picture type
            mlen = struct.unpack('>I', data[j:j + 4])[0]; j += 4
            mime = data[j:j + mlen].decode('ascii', 'replace'); j += mlen
            dlen = struct.unpack('>I', data[j:j + 4])[0]; j += 4 + dlen
            w, h = struct.unpack('>II', data[j:j + 8])
            j += 16                          # w,h,depth,colors
            plen = struct.unpack('>I', data[j:j + 4])[0]; j += 4
            out['pictures'].append({'mime': mime, 'w': w, 'h': h,
                                    'bytes': data[j:j + plen]})
        if last:
            break
    return out


# ---------------------------------------------------------------- ID3v2
def _syncsafe(b):
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _id3_text(payload):
    enc = payload[0]
    body = payload[1:]
    if enc == 0:
        return body.decode('latin-1', 'replace').strip('\x00')
    if enc == 1:
        return body.decode('utf-16', 'replace').strip('\x00')
    if enc == 2:
        return body.decode('utf-16-be', 'replace').strip('\x00')
    return body.decode('utf-8', 'replace').strip('\x00')


def read_id3(f):
    head = f.read(10)
    if head[:3] != b'ID3':
        return None
    size = _syncsafe(head[6:10])
    blob = f.read(size)
    out = {'format': 'id3', 'tags': {}, 'pictures': []}
    i = 0
    while i + 10 <= len(blob):
        fid = blob[i:i + 4]
        if not fid.strip(b'\x00'):
            break
        fsz = _syncsafe(blob[i + 4:i + 8])
        payload = blob[i + 10:i + 10 + fsz]
        i += 10 + fsz
        if fid == b'APIC':
            p = payload
            enc = p[0]; j = 1
            nul = p.index(b'\x00', j)
            mime = p[j:nul].decode('latin-1')
            j = nul + 1
            j += 1                            # picture type
            if enc in (1, 2):
                k = j
                while k + 1 < len(p) and not (p[k] == 0 and p[k + 1] == 0):
                    k += 2
                j = k + 2
            else:
                j = p.index(b'\x00', j) + 1
            out['pictures'].append({'mime': mime, 'w': 0, 'h': 0, 'bytes': p[j:]})
        elif fid in (b'USLT', b'COMM'):
            txt = _id3_text(payload)
            if len(txt) > 8:
                out['tags'].setdefault('LYRICS', txt)
        elif fid[:4] == b'TXXX':
            enc = payload[0]
            try:
                if enc in (1, 2):
                    k = 1
                    while k + 1 < len(payload) and not (payload[k] == 0 and payload[k + 1] == 0):
                        k += 2
                    desc = payload[1:k].decode('utf-16', 'replace')
                    val = payload[k + 2:].decode('utf-16', 'replace').strip('\x00')
                else:
                    k = payload.index(b'\x00', 1)
                    desc = payload[1:k].decode('latin-1', 'replace')
                    val = payload[k + 1:].decode('utf-8', 'replace').strip('\x00')
                if 'LYRIC' in desc.upper():
                    out['tags'].setdefault('LYRICS', val)
            except Exception:
                pass
    return out


# ---------------------------------------------------------------- MP4
def read_mp4(f):
    data = f.read(2 * 1024 * 1024)
    if len(data) < 12 or data[4:8] != b'ftyp':
        return None
    out = {'format': 'mp4', 'tags': {}, 'pictures': []}
    i = data.find(b'\xa9lyr')
    if i >= 0:
        # 简单扫：©lyr 后跟 data box（含长度）
        try:
            j = data.index(b'data', i)
            ln = int.from_bytes(data[j - 4:j], 'big')
            start = j + 8
            out['tags']['LYRICS'] = data[start:start + ln - 8].decode('utf-8', 'replace')
        except Exception:
            pass
    i = data.find(b'covr')
    if i >= 0:
        try:
            j = data.index(b'data', i)
            ln = int.from_bytes(data[j - 4:j], 'big')
            out['pictures'].append({'mime': 'image/jpeg', 'w': 0, 'h': 0,
                                    'bytes': data[j + 8:j + 4 + ln]})
        except Exception:
            pass
    return out


def sniff(path):
    with open(path, 'rb') as f:
        head = f.read(12)
    if head[:4] == b'fLaC':
        return 'flac'
    if head[:3] == b'ID3':
        return 'id3'
    if len(head) >= 8 and head[4:8] == b'ftyp':
        return 'mp4'
    if head[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'):
        return 'mp3-raw'
    return 'unknown'


def split_translation(lyrics):
    """把 [TLYRIC] / [翻译] / [zh] 之后的段落拆出来（双语歌词常见结构）"""
    for marker in ('[TLYRIC]', '[翻译]', '[中文翻译]', '[ZH]'):
        if marker in lyrics:
            a, b = lyrics.split(marker, 1)
            return a.strip(), b.strip()
    return lyrics, ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('audio')
    ap.add_argument('-o', '--out', default=None, help='输出目录')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check', action='store_true', help='只报告真实格式')
    args = ap.parse_args()

    fmt = sniff(args.audio)
    if args.check:
        print('真实容器：%s（扩展名 %s）' % (fmt, os.path.splitext(args.audio)[1]))
        return 0

    with open(args.audio, 'rb') as f:
        info = read_flac(f) or read_id3(f) or read_mp4(f) or {'format': fmt, 'tags': {}, 'pictures': []}
    info['container'] = fmt

    lyrics = info['tags'].get('LYRICS') or info['tags'].get('UNSYNCEDLYRICS', '')
    main_l, trans = split_translation(lyrics)
    info['has_lyrics'] = bool(lyrics)
    info['lyrics_lines'] = len([l for l in main_l.split('\n') if l.strip()])
    info['trans_lines'] = len([l for l in trans.split('\n') if l.strip()])
    info['has_cover'] = bool(info['pictures'])

    if args.json or not args.out:
        show = {k: v for k, v in info.items() if k not in ('pictures',)}
        show['tags'] = {k: (v[:60] + '…' if len(v) > 60 else v) for k, v in info['tags'].items()}
        show['pictures'] = [{'mime': p['mime'], 'w': p['w'], 'h': p['h'], 'bytes': len(p['bytes'])}
                            for p in info['pictures']]
        print(json.dumps(show, ensure_ascii=False, indent=1))

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        if main_l:
            open(os.path.join(args.out, 'lyrics.lrc'), 'w', encoding='utf-8').write(main_l)
            print('[ok] lyrics.lrc  %d 行' % info['lyrics_lines'])
        if trans:
            open(os.path.join(args.out, 'lyrics.zh.txt'), 'w', encoding='utf-8').write(trans)
            print('[ok] lyrics.zh.txt  %d 行（翻译段）' % info['trans_lines'])
        for n, pic in enumerate(info['pictures']):
            ext = '.png' if 'png' in pic['mime'] else '.jpg'
            p = os.path.join(args.out, 'cover%s%s' % ('' if n == 0 else str(n), ext))
            open(p, 'wb').write(pic['bytes'])
            print('[ok] %s  %d×%d  %.0f KB' % (os.path.basename(p), pic['w'], pic['h'],
                                               len(pic['bytes']) / 1024))
        if not info['pictures']:
            print('[!] 没有内嵌封面 —— 需要向曲师/平台另取，或用 --check 确认文件是否被重封装过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
