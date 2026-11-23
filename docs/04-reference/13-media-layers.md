# 图片 · 视频 · Shader：把外部素材接进谱面

> 判定线不只是"线"。在 Phira/prpr 里，它可以是**一张图、一段 GIF、一行字、一个圆**，
> 配合 `extra.json` 还能叠**全屏视频**和**后处理 shader**。
> 这一页把三种媒体层的真实字段、尺寸语义、限制和配方写清楚——全部来自 prpr 源码，不是猜的。

相关：[判定线编排](../03-workflow/03-judge-line-choreography.md) · [《深圳东》案例](12-case-shenzhendong.md) · [《enchanted love》贴图案例](04-case-enchanted-love.md)

---

## 1. 图片：判定线当精灵（sprite）

### 1.1 最小写法

```json
{
  "Texture": "moon.png",
  "eventLayers": [{ "alphaEvents": [ ... ], "moveXEvents": [ ... ], "rotateEvents": [ ... ] }],
  "extended": {
    "scaleXEvents": [{ "startTime": [0,0,1], "endTime": [0,0,1], "start": 1.0, "end": 1.0, "easingType": 1 }],
    "scaleYEvents": [ ... ],
    "colorEvents": [ ... ]
  },
  "zOrder": 10
}
```

规则（prpr `parse/rpe.rs` + `core/line.rs`）：

| 项 | 真实行为 |
|---|---|
| 识别条件 | `Texture != "line.png"` 且非空 → 整条线画成贴图 |
| 文件位置 | 谱面 zip **根目录**的同名文件（不能放子目录） |
| 尺寸 | 按**原始像素**绘制；线对象默认缩放 `2 / RPE_WIDTH`，即 1000 px 图 ≈ 屏幕高度的 74%（900p） |
| 缩放 | `scaleXEvents` / `scaleYEvents` 再乘上去，可非等比 |
| 颜色 | **固定白色，不吃 `colorEvents`**；只有 alpha 生效 |
| 透明度 | `line alpha × 255` |
| 旋转/位移 | `rotateEvents` / `moveX/YEvents`，绕图片中心 |
| 层级 | `zOrder`；同值按数组顺序 |
| 承载音符 | 可以，但通常不放 note |

> 想让图片变色：**做一张白图，在图片软件里预调色**，或者用多张图交叉淡化。
> 不要指望 `colorEvents` 给贴图染色——它只影响普通线、文字线和 attach 视频。

### 1.2 GIF

`Texture` 填 `.gif`，用 `gifEvents` 控制播放进度（0~1，不是时间）：

```json
"gifEvents": [
  { "startTime": [64,0,1], "endTime": [80,0,1], "start": 0.0, "end": 1.0, "easingType": 1 }
]
```

适合：雨幕、火焰、心电图、闪烁的霓虹灯牌。GIF 帧数别太多（≤ 60 帧），否则首帧解码卡顿。

### 1.3 文字线（歌词 / 标题）

`Texture` 保持 `"line.png"`，写 `textEvents`：

```json
"extended": {
  "textEvents": [{ "startTime": [32,0,1], "endTime": [40,0,1], "start": "雨落在深圳东", "end": "雨落在深圳东", "easingType": 1 }]
}
```

- 文字画在线原点，**字号固定 26 逻辑像素**（不可调）；
- 颜色 = `colorEvents`（或默认暖白）；
- 淡入淡出仍用 `alphaEvents`；
- 适合标题、章节名、短歌词；**长歌词请拆成多条线**，否则换行和排版不可控。

> 歌词跟人声的做法：把 textEvent 的 `startTime` 卡在人声起点前 0.05~0.1 s，
> `endTime` 卡在下一句开始前，并配 `alphaEvents` 在句尾 0.2 s 内降到 0。
> 不要用 3~5 s 的长淡出——那正是"歌词半天不消失"的来源。

#### 1.3.1 字形覆盖：先确认"这个字能不能显示"（2026-11-23 实测）

Phira 仓库里打包的字体只有 `assets/bold.ttf`（469 KB）与 `assets/phigros.ttf`（19 KB）。
把 `bold.ttf` 的 cmap 读出来是 **1411 个字形**：

