# 判定线的四种形态：普通 / 文字 / 光圈 / 贴图（附 shader 特效）

> 一条判定线在客户端里**能画成四种完全不同的东西**，取决于 `Texture` 与 `extended` 里
> 有没有 `paintEvents` / `textEvents`。这个判定顺序在 prpr 源码
> `prpr/src/parse/rpe.rs` 里写得很死，踩错就"什么都不显示"。

## 1. 判定顺序（照抄源码）

```rust
kind: if rpe.texture == "line.png" {
    if paintEvents 存在  → Paint   // 圆形填充（光圈 / iris）
    else if textEvents   → Text    // 居中文案
    else                 → Normal  // 普通一条线
} else {
    → Texture          // 贴图精灵，text/paint 全部失效
}
```

由此得到四条硬规则：

| 你想要 | 必须满足 | 反例（会静默失效） |
|---|---|---|
| 普通线 | `Texture: "line.png"` | — |
| 文字 | `Texture: "line.png"` + `textEvents`，**且没有** `paintEvents` | 写了 `paintEvents` → 文字被吞 |
| 光圈 | `Texture: "line.png"` + `paintEvents` | 贴图线 + paint → 光圈不生效 |
| 贴图精灵 | `Texture` 指向真实图片 | 贴图线 + text → 文字不显示 |

`validate_chart.py` 会对以上三种失效组合直接报警（§`_check_line_kinds`）。

---

## 2. `textEvents`：文字系统

### 2.1 字段（实测 4 张谱全部一致）

```json
{
  "startTime": [316, 0, 1],          // 拍三元组
  "endTime":   [319, 3, 4],
  "start":     "",                    // 起始文本（空串 = 打字机）
  "end":       "-貴女の想",           // 目标文本
  "easingType": 1,
  "easingLeft": 0.0,
  "easingRight": 1.0,
  "bezier": 0,
  "bezierPoints": [0.0, 0.0, 0.0, 0.0],
  "linkgroup": 0
}
```

**没有** `font`、`size`、`align`、`color` 字段。字体与字号是客户端固定的，
颜色取该线的 `colorEvents`，透明度取该线的 `alphaEvents`。
（网上有的教程让你写 `"font": "..."`，那是无效字段，`chart_builder` 早期版本也这么写过，已删。）

### 2.2 三种用法

**静态字幕**：`start == end`，从 `startTime` 持续到 `endTime`。

```json
{"startTime":[1,0,1],"endTime":[3,0,1],
 "start":"   鹿be free\n\n谱师:时辰shars\n\n  演唱:尚雯婕",
 "end":  "   鹿be free\n\n谱师:时辰shars\n\n  演唱:尚雯婕"}
```
> 出自 84416（Lv.9）。注意它是**用空格 + 换行手动排版**的，因为客户端没有对齐参数。

**打字机**：`start: ""` → `end: "全文"`，文本按进度逐字出现。

```json
{"startTime":[316,0,1],"endTime":[319,3,4],"start":"","end":"-貴女の想"}
```
> 出自 84336（Lv.18）。同一句常拆成 2~3 个连续事件，做出"说到一半停一下"的呼吸感：
> `"" → "-貴女の想"`，`"-貴女の想" → "-貴女の想い"`。

**整体推送**：`start` 与 `end` 都是完整句子但内容不同，用于换行字幕（用得少）。

### 2.3 渲染细节（prpr 实测）

```rust
draw_text_aligned(ui, &now, 0., 0., (0.5, 0.5), 1., color);
```

- 锚点固定 **正中心** `(0.5, 0.5)`，无法改成左对齐
- 缩放参数固定 `1.0` → **字号不可调**
- 位置 = 这条线自身的位置（`posControl` / `moveX` / `moveY` / `rotate` 都作用在文字上）
- 多行用 `\n`，行距由客户端决定
- 因此"标题变大"只能靠 **scaleX/scaleY**，或者干脆做多条线

### 2.4 怎么用它做叙事

| 场景 | 做法 |
|---|---|
| 曲名 / Staff | 静态字幕，3~4 秒，配 `alpha 0→255→0` |
| 念白 / 歌词 | 打字机，一句一个事件，卡在乐句起点 |
| 剧情对话 | 2 条线分别放在上下 1/3 处，交替 `alpha` |
| 强调重音 | 文字 `moveY` 弹一下 + `colorEvents` 闪白 |

