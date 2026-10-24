# ⭐ 踩坑清单（PITFALLS）

> 这一页是整个仓库最贵的部分——每一条都是真实报错换来的。
> **每次写谱前通读一遍，能省掉 90% 的导入失败。**

---

## 一、报错 → 病因 → 修法（精确对照表）

### P01 `invalid length 0, expected struct RPEEventLayer with 5 elements`

**病因**：`eventLayers` 里的层不是完整的 5 事件结构。
**修法**：每层必须同时写全 5 个数组，哪怕都是空数组。

```json
"eventLayers": [{
  "alphaEvents": [], "moveXEvents": [], "moveYEvents": [],
  "rotateEvents": [], "speedEvents": []
}]
```

---

### P02 `trailing characters at line 1 column 601`

**病因**：`chart.json` 不是**单个**合法 JSON。常见于：
- 文件末尾拼接了第二个对象
- 生成时先写了一个 header 再 append
- UTF-8 BOM

**修法**：

```bash
python3 -c "import json;json.load(open('chart.json',encoding='utf-8-sig'))"   # 先验证
```

生成端只调用一次 `json.dump`，且用 `open(..., 'w', encoding='utf-8')`（不要 `utf-8-sig`）。

---

### P03 `missing field endTime at line 1706 column 9`

**病因**：**Tap / Flick 没写 `endTime`**。很多人以为只有 Hold 需要。
**修法**：**所有 note 都写 `endTime`**；非 Hold 统一写 `[0, 0, 1]` 占位。

```json
{ "type": 1, "startTime": [4,0,1], "endTime": [0,0,1], "positionX": 0, ... }
```

> 这是本项目**复发次数最多**的错误。`tools/chart_builder.py` 的 `note()` 已强制补全。

---

### P04 `missing field positionX at line 1711 column 9`

**病因**：note 缺 `positionX`（以及同类必填的 `size` / `visibleTime` / `alpha` / `yOffset`）。
**修法**：只使用这份 11 字段白名单：

```
type, startTime, endTime, positionX, speed, above, isFake,
alpha, size, visibleTime, yOffset
```

多一个都可能出错（见 P08）。

---

### P05 `invalid type: floating point 0.5, expected u32`

**病因**：beat 三元组里出现小数，例如 `[14, 0, 0.5]`。
**修法**：转成分数。

```python
from fractions import Fraction
f = Fraction(0.5).limit_denominator(16)   # 1/2
[14, 0 + f.numerator, f.denominator]      # → [14, 1, 2]
```

更一般地：`beat + frac` → `[int(beat), frac_num, frac_den]`（时间 = 整拍 + 分子/分母）。
**永远不要**把 float 直接塞进三元组。

---

### P06 `invalid type: boolean false, expected u8`

**病因**：把 `isCover` 写成了 `false`。
**修法**：`isCover: 0` / `isCover: 1`（int）。

同类：
- `isGif`：**是 bool**，写 `true/false`（别反过来）
- `isFake`：int
- `noteUniformScale` / `holdPartialCover`（info.yml）：bool

> 记忆口诀：**JSON 里只有 `isGif` 是布尔**，其余 `is*` 全是整数。

---

### P07 `invalid type: string 'dangerous_maid_001', expected i32` / `invalid type: string 'maid', expected i32`

**病因**：`info.yml` 的 `id`、`uploader` 写成了字符串。
**修法**：

```yaml
id: 88001        # 不是 "88001"
uploader: 1233   # 不是 "maid"
```

> 注意 `chart.json → META.id` **是字符串**，两个文件规则不同，别混。

---

### P08 各种"多余字段 / 类型不符"

**病因**：把 RPE 编辑器内部字段（`tint`、`judgeArea` 等）原样抄进了 Phira 谱面。
**修法**：note 只保留 11 个白名单字段；判定线只保留 19 个规范字段。
拿不准时，**打开一张成功导入的谱，逐字段 diff**。

---

### P09 `mapping values are not allowed in this context at line 25 column 34`

**病因**：`info.yml` 字符串里有裸冒号（`:`），YAML 把它当键值分隔符。
**修法**：给字符串加引号。

```yaml
intro: '谱师: Maid'                  # ✅
tip: "Dangerous! The girl..."       # ✅
```

另外：YAML **不能用 Tab 缩进**。

---

### P10 `missing field start at line 35840 column 11`

**病因**：事件对象缺 `start`。多见于自己手写事件时只写了 `startTime`+`end`。
**修法**：事件 10 个字段一个不能少：

```
startTime, endTime, start, end, easingType,
easingLeft, easingRight, bezier, bezierPoints, linkgroup
```

---

### P11 `missing field bpm at line 1043 column 1`（导入成功，加载谱面失败）

**病因**：`BPMList` 的元素缺 `bpm`，或 `extra.json` 的 bpm 段格式错。
**修法**：

```json
"BPMList": [{ "bpm": 128.0, "startTime": [0,0,1] }]
```

> 这类错误只在**加载**阶段暴露，所以"导入成功"≠"能玩"。**必须验证到能进游戏。**

---

### P12 `extra.json` 的 `start` / `end` 写成了数字

**病因**：以为特效时间是秒数。
**修法**：`"start": [2,0,1]`、`"end": [4,0,1]`，beat 三元组。

---

### P13 时间全部挤在歌曲前 1/4：把"小节"当成了 beat

**症状**：161 秒的歌，所有 note 都落在前 40 秒；谱面后半段完全空白。

**病因**：把三元组的 `[0]` 当成了"小节号"，写成 `[小节, 小节内拍, 0]`。
RPE 的 `[0]` 实际是**第几拍（quarter beat）**，且**分母不能是 0**。

