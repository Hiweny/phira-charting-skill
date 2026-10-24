# 01 · 自检流程（做完谱后必走）

> 目的：**在任何工具打开之前，就知道自己做出来的是什么谱。**
> 不要靠"导入试试"碰运气。

---

## 0. 四级验证

```
L0 生成期    → chart_builder 保证字段合法
L1 静态      → validate_chart.py 结构与语义检查
L2 量化      → --report 输出曲线/分布，人工判定设计是否达标
L3 实机      → Phira 导入 → 加载 → 试玩 → 观感
L4 交叉      → 用另一个渲染器（phira-render / prpr）复核
```

**L1 不过，不要往下走。L3 没玩过，不要交付。**

---

## 1. L1 静态校验

```bash
python3 tools/validate_chart.py my-chart
```

会检查（详见脚本）：

| 类别 | 检查项 |
|---|---|
| 文件 | info.yml / chart.json / 音乐 / 曲绘 是否存在；zip 是否扁平 |
| YAML | 必需字段、类型（id/uploader 是 int） |
| JSON | 单对象、可解析、顶层 7 字段 |
| 时间 | 三元组全整数、分母合法、end ≥ start |
| 音符 | 11 字段齐全、类型 1~4、positionX int、时间越界 |
| 判定线 | 19 字段、control 是数组、father 下标合法、Group 合法 |
| 事件 | 5 个数组齐全、10 字段齐全、时间顺序 |
| 语义 | 重叠 note、密度突变、X 越界、速度为 0/负值警告、alpha 全 0 |
| extra | start/end 是三元组、shader 名非空 |

退出码 `0` = 无 error（warn 仍会打印）。

---

## 2. L2 量化报告

```bash
python3 tools/validate_chart.py my-chart --report
```

输出类似：

```
=== Chart Report ===
Lines         : 6 (playing 4 / perform 2)
Notes         : 767  (Tap 420 / Hold 88 / Flick 34 / Drag 225)
Duration      : 161.56s
Avg NPS       : 4.75
Peak NPS      : 9.20 @ 58.4s
Notes/line    : MJ 512 | Left 110 | Right 92 | ...
X range       : -520 ~ 520 (mean 3.2)
Event density : MJ moveX 96 / Spotlight 210 / Rhythm 180
Speed range   : 3.0 ~ 14.0 (segments: 5)
Effects       : 5 (vignette, chromatic, shockwave×2, glitch)
```

### 对照验收表

| 指标 | 健康区间 | 异常信号 |
|---|---|---|
| 平均 NPS | 与定数匹配（见下表） | 全曲 < 1 或 > 10 |
| NPS 曲线 | 段落之间有起伏 | 一条直线 |
| 演奏线数 | 2~4 | 1（单调）或 > 6（看不过来） |
| 表演线事件 | ≥ 1 条线 > 100 事件 | 所有线 < 30（死板） |
| X 分布 | 覆盖 ±400 以上 | 全在 ±100（挤中间） |
| 音符类型 | 无单一类型 > 80% | 全 Tap / 全 Drag |
| 最长 Hold | ≤ 2 拍（快歌） | > 4 拍（手僵） |
| 速度段数 | ≥ 3 | 1 段（无呼吸） |
| 重叠 note | 0 | > 0（必漏判） |
| 越界 note | 0（演奏线） | > 0（看不见） |

定数 → NPS 参考：IN12 ≈ 3~5，IN13 ≈ 4~6，IN14 ≈ 5~7，IN15 ≈ 6~8。

---

## 3. L3 实机验证（Phira 本体验证，最权威）

1. 打包：`bash tools/package_chart.sh my-chart`
2. Phira → 本地谱面 → 导入 zip
3. 三步确认：
   - **能导入**（格式过）
   - **能加载**（BPMList / 资源过）
   - **能游玩**（判定 / 演出过）
4. 试玩检查表：

| 检查 | 通过标准 |
|---|---|
| note 下落 | 从上方/下方正常飞入，不黏在线上 |
| 可见性 | 每个 note 都能看清（无被线遮挡） |
| 判定 | 卡点打得上，不早不晚 |
| 手感 | 流速舒适，不拖沓不闪现 |
| 演出 | 线在动，但不挡视线 |
| 特效 | 不影响读谱 |
| 首尾 | 开头不突兀，结尾收干净 |
| 音画同步 | 副歌重音与 note 对齐 |

5. 录屏回看一遍（自己玩的时候注意不到的问题，回放能看见）。

---

## 4. L4 交叉验证（没有 Phira 客户端时）

按可信度排序：

| 工具 | 类型 | 用法 | 可信度 |
|---|---|---|---|
| **Phira 客户端** | 官方 | 导入 zip 试玩 | ★★★★★（最终标准） |
| **Re:PhiEdit / Phiedit-2573** | 编辑器 | 直接打开 `chart.json`，可视化编辑 | ★★★★☆ |
| **phira-render** | Web 渲染 | 上传谱面渲染视频 | ★★★★☆（与 Phira 同源） |
| **prpr** | 播放器 | 载入 RPE JSON 播放 | ★★★★☆（Phira 特效体系来源） |
| **PhiZone/player** | Web 模拟器 | 浏览器播放 | ★★★☆☆ |
| **Kipphi** | 解析库 | 程序化检查 | ★★★☆☆ |

> 注意：第三方渲染器对自定义 shader / 新版本字段的兼容性不如 Phira 本体。
> **最终验收必须在 Phira 里完成。**

---

## 5. 自检清单（打印版）

```
□ 1. 目录扁平，info.yml 在根
□ 2. info.yml: id/uploader 是整数；字符串带引号；无 Tab
□ 3. chart.json 能 json.load
□ 4. 顶层 7 字段齐全
□ 5. BPMList 每项有 bpm(float) + startTime(3 int)
□ 6. 所有 note 有 11 字段（尤其 endTime / positionX）
□ 7. 所有时间三元组是整数
□ 8. eventLayers 每层 5 个事件数组
□ 9. control 字段都是 []
□ 10. isCover 是 0/1；isGif 是 bool
□ 11. extra.json 的 start/end 是三元组
□ 12. validate_chart.py 退出码 0
□ 13. --report 的 NPS / X / 事件密度符合设计
□ 14. 打包 zip 无多余目录
□ 15. Phira 导入成功
□ 16. Phira 加载成功
□ 17. 试玩通过（下落 / 判定 / 演出 / 同步）
□ 18. 录屏回看无遮挡、无漏判
```

---

## 6. 交付时必须报告的数字

```
工程：my-chart
线：6（演奏 4 / 表演 2）
音符：767（Tap 420 / Hold 88 / Flick 34 / Drag 225）
时长：161.56s，平均 NPS 4.75，峰值 9.20 @ 58.4s
X 覆盖：-520 ~ 520
特效：5（vignette / chromatic / shockwave×2 / glitch）
校验：0 error, 2 warn（warn: bridge 段速度偏低）
实机：Phira 导入 / 加载 / 试玩 通过
```

没有这组数字的交付 = 没做完。

---

## 7. 自动化（CI 思路）

可把 L1 做成 pre-commit：

```bash
# .git/hooks/pre-commit
python3 tools/validate_chart.py examples/minimal || exit 1
```

L3 无法自动化（需要 Phira 客户端）。替代方案：
用 `phira-render` 的 CLI 渲染首 10 秒截图，人工比对。
