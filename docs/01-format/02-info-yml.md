# 02 · info.yml 规范

`info.yml` 是 Phira 的谱面入口。**YAML 类型错误 = 导入直接失败**，且报错信息往往只说"expected i32"，不会告诉你是哪个字段。

## 1. 完整字段表

| 字段 | 类型 | 必需 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | **int (i32)** | 否 | — | 谱面 ID。**绝不能写字符串**。本地自用随便给个整数，如 `88001` |
| `uploader` | **int (i32)** | 否 | — | 上传者 UID。**绝不能写名字**，如 `1233` |
| `name` | string | ✅ | — | 曲名 |
| `difficulty` | **float** | ✅ | — | 定数，如 `13.0`（写 `13` 也接受，但建议带小数） |
| `level` | string | ✅ | — | 难度显示，如 `"IN 13"`、`"IN Lv.13+"` |
| `charter` | string | ✅ | — | 谱师名 |
| `composer` | string | ✅ | — | 曲师 |
| `illustrator` | string | ✅ | — | 曲绘作者 |
| `chart` | string | ✅ | — | 谱面 JSON 文件名（**不是路径**） |
| `music` | string | ✅ | — | 音乐文件名 |
| `illustration` | string | ✅ | — | 曲绘文件名 |
| `format` | string/null | ❌ | null | 一般留 null |
| `unlockVideo` | string/null | ❌ | null | 解锁视频文件名 |
| `previewStart` | float | ✅ | 0.0 | 试听起点（秒） |
| `previewEnd` | float/null | ❌ | null | 试听终点；null 时默认 +15s |
| `aspectRatio` | float | ✅ | 1.0 | 画面比例，16:9 用 `1.777778` |
| `backgroundDim` | float | ✅ | 0.6 | 背景暗化 0~1 |
| `lineLength` | float | ✅ | 6.0 | 判定线长度 |
| `offset` | float | ✅ | 0.0 | 全局延迟（**秒**） |
| `tip` | string | ❌ | — | 提示语 |
| `tags` | list[string] | ✅ | — | 标签，如 `["Pop", "Dance"]` |
| `intro` | string | ✅ | — | 简介 |
| `holdPartialCover` | bool | ✅ | false | Hold 遮罩位置 |
| `noteUniformScale` | bool | ✅ | false | note 统一缩放 |
| `forceAspectRatio` | bool | ✅ | false | 强制宽高比 |
| `useAttachUiFix` | bool | ✅ | true | 修复 attachUI 显示 |
| `useRpe170Speed` | bool/null | ❌ | null | 是否用 RPE 1.7.0 速度语义 |

## 2. 一份可直接用的模板

```yaml
id: 88001
uploader: 1233
name: Dangerous (Immortal Version)
difficulty: 13.0
level: IN 13
charter: Maid
composer: Michael Jackson
illustrator: Michael Jackson
chart: chart.json
format: null
music: song.mp3
illustration: illustration.png
unlockVideo: null
previewStart: 43.0
previewEnd: null
aspectRatio: 1.0
backgroundDim: 0.75
lineLength: 6.0
offset: 0.0
tip: 'Dangerous! The girl is so dangerous!'
tags:
  - Michael Jackson
  - Pop
  - Dance
intro: 'MJ''s Dangerous - charted with love by Maid.'
holdPartialCover: false
noteUniformScale: false
forceAspectRatio: false
useRpe170Speed: null
useAttachUiFix: true
```

## 3. 两套字段命名（都能导入）

除了上面的 RPE 小写格式，Phira 也接受旧版 Phi 格式：

```yaml
Name: 你总是盘旋在我脑海里面
Song: 你总是盘旋在我脑海里面.mp3
Picture: illustration.jpg
Chart: 你总是盘旋在我脑海里面.json
Level: IN Lv.13
Composer: DJ
Charter: 愉是心上结
```

- 旧版只有 7 个字段，没有 `difficulty/id/uploader/offset/...`，Phira 会补默认值。
- **不要混用**两套命名；新写的谱一律用 RPE 小写格式。
- `validate_chart.py` 会自动识别两套格式。

## 4. 三个高频翻车点

### 4.1 `id` / `uploader` 写成字符串

```yaml
id: dangerous_maid_001   # ❌ invalid type: string, expected i32
uploader: maid           # ❌ invalid type: string, expected i32
```
```yaml
id: 88001                # ✅
uploader: 1233           # ✅
```

### 4.2 字符串里裸写冒号

```yaml
tip: Dangerous! The girl is so dangerous!   # ✅ 无冒号，安全
intro: 谱师: Maid                            # ❌ mapping values are not allowed
intro: '谱师: Maid'                          # ✅
```

同理：`#`、`{`、`[`、`&`、`*`、`|`、`>` 开头的字符串都要加引号。

### 4.3 缩进用了 Tab

YAML 只认空格。用 2 空格缩进，`tags` 列表项前用 `  - `。

## 5. offset 的双重性

- `info.yml` 的 `offset` 单位是**秒**（float）。
- `chart.json` 的 `META.offset` 单位是**毫秒**（int）。

两者可能不一致。**以 info.yml 为准**做手感微调；`META.offset` 建议与 `info.yml.offset * 1000` 保持一致，避免不同端表现不同。

## 6. 常见报错速查

| 报错 | 原因 |
|---|---|
| `invalid type: string, expected i32` | `id` / `uploader` 写成了字符串 |
| `mapping values are not allowed in this context` | 字符串里有裸 `:` |
| `did not find expected key` | 缩进错 / Tab |
| `missing field <x>` | 缺必需字段 |
| 导入成功但"加载谱面失败" | `chart` / `music` 文件名与实际不符，或 `chart.json` 里缺 `BPMList.bpm` |
