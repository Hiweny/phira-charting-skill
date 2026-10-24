# 01 · 资源索引（维基 / 官方文档 / GitHub 生态 / 工具）

> 链接核验日期：2026-10-24。标 ⭐ 的是开发本项目时最常用的。

---

## 一、制谱维基（必读）

| 站点 | 说明 |
|---|---|
| ⭐ [Phigros 自制谱 Wiki](https://pgrfm.miraheze.org/) | 中文社区最权威的制谱技术 wiki。RPE 谱面格式、事件、缓动、术语都在这里 |

### 关键条目

| 条目 | 链接 | 用途 |
|---|---|---|
| 首页 | <https://pgrfm.miraheze.org/wiki/首页> | 总入口 |
| RPEJSON | <https://pgrfm.miraheze.org/wiki/RPEJSON> | JSON 结构 |
| 判定线 | <https://pgrfm.miraheze.org/wiki/判定线> | 线字段与控制序列 |
| 事件 | <https://pgrfm.miraheze.org/wiki/事件> | 5 类普通事件 + 扩展事件 |
| 缓动 | <https://pgrfm.miraheze.org/wiki/缓动> | **缓动序号表**（本项目 0/1/2/3/4/5/6/7/8/9/10/11/12/13 的来源） |
| 音符 | <https://pgrfm.miraheze.org/wiki/音符> | 四类 note 与字段 |
| 速度 | <https://pgrfm.miraheze.org/wiki/速度> | 速度事件语义（1.6 / 1.7 差异） |
| 故事版 | <https://pgrfm.miraheze.org/wiki/故事版> | textEvents / 叙事 |
| 通用制谱术语 | <https://pgrfm.miraheze.org/wiki/通用制谱术语> | 行话对照（NPS、Drop、Buildup…） |
| Phira 资源包 | <https://pgrfm.miraheze.org/wiki/Phira资源包> | 资源打包规范 |

---

## 二、Phira 官方文档

| 文档 | 链接 |
|---|---|
| ⭐ Phira Docs 总站 | <https://teamflos.github.io/phira-docs/> |
| 谱面标准 | <https://teamflos.github.io/phira-docs/chart-standard/> |
| 谱面文件格式 | <https://teamflos.github.io/phira-docs/chart-standard/chart-format/> |
| 谱面信息 info.yml | <https://teamflos.github.io/phira-docs/chart-standard/chartinfo.html> |
| ⭐ 特效 extra.json | <https://teamflos.github.io/phira-docs/chart-standard/extra/effect/> |
| 内置着色器 | <https://teamflos.github.io/phira-docs/chart-standard/extra/effect/builtin/> |
| 自定义着色器 | <https://teamflos.github.io/phira-docs/chart-standard/extra/effect/custom-shader.html> |

> 官方文档明确：**元数据以 `info.yml` 为准，RPE JSON 内的 META 可能与之一致性冲突。**

---

## 三、GitHub 生态

### 3.1 Phira 本体（对照开发必看）

| 仓库 | 星 | 说明 |
|---|---|---|
| ⭐ [TeamFlos/phira](https://github.com/TeamFlos/phira) | 2.7k | **Phira 客户端主项目（Rust）**。谱面解析逻辑的最终真相 |
| ⭐ [TeamFlos/phira-docs](https://github.com/TeamFlos/phira-docs) | 12 | 官方文档源码（含谱面标准） |
| [TeamFlos/phira-render](https://github.com/TeamFlos/phira-render) | 42 | **Web 谱面渲染器（Vue）**，无客户端时的可视化验证首选 |
| [TeamFlos/phira-mp](https://github.com/TeamFlos/phira-mp) | 98 | 多人联机服务端（与本项目无关，但了解生态） |

> **开发建议**：遇到"这个字段到底该是什么类型"的疑问，直接去
> `TeamFlos/phira` 里搜结构体定义（`serde` 的 `Deserialize` 实现），比猜快 100 倍。

### 3.2 编辑器

| 仓库 / 项目 | 说明 |
|---|---|
| ⭐ [kclg-YSJ/rpe-next](https://github.com/kclg-YSJ/rpe-next) | Re:PhiEdit Next（AI 重构的非官方 RPE） |
| [happymimimix/Ex-Phiedit](https://github.com/happymimimix/Ex-Phiedit) | 自制 Phigros 编辑器 |
| [Chengxuxiaoyuan-2573/Phiedit-2573](https://github.com/Chengxuxiaoyuan-2573/Phiedit-2573) | Vue-Electron 编辑器，支持 RPE 格式 + 渲染 |
| [Zes-MinKey-Young/KipPhiApparatus](https://github.com/Zes-MinKey-Young/KipPhiApparatus) | 高性能 Phigros 谱面编辑器 |

### 3.3 播放 / 渲染 / 校验

| 仓库 | 说明 |
|---|---|
| ⭐ [Mivik/prpr](https://github.com/Mivik/prpr) | 轻量 Phigros 谱面播放器（Phira 特效体系即源自 prpr） |
| [PhiZone/player](https://github.com/PhiZone/player) | HTML5 Phigros 谱面播放器 / 模拟器 |
| [q-roo/phigros-chart-engine](https://q-roo.github.io/phigros-chart-engine/) | 网页谱面引擎（第三方） |
| [TeamZincs/Kipphi](https://github.com/TeamZincs/Kipphi) | 谱面解析库（编辑器友好格式） |

### 3.4 格式转换 / 辅助

| 仓库 | 说明 |
|---|---|
| [swordalt/phigros-chart-downloader](https://github.com/swordalt/phigros-chart-downloader) | 导出官谱为 Phira / PhiEdit 可用格式 |
| [zwtwz/PhigrosChartTransformer](https://github.com/zwtwz/PhigrosChartTransformer) | 官谱 → Phira pez |
| [liquidhelium/mid2json](https://github.com/liquidhelium/mid2json) | MIDI → RPE JSON（自动制谱参考） |
| [MisaLiu/rpe-version-convert](https://github.com/MisaLiu/rpe-version-convert) | RPE 版本转换 / 压缩 |

### 3.5 自动制谱 / 音频研究（跨游戏参考）

| 项目 | 说明 |
|---|---|
| [ardnebg/strum](https://github.com/ardnebg/strum) | 最完整的自动制谱流水线（Demucs + CRNN + 规则后处理，鼓 F1=0.838） |
| [auto-osu/auto-osu](https://github.com/auto-osu/auto-osu) | osu!mania 端到端谱面生成 |
| [facebookresearch/demucs](https://github.com/facebookresearch/demucs) | 音源分离（人声/鼓/贝斯/其他） |
| [librosa](https://librosa.org/doc/latest/) | 音频分析核心库（BPM / onset / 特征 / 结构） |

---

## 四、社区与教程

| 资源 | 链接 |
|---|---|
| B 站制谱教程 1 | <https://www.bilibili.com/read/cv12131531/> |
| B 站制谱教程 2 | <https://www.bilibili.com/read/cv26218262/> |
| TapTap Phira 社区 | <https://www.taptap.cn/moment/522477244472364098> |
| Phigros 自制谱交流群 | 478824121（wiki 首页公告，**技术规范向，非谱师慎入**） |

---

## 五、工具速查

| 需求 | 工具 |
|---|---|
| 音乐分析 | `tools/analyze_music.py`（librosa） |
| 音源分离 | `demucs --two-stems=vocals song.mp3 -o stems/` |
| 谱面生成 | `tools/chart_builder.py` |
| 谱面校验 | `tools/validate_chart.py` |
| 打包 | `tools/package_chart.sh` |
| 可视化验证 | Phira 客户端 / phira-render / prpr / PhiZone player / Re:PhiEdit |
| 类型溯源 | `TeamFlos/phira` 源码里的 serde 结构体 |

---

## 六、本仓库的"事实来源"分级

| 级别 | 来源 | 可信度 |
|---|---|---|
| A | Phira 官方文档 + 主项目源码 | 最高 |
| B | Phigros 自制谱 Wiki | 高（社区维护，偶有滞后） |
| C | 真实可导入谱面的字段实测 | 高（但受版本限制） |
| D | 第三方项目 / 教程 | 中（需交叉验证） |

> 写进本仓库的结论，至少是 B/C 级。凡未验证的，文中已标注"需实机确认"。
