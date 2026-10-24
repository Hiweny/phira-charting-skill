# 03 · chart.json（RPE 格式）完整规范

> 本文件中的**类型**均来自真实可导入谱面的字段实测。
> 写代码时把这里的类型表当成契约，不要凭印象。

## 1. 顶层结构（7 个字段）

```json
{
  "BPMList": [ { "bpm": 128.0, "startTime": [0, 0, 1] } ],
  "META": { ... },
  "chartTime": 200.0,
  "judgeLineGroup": ["Default", "Performance"],
  "judgeLineList": [ ... ],
  "multiLineString": "",
  "multiScale": 1.0
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `BPMList` | array | ✅ | BPM 变化列表，见 §2 |
| `META` | object | ✅ | 元数据，见 §3 |
| `chartTime` | float | ✅ | 编辑器内总时长（秒），一般取音乐时长 |
| `judgeLineGroup` | array[string] | ✅ | 组名表，`Group` 字段是它的下标 |
| `judgeLineList` | array | ✅ | 判定线列表，**核心数据** |
| `multiLineString` | string | ❌ | 多行文本，没有就给 `""` |
| `multiScale` | float | ❌ | 多线缩放，没有就给 `1.0` |

> ⚠️ 实测 `multiLineString: []`、`multiScale: false` 也能被容忍，但**不要学**，按规范给 `""` / `1.0`。

## 2. BPMList

```json
"BPMList": [
  { "bpm": 128.0, "startTime": [0, 0, 1] },
  { "bpm": 174.0, "startTime": [64, 0, 1] }
]
```

- `bpm`：float，**必需**。缺了会在"加载谱面"阶段报 `missing field bpm`（导入能过，加载失败）。
- `startTime`：beat 三元组（整数）。
- 变速曲必须按时间顺序列出**所有** BPM 段；段内时间换算见 [`05-timing.md`](05-timing.md)。

## 3. META

```json
"META": {
  "RPEVersion": 170,
  "background": "illustration.png",
  "charter": "Maid",
  "composer": "Michael Jackson",
  "duration": 161.56,
  "id": "dangerous_maid",
  "level": "IN 13",
  "name": "Dangerous (Immortal Version)",
  "offset": 0,
  "song": "song.mp3"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `RPEVersion` | int | 170 = RPE 1.7.0（本项目验证版本） |
| `background` | string | 背景图文件名 |
| `charter` | string | 谱师 |
| `composer` | string | 曲师 |
| `duration` | float | 音乐时长（秒） |
| `id` | **string** | ⚠️ 这里可以也是字符串，与 info.yml 的 int 不同 |
| `level` | string | 难度显示 |
| `name` | string | 曲名 |
| `offset` | int | **毫秒** |
| `song` | string | 音乐文件名 |

> `META` 里的元数据 **Phira 以 `info.yml` 为准**（官方文档明确说明 RPE JSON 存元数据不被推荐）。两边保持一致最稳。

## 4. judgeLineList（判定线）

```json
{
  "Group": 0,
  "Name": "Main",
  "Texture": "line.png",
  "anchor": [0.5, 0.5],
  "bpmfactor": 1.0,
  "eventLayers": [ { ... } ],
  "extended": {},
  "father": -1,
  "isCover": 0,
  "isGif": false,
  "notes": [ ... ],
  "numOfNotes": 0,
  "posControl": [],
  "sizeControl": [],
  "skewControl": [],
  "yControl": [],
  "alphaControl": [ {"alpha": 1.0, "easing": 1, "x": 0.0},
                    {"alpha": 1.0, "easing": 1, "x": 9999999.0} ],
  "zOrder": 0
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `Group` | **int** | ✅ | `judgeLineGroup` 下标 |
| `Name` | string | ✅ | 线名（给自己的语义标签） |
| `Texture` | string | ✅ | 默认 `"line.png"` |
| `anchor` | [float, float] | ⭕ | 纹理锚点，省略时默认 `[0.5,0.5]` |
| `bpmfactor` | float | ✅ | BPM 影响因子，默认 1.0 |
| `eventLayers` | **array** | ✅ | 事件层，最多 5 层，见 §5 |
| `extended` | **object** | ✅ | 扩展事件，没有就给 `{}` |
| `father` | **int** | ✅ | 父线下标，`-1` = 无 |
| `isCover` | **int** | ✅ | `0/1`，**不是 bool** |
| `isGif` | bool | ⭕ | 纹理是否 GIF；**只有它是布尔**，省略默认 false |
| `notes` | array | ⭕ | 音符列表；没有音符的线可省略 |
| `numOfNotes` | int | ⭕ | 导出器缓存字段，Phira 会自行统计，**不要依赖它** |
| `posControl` | **array** | ✅ | 位置控制序列，**必须是 `[]` 不能是 `{}`** |
| `sizeControl` | **array** | ✅ | 尺寸控制序列 |
| `skewControl` | **array** | ✅ | 倾斜控制序列 |
| `yControl` | **array** | ✅ | Y 轴控制序列 |
| `alphaControl` | array | ✅ | 全局透明度控制，**这个是真数组** |
| `zOrder` | int | ✅ | 图层顺序，±100 |

### 4.1 坐标系

- 屏幕中心为原点。X ∈ [-675, 675]，Y ∈ [-450, 450]（16:9）。
- 超出范围 = 线/音符飞出屏幕，可用于"划过"效果，但演奏线别乱跑。

### 4.2 Control 序列的语义

`alphaControl` / `posControl` / `sizeControl` / `yControl` / `skewControl`
控制"音符离判定线越远，属性如何变化"：

| 字段 | 效果 | 典型值 |
|---|---|---|
| `alphaControl` | 远端透明度 | 1.0 常亮 |
| `posControl` | 远端位置偏移缩放 | 1.0 |
| `sizeControl` | 远端大小缩放 | 1.0 |
| `yControl` | 远端 Y 缩放 | 1.0 |
| `skewControl` | 远端倾斜 | 0.0 |

多数谱面保持默认。`alphaControl` 的数组元素格式为 `{alpha, easing, x}`，`x` 是"距离"参数（默认写 0 和 9999999 两个端点）。

## 5. eventLayers

**推荐每层写全 5 个事件数组**（最稳）：

```json
"eventLayers": [
  {
    "alphaEvents":  [],
    "moveXEvents":  [],
    "moveYEvents":  [],
    "rotateEvents": [],
    "speedEvents":  []
  }
]
```

真实 Phira 谱面里也有只写部分数组的层（缺的由默认值补齐），但**不同版本对缺省字段的严格程度不一样**。为了不踩版本差异，生成谱面时一律写全 5 个数组。

另外：`eventLayers` 里的单个元素可以是 `null`（表示空图层），真实谱面大量使用这种写法。

| 事件 | `start`/`end` 类型 | 语义 |
|---|---|---|
| `alphaEvents` | int 0~255 | 透明度。**end 为负数 → 隐藏该线及其全部 note** |
| `moveXEvents` | float | 水平位移（像素） |
| `moveYEvents` | float | 垂直位移 |
| `rotateEvents` | float | 旋转角度（度，逆时针为正） |
| `speedEvents` | float | 音符流速倍率；**负数 = 音符向上飞** |

### 5.1 单个事件对象

```json
{
  "startTime": [0, 0, 1],
  "endTime": [4, 0, 1],
  "start": 0,
  "end": 255,
  "easingType": 1,
  "easingLeft": 0.0,
  "easingRight": 1.0,
  "bezier": 0,
  "bezierPoints": [0.0, 0.0, 0.0, 0.0],
  "linkgroup": 0
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `startTime` / `endTime` | beat[3] | **三个整数** |
| `start` / `end` | number | int（alpha）或 float（其他） |
| `easingType` | int | 缓动序号，见 §5.2 |
| `easingLeft` / `easingRight` | float | 缓动作用区间，默认 0 / 1 |
| `bezier` | int | 1 = 使用 `bezierPoints` 自定义曲线 |
| `bezierPoints` | 4 个数 | 三次贝塞尔控制点 |
| `linkgroup` | int | 联动组，0 = 不联动 |

> `bezierPoints` 实测 `[0,0,0,0]`（int）与 `[0.0,0.0,0.0,0.0]`（float）都能过，统一写 float 即可。

### 5.2 缓动序号（Easing）

来源：[Phigros 自制谱 Wiki · 缓动](https://pgrfm.miraheze.org/wiki/%E7%BC%93%E5%8A%A8)

| 序号 | 含义 |
|---|---|
| 0 | fixed（阶跃，无过渡） |
| 1 | linear（线性） |
| 2 | easeInSine |
| 3 | easeOutSine |
| 4 | easeInQuad |
| 5 | easeOutQuad |
| 6 | easeInOutSine |
| 7 | easeInOutQuad |
| 8 | easeInCubic |
| 9 | easeOutCubic |
| 10 | easeInQuart |
| 11 | easeOutQuart |
| 12 | easeInOutCubic |
| 13 | easeInOutQuart |
| 14+ | Quint / Expo / Circ / Back / Elastic / Bounce 系列 |

**实践建议**：
- 拍点跳动、瞬间切换 → `0` 或 `1`
- 平滑移动 / 缓动飘落 → `1`（线性）配合高频关键帧，或 `3` / `5` 缓出
- 呼吸感振荡 → 用线性事件拼正弦，不要指望缓动能做出循环

> 官谱 JSON 里几乎只有线性缓动，非线性效果靠"大量线性关键帧"拟合。**高频线性关键帧 > 一个长非线性事件**，这是演出感的关键差别。

## 6. notes（音符）

```json
{
  "type": 1,
  "startTime": [4, 0, 1],
  "endTime": [0, 0, 1],
  "positionX": 0,
  "speed": 1.0,
  "above": 1,
  "isFake": 0,
  "alpha": 255,
  "size": 1.0,
  "visibleTime": 999999.0,
  "yOffset": 0
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `type` | int | ✅ | 1=Tap · 2=Hold · 3=Flick · 4=Drag |
| `startTime` | beat[3] | ✅ | **三个整数** |
| `endTime` | beat[3] | ✅ | **不能省略**。Tap/Flick 也要写 `[0,0,1]` 占位 |
| `positionX` | **number** | ✅ | 相对判定线中心的 X。真实谱面大量使用小数（如 337.5 / 385.71） |
| `speed` | float | ✅ | 音符自身流速倍率 |
| `above` | int | ✅ | 1=正面，其他=背面 |
| `isFake` | int | ✅ | 1=假音符（不判定、不计分，纯装饰） |
| `alpha` | int | ✅ | 0~255 |
| `size` | float | ✅ | 大小倍率，1.0 标准 |
| `visibleTime` | float | ✅ | 可见时间（秒），常规写 `999999.0` |
| `yOffset` | number | ✅ | Y 偏移，一般 `0` |

### 6.1 不要出现的字段

`tint`、`judgeArea` 等 RPE 编辑器内部字段 **不要写进 Phira 谱面**。
多余的字段会导致类型错误或解析失败。只写上表 11 个键最安全。

### 6.2 四类 note 的设计语义

| 类型 | 操作 | 设计用途 |
|---|---|---|
| Tap (1) | 点击 | 主节奏骨架、重音 |
| Hold (2) | 按住到 endTime | 长音、人声、弦乐持续 |
| Flick (3) | 到达时滑动 | 转折、镲片、情绪爆点 |
| Drag (4) | 手指经过即可 | 密集过场、装饰性流动、多线交错 |

### 6.3 Hold 的 endTime

- Hold（type=2）和 Drag（type=4）**必须有意义地使用 `endTime`**。
- `endTime` 的 beat 值必须 ≥ `startTime`。
- 其余类型 `endTime` 可以等于 `startTime`，但为了兼容统一写 `[0,0,1]`（本项目实测通过）。

## 7. extended（扩展事件）

`extended` 是对象，按需放以下键（全部为**事件数组**）：

| 键 | 作用 |
|---|---|
| `textEvents` | 文字/歌词。`start`/`end` 是**字符串**，另有 `font` 字段 |
| `scaleXEvents` / `scaleYEvents` | 纹理缩放（可把小图放大铺满屏） |
| `colorEvents` | 判定线颜色（RGB） |
| `gifEvents` | GIF 播放控制 |
| `paintEvents` | 纹理/涂色相关 |

`textEvents` 单个事件：

```json
{
  "startTime": [16, 0, 8],
  "endTime": [24, 0, 8],
  "start": "歌词内容",
  "end": "歌词内容",
  "font": "",
  "easingType": 1,
  "easingLeft": 0.0,
  "easingRight": 1.0,
  "bezier": 0,
  "bezierPoints": [0.0, 0.0, 0.0, 0.0],
  "linkgroup": 0
}
```

> 用 `textEvents` 做歌词时，`start`/`end` 都写同一句话即可。留空字符串 = 清空文字。

## 8. 最小可导入骨架

完整文件见 [`examples/minimal/chart.json`](../../examples/minimal/chart.json)。核心就三条线：

```json
{
  "BPMList": [{"bpm": 120.0, "startTime": [0,0,1]}],
  "META": {"RPEVersion":170,"background":"illustration.png","charter":"Maid","composer":"Unknown","duration":30.0,"id":"demo","level":"IN 1","name":"Demo","offset":0,"song":"song.mp3"},
  "chartTime": 30.0,
  "judgeLineGroup": ["Default"],
  "judgeLineList": [ { ...一条线，notes 至少 1 个... } ],
  "multiLineString": "",
  "multiScale": 1.0
}
```

## 9. 结构速查清单

```
chart.json
├─ BPMList[]        bpm(float) + startTime(3 int)
├─ META             10 个字段
├─ chartTime        float
├─ judgeLineGroup[] string
├─ judgeLineList[]  19 个字段
│   ├─ eventLayers[] 每层推荐 5 个事件数组（可为 null）
│   │   └─ 事件 {startTime,endTime(3int),start,end,easingType,...}
│   ├─ extended{}    text/scaleX/scaleY/color/gif
│   └─ notes[]       {type,startTime,endTime,positionX(int),speed,above,isFake,alpha,size,visibleTime,yOffset}
└─ multiLineString / multiScale
```
