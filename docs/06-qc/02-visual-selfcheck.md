# 02 · 视觉自检（不把"导入试玩"甩给用户）

> 原则：**交付给用户的谱面，必须是"你已经看过了"的谱面。**
> 用户没有 Phira 客户端、没有编辑器、也不想当测试员。所以你必须在本地把画面跑出来。

本技能自带一个不依赖 Phira 客户端的离屏渲染器
[`tools/preview_render.py`](../../tools/preview_render.py)，它直接解析 `chart.json`，
按 Phira/prpr 的下落公式画出 note 与判定线。

---

## 1. 一键自检

```bash
bash tools/selfcheck.sh <工程目录或zip> [输出目录]
```

产出：

| 文件 | 内容 |
|---|---|
| `validate.txt` | 结构校验（L1） |
| `stats.json` | 量化指标（L2） |
| `contact_sheet.png` | 12 帧联系表（L2.5） |
| `summary.md` | 汇总报告 |

`validate_chart.py` 退出码非 0 会直接中止——**格式不对，谈视觉没有意义**。

---

## 2. 三类视觉产物

### 2.1 单帧截图（看细节）

```bash
python3 tools/preview_render.py my-chart --frame 78.4 -o shot.png
python3 tools/preview_render.py my-chart --frame 78.4 -o shot.png --no-hud   # 不要叠加文字
```

用途：检查某一次撞线、某一次爆炸、某一段排版。

### 2.2 联系表（看整体）

```bash
# 自动均匀取 12 帧
python3 tools/preview_render.py my-chart --contact-sheet sheet.png

# 指定时间点（推荐：按段落交界 + 峰值取）
python3 tools/preview_render.py my-chart --contact-sheet sheet.png \
  --times 0,12,30,52,78,90,105,118,130,145
```

**这是最省时间的一步**：一眼看出"舞台是否成立"——线有没有用满屏幕、有没有一段全黑、
高潮段是否明显更密、note 是否全挤在中间。

### 2.3 视频（看运动）

```bash
# 全曲（默认 1350x900 / 30fps，带音频）
python3 tools/preview_render.py my-chart --video out.mp4

# 只渲一段（迭代时更快，强烈推荐）
python3 tools/preview_render.py my-chart --video drop.mp4 --from 75 --to 95 --fps 60

# 换个下落速度看手感
python3 tools/preview_render.py my-chart --video fast.mp4 --from 75 --to 85 --speed-mul 1.6
```

渲染器会把工程里的音频混进 mp4（H.264 + AAC），**可以直接播放，也可以直接用
`Read` 工具读取视频**做视觉分析（读视频时请传入 `target` 描述你要看什么）。

> 如果视频读取失败（格式/体积限制），退回"抽帧 + 读图"，效果一样：
>
> ```bash
> ffmpeg -v error -ss 78.5 -i out.mp4 -frames:v 1 f.png -y
> ```
>
> 抽 3~5 个关键时刻（转场、爆发、结尾）就够判断了。

> 视频分析的正确提法：
> "分析 75s–95s 这一段：01 副歌第一拍判定线炸开时 note 是否被遮挡；
> 02 00:08 处是否有音符黏在判定线上；03 高潮段的横向铺开是否覆盖屏幕两侧。"

---

## 3. `--stats` 指标解读

```bash
python3 tools/preview_render.py my-chart --stats > stats.json
```

| 指标 | 含义 | 合格线 | 超标怎么办 |
|---|---|---|---|
| `duration` | 谱面时长 | 与音频差 < 0.5s | 检查 `META.duration` / 最后一个 note |
| `notes` / `types` | 音符总数与四类占比 | — | 占比反映演奏风格是否多样 |
| `avg_nps` / `peak_nps_1s` | 平均/峰值密度 | 见难度表 | 调密度 |
| `x_range` / `x_std` | note 横向范围/离散度 | 覆盖 ≥ 50% 屏宽 | note 全挤中间 → 重排 `positionX` |
| `line_x_cover` | 判定线横向覆盖 | 接近 `[-675, 675]` | 舞台没用满 → 扩大移动幅度 |
| `hidden_notes` | 命中瞬间线不可见 | **必须为 0** | alpha 动画与 note 时间冲突 |
| `offscreen_hit_notes` | 命中点出屏 | ≤ 2% | 线跑太远 / note 太偏 |
| `approach_visible_ratio` | 命中前 0.4s 已进入画面 | ≥ 0.80 | 偏低 → 把演奏线**往下放**（`yControl` 负值）或降速 |
| `approach_dist_median` | 命中前 0.4s 的下落距离 | 350–650 px | 太低=闪现，太高=来不及 |
| `top_event_lines` | 事件最多的线 | — | 确认"表演线"确实在表演 |
| `effects` | 特效数量 | 0–6 | 过多且无动机 = 噪音 |

