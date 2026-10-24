# 05 · 时间系统（beat 三元组）

这是整个格式**最容易翻车**的地方。

## 1. 格式

```
[whole, numerator, denominator]
 整拍      分子        分母
```

时间值（单位：四分音符拍，quarter beat）：

```
beat = whole + numerator / denominator
```

- 三个元素**全部必须是整数**（Rust 里是 `u32`）。
- **分母必须 ≥ 1**。整数拍写 `[3, 0, 1]`，绝不能写 `[3, 0, 0]` —— RPE 的换算公式里有除法，分母 0 会得到 NaN/Inf。
- **禁止** `[14, 0, 0.5]`。要表示半拍写 `[14, 1, 2]`。

> 官方换算（[phira-docs · rpe/beat](https://github.com/TeamFlos/phira-docs/blob/main/src/chart-standard/chart-format/rpe/beat.md)）：
> `double beat = RPEBeat[1] / RPEBeat[2] + RPEBeat[0];`
> `double seconds = 60 / BPM * beat;`

## 2. 最容易搞混的一点：`[0]` 是"第几拍"，不是"第几小节"

`[0]` 的单位是**四分音符拍**，不是小节号。

- 4/4 拍里，第 2 小节第 3 拍 = 第 `2*4 + 2 = 10` 拍 → 写 `[10, 0, 1]`。
- 写谱时**先统一用 beat 值思考**，最后再转三元组。
- 一旦把 `[0]` 当小节号，整张谱的时间会缩小到 1/4，典型症状是"音符全挤在歌曲前 40 秒"。

> 真实踩坑：曾经用 `[小节, 小节内拍, 0]` 生成了一张 161 秒的谱，所有音符落在前 40 秒内。
> 排查方法：`max(beat) * 60 / BPM ≈ 歌曲时长`？不等就说明三元组语义用错了。

## 3. 拍 → 秒

单 BPM：

```
seconds = beat * 60 / bpm
```

多 BPM（分段累加）：

```
sec = 0
for 每个 BPM 段 i:
    if 目标 beat 落在段 i 内:
        sec += (目标beat - 段i起始beat) * 60 / 段i.bpm
        break
    else:
        sec += (段i+1起始beat - 段i起始beat) * 60 / 段i.bpm
```

## 4. 秒 → 拍（写谱时最常用）

```python
def sec_to_beat(sec, bpm):
    return sec * bpm / 60.0
```

再转三元组（**用 Fraction，不要手写浮点**）：

```python
from fractions import Fraction

def bt_from_beat(beat_value, max_den=16):
    """beat_value 如 12.375 → [12, 3, 8]"""
    f = Fraction(beat_value).limit_denominator(max_den)
    whole = int(f)                # 整数拍部分
    num = f.numerator - whole * f.denominator
    den = f.denominator
    if num == 0:
        return [whole, 0, 1]
    return [whole, num, den]
```

> 直接 `int(x*1000)/1000` 再转分会得到 `0.375` 之类的小数，写进 JSON 就报错。
> **一律走 `Fraction`**。

## 5. 常用等价写法（beat 值 = `[0] + [1]/[2]`）

| 想要的拍值 | 写法 | 说明 |
|---|---|---|
| 第 8 拍 | `[8, 0, 1]` | 8.0 |
| 第 8 拍后半拍 | `[8, 1, 2]` | 8.5 |
| 第 8 拍 1/4 处 | `[8, 1, 4]` | 8.25 |
| 第 8 拍 1/8 处 | `[8, 1, 8]` | 8.125 |
| 第 8 拍 3/16 处 | `[8, 3, 16]` | 8.1875 |
| 第 3 拍 | `[3, 0, 1]` | 3.0 |

`tools/chart_builder.py` 的 `bt()` 已经帮你做完了这件事：

```python
bt(8)      -> [8, 0, 1]
bt(8.5)    -> [8, 1, 2]
bt(8.375)  -> [8, 3, 8]
bt(8, 3, 16) -> [8, 3, 16]
```

## 6. offset

| 位置 | 单位 | 用途 |
|---|---|---|
| `info.yml.offset` | 秒（float） | 手感校准，**以此为准** |
| `chart.json → META.offset` | 毫秒（int） | 兼容用 |

调整原则：
- 玩家觉得"音符来得早"→ 减小 offset（或调大，取决于约定；**一次只改 10~20ms 试**）。
- 每次调整后记录版本号，别一次改 200ms。

## 7. BPM 变化

`BPMList` 必须覆盖整首曲子的所有变速点：

```json
"BPMList": [
  { "bpm": 128.0, "startTime": [0, 0, 1] },
  { "bpm": 128.0, "startTime": [32, 0, 1] },
  { "bpm": 174.0, "startTime": [64, 0, 1] },
  { "bpm": 128.0, "startTime": [96, 0, 1] }
]
```

- 顺序必须按时间递增。
- 相同 BPM 重复列出也无害，但没必要。
- **漏掉变速点 = 后半段整体偏移**，这是"感觉谱面越玩越飘"的常见原因。

## 8. 自检脚本里的时间校验

[`tools/validate_chart.py`](../../tools/validate_chart.py) 会检查：

- 三元组元素是否全为整数
- 分母是否为 0（任何分母为 0 都报 error）
- `endTime < startTime` 的 note / event
- note 时间是否超出 `META.duration`（不是 `chartTime`，后者在部分导出中是 0 或单位异常）
- `META.duration` 缺失时回退到 `chartTime` / 最后一个 note