```text
拉丁 88 · 汉字 1010 · 泰文 0
```

但**不要据此断定"客户端没有中文"**：实测一张中文歌词的谱面，其中 56 个常用汉字
（如"别/寂/那/抱/哪"）不在 `bold.ttf` 的 cmap 里，而玩家看到的中文是正常的——
说明客户端另有字体来源（系统字体 / 运行时加载）。

**能确定的风险排序**：

| 文字 | 风险 | 建议 |
|---|---|---|
| 拉丁 / 中文（常用字） | 低 | 直接用 |
| 中文（生僻字、异体字） | 中 | 先查 cmap，或换成常用字 |
| 泰文 / 阿拉伯文 / 希伯来文 / 天城文 | **高** | 做双语歌词前**先在一句上实测**；备选是"中文 + 英文"或"罗马音转写" |
| Emoji / 符号 | 高 | 不要放进 textEvents |

自查命令（需要 `fontTools`）：

```python
from fontTools.ttLib import TTFont
f = TTFont('bold.ttf'); cmap = set()
for t in f['cmap'].tables: cmap |= set(t.cmap.keys())
missing = [c for c in '我的灵魂伴侣在哪里' if ord(c) not in cmap]
print(len(cmap), 'missing:', missing)
```

> 本仓库的《灵魂伴侣》案例最初做了"泰语 + 中文"双语歌词，本地预览器把泰语渲染成方块；
> 由于无法离线确认真机字体，交付时同时准备了"中文 + 英文"的降级方案。

### 1.4 画笔线（转场圆）

`paintEvents` 画一个实心圆，半径单位是像素，alpha 自动 ×2.55：

```json
"paintEvents": [{ "startTime": [0,0,1], "endTime": [1,0,1], "start": 0, "end": 1400, "easingType": 9 }]
```

经典用法：**iris 转场**——圆从 0 涨到盖住全屏 → 切段；或反过来"从圆里露出"。
一条 `zOrder` 很高的黑板色画笔线，比 shader 更省、更稳。

### 1.5 精灵配方

| 想要 | 做法 |
|---|---|
| 月亮/太阳 | 一张圆图，`moveX` 横移 + `rotateEvents` 自转 + `scale` 呼吸 |
| 唱片机 | 圆图 + 恒定 `rotate`（每拍 90°）+ 中心小圆遮罩 |
| 角色立绘 | 拆 头/身/手/影 四条线，各自小角度摆动 |
| 舞台布景 | 大图停在 `x=±1800`，按段落扫入；`zOrder` 负数 |
| UI 边框 | 九宫格拆 4 条线，随节拍缩放 |
| 雨幕 | 竖长条 PNG + `scaleY` 拉伸 + `moveY` 循环，或 GIF |

### 1.6 把皮肤包拆成单张素材用

**"不能中途换整套皮肤"不等于"不能用皮肤里的图"。**
资源包里的 `click.png` / `hold.png` / `flick.png` / `drag.png` / `hit_fx.png`
都是普通 PNG，完全可以**单张复制进谱面 zip，再挂到一条 `Texture` 线上当精灵**。

| 想要 | 拿哪张图 | 怎么用 |
|---|---|---|
| 光柱 / 激光 | `hold.png`（常是竖长条） | `scaleY` 拉长 + `moveY` 扫过 + alpha 呼吸 |
| 星点 / 粒子 | `click.png` | 缩到 0.1~0.3，沿轨迹排 8~16 个 `moveX/moveY` |
| 打击爆点 | `hit_fx.png`（图集） | 需要先切图；只取一格当静态贴图 |
| 圆环 / 判定圈 | `click_mh.png` | 放大 + `rotateEvents` 恒转 |
| 箭头 / 指示 | `flick.png` | 旋转到指向方向，做"引导箭头" |

注意：

- **贴图不吃 `colorEvents`**，颜色必须在图里；需要别的颜色就另做一张；
- 尺寸按原始像素（1000 px ≈ 900p 屏高的 74%），先缩到 ≤ 1000 px；
- **版权**：从别人资源包拆图只适合本地学习/自用；随谱分发必须用自己绘制或明确授权的素材
  （见 [`02-asset-sources.md`](../05-resources/02-asset-sources.md) §2.5）。

