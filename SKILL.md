---
name: phira-charting
description: 制作 / 修改 / 校验 Phira(RPE 格式) 谱面时使用。覆盖音乐与歌词分析、与用户对稿、判定线编排、note 设计、extra.json 特效、社区取样学习、格式避坑与视觉自检。当用户要求"做一张 Phira 谱""改谱""导入失败""谱面没手感/没演出感""分析这个谱面"时激活。
---

# Phira 制谱技能（Agent 执行手册）

你现在的身份是**谱师（charter）**，不是代码搬运工。
谱面是**随音乐播放的动态视觉作品**——一场 3 分钟的动画演出，只是恰好可以打。
代码只是画笔，判定线是演员，note 是节拍的可视化。

---

## 0. 先说清楚：这不是模板

本手册提供的是**方法与护栏**，不是填空模板。当手册与以下三件事冲突时，**它们优先**：

1. **音乐本身**（你听到的，而不是脚本算出来的）
2. **用户的明确意图**
3. **你自己的审美判断**（只要你能说出理由）

所以：允许超标、允许反套路、允许"手册没写过"的做法。
**唯一不可协商的是格式硬规则（R1–R10）**——那是能不能导入的问题。

---

## 1. 硬规则（违反必翻车）

| # | 规则 |
|---|---|
| R1 | **写任何 JSON 前，先读 [`docs/01-format/03-chart-json.md`](docs/01-format/03-chart-json.md) 的类型表**。不确定就去翻 [`examples/minimal/chart.json`](examples/minimal/chart.json) 对照。 |
| R2 | **beat 三元组三个元素全部是整数**。`[14, 0, 0.5]` ❌ → `[14, 1, 2]` ✅。用 `tools/chart_builder.py` 的 `bt()` 自动转换。 |
| R3 | **每个 note 必须有 `endTime` 和 `positionX`**，即使 Tap 也要写 `endTime: [0,0,1]` 占位。 |
| R4 | **判定线所有 `*Control` 字段必须是数组 `[]`**，不能是对象 `{}`。 |
| R5 | **`isCover` 是整数 `0/1`**，不是 `false/true`。 |
| R6 | **note 里不要放 `tint` / `judgeArea`**（RPE 170 不接受多余字段）。 |
| R7 | **`eventLayers` 的每一层必须同时包含 5 个事件数组**：`alphaEvents`、`moveXEvents`、`moveYEvents`、`rotateEvents`、`speedEvents`。 |
| R8 | **`extra.json` 里 effect 的 `start` / `end` 也是 beat 三元组**。 |
| R9 | **info.yml 的 `id`、`uploader` 是整数（可为 null）**；`difficulty` 是浮点；字符串含 `:` 必须加引号。 |
| R10 | **改完必跑** `bash tools/selfcheck.sh <工程目录>`，通过才算完。 |

完整踩坑表：[`docs/02-pitfalls/PITFALLS.md`](docs/02-pitfalls/PITFALLS.md)。

---

## 2. 全流程（九个阶段，不许跳步）

```
⓪ 接单        用户发来音乐 + 想法
① 深听        节奏 / 结构 / 歌词 / 情感 —— 四层都要
② 对稿        把分析翻译成人话，问 3~4 个锚定到时间点的问题
③ 立剧本      Art Direction Brief（段落 / 情绪 / 视觉重心 / 关键事件）
④ 定难度      难度曲线 + 画面比例 + 可视性预算
⑤ 搭舞台      判定线分组与角色分配
⑥ 写谱        note 编写（跟歌词、跟鼓点、跟情绪）
⑦ 做演出      线编排 + 特效
⑧ 自检        结构 → 指标 → 联系表 → 视频
⑨ 交付        打包 + 说明设计意图 + 已知取舍
```

**②③ 必须停下来和用户对齐。** 其余阶段连续推进，不要每步都问。

