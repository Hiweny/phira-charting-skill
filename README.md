# Phira Charting Skill

> 一套可以直接交给 AI Agent 接手、持续迭代的 **Phira / RPE 制谱技能包**。
> 不写死模板，只给方法、护栏和工具：**听音乐 → 对稿 → 立剧本 → 写谱 → 做演出 → 自检 → 交付**。
> 每轮研究与被纠正都记在 [`docs/00-learning-log.md`](docs/00-learning-log.md)。

---

## 这是什么

谱面不是"音符文件"，而是**随音乐播放的动态视觉作品**。
这套技能包让 Agent 像谱师和艺术家一样工作，而不是像代码搬运工：

- 想从 0 做一张能导入 Phira 的谱面 → 读 [`SKILL.md`](SKILL.md)，按十阶段流程走。
- 拿到歌不知道从哪下手 → 读 [`docs/03-workflow/00-intake.md`](docs/03-workflow/00-intake.md)（接单与对稿）。
- 想真正听懂音乐（节奏 / 结构 / **歌词** / **情感**）→ 读 [`docs/03-workflow/01-music-analysis.md`](docs/03-workflow/01-music-analysis.md)。
- 想知道 RPE JSON 每个字段到底是什么类型 → 读 [`docs/01-format/`](docs/01-format)。
- 想避免"导入失败"的折磨 → 读 [`docs/02-pitfalls/PITFALLS.md`](docs/02-pitfalls/PITFALLS.md)。
- 想做有演出感的谱 → 读 [`docs/03-workflow/`](docs/03-workflow) 与 [`docs/04-reference/`](docs/04-reference)。
- **不想让用户替你测试** → 读 [`docs/06-qc/02-visual-selfcheck.md`](docs/06-qc/02-visual-selfcheck.md)，跑 `tools/selfcheck.sh` 出图出视频。
- 想偷师高手 → 用 `tools/phira_community.py` 直接下载社区高评分谱面，见 [`docs/04-reference/03-community-sampling.md`](docs/04-reference/03-community-sampling.md)。
- 想让 note / 判定线"活过来"（任意轨迹、拟物化、3D 纵深）→ 读 [`11-note-and-line-choreography.md`](docs/04-reference/11-note-and-line-choreography.md) 与 [`10-case-shiluozhiyu.md`](docs/04-reference/10-case-shiluozhiyu.md)。
- 想学颜色、节奏交互、线框空间与留白 → 读 [`12-case-shenzhendong.md`](docs/04-reference/12-case-shenzhendong.md)（《深圳东》逐帧视觉拆解）。
- 想嵌外部图片 / GIF / 文字 / 视频 / shader → 读 [`13-media-layers.md`](docs/04-reference/13-media-layers.md)（含"皮肤单图当贴图素材"）。
- 先搞清主人固定的审美底线（一条演奏线 / Lv12–13 / 几何美 / 歌词时限）→ 读 [`06-art-contract.md`](docs/03-workflow/06-art-contract.md)。
- 找歌 / 找皮肤 / 想在高潮"换材质" → 读 [`02-asset-sources.md`](docs/05-resources/02-asset-sources.md)。
- 要在真实 Phira 里验证（皮肤、打击特效、手感）→ 读 [`03-real-engine.md`](docs/06-qc/03-real-engine.md)。

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
   ↓
⑩ 复盘：新手法/教训写进 learning-log，push 回仓库
```

---

## 仓库结构

```
.
├── SKILL.md                      # Agent 入口：身份 / 硬规则 / 十阶段流程 / 艺术原则
├── docs/
│   ├── 01-format/                # 格式规范（工程结构 / info.yml / chart.json / extra.json / 时间系统）
│   ├── 02-pitfalls/              # ⭐ 踩坑清单 + 导入前检查表
│   ├── 03-workflow/              # 接单对稿 → 音乐歌词情感 → 难度比例 → 写谱 → 线编排 → 特效 → 审美契约
│   ├── 04-reference/             # 精品谱拆解方法论 + 大师案例 + 社区取样 + note/线编排手册
│   ├── 05-resources/             # 维基、官方文档、GitHub 生态、源码导览、曲源与皮肤
│   └── 06-qc/                    # 自检流程 + 视觉自检（离屏渲染）+ 真机验证
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

## 核心结论（先记住这九条）

1. **beat 三元组 `[整拍, 分子, 分母]` 只能是整数**，时间 = `整拍 + 分子/分母`（单位是四分音符拍）。任何 `0.5` 都会报 `expected u32`。
2. **字段类型必须和一张"已成功导入"的参考谱逐一对照**，不要凭记忆写。
3. **先听音乐四层（节奏/结构/歌词/情感），再写谱**。只有 BPM 就动笔 = 节拍器。
4. **判定线是演员，不是背景板**。80% 的视觉表现来自 line 事件编排，不是 note 本身。
5. **和用户对稿时，把数据翻译成人话**："1:18 副歌第一下鼓砸下来"，不是"RMS 峰值 78.4s"。
6. **别让用户替你测试**。`selfcheck.sh` 出联系表、`--video` 出视频，先自己看。
7. **只看数据会漏掉灵魂**。note 与线要合起来看：轨迹、拟物、3D、留白、颜色、遮挡。
   **研究谱和做谱都要看画面**；本地预览不够就上真实引擎。
8. **视觉效果与手感只看代码看不出来**。每写完一段就抽联系表/视频，不合格当场改。
9. **手册是护栏，不是模板**。音乐、用户意图、审美判断三者优先于文档。

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

- 已沉淀：RPE 170 格式与类型表、librosa 分析流水线、接单对稿协议、难度与比例规范、判定线编排方法、特效动机体系、**七份精品谱深度拆解**（琵琶行 / 放空 / 时落之雨 / enchanted love / 巴拉莱卡 / 社区批扫 / **深圳东**）、**note 轨迹与 3D 编排手册**、**图片·视频·Shader 手册**、**审美契约（含视觉与手感验收）**、**曲源与皮肤资源**、**真机验证流程**、社区取样工具、离屏渲染自检闭环。
- 预览器对齐：已按 prpr 源码对齐 note 位置/尺寸/默认色、线长、`visibleTime`、控制事件的距离求值、10 个内置 shader、贴图/GIF/文字/画笔线、`videos`；仍属近似的部分（皮肤、粒子、真实 shader 公式、`attach` 透视、判定手感）见 [`03-real-engine.md`](docs/06-qc/03-real-engine.md) §6。
- 待补充：自动 note 生成算法、难度定数自动估算、更多曲风模板、CI 化的导入回归测试、皮肤与谱面的自动配色建议。

## 参考与致谢

格式与术语来源详见 [`docs/05-resources/01-links.md`](docs/05-resources/01-links.md)。
Phira 主项目：[TeamFlos/phira](https://github.com/TeamFlos/phira)。

## License

MIT
