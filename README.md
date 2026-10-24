# Phira Charting Skill

> 一套可以直接交给 AI Agent 接手、持续迭代的 **Phira / RPE 制谱技能包**。
> 不写死模板，只给方法、护栏和工具：**听音乐 → 对稿 → 立剧本 → 写谱 → 做演出 → 自检 → 交付**。

---

## 这是什么

谱面不是"音符文件"，而是**随音乐播放的动态视觉作品**。
这套技能包让 Agent 像谱师和艺术家一样工作，而不是像代码搬运工：

- 想从 0 做一张能导入 Phira 的谱面 → 读 [`SKILL.md`](SKILL.md)，按九阶段流程走。
- 拿到歌不知道从哪下手 → 读 [`docs/03-workflow/00-intake.md`](docs/03-workflow/00-intake.md)（接单与对稿）。
- 想真正听懂音乐（节奏 / 结构 / **歌词** / **情感**）→ 读 [`docs/03-workflow/01-music-analysis.md`](docs/03-workflow/01-music-analysis.md)。
- 想知道 RPE JSON 每个字段到底是什么类型 → 读 [`docs/01-format/`](docs/01-format)。
- 想避免"导入失败"的折磨 → 读 [`docs/02-pitfalls/PITFALLS.md`](docs/02-pitfalls/PITFALLS.md)。
- 想做有演出感的谱 → 读 [`docs/03-workflow/`](docs/03-workflow) 与 [`docs/04-reference/`](docs/04-reference)。
- **不想让用户替你测试** → 读 [`docs/06-qc/02-visual-selfcheck.md`](docs/06-qc/02-visual-selfcheck.md)，跑 `tools/selfcheck.sh` 出图出视频。
- 想偷师高手 → 用 `tools/phira_community.py` 直接下载社区高评分谱面，见 [`docs/04-reference/03-community-sampling.md`](docs/04-reference/03-community-sampling.md)。

---

## 30 秒上手

```bash
# 1. 依赖
pip install --break-system-packages librosa numpy scipy soundfile matplotlib pyyaml

# 2. 分析音乐（BPM / 节拍 / onset / 能量 / 结构 / 人声区段）
python3 tools/analyze_music.py song.mp3 -o analysis.json

# 3. 复制最小工程，改造成你的谱
cp -r examples/minimal my-chart
#    → 把 song.mp3、插画放进去，改 info.yml

# 4. 写完谱后一键自检（结构 + 指标 + 联系表）
bash tools/selfcheck.sh my-chart

# 5. 看关键段视频（可选但强烈推荐）
python3 tools/preview_render.py my-chart --video drop.mp4 --from 75 --to 95 --fps 60

# 6. 打包
bash tools/package_chart.sh my-chart        # → my-chart.zip
```

---

## 完整流程

```
用户发来音乐 + 想法
   ↓
① 深听四层：节奏 / 结构 / 歌词 / 情感
   ↓
② 对稿：把分析翻译成人话，问 3~4 个锚定时间点的问题（用户没说的自由发挥）
   ↓
③ 立剧本：Art Direction Brief（一页纸，双方确认）
   ↓
④⑤ 定难度 · 搭舞台
   ↓
⑥⑦ 写谱 · 做演出
   ↓
⑧ 自检：validate → stats → 联系表 → 视频（不需要用户测）
   ↓
⑨ 交付：打包 + 说明设计意图与取舍
```

---

## 仓库结构

```
.
├── SKILL.md                      # Agent 入口：身份 / 硬规则 / 九阶段流程 / 艺术原则
├── docs/
│   ├── 01-format/                # 格式规范（工程结构 / info.yml / chart.json / extra.json / 时间系统）
│   ├── 02-pitfalls/              # ⭐ 踩坑清单 + 导入前检查表
│   ├── 03-workflow/              # 接单对稿 → 音乐歌词情感 → 难度比例 → 写谱 → 线编排 → 特效
│   ├── 04-reference/             # 精品谱拆解方法论 + 大师案例 + 社区取样
│   ├── 05-resources/             # 维基、官方文档、GitHub 生态、源码导览
│   └── 06-qc/                    # 自检流程 + 视觉自检（离屏渲染）
├── tools/
│   ├── analyze_music.py          # librosa 音乐分析
│   ├── lyrics_align.py           # 歌词（LRC/SRT）→ beat 落点表
│   ├── chart_builder.py          # 谱面构建库（bt/note/line/event 封装）
│   ├── validate_chart.py         # 结构与语义校验器（导入前必跑）
│   ├── preview_render.py         # 离屏渲染：单帧 / 联系表 / 视频 / 量化指标
│   ├── selfcheck.sh              # 一键自检（L1 结构 + L2 指标 + L2.5 视觉）
│   ├── phira_community.py        # 社区谱面搜索 / 下载 / 批量取样
│   └── package_chart.sh          # 打包成可导入的 zip
└── examples/
    └── minimal/                  # 最小可导入工程（照着改最快）
```

---

## 核心结论（先记住这七条）

1. **beat 三元组 `[整拍, 分子, 分母]` 只能是整数**，时间 = `整拍 + 分子/分母`（单位是四分音符拍）。任何 `0.5` 都会报 `expected u32`。
2. **字段类型必须和一张"已成功导入"的参考谱逐一对照**，不要凭记忆写。
3. **先听音乐四层（节奏/结构/歌词/情感），再写谱**。只有 BPM 就动笔 = 节拍器。
4. **判定线是演员，不是背景板**。80% 的视觉表现来自 line 事件编排，不是 note 本身。
5. **和用户对稿时，把数据翻译成人话**："1:18 副歌第一下鼓砸下来"，不是"RMS 峰值 78.4s"。
6. **别让用户替你测试**。`selfcheck.sh` 出联系表、`--video` 出视频，先自己看。
7. **手册是护栏，不是模板**。音乐、用户意图、审美判断三者优先于文档。

---

## 社区接口

| 用途 | 地址 |
|---|---|
| 搜索/列表 | `https://api.phira.cn/chart?search=<关键词>&sort=rating&tag=<标签>` |
| 单谱详情 | `https://api.phira.cn/chart/<id>`（`file` 是 zip 直链） |

```bash
python3 tools/phira_community.py search "探窗" --sort rating
python3 tools/phira_community.py download 61048 -o samples/tanchuang
bash tools/selfcheck.sh samples/tanchuang samples/tanchuang/_qc
```

> 公开只读接口，无需登录；请低频访问（脚本默认 0.4s 间隔）。下载的谱面仅用于本地学习，不要二次分发。

---

## 状态

- 已沉淀：RPE 170 格式与类型表、librosa 分析流水线、接单对稿协议、难度与比例规范、判定线编排方法、特效动机体系、三张精品谱深度拆解、社区取样工具、离屏渲染自检闭环。
- 已知近似：`preview_render.py` 对父线继承、扩展事件、真实 shader 为近似实现；特效与像素级验收请走 prpr-render / phichain-renderer（见 [`02-visual-selfcheck.md`](docs/06-qc/02-visual-selfcheck.md)）。
- 待补充：自动 note 生成算法、难度定数自动估算、更多曲风模板、CI 化的导入回归测试。

## 参考与致谢

格式与术语来源详见 [`docs/05-resources/01-links.md`](docs/05-resources/01-links.md)。
Phira 主项目：[TeamFlos/phira](https://github.com/TeamFlos/phira)。

## License

MIT
