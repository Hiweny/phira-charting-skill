# 00 · 学习与迭代日志（Learning Log）

> 这个技能包是"活的"。每研究一份新谱、每被主人纠正一次，就在这里记一行。
> 下一个 Agent 先看最新一条，再决定今天补什么。

---

## 2026-11-22（深夜）· 首张"从文件到成品"的完整实战：《我的灵魂伴侣在哪里》

### 新拆解 / 新案例

- **《เนื้อคู่ฉันอยู่ไหน（中国版）》Sweety Boy → [`14-case-lyrics-pop.md`](04-reference/14-case-lyrics-pop.md)**
  - 完整链路：文件体检 → 网格标定 → 结构表 → 剧本 → 生成 → 自检，全部数字可复现
  - 核心成果：12 条线 / 710 真音符 / IN 13 / 峰值 12 NPS / `approach_visible` 0.986

### 新工具

- **`tools/extract_tags.py`**：从 FLAC(VORBIS_COMMENT+PICTURE) / ID3v2(USLT/APIC) / MP4(©lyr/covr)
  提取**内嵌歌词与封面**；自动识别 `[TLYRIC]` 双语段并拆成 `lyrics.lrc` + `lyrics.zh.txt`；
  `--check` 可识别"扩展名撒谎"（fLaC 存成 .mp3）。

### 新方法（写进 workflow）

1. **BPM 记法双证据判定**（[`02-chart-authoring.md`](03-workflow/02-chart-authoring.md)）：
   鼓点网格得分 + 歌词整拍率。本次 182.9 / 91.43 两解都对，但只有 91.43 让 48 句全落整拍。
2. **静音尾巴检测**：尾部连续 < −25 dB 且 6 kHz 以上衰减 → 有效内容终点（本次 152.4 s，后面 24 s 空白）。
3. **歌词向流行曲的密度配方**：主歌 2.7–3.3、预副 2.4–2.6、副歌 6.6–6.9、Rap 7.2（16 分 Drag 流）、
   Bridge 1.9（含 6 拍零音符）。峰值控制靠"把 16 分收尾段改成 8 分"。
4. **降速换可见性**：speed 10 → 8.8，`approach_visible_ratio` 从 0.84 升到 0.986，密度一点没加。

### 新坑

- **contact-sheet 会因排版未填满出现"黑格"**，别误判成谱面渲染失败；先用 `--frame` 单帧确认。
- **`extra.json` 的 `vars` 常量（如 `radius: 90`）会让本地预览器崩**（`'float' object is not iterable`）；
  一律写成单事件数组，Phira 与预览器通吃。
- **歌词线 alpha 事件别用"点列表自动补到 240 拍"的写法**：最后一点会生成一条到曲末的长事件，
  把后面所有句子的 alpha 覆盖掉（表现为"只有第一句歌词"）。逐句显式写 3 段事件。
- `speedEvents` 不吃 `easingType`；`bpmfactor` 是 BPM **除以**它，不是乘。

### 未解 / 下一步

- [ ] 事件密度只有 2.0/音符（社区中位 3–6）：下一版用 `eventLayers` 加法层做高频呼吸，而不是继续加密主曲线
- [ ] Hold 占比 6.8% 偏低，抒情向可到 10–15%
- [ ] 真机导入仍未验证：声音延迟、打击特效、皮肤配色

---

## 2026-11-22

### 新拆解

- **《琵琶行（Full ver.）》** → [`09-case-studies.md`](04-reference/09-case-studies.md)
  - 断线浮空（线 alpha=0，音符仍可见/可判定）
  - 扫线/刮奏墙、频闪、双线轮班、天顶线、蛇形 Drag
- **《放空》** → 同上
  - 全正拍 + 每拍一个 2–6 押和弦 + 75 px 网格
  - 992 个假 note（59.6%），真实密度仅 4.5 NPS
  - 假 note 光柱、叠线发光
- **《时落之雨》** → [`10-case-shiluozhiyu.md`](04-reference/10-case-shiluozhiyu.md)
  - 母题统一：雨滴 / 雨柱 / 雨丝 / 水花
  - 发射器线、线即轨迹（±540°）、速度视差、扇阵、线框空间、微呼吸
  - 24 条线 × 8.7 s 假 Hold + `speed=1000` = 按拍闪现的雨柱

### 新方法

- [`11-note-and-line-choreography.md`](04-reference/11-note-and-line-choreography.md)：
  引擎位置公式、四条"活"法则、拟物配方表、五种轨迹、四种 3D、叠音/接音、参数预算。
- [`03-workflow/06-art-contract.md`](03-workflow/06-art-contract.md)：
  把主人的硬约束（一条演奏线 / Lv12–13 / 几何美 / 3D 参与演奏 / 歌词时限）固化。

### 新资源

- [`05-resources/02-asset-sources.md`](05-resources/02-asset-sources.md)：
  Otter Music（多源搜歌/下载）、PrprBako（Phira 资源包）、
  资源包结构、`data/respack` 安装、高潮换材质的可行做法。

### 新验证

- [`06-qc/03-real-engine.md`](06-qc/03-real-engine.md)：
  Phira Linux 包下载、Xvfb + llvmpipe 启动、`data/charts/custom` 导入、
  已知黑屏坑（`add renderer ... buffer is full`）。