**错误写法**（Dangerous 初版）：
```json
"startTime": [9, 2, 0]     // 以为 = 第 9 小节第 2 拍
```

**正确写法**：
```json
"startTime": [38, 0, 1]    // 9*4 + 2 = 38 拍
```

**自检法**：`max(beat) * 60 / BPM` 应该约等于歌曲时长。差 4 倍就是踩了这个坑。

---

### P14 info.yml 有两套字段命名，别混用

Phira 同时接受：

- **RPE 格式（推荐）**：`name / music / illustration / chart / level / composer / charter / difficulty / id / uploader ...`
- **旧版 Phi 格式**：`Name / Song / Picture / Chart / Level / Composer / Charter`（只有 7 个字段，也能导入）

真实案例：`你总是盘旋在我脑海里面.zip` 用的是旧版大写格式，Phira 照样能导入。

**规则**：一套用到底。混着写（比如同时有 `name` 和 `Song`）容易解析成半空对象。

---

## 二、能导入但"没法玩"的问题

| 症状 | 病因 | 修法 |
|---|---|---|
| note 全黏在判定线上，没有下落 | 判定线静止 + 没有 `speedEvents`；或 `speed` 太小 | 给演奏线写 `speedEvents`（如 10 → 12），note `speed` 用 1.0 |
| note 全挤在屏幕中间 | `positionX` 全是 0 / 随机范围太小 | 用离散对称坐标 ±490/±368/±306/±184/±122/0 |
| 有些 note 看不见 | `alpha=0`、`alphaEvents` 把线透明了、`above` 方向反了、`isFake=1` | 检查 alpha 与线透明度 |
| 下落太慢，手感拖沓 | `speedEvents` 值过小（<5），或 `bpmfactor` 不对 | 常规流速 8~12；变速段 3~20 |
| 判定线表演全在中间 | `moveX/moveY` 振幅只有 ±50 | 用满 X∈[-675,675]、Y∈[-450,450] |
| 演出挡视线，看不清 note | 表演线 `zOrder` 压在演奏线上；alpha 太高 | 表演线 `zOrder` 调低、alpha 100~200 |
| 特效加了比不加还难看 | 全局特效长时间堆叠 | 单段 ≤2 个特效，参数默认 0，只在拍点推峰值 |
| 越到后面越偏 | `BPMList` 漏变速点 | 补齐所有 BPM 段 |
| 判定全 Miss / 音符一闪而过 | `visibleTime` 太小（有人误写成 0.5） | 常规 `999999.0` |

---

## 三、为什么会反复踩同一个坑

真实教训：**格式错误不是"知识不足"，是"流程缺失"**。

错误做法：
```
凭记忆写字段 → 打包 → 导入 → 报错 → 改一个 → 再导入 → 又报错 → ...
```

正确做法：
```
① 打开一张已验证可导入的谱作为"类型基准"
② 用 chart_builder 生成（字段由库保证）
③ 跑 validate_chart.py（静态检查）
④ 再打包导入
```

**核心心法**：*不要问"这个字段应该是什么类型"，去问"参考谱里它是多少、什么类型"。*

---

## 四、字段类型总表（打印出来贴墙）

| 位置 | 字段 | 类型 |
|---|---|---|
| info.yml | `id` / `uploader` | **int** |
| info.yml | `difficulty` / `offset` / `previewStart` | float |
| info.yml | `tags` | list[string] |
| chart.json | `META.id` / `META.level` / `META.name` | **string** |
| chart.json | `META.offset` | **int（毫秒）** |
| chart.json | `META.RPEVersion` | int |
| chart.json | 所有 `startTime` / `endTime` | **beat[3]，全整数** |
| chart.json | `note.positionX` | **number（int/float 都可）** |
| chart.json | `note.type` / `above` / `isFake` / `alpha` | int |
| chart.json | `note.speed` / `size` / `visibleTime` / `yOffset` | number |
| chart.json | `note.judgeArea` / `note.tint`（可选） | 真实谱面常见，Phira 接受 |
| chart.json | `line.Group` / `father` / `isCover` / `zOrder` / `numOfNotes` | **int** |
| chart.json | `line.isGif` | **bool** |
| chart.json | `line.anchor` | [float, float] |
| chart.json | `line.bpmfactor` | float |
| chart.json | `line.posControl` / `sizeControl` / `skewControl` / `yControl` | **array（不能是 {}）** |
| chart.json | `line.extended` | **object** |
| chart.json | `event.easingType` / `bezier` / `linkgroup` | int |
| chart.json | `event.easingLeft` / `easingRight` / `bezierPoints` | float |
| chart.json | `textEvent.start` / `end` | **string** |
| extra.json | `effect.start` / `effect.end` | **beat[3]** |
| extra.json | `effect.global` | bool |
| extra.json | `effect.vars` | object |

---

## 五、血泪教训（不是技术，是态度）

1. **"导入成功了"不等于完成**。要玩到、要手感对、要好看。
2. **不要生搬硬套参考谱**。学的是"为什么这么排"，不是把别人的 event 复制过来。
3. **先分析音乐再碰谱面**。没有音乐理解的谱面，音符再多也是噪音。
4. **一次只改一类东西**（时间 / 位置 / 演出 / 特效），否则出了问题无法定位。
5. **每改必验**。`validate_chart.py` 5 秒，比导入失败后重来 5 分钟便宜。
6. **保留版本**。`v1` `v2` `v3` 都留着，用户说"上一版更好"时能立刻回滚。
