# 01 · 谱面工程结构

## 1. 分发形态

Phira 谱面以 **ZIP 包**分发，解压后必须是**扁平目录**（不能多包一层文件夹）。

```
chart-project/
├── info.yml               # 必需 · 元数据入口
├── chart.json             # 必需 · RPE 谱面数据
├── song.mp3               # 必需 · 音乐
├── illustration.png       # 必需 · 曲绘（jpg/png）
├── extra.json             # 可选 · 特效 / 着色器 / 背景视频
├── line.png               # 可选 · 判定线纹理
├── blossom.png            # 可选 · 自定义纹理素材
├── unlock.mp4             # 可选 · 解锁视频
└── info.txt               # 可选 · 编辑器导出信息（可忽略）
```

> `info.yml` 里的 `chart` / `music` / `illustration` 字段**才是真实文件名**。
> 文件名里的数字 ID 只是平台习惯，不参与解析。

## 2. 最小可导入集合

| 文件 | 必需 | 说明 |
|---|---|---|
| `info.yml` | ✅ | 缺任何必需字段 → 导入即失败 |
| `chart.json` | ✅ | 顶层 7 字段 + judgeLineList 至少 1 条线 |
| 音乐文件 | ✅ | mp3/ogg/wav |
| 曲绘 | ✅ | 严格说 Phira 可容忍缺失，但导入流程通常要求 |
| `extra.json` | ❌ | 无特效可完全不提供 |
| 自定义纹理 | ❌ | 引用了就必须一起打进 zip |

## 3. 打包

```bash
cd my-chart && zip -r ../my-chart.zip . -x '.*' -x '__MACOSX/*'
```

**坑**：在 `my-chart/` 外面直接 `zip -r my-chart.zip my-chart/` 会多一层目录，Phira 读不到 `info.yml`。

用 [`tools/package_chart.sh`](../../tools/package_chart.sh) 可避免。

## 4. 编码与格式

- `info.yml`：**UTF-8，不要 BOM**。含 `:`、`#`、`-`、`[` 等 YAML 特殊字符的字符串必须加引号。
- `chart.json`：UTF-8，单个 JSON 对象。**不能有 BOM，不能有第二个对象，不能有注释**（否则报 `trailing characters`）。
- 生成时统一 `json.dump(..., ensure_ascii=False, separators=(',', ':'))` 可显著减小体积。

## 5. 版本

- `META.RPEVersion`：本项目验证于 `170`（RPE 1.7.0）。
- 不同版本对 `speedEvents` 的解释不同（1.7.0 改了速度语义，`useRpe170Speed` 控制）。
- 拿不准时：**和参考谱保持同版本**。

## 6. 命名建议

```
info.yml
chart.json
song.mp3
illustration.png
extra.json
textures/          ← 不推荐，Phira 对子目录支持不稳定，纹理请放根目录
```