- `preview_render.py` 修正：note alpha 不再乘判定线 alpha（与 Phira 一致）。
- `validate_chart.py` 新增：真 note 但 alpha≤10 的"幽灵 note"警告。

### 未解 / 下一步

- [ ] `multiLineString` / `multiScale` 在 Phira 的兼容性仍未定论（RPE 1.7 编辑器级联动）。
- [ ] Phira 无 GPU 环境下的黑屏是否有运行时开关可绕过（miniquad/llvmpipe）。
- [ ] "一个 note 接住其他 note" 的更多官方/社区实例，继续补充配方。
- [ ] 皮肤与谱面的自动配色建议（从插画主色推导 note 颜色）。
- [ ] 把《时落之雨》的雨滴/光柱/扇阵移植到《君自故乡来》v6。
- [ ] 继续收集"3D 纵深"案例，优先找带 scale/incline 的 RPE 1.7 谱。

---

## 2026-11-22（晚）·《深圳东》· 媒体层 · 预览器二次对齐

### 新拆解

- **《深圳东》AT Lv.15.9** → [`12-case-shenzhendong.md`](04-reference/12-case-shenzhendong.md)
  - **两态结构**：中心柱（L9/L18，x=0，speed 10）↔ 全屏散开（L2/L19/L5+L6/L10–13）；
  - **线接力**：16 条线真正承载 note，但同一时刻最多 2 条，旧线扔到 `x=114514`；
  - **颜色三层**：默认皮肤类型色（蓝/黄/红/白）→ shader 时间轴 → 插画 dim；全谱 0 个 `colorEvents`；
  - **节奏交互**：双线对打 ±5°、镜像对打 ±135、Flick 对打 ±405、四线收束、密度递增只缩间隔；
  - **线框空间**：53 条默认线、`lineLength=6`（6 屏高）、共点星芒、四角射线、速度倒流 `-4`；
  - **逐帧视觉观察**（新增 §1.5）：明度分层背景<线<note、两态一眼可分、红色只做信号、留白靠 vignette + 撤物量。

- **媒体层手册** → [`13-media-layers.md`](04-reference/13-media-layers.md)
  - 贴图精灵 / GIF（`gifEvents` 0~1 是播放进度）/ 文字线（26 px 固定）/ 画笔 iris / `videos`；
  - `videos` 真实字段只有 `path/time/scale/alpha/dim/attach`（旧文档的 `startTime/endTime/colorFilter` 是错的）；
  - 10 个内置 shader 的变量、配方与"NO_SHADER 降级"要求；
  - **皮肤单图可当贴图素材**：整套换不了，但 `hold.png` 可当光柱、`click.png` 可当星点。

### 被主人纠正 / 强调

- **研究谱不能只看代码，必须看画面**：数据说"用了什么"，画面才说"为什么好看"。
- **皮肤整套不能中途换，但单图仍可当贴图资源**；外部图片/视频的嵌入手法要写清楚。
- **skill 必须强调：制谱过程中就要看视觉效果与手感**，这两样只看代码看不出来。
- 没法真机开 Phira，就**对照 Phira 仓库把预览器做到尽量对齐**。

### 新工具 / 新对齐

- `tools/preview_render.py` 第二轮按 prpr 源码对齐：
  - note 位置公式 `line_pos + R(rot)·(positionX, -height)`，修正"发射器线 note 跑到屏幕中心"；
  - 线长按 `lineLength`（默认 6）画 12 世界单位；
  - note 全宽按 `NOTE_WIDTH_RATIO_BASE`（0.2635 世界单位），默认皮肤色对齐 Tap 蓝 / Hold 近白 / Drag 黄 / Flick 红；
  - `alpha/size/pos/yControl` 改为按 note 行进距离求值；
  - `above=2` 不再反向；`visibleTime` 淡入；
  - 10 个内置 shader、贴图线、GIF 帧、文字线、画笔线、`videos`（含 attach 近似）。
- 对齐清单与仍属近似的部分见 [`03-real-engine.md`](06-qc/03-real-engine.md) §6/§7。

### 新坑（已写进各文档）

- 负 alpha 在 Phira 的 RPE 解析里被 `max(0)`，不能用 Phigros 负 alpha 扩展；
- 贴图线固定白色、**不吃 `colorEvents`**；
- `above=2` 只影响粒子朝向，不影响下落方向；负 speed 才是反向；
- `skewControl`、`multiLineString`、`multiScale` 被 Phira 忽略；
- 视频没有 `startTime/endTime/colorFilter`，要截断只能剪视频本身。

### 未解 / 下一步

- [ ] Phira 在无 GPU 的 CI 里仍黑屏（miniquad + llvmpipe），皮肤/打击特效/手感仍须真机；
- [ ] `attach` 视频的透视变换仍是近似（简化为"旋转后的全屏图"）；
- [ ] 继续收集"贴图线 + attach 视频"的实例，补进 13 的配方；
- [ ] 把《深圳东》的两态 + 线接力 + shader 时间轴移植到下一张单线谱。

---

## 模板（以后每条照这个写）

```text
## YYYY-MM-DD
### 新拆解：曲名 → 文档链接
- 3~6 条可复现结论（带参数/时间点）
### 新方法 / 新工具
### 被主人纠正的点
### 未解 / 下一步
```
