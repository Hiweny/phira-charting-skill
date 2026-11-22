# 00 · 学习与迭代日志（Learning Log）

> 这个技能包是"活的"。每研究一份新谱、每被主人纠正一次，就在这里记一行。
> 下一个 Agent 先看最新一条，再决定今天补什么。

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

## 模板（以后每条照这个写）

```text
## YYYY-MM-DD
### 新拆解：曲名 → 文档链接
- 3~6 条可复现结论（带参数/时间点）
### 新方法 / 新工具
### 被主人纠正的点
### 未解 / 下一步
```