---

## 3. `paintEvents`：零素材光圈（iris）

字段与普通事件一致，但 `start` / `end` 是**像素半径**：

```json
{"startTime":[9,0,1],"endTime":[15,0,1],"start":0.0,"end":1500.0}
```

渲染语义（prpr `line.rs`）：

```rust
if size <= 0. { 清空 }                       // 半径 <= 0 = 不画
else { ui.fill_circle(0., 0., size / vp.2 * 2., color); }
// 随后把整个离屏 pass 贴满屏幕 → 只剩一个圆
```

- `-1` 是编辑器写的"未设置"哨兵，等于关闭
- 圆心 = 判定线原点，所以**用 `moveX/moveY` 可以把光圈中心挪走**
- 半径 1200+ 就是满屏，常用来做"黑场 → 开屏"

**一次开屏**：

```python
iris = c.add_line("iris", texture="line.png", z_order=9)
iris.add_paint(9, 15, 0.0, 1500.0)          # 0 → 1500 像素，开屏
```

**一次收束**（转场到下一段）：反向写 `1500 → 0`。
这就是《enchanted love》里那些"光圈开合"的实现方式，**不需要任何贴图**。

---

## 4. `gifEvents`：GIF 帧进度

```json
{"startTime":[153,0,1],"endTime":[154,1,6],"start":0.0,"end":1.0}
```

- 值是 **0~1 的归一化播放进度**，不是播放速度
- `0 → 1` = 让这张 GIF 完整播一遍（实测：《enchanted love》line 180，`scan.line_45deg.gif`，
  用 1.2 拍播完一次"斜向扫描线"）
- 恒定值 = 定格在某一帧
- 需要真实 GIF 文件；`preview_render` 目前只取首帧，看不到动画

---

## 5. shader 特效（`effects`）

### 5.1 存在哪里

| 位置 | 谁读 |
|---|---|
| `extra.json` 的 `effects` | prpr（`ChartExtra.effects`） |
| `chart.json` 顶层 `effects` | RPE 1.7 编辑器 |

**两边都写**才不会丢。`chart_builder.save()` 现在会自动双写。

### 5.2 结构

```json
{
  "shader": "/rain_pr.glsl",   // 或内置名，如 "grayscale"
  "start":  [1,0,1],           // 拍
  "end":    [2,0,1],
  "global": false,
  "line":   0,                 // 绑定到哪条线的渲染上下文（0 = 全屏层）
  "order":  0,
  "clone":  false,
  "vars": {
    "density": [{"startTime":[0,5,8],"endTime":[2,0,1],"start":0,"end":100,"easingType":1}],
    "height":  [{"startTime":[1,0,1],"endTime":[2,0,1],"start":0.03,"end":0.03,"easingType":1}]
  }
}
```

要点：

- `shader` 带前导 `/` 表示工程根目录下的文件
- `vars` 的每个键都是**一条时间轴（事件数组）**，和其它通道完全同构
- 同一个 shader 可以挂多段（开 → 保持 → 关），靠 `start/end` 拼

### 5.3 社区在用的 shader（84256，Lv.12，共 14 个 effect）

| shader | 次数 | 变量 | 效果 |
|---|---|---|---|
| `glow_effect_pr.glsl` | 6 | `intensity` `threshold` | 辉光 / 泛光，随副歌起落 |
| `rain_pr.glsl` | 3 | `density` `height` | 雨 |
| `snow_pr.glsl` | 3 | `size` `snowCount` | 雪 |
| `grayscale`（内置） | 2 | `factor` | 灰度，做段落抽色 |

真实用法（84256）：

```
0.6s  rain  density 0 → 100     （雨渐起）
2.6s  rain  density 保持 100
10.5s rain  density 100 → 0     （雨停）
12.0s glow  intensity 0 → 0.8   （副歌泛光）
...   glow  intensity 保持 0.8
148s  grayscale factor 0 → 1    （尾段抽成黑白）
```