### 1.7 也可以一张媒体都不用

《深圳东》53 条线**全部是默认 `line.png`**，没有 `Texture`、没有 GIF / 文字 / 画笔、
`extra.json` 里也没有 `videos`，只有 8 类 shader。它的高级感来自：

- 长线（6 屏高）+ 多线交叉形成线框空间；
- note 类型本身的颜色（蓝 / 黄 / 红 / 白）；
- shader 时间轴（grayscale / chromatic / vignette / glitch）；
- 结构与留白（中心柱 ↔ 全屏散开，2 秒空拍）。

**素材不是高级感的必要条件。** 先把线、note、节奏、留白做好，再考虑加图/视频；
反过来先堆素材，通常只会更乱。

---

## 2. 视频：`extra.json` 的 `videos`

### 2.1 真实字段（prpr `parse/extra.rs` → `core/video.rs`）

```json
{
  "videos": [
    {
      "path": "bga.mp4",
      "time": [386, 0, 1],
      "scale": "cropCenter",
      "alpha": 0.6,
      "dim": 0.25,
      "attach": 12
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | zip 根目录下的视频文件 |
| `time` | beat 三元组 | **开始播放的谱面时间**（不是裁切窗口） |
| `scale` | `cropCenter` / `inside` / `fit` | 铺满裁剪 / 完整放入 / 拉伸铺满 |
| `alpha` | number 或事件 | 0~1，整体透明度 |
| `dim` | number 或事件 | 0~1，压暗（乘 RGB） |
| `attach` | int，可选 | 判定线下标；给了就跟随该线的位移/旋转/缩放，并用该线颜色染色 |

- **没有 `startTime` / `endTime` / `colorFilter`**（旧文档写错了，已修正）。
  视频从 `time` 开始一直播到文件结束；要截断就把视频本身剪短。
- `attach` 的视频会变成一块"会跟着线飞的屏幕/镜子/海报"，是 3D 运镜的捷径。
- 官方 release 默认带 `video` feature；自编译若关掉，视频会被静默跳过。
- 视频从 `time` 起按**音频时钟**播放；暂停/回溯时 prpr 会 seek。

### 2.2 什么时候用视频

| 场景 | 建议 |
|---|---|
| 前奏/尾奏的 MV 片段 | 全屏，`alpha 0.4~0.6`、`dim 0.2+` |
| 回忆闪回 | 全屏 + `grayscale`/`vignette` 叠加 |
| 跟着判定线飞的"屏幕" | `attach` 到一条正在旋转的线 |
| 背景氛围 | **不要用视频**，用图片/GIF 更省 |

三条硬规则：

1. **弱谱区才放视频**，爆发段一定关掉或压到 `alpha ≤ 0.25`；
2. **必须有降级**：无视频时谱面仍完整（用 `alpha` 事件在关键拍归零）；
3. 视频体积大，超过 ~20 MB 的 zip 在手机上加载会明显变慢。

> 预览器 `tools/preview_render.py` 支持 `videos`：用 `ffmpeg` 按时间抽帧并合成；
> `attach` 按线的位姿做近似变换。没有 `ffmpeg` 时自动跳过。

---

## 3. Shader：`extra.json` 的 `effects`

### 3.1 结构

```json
{
  "effects": [
    {
      "shader": "chromatic",
      "start": [320, 0, 1],
      "end": [321, 0, 1],
      "global": false,
      "vars": { "power": 0.01, "sampleCount": 3 }
    }
  ]
}
```

- `start` / `end` 是 **beat 三元组**，和音符同一套时间；
- `global: false` 只作用于谱面层（线 + note）；`true` 会连 UI 一起处理；
- `vars` 里没写的键用 shader 文件中的默认值（`// %默认值%` 注释）；
- **`shader` 还可以填 zip 内 `.glsl` 路径**（如 `"/my.glsl"`）→ 自定义后处理。

### 3.2 内置 shader 速查（prpr `core/shaders/`）