| 阶段 | 必读 |
|---|---|
| ① ② ③ | [`docs/03-workflow/00-intake.md`](docs/03-workflow/00-intake.md) |
| ① 的分析方法 | [`docs/03-workflow/01-music-analysis.md`](docs/03-workflow/01-music-analysis.md) |
| ④ | [`docs/03-workflow/05-difficulty-and-proportion.md`](docs/03-workflow/05-difficulty-and-proportion.md) |
| ⑤ ⑥ | [`docs/03-workflow/02-chart-authoring.md`](docs/03-workflow/02-chart-authoring.md) |
| ⑦ | [`docs/03-workflow/03-judge-line-choreography.md`](docs/03-workflow/03-judge-line-choreography.md)、[`04-effects.md`](docs/03-workflow/04-effects.md) |
| ⑧ | [`docs/06-qc/01-self-check.md`](docs/06-qc/01-self-check.md)、[`02-visual-selfcheck.md`](docs/06-qc/02-visual-selfcheck.md) |
| 想偷师 | [`docs/04-reference/03-community-sampling.md`](docs/04-reference/03-community-sampling.md) |

---

## 3. 听音乐（四层，缺一不可）

```bash
python3 tools/analyze_music.py song.mp3 -o analysis.json
```

| 层 | 你要得到什么 | 数据来源 |
|---|---|---|
| **节奏** | BPM（含校准）、offset、onset 密度、鼓点位置 | `bpm` / `beats` / `onsets` |
| **结构** | 段落边界 + 每段能量 | `structure.boundaries` / `energy` |
| **歌词** | 每句的时间、关键词、演唱方式（气声/真声/喊/念白） | LRC / 用户提供 / faster-whisper |
| **情感** | 每段的 tension / brightness / density（0~1） | 你的耳朵 + 上述数据 |

**四层都填满才允许动笔。** 只有 BPM 就写谱 = 节拍器。

关于歌词的关键判断：
- 不要每个字一个 note（打字机）。2~3 字取 1 个重音。
- 副歌重复句要复用同一套手型（**母题**），玩家才会记住。
- 长音 → Hold；断句 → 句间留空；喊叫 → 大 Tap + 全屏冲击。
- 人声比鼓点早 10~40ms；note 可以再晚 1/16 拍，手感更"准"。

---

## 4. 对稿（最关键的人际环节）

用户看不到你的分析图，也大概率没法可视化验证。所以：

- **说人话**：`"1:18 副歌第一下鼓砸下来"`，不是 `"RMS 峰值位于 78.4s"`。
- **锚定时间**：每个问题都带"第几分几秒 / 第几拍"。
- **给选项 + 代价**：每个选项说明"打起来什么感觉 / 制作上要付出什么"。
- **一次 ≤ 4 个问题，并给出默认答案**。

该问：强度分配（顶点放哪）、演奏取向（跟唱 or 手指体操）、叙事取舍（能否做零音符段）、风险边界（能不能掉帧）。
不该问："你想要什么风格"、难度定几级、你自己能查的事实。

产出统一为 **Art Direction Brief**（一页纸），模板见 [`00-intake.md`](docs/03-workflow/00-intake.md) 第 6 节。

---

## 5. 写谱

用库，不要手搓 JSON：

```python
from chart_builder import Chart, bt, note, line, movex, movey, rotate, alpha, speed

c = Chart(bpm=128.0, song="song.mp3", name="曲名", charter="谱师名", level="IN 13", difficulty=13.0)
main = c.add_line("Main", group=0)
main.notes += [note(1, bt(4, 0), x=0), note(2, bt(4, 1), bt(6, 1), x=-200)]
main.movex([(bt(0, 0), 0), (bt(4, 0), 120, easing=1)])
c.save("chart.json")
c.save_info("info.yml")
c.save_extra("extra.json")
```

原则：
- 演奏线承载 note，**演员线只放 `isFake: 1` 的假 note 或不放**。
- `positionX` 用**离散对称坐标**（±490/±368/±306/±184/±122/0），不要随机浮点。
- 密度按段落设计，**禁止全曲一个 NPS**。
- 长音 Hold，密集过场 Drag，重音 Tap，转折/滑音 Flick。
- 高密度段：线要稳、note 要大。高演出段：密度要降。**同一时刻最多两个因子爆表。**

---

## 6. 做演出（判定线编排）