注意它们**都不是"加个滤镜"，而是按段落开关的叙事工具**。

### 5.4 环境变量约定

社区 shader 用 `#version 100` + `uniform sampler2D screenTexture` / `uniform vec2 screenSize`，
并在头部标注模板来源：

```glsl
// @rpen-template {"name":"rain_pr","chart":"好きな隙間","version":1}
// @rpen-builtin
```

`@rpen-builtin` 说明它来自 rpen 的内置模板库，可复用。

---

## 6. 客户端差异（决定"能不能用"）

| 能力 | RPE 编辑器 | prpr（PC 播放器） | Phira |
|---|---|---|---|
| 文字 | ✅ | ✅（居中、字号固定） | ⚠️ 未实测 |
| 光圈 paintEvents | ✅ | ✅ | ⚠️ 未实测 |
| GIF 帧进度 | ✅ | ✅（需真实 gif） | ⚠️ 未实测 |
| `.glsl` shader | ✅ | ✅（miniquad 后端） | ❌ 一般不加载 |

**结论：文字/光圈/GIF 属于"RPE 原生 + prpr 可播"，发到 Phira 前必须实机确认。**
纯 RPE 原生谱（本站主要分发对象是 Phira）里，这三样要谨慎使用，
最稳的替代是"贴图 + alpha"，代价是多一张图。

---

## 7. 自检渲染怎么做近似（`preview_render`）

PIL 跑不了 GLSL，所以按"看到的结构对、参数随事件轴变化"的标准做近似。
**作用：验证演出节奏，不追求像素级一致。**

| shader | 近似做法 | 变量映射 |
|---|---|---|
| `grayscale` | `Image.blend(原图, 灰度图, factor)` | `factor` 0~1 |
| `glow_effect_pr` | 亮度阈值取亮部 → 高斯模糊 → `screen` 叠加 | `intensity`、`threshold` |
| `rain_pr` | 画 N 条斜线，`y` 随时间循环 | `density`(条数)、`height`(长度比)、`width`、`speed` |
| `snow_pr` | N 个白点，`x/y` 随时间漂移 | `snowCount`、`size`、`speedx`、`speedy` |
| `chromatic` | R/B 通道水平位移 | — |

实现要点：

- `effects` 会同时从 `extra.json` 与 `chart.json` 顶层合并（按 `startTime + shader` 去重）
- 每个变量都走**事件轴求值**，所以"雨从 0 加到 100"在自检里也真的是渐进的
- 未知 shader 名称会被忽略但不报错，`HUD` 里会显示当前激活的 shader 名

**GIF 判定线**：`preview_render` 现在会按 `gifEvents` 的进度取帧
（`gif_frame_index()`），所以"扫描线扫过一次"这类动画可以逐帧验收。
GIF 只随事件走、不按真实时间自播 —— 这与 RPE 的行为一致。

**已知近似误差**：

| 项 | 差异 |
|---|---|
| 雨/雪 | 用的是固定随机种子，不是 shader 里的 hash，图案不会逐帧完全一致 |
| 辉光 | 只做一层模糊，真实 shader 是多重采样 |
| 文字 | 字体、字号取自本机 Noto CJK，客户端可能不同 |
| 光圈 | 用 `ellipse` 填充，边缘无抗锯齿 |

---

## 8. 踩坑清单

| 现象 | 原因 | 修法 |
|---|---|---|
| 文字完全不显示 | `Texture` 是真实贴图 | 改成 `line.png` |
| 文字被"吃掉" | 同线还有 `paintEvents`（Paint 优先） | 拆成两条线 |
| 光圈变成"没反应" | 贴图线上写 `paintEvents` | 用 `line.png` |
| 文字太小/太大 | 字号由客户端固定，`size` 不生效 | 用 `scaleX/scaleY` 或不改 |
| 文字偏左/偏右 | 锚点恒为中心 | 用空格在字符串里补位 |
| 中文变方块 | 客户端缺字体 | 换常见字重，别用生僻字 |
| shader 不生效 | 只写进了 chart.json，而播放器读 extra.json | 双写 |
| shader 每帧都重载 | 忘了 `clone: false` 与连续时间段拼接 | 用"开 / 保持 / 关"三段 |