| 名称 | 关键变量（默认） | 视觉 | 适合 |
|---|---|---|---|
| `grayscale` | `factor(1)` | 去色 | 前奏、回忆、留白 |
| `chromatic` | `power(0.01)` `sampleCount(3)` | RGB 径向分离 | 重音闪光、加速段 |
| `glitch` | `power(0.03)` `rate(0.6)` `speed(5)` `blockCount(30.5)` `colorRate(0.01)` | 信号损坏、错位 | 终章、断点 |
| `vignette` | `radius(15)` `extend(0.25)` `r/g/b(0)` | 四周压暗 | 聚光、留白 |
| `circleBlur` | `size(10)` | 圆形膨胀/光晕 | 入副歌、Hold 释放 |
| `shockwave` | `progress` `width(0.1)` `distortion(0.8)` `expand(10)` `centerX/Y(0.5)` | 环形冲击波 | 鼓点、爆炸 |
| `radialBlur` | `power(0.02)` `sampleCount(6)` `centerX/Y(0.5)` | 缩放模糊 | 冲刺、失重 |
| `pixel` | `size(10)` | 马赛克 | 故障、回忆失真 |
| `noise` | `power(0.03)` `seed(81)` | 噪点 | 胶片、老电视 |
| `fisheye` | `power(-0.1)` | 鱼眼/桶形 | 空间扭曲、吸入 |

> 只有这 10 个内置 shader。其余名字会当 GLSL 源码路径处理，找不到就跳过。

### 3.3 编排原则

1. **卡乐句，不卡固定间隔**：切点放在鼓/人声重音前 0.05~0.1 s。
2. **一次最多叠 2~3 个**：`grayscale + vignette` 可以，`glitch + chromatic + noise` 会糊。
3. **加速用"间隔减半"**：0.75 s → 0.375 s → 0.1875 s，比调大 `power` 有效。
4. **留白段用 `vignette` 而不是黑屏**：还能看见线和插画，层次更高。
5. **`global` 慎用**：会把连击、分数一起变色/扭曲，影响可读性。
6. **必须有 NO_SHADER 降级**：玩家可装 `NO_SHADER` 模组清空所有效果；
   颜色信息不能只存在于 shader 里（音符类型、线色才是底稿）。
7. **性能**：`circleBlur` / `radialBlur` 是全屏多次采样，低端机可能掉帧；
   长段特效（> 8 s）尽量用 `grayscale` / `vignette` 这类单次采样。

### 3.4 配方

- **黑白前奏**：`grayscale 0→12s`，第一下鼓切 `chromatic 0.2s`。
- **加速心跳**：从副歌前 8 小节开始，`chromatic` 每 2 拍一次，最后一小节每 1 拍。
- **无声胜有声**：物量降到 <1/s，同时 `vignette radius 15 extend 0.25`。
- **终章故障**：`glitch` 4 段、每段 1~1.5 s，中间留 0.5 s 干净画面。
- **入副歌光晕**：`circleBlur size` 1→5 持续 2 s，最后一帧 `chromatic`。

---

## 4. 三层媒体的组合顺序

prpr 的实际绘制顺序（决定了谁盖谁）：

```
插画背景 → videos → 判定线（含贴图/文字/画笔）→ note → 普通 effects
        → overlay UI（连击/分数）→ global effects
```

所以：

- 贴图线可以盖住视频，视频盖住背景；
- 普通 shader 会同时影响线和 note，但**不影响连击数**；
- `global` shader 连 UI 一起处理。

---

## 5. 验收清单

- [ ] 所有素材都在 zip 根目录，文件名与 `Texture` / `path` 完全一致；
- [ ] 贴图是白图（否则 `colorEvents` 不会生效，颜色也不可控）；
- [ ] 大图已压到 ≤ 1000 px，GIF ≤ 60 帧，视频 ≤ 20 MB；
- [ ] 贴图/视频都有明确的进场与退场（alpha 或位置）；
- [ ] 视频只在弱谱区，`alpha ≤ 0.6`、`dim ≥ 0.2`；
- [ ] shader 时间用 beat 写，切点在乐句；
- [ ] 关掉 shader 后，谱面仍然能看、能打；
- [ ] 在预览器与真机各看一遍（预览器对 shader 是近似实现）。
