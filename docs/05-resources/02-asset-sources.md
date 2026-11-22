# 02 · 曲源与皮肤资源站（Asset Sources）

> 制谱需要两类外部资源：**歌**和**皮肤/资源包**。
> 这一页记录两个社区站点、它们的正确用法、以及"高潮换皮肤"到底能不能做。
> 核对日期：2026-11-22。

---

## 1. Otter Music · 歌曲搜索与下载

- 地址：<https://otter-music.pages.dev/search>
- 性质：多源音乐搜索/试听/下载聚合站。
- 可检索的来源（站点前端可见）：网易云、QQ 音乐、酷我、咪咕、Bilibili、播客等。
- 能拿到：音频文件（mp3/flac 等）、封面、部分元数据（歌名/歌手/专辑/时长）。

### 1.1 制谱取歌流程

```text
① 在搜索框输入"歌名 + 歌手"，优先选音质高、时长与官方一致的版本
② 下载音频 + 封面（封面用于 info.yml 的 illustration）
③ 用 ffprobe 核对时长；用 tools/analyze_music.py 核对 BPM 与 offset
④ 与 B 站/官方音源交叉比对：前奏长度、是否有剪辑、是否加长版
⑤ 放进谱面工程：music.mp3（或 ogg）+ illustration.png
```

### 1.2 必须核对的三件事

| 检查 | 方法 | 为什么 |
|---|---|---|
| 时长 | `ffprobe -show_entries format=duration` | 剪辑版/加长版会导致全谱偏移 |
| BPM | `tools/analyze_music.py` + 手动数 8 小节 | BPM 错 1，后半段全错 |
| offset | 对齐第一下鼓点/人声 | 直接决定手感"准不准" |

> 注意：不同来源的同一首歌可能有 ±20~80 ms 的起始静音差异；
> 换源后必须重跑 BPM/offset，不能沿用旧数据。

### 1.3 版权

- 仅用于**个人制谱/学习**；不要把音频直接公开分发。
- 投稿 Phira 时遵守平台规则；需要授权就去找版权方/作者。
- 谱面 zip 里不要塞来源不明的无损音频。

---

## 2. PrprBako · Phira 皮肤/资源包

- 地址：<https://prprbako.kevin2106.top/#/>
- 性质：Phira 资源包（皮肤）的上传、审核、展示、下载站。
- 内容：note 贴图、打击特效、Hold 材质、音效等整套资源包。

### 2.1 资源包结构（Phira 实际读取）

```text
MySkin/
├── info.yml
├── click.png      # Tap
├── hold.png       # Hold 头
├── flick.png      # Flick
├── drag.png       # Drag
├── click_mh.png   # 多押/大判定用的备用图（必需）
├── hold_mh.png
├── flick_mh.png
├── drag_mh.png
├── hold_body.png  # 可选：Hold 身体
├── hit_fx.png     # 可选：打击特效图集
└── click.ogg / drag.ogg / flick.ogg / ending.ogg   # 可选音效
```

`info.yml` 常用字段：

```yaml
name: 雨夜
author: 某某
description: 冷色玻璃质感
hit_fx: 4          # 图集切分（1/4/8/16…）
hit_fx_duration: 0.4
hit_fx_scale: 1.0
hit_fx_rotate: false
hide_particles: false
hit_fx_tinted: true
hold_atlas: false
holdAtlasMH: false
hold_keep_head: false
hold_repeat: true
hold_compact: false
```

### 2.2 安装

- 图形界面：Phira → 设置/资源包 → 导入 zip。
- 手动：解压到 Phira 目录下的 **`data/respack/<包名>/`**（与 `data/charts/` 同级）。
- 切换：资源包是**全局单选用**，一局只能启用一套。

### 2.3 关键事实：Phira 不支持"谱面中途换全局皮肤"

资源包是应用级设置，谱面里没有"第 120 秒换成另一套 note 贴图"的字段。
所以"高潮时直接应用另一套按键皮肤"**不能靠切 respack 实现**。

可行的三种替代：

| 目标 | 做法 | 说明 |
|---|---|---|
| **高潮换视觉材质** | 两条位置/角度完全重合的判定线，挂不同 `Texture`，用 alpha 交叉淡化 | 谱内唯一可靠的"换材质"；贴图需随谱打包 |
| **高潮换打击感** | 无法换 note 图；改用**假 note 爆发 + 线框/光柱**制造"升级"错觉 | 观感提升，判定图不变 |
| **推荐皮肤** | 在交付说明里推荐 1~2 套与曲风匹配的资源包，让玩家自己装 | 最稳、最尊重玩家习惯 |

**但"不能换整套皮肤"≠"不能用皮肤里的图"。**
资源包里的单张 `click.png` / `hold.png` / `flick.png` / `drag.png` 都是普通 PNG，
可以复制进谱面 zip，挂到一条 `Texture` 判定线上当**精灵/贴图素材**：
光柱、星点、圆环、箭头、UI 边框都能这么做。真实字段、尺寸语义与版权注意见
[`13-media-layers.md`](../04-reference/13-media-layers.md) §1.6。

> 一句话：**整套皮肤换不了，但单张图可以当素材用**；颜色要预先做进图里，
> 因为贴图线不吃 `colorEvents`。

### 2.4 选皮肤的判断标准（制谱视角）

| 维度 | 适合本谱的选择 |
|---|---|
| 明度 | 深色背景 → 高明度、带描边的 note；浅色背景 → 深色实心 |
| 大小 | Drag 多 → 选小而清晰的 Drag；Hold 多 → 选细长、不遮线的 Hold |
| 打击特效 | 密集段选短促（≤0.3 s）、低遮挡；留白段可选大特效 |
| 颜色 | 与插画主色同系，避免互补色打架 |
| 音效 | 抒情曲不要用金属/电子重音效 |

> 建议流程：先完成谱面 → 用 2~3 套皮肤各看一遍联系表 →
> 选"最不抢 note、又能读出类型"的一套，写进交付说明。
> 如果主人指定了皮肤，就以主人的选择为准。

### 2.5 版权与打包

- 下载的资源包**不要**直接塞进谱面 zip 再分发（作者版权）。
- 需要随谱分发自定义贴图时，只打包**自己绘制**或**明确授权**的素材。
- 在 `info.yml` / 交付说明里标注素材来源与作者。

---

## 3. 其他已知资源入口

| 用途 | 入口 |
|---|---|
| 社区谱面搜索/下载 | `tools/phira_community.py`（见 `docs/04-reference/03-community-sampling.md`） |
| Phira 官方文档 | <https://docs.phira.link/> |
| Phira 官网/谱面库 | <https://phira.moe/> |
| RPE/Phira 格式文档 | <https://teamflos.github.io/phira-docs/> |

> 站点可能改版；如果链接失效，先在官网/文档找新入口，再把新地址补回本页。
