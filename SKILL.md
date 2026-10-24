---
name: phira-charting
description: 制作 / 修改 / 校验 Phira(RPE 格式) 谱面时使用。覆盖音乐分析、判定线编排、note 设计、extra.json 特效、格式避坑与自检。当用户要求"做一张 Phira 谱""改谱""导入失败""谱面没手感/没演出感"时激活。
---

# Phira 制谱技能（Agent 执行手册）

你现在的身份是**谱师（charter）**，不是代码搬运工。
谱面是"音乐的可视化编舞"，代码只是画笔。

---

## 0. 硬规则（违反必翻车）

| # | 规则 |
|---|---|
| R1 | **写任何 JSON 前，先读 `docs/01-format/03-chart-json.md` 的类型表**。不确定就去翻 `examples/minimal/chart.json` 对照。 |
| R2 | **beat 三元组三个元素全部是整数**。`[14, 0, 0.5]` ❌ → `[14, 1, 2]` ✅。用 `tools/chart_builder.py` 的 `bt()` 自动转换。 |
| R3 | **每个 note 必须有 `endTime` 和 `positionX`**，即使 Tap 也要写 `endTime: [0,0,1]` 占位。 |
| R4 | **判定线所有 `*Control` 字段必须是数组 `[]`**，不能是对象 `{}`。 |
| R5 | **`isCover` 是整数 `0/1`**，不是 `false/true`。 |
| R6 | **note 里不要放 `tint` / `judgeArea`**（RPE 170 不接受多余字段会导致类型错误）。 |
| R7 | **`eventLayers` 的每一层必须同时包含 5 个事件数组**：`alphaEvents`、`moveXEvents`、`moveYEvents`、`rotateEvents`、`speedEvents`。缺一个就报 `expected struct RPEEventLayer with 5 elements`。 |
| R8 | **`extra.json` 里 effect 的 `start` / `end` 也是 beat 三元组**，不是数字。 |
| R9 | **info.yml 的 `id`、`uploader` 是整数**；`difficulty` 是浮点；字符串里含 `:` 必须加引号。 |
| R10 | **改完必跑** `python3 tools/validate_chart.py <工程目录>`，退出码 0 才算完。 |

---

## 1. 标准工作流（不要跳步）

```
① 听懂音乐        → tools/analyze_music.py
② 画段落地图      → 手写/表格：Intro / Verse / Chorus / Drop / Outro + 每段时间与能量
③ 设计难度曲线    → 每段的 NPS 目标、note 类型比例
④ 设计舞台        → 判定线分组与角色（演奏线 / 演员线 / 纹理线 / 文字线 / UI）
⑤ 写谱            → tools/chart_builder.py 生成 chart.json
⑥ 加演出          → line 事件编排 + extra.json 特效
⑦ 自检            → validate_chart.py + docs/06-qc 检查表
⑧ 打包实测        → package_chart.sh → Phira 导入试玩 → 按体感回调
```

**每完成 ③④ 就停下来跟用户确认一次**，不要一口气冲到 ⑧。

---

## 2. 分析音乐（必须先做）

```bash
python3 tools/analyze_music.py song.mp3 -o analysis.json
```

必须从结果中提取并写进"设计笔记"的量：

- `bpm.static`：谱面 BPMList 的基准（误差 ±3 内可用；偏差大就用 `--bpm` 手动指定做网格搜索）
- `beats.first_10_beats`：用于确定 `META.offset`（第一个强拍相对 0 的位置）
- `onsets`：决定 note 密度上限
- `energy.rms_db_*` / `high_energy_sections`：决定高潮段落
- `structure.boundaries`：段落切分
- `vocal.vocal_sections`：人声段落 → Hold 的位置来源

**判断标准**：如果设计笔记里没有"第 X 秒到第 Y 秒是副歌，能量峰值在哪一拍"，就还没资格开始写谱。

详见 [`docs/03-workflow/01-music-analysis.md`](docs/03-workflow/01-music-analysis.md)。

---

## 3. 写谱

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

规则：
- 演奏线承载 note，**演员线不承载或只放 `isFake: 1` 的假 note**。
- `positionX` 用**离散对称坐标**（如 ±490/±368/±306/±184/±122/0），不要随机浮点。
- 密度按段落设计，禁止全曲一个 NPS。
- 长音用 Hold，密集过场用 Drag，重音用 Tap，转折/滑音用 Flick。

详见 [`docs/03-workflow/02-chart-authoring.md`](docs/03-workflow/02-chart-authoring.md)。

---

## 4. 做演出（判定线编排）

- 线的移动范围要**用满全屏**：X ∈ [-675, 675]，Y ∈ [-450, 450]。只在中间 ±50 晃 = 死板。
- 高频表演（振荡、抖动、飘落）粒度到 **1/8 ~ 1/16 拍**，事件数量级 100+。
- 父线管"整体位移"，子线管"各自旋转/缩放"。
- 分组要有语义：`Main / Performance / Textures / Text / UI`。
- `alphaEvents` 的 `end` 可以是负数 → 隐藏线与全部 note。
- 全局特效克制使用：**没有概念的堆砌比不加更难看**。

详见 [`docs/03-workflow/03-judge-line-choreography.md`](docs/03-workflow/03-judge-line-choreography.md)、[`04-effects.md`](docs/03-workflow/04-effects.md)。

---

## 5. 自检（本技能的核心价值）

三级验证，缺一不可：

| 级别 | 手段 | 通过标准 |
|---|---|---|
| L1 结构 | `python3 tools/validate_chart.py <dir>` | 0 error |
| L2 语义 | `validate_chart.py --report` 输出的统计 + 人工看曲线 | NPS 曲线符合段落设计、无越界/堆叠 note、时长匹配 |
| L3 实机 | Phira 导入 → 加载 → 试玩 | 能进游戏、note 可见、判定手感正常、演出不挡视线 |

替代可视化的编辑器/渲染器（本机没有 Phira 时）：
- Re:PhiEdit（RPE）桌面编辑器直接打开 `chart.json`
- [TeamFlos/phira-render](https://github.com/TeamFlos/phira-render)（Web 渲染）
- [Mivik/prpr](https://github.com/Mivik/prpr) / [PhiZone/player](https://github.com/PhiZone/player)（浏览器播放器）

完整验收清单见 [`docs/06-qc/01-self-check.md`](docs/06-qc/01-self-check.md)。

---

## 6. 出错时怎么办

1. 读报错原文，定位 `line/column` → 用 `python3 -c "import json;json.load(open('chart.json'))"` 先确认 JSON 合法。
2. 到 [`docs/02-pitfalls/PITFALLS.md`](docs/02-pitfalls/PITFALLS.md) 的"报错 → 病因 → 修法"表里查。
3. **不要凭感觉猜类型**。找一张已成功导入的谱，`diff` 对应字段。
4. 修完重跑 L1。连续两次同一报错 = 你的假设错了，换对照样本。

---

## 7. 交付话术（对用户）

交付时说明四件事：
1. 这首曲子的结构与你的设计意图；
2. 谱面用了哪些技术（分组/父线/特效/纹理）；
3. 自检结果（error 数、note 数、NPS 峰值、时长）；
4. 已知不足与下一步建议。

不要只说"做好了"。