> 这些阈值是**参考线，不是法律**。艺术判断优先，但超标时你必须能说出理由。

### 3.1 已知近似（把指标当"信号"，别当"判决"）

`preview_render.py` 是近似实现，以下情况会产生偏差：

| 现象 | 原因 | 处理 |
|---|---|---|
| 高评分谱也报 `hidden_notes` 偏高 | 父线/子线继承、`eventLayers` 复合语义、扩展事件未完全还原 | 只把你**自己写的**谱的高 hidden 当错误 |
| 画面里 note 比预期少 | 只渲染命中前 3 秒窗口内的 note，高速谱的大量 note 还在屏幕外 | 属正常 |
| 判定线形状/位置略有出入 | 近似处理 `skew`、`xybind`、`multiLineString` | 需要精确时走下面第 4 节 |
| 特效只是示意 | 用近似滤镜代替真实 shader | 特效验收必须走 prpr-render 或 Phira 本体 |

> 一句话：**结构错误看 `validate_chart.py`，运动与构图看 `preview_render.py`，
> 特效与像素看 prpr-render。**

---

## 4. 更精确的渲染路线（需要像素级对照时）

`preview_render.py` 是"够用"的近似渲染，适合自查与迭代。
需要与真实 Phira **逐像素对齐**时，用下列开源渲染器。三者都需要 Rust/Node 工具链。

### 4.1 phichain（推荐，命令行最友好）

仓库：<https://github.com/Ivan-1F/phichain>

```bash
git clone https://github.com/Ivan-1F/phichain
cd phichain
cargo build --release
# 离屏渲染（输出无音频的 H.264）
./target/release/phichain-renderer <chart.json> chart.mp4 \
  --from 0 --to 30 --width 1350 --height 900 --fps 60
# 合并音频
ffmpeg -i chart.mp4 -i song.mp3 -c:v copy -c:a aac -shortest out.mp4
```

- `--note-scale` 调 note 视觉大小，`--hide-hit-effect` 关掉打击特效
- 同仓库的 `phichain-converter` 支持 rpe ↔ official ↔ phichain 互转，可用来交叉验证解析

### 4.2 prpr-render

仓库：<https://github.com/Mivik/prpr>

Phira 的特效体系直接源自 prpr，**它对 `extra.json` 的还原度最高**。
适合验证自定义 shader / 特效参数。

### 4.3 phira-render（GUI）

仓库：<https://github.com/TeamFlos/phira-render>

Tauri + Vuetify 桌面 GUI，导入 zip 即可预览。需要图形环境，无头服务器上不适用。

> **选择建议**：
> 日常迭代 → `preview_render.py`（秒级）；
> 特效/着色器验收 → prpr-render；
> 上线前最终确认 → Phira 本体（或请用户在客户端里看一眼关键段，只作为最后一步）。

---

## 5. 视觉分析：人眼要看什么

拿到联系表/视频后，按这个顺序过一遍（**每一帧都要能回答**）：

1. **构图**：视觉重心在哪？有没有一段画面是空的/碎的？
2. **方向**：note 是否都在向下落？有没有个案"横着飞"或"黏在线上"？
3. **层次**：表演线是否压住了演奏线？note 与背景的对比够不够？
4. **节奏可见性**：不看音乐，光看画面能不能感觉到"这一段更激烈"？
5. **覆盖**：判定线有没有用满屏幕？还是只在中线 ±50 里抖？
6. **转场**：段落之间有没有明确的视觉事件，还是"悄悄变了"？
7. **一致性**：同一种演出语言是否重复出现？（重复=可记忆，乱变=噪音）
8. **首屏**：开头 3 秒够不够抓人？

只要有一条答不上来，就回去改——**不要等用户发现**。

---

## 6. 迭代闭环

```
改代码 → selfcheck.sh → 看 contact_sheet.png
        ↓                    ↓ 发现问题
        └──── 改 ←──── 截图定位到具体秒数 ────┘
                             ↓ 都 OK
                    录 10~20s 关键段视频 → 看运动是否流畅
                             ↓ 都 OK
                      打包 zip → 交付
```

**每轮迭代只改一件事**，否则你无法判断是哪次修改生效了。

---

## 7. 交付前最后一道门

- [ ] `validate_chart.py` 退出码 0
- [ ] `hidden_notes == 0`
- [ ] `contact_sheet.png` 没有全黑帧、没有空舞台帧
- [ ] 关键段视频已看过（至少 Drop / 结尾 / 转场）
- [ ] `duration` 与音频误差 < 0.5s
- [ ] zip 里包含：`chart.json` / `info.yml` / 音频 / 曲绘（`extra.json` 可选）
- [ ] 文件名与 `info.yml` 里的 `chart` / `music` / `illustration` 完全一致（大小写也要一致）

> 最后一条是历史翻车高发区：`music: song.mp3` 但文件叫 `Song.mp3`，导入后无声。
