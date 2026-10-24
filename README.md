# Phira Charting Skill

> 一套可以直接交给 AI Agent 接手、持续迭代的 **Phira / RPE 制谱技能包**。
> 包含：格式规范（含精确类型）、音乐分析流程、谱面生成代码库、精品谱面拆解、踩坑清单、自检工具。

---

## 这是什么

这不是一份"教程散文"，而是一份**可执行的工程手册**：

- 想从 0 做一张能导入 Phira 的谱面 → 读 [`SKILL.md`](SKILL.md)，按流程走。
- 想知道 RPE JSON 每个字段到底是什么类型 → 读 [`docs/01-format/`](docs/01-format)。
- 想避免"导入失败"的折磨 → 直接读 [`docs/02-pitfalls/PITFALLS.md`](docs/02-pitfalls/PITFALLS.md)。
- 想做出有演出感的谱 → 读 [`docs/03-workflow/`](docs/03-workflow) 与 [`docs/04-reference/`](docs/04-reference)。
- 想验证自己做的谱到底长什么样 → 读 [`docs/06-qc/`](docs/06-qc)，跑 `tools/validate_chart.py`。

## 30 秒上手

```bash
# 1. 依赖
pip install --break-system-packages librosa numpy scipy soundfile matplotlib pyyaml

# 2. 分析音乐（产出 BPM / 节拍 / onset / 能量 / 结构）
python3 tools/analyze_music.py song.mp3 -o analysis.json

# 3. 复制最小工程，改造成你的谱
cp -r examples/minimal my-chart
#    → 把 song.mp3、插画放进去，改 info.yml

# 4. 写完谱后自检（必做）
python3 tools/validate_chart.py my-chart

# 5. 打包
bash tools/package_chart.sh my-chart        # → my-chart.zip
```

把 zip 传到 Phira 即可导入。

## 仓库结构

```
.
├── SKILL.md                      # Agent 入口：技能定义 + 强制流程 + 硬规则
├── docs/
│   ├── 01-format/                # 格式规范（工程结构 / info.yml / chart.json / extra.json / 时间系统）
│   ├── 02-pitfalls/              # ⭐ 踩坑清单 + 导入前检查表
│   ├── 03-workflow/              # 音乐分析 → 谱面编写 → 判定线编排 → 特效
│   ├── 04-reference/             # 精品谱面拆解方法论 + 三个大师级谱面沉淀
│   ├── 05-resources/             # 维基、官方文档、GitHub 生态、工具链
│   └── 06-qc/                    # 自检流程与验收标准
├── tools/
│   ├── analyze_music.py          # librosa 音乐分析
│   ├── chart_builder.py           # 谱面构建库（bt/note/line/event 封装）
│   ├── validate_chart.py          # 结构与语义校验器（导入前必跑）
│   └── package_chart.sh           # 打包成可导入的 zip
└── examples/
    └── minimal/                   # 最小可导入工程（照着改最快）
```

## 核心结论（先记住这五条）

1. **beat 三元组 `[整拍, 分子, 分母]` 只能是整数**，时间 = `整拍 + 分子/分母`（单位是四分音符拍，不是小节）。任何 `0.5` 都会让 Phira 报 `expected u32`；分母必须 ≥ 1。
2. **字段类型必须和一张"已成功导入"的参考谱逐一对照**，不要凭记忆写。
3. **先分析音乐，再分析谱面，最后才动手写谱**。顺序反了就是生搬硬套。
4. **判定线是演员，不是背景板**。谱面的 80% 视觉表现来自 line 事件编排，不是 note 本身。
5. **每改一次谱就跑一次 `validate_chart.py`**，不要等导入报错。

## 状态

- 已沉淀：RPE 170 格式、librosa 分析流水线、MJ Dangerous 完整案例、三张精品谱深度拆解。
- 待补充（欢迎接手）：自动 note 生成算法、难度定数估算、更多曲风模板、CI 化的导入回归测试。

## 参考与致谢

格式与术语来源详见 [`docs/05-resources/01-links.md`](docs/05-resources/01-links.md)。
Phira 主项目：[TeamFlos/phira](https://github.com/TeamFlos/phira)。

## License

MIT