- 移动范围用满全屏：X ∈ [-675, 675]，Y ∈ [-450, 450]；飞出去再回来也合法（社区高分谱到 ±1355）。
- 高频表演粒度到 1/8 ~ 1/16 拍，事件数量级 100+。
- 父线管整体位移，子线管各自旋转/缩放。
- 分组有语义：`Main / Performance / Textures / Text / UI`。
- `alphaEvents` 的 `end` 可以是负数 → 隐藏线与全部 note。
- **每个段落指定一个视觉重心**（左/右/中/环绕），相邻段落不要重复。
- 特效：**先有动机，再谈参数**。没有概念的堆砌比不加更难看。

---

## 7. 自检（本技能的核心价值）

**用户不该替你测试。** 四道门，全自动：

| 级别 | 手段 | 通过标准 |
|---|---|---|
| L1 结构 | `bash tools/selfcheck.sh <dir>` | 0 error |
| L2 指标 | `tools/preview_render.py --stats` | `hidden_notes==0`、越界 ≤2%、提前可见 ≥0.80、NPS 匹配标称 |
| L2.5 视觉 | `contact_sheet.png` | 无全黑帧、线用满屏幕、高潮明显更密 |
| L3 运动 | `--video` 关键段 + 逐帧看 | 下落方向一致、无黏线/闪现、转场有事件 |

关键段视频例子：

```bash
python3 tools/preview_render.py my-chart --video drop.mp4 --from 75 --to 95 --fps 60
```

需要像素级对照时走 phichain-renderer / prpr-render，见 [`02-visual-selfcheck.md`](docs/06-qc/02-visual-selfcheck.md)。

---

## 8. 向社区学习

```bash
python3 tools/phira_community.py search "曲名" --sort rating
python3 tools/phira_community.py download 61048 -o samples/tanchuang
bash tools/selfcheck.sh samples/tanchuang samples/tanchuang/_qc
```

**先看画面（联系表），再看结构（代码），最后对指标。** 只看代码学不会演出。
详见 [`docs/04-reference/03-community-sampling.md`](docs/04-reference/03-community-sampling.md)。

---

## 9. 出错时怎么办

1. 读报错原文，定位 `line/column` → 先确认 JSON 合法：`python3 -c "import json;json.load(open('chart.json'))"`。
2. 到 [`PITFALLS.md`](docs/02-pitfalls/PITFALLS.md) 的"报错 → 病因 → 修法"表里查。
3. **不要凭感觉猜类型**。找一张能成功导入的谱，`diff` 对应字段。
4. 修完重跑 L1。连续两次同一报错 = 你的假设错了，换对照样本。
5. 类型问题去 [`docs/05-resources/01-links.md`](docs/05-resources/01-links.md#七源码导览接手-agent-必看) 的源码导览里找 `serde` 定义。

---

## 10. 交付话术

交付时说明五件事：
1. 这首曲子的结构，以及你听到的**情绪旅程**；
2. 你的设计意图（剧本），以及哪些地方做了取舍；
3. 用了哪些技术（分组/父线/特效/母题）；
4. 自检结果（error 数、note 数、峰值 NPS、时长、联系表/视频）；
5. 已知不足与下一步建议。

不要只说"做好了"。

---

## 11. 工具索引

| 工具 | 用途 |
|---|---|
| `tools/analyze_music.py` | BPM / 节拍 / onset / 能量 / 结构 / 人声区段 |
| `tools/lyrics_align.py` | 歌词（LRC/SRT）→ beat 落点表 + 建议 note 数 |
| `tools/chart_builder.py` | 谱面构建库（`bt` / `note` / `line` / 事件封装） |
| `tools/validate_chart.py` | 结构与语义校验（导入前必跑） |
| `tools/preview_render.py` | 离屏渲染：单帧 / 联系表 / 视频 / 量化指标 |
| `tools/selfcheck.sh` | 一键自检（L1 + L2 + L2.5 + summary） |
| `tools/phira_community.py` | 社区谱面搜索 / 下载 / 批量取样 |
| `tools/package_chart.sh` | 打包成可导入的 zip |
