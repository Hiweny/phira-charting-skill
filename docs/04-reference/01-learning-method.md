# 01 · 如何学习一张精品谱（方法论）

> 这是"沉淀"的方法，不是结论。
> 结论会过时，方法不会。学会这套流程，任何一张好谱都能拆。

---

## 0. 顺序不能反

```
① 听音乐 → ② 分析音乐 → ③ 只看谱面数据 → ④ 对照音乐看谱面 → ⑤ 提炼手法 → ⑥ 在自己的曲子上做实验
```

**反例（我们真实犯过）**：拿到谱面直接统计 note 数量、判定线数量，然后照搬结构。
→ 结果：形式对了，灵魂没有。用户原话："不要生搬硬套！"

---

## 1. Step 1-2：先成为这首曲子的听众

- 听 3 遍，写"情绪地图"：哪秒起鸡皮、哪秒想跟着动、哪秒安静。
- 跑 `analyze_music.py`，得到 BPM / 段落 / 能量 / onset。
- **把两者对照**：你感觉"爽"的地方，是不是能量峰值？如果不是，说明作曲家用了别的技巧（留白、变速、和声），这些正是你要在谱面里复现的。

产出：一张"音乐地图"（段落 + 情绪 + 关键时间点）。

---

## 2. Step 3：谱面静态统计

写谱前先量一遍，别凭感觉。

```python
import json, collections

d = json.load(open("chart.json", encoding="utf-8"))
lines = d["judgeLineList"]

print("判定线:", len(lines))
print("音符:", sum(l["numOfNotes"] for l in lines))
print("分组:", d["judgeLineGroup"])

# 每线事件密度
for i, l in enumerate(lines):
    ev = collections.Counter()
    for layer in l["eventLayers"]:
        for k, arr in layer.items():
            ev[k] = max(ev[k], len(arr))
    print(i, l["Name"], "notes=", l["numOfNotes"],
          "| moveX", ev["moveXEvents"], "moveY", ev["moveYEvents"],
          "rot", ev["rotateEvents"], "alpha", ev["alphaEvents"],
          "speed", ev["speedEvents"], "| father=", l["father"],
          "z=", l["zOrder"])

# 音符类型
types = collections.Counter()
xs = []
for l in lines:
    for n in l["notes"]:
        types[n["type"]] += 1
        xs.append(n.get("positionX", 0))
print({k: f"{v} ({v/sum(types.values()):.1%})" for k, v in types.items()})
print("X 范围:", min(xs), max(xs))
```

要得到的指标：

| 指标 | 意义 |
|---|---|
| 线总数 / 承载 note 的线数 | 判断"演员线"比例 |
| 分组数与命名 | 看设计意图 |
| 每线事件数 | 找"主角线" |
| 事件粒度（看时间间隔） | 判断是粗粒度还是逐帧 |
| 音符类型比例 | 判断谱风（Drag 流 / Tap 流） |
| X 分布范围与均值 | 看是否用满全屏、是否对称 |
| 父线数量 | 看是否用家族式编排 |
| extra.json 特效数 | 看是"着色器派"还是"线动画派" |

---

## 3. Step 4：对着音乐看谱面（最重要的一步）

选 3 个关键时间点，逐拍对照：

### 选点原则
1. 第一次副歌的第一拍（Drop）
2. 最安静的一段（Bridge / 留白）
3. 全曲最高潮

### 对照表

| 时间(beat) | 音乐发生了什么 | 谱面发生了什么 | 设计意图 |
|---|---|---|---|
| 124 | 底鼓 + 贝斯进入 | 主线 speed 10→20，6 条表演线同时炸开 | 爆发 |
| 192 | 人声独白，鼓消失 | 所有 note 停止，只有花瓣线飘落 | 留白反差 |
| 236 | 全乐器齐鸣 | 37 线全开 + 特效 | 顶点 |

**只做统计不做这一步 = 白学。**

---

## 4. Step 5：提炼"可迁移手法"

把观察结果分成三类：

| 类型 | 例子 | 处理 |
|---|---|---|
| **可迁移手法** | 阻尼振荡、1/16 拍花瓣线、9 层分组、多线错峰加入 | 抄进自己的工具箱 |
| **曲目专属设计** | "探窗"的窗棂纹理、"声嘶力竭"的雨滴线 | 理解思路，不要照搬素材 |
| **无法复用** | 特定 BGM 的叙事、版权纹理 | 跳过 |

写进笔记时用这个格式：

```
【手法】阻尼振荡
【出处】Night Drawmers, Line 0, beat 19-21
【原理】振幅按 exp(-k*i) 衰减，每 1/8 拍一个关键帧
【适用】任何"被敲击→抖动→静止"的瞬间
【代码】见 docs/03-workflow/03-judge-line-choreography.md §4.2
```

---

## 5. Step 6：在自己的曲子上做 A/B 实验

**一次只验证一个手法。**

例：想验证"1/16 拍花瓣线"是否有效
1. 在自己的谱里加 1 条花瓣线（1/16 粒度）
2. 其他一切不变
3. 对比：有/无的观感差异
4. 记录结论：有效 → 保留；无效 → 分析原因（素材太小？alpha 太高？）

> 这一条是"从会看谱"到"会写谱"的唯一通道。

---

## 6. 拆谱清单（每张精品谱都填一遍）

```markdown
# 《曲名》拆解

## 音乐
- BPM / 时长 / 段落结构
- 情绪峰值位置

## 规模
- 线数 / 音符数 / 分组数 / 特效数
- 承载 note 的线占比

## 舞台
- 各线角色（列表）
- 父子线结构
- zOrder 分配

## 编排
- 事件粒度（最密的是哪条线，多少事件）
- 速度曲线（几段、范围）
- alpha 用法（有没有负值隐藏）
- 纹理/文字/UI 使用情况

## 对照音乐
- 3 个关键时间点的"音乐 vs 谱面"表

## 可迁移手法（3~5 条）
1. ...
2. ...

## 我的实验计划
- [ ] 手法 A 在《我的曲子》上验证
```

---

## 7. 常见的学习误区

| 误区 | 后果 | 正解 |
|---|---|---|
| 只看 note 结构 | 学成"打地鼠" | 先看线、再看 note |
| 照抄事件数值 | 曲风不符，生硬 | 学"为什么"，不学"多少" |
| 追求线多 | 视觉噪音 | 角色清晰 > 数量 |
| 忽略音乐分析 | 对齐但无灵魂 | 先听 3 遍 |
| 一次改 10 个地方 | 无法定位效果 | 一次一个变量 |

---

## 8. 拆解结论沉淀在哪

- 结论写进 [`02-masterclass-notes.md`](02-masterclass-notes.md)
- 手法写进 [`docs/03-workflow/03-judge-line-choreography.md`](../03-workflow/03-judge-line-choreography.md)
- 代码写进 `tools/chart_builder.py`
- 踩坑写进 [`docs/02-pitfalls/PITFALLS.md`](../02-pitfalls/PITFALLS.md)
