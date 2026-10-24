# 01 · 音乐分析流程

> **铁律：拿到一首曲子，先分析音乐，再分析谱面，最后才写谱。**
> 顺序反了，做出来的就是"音符堆积"，不是谱面。

---

## 1. 目标产出

分析完必须能回答这 12 个问题，并写成"设计笔记"：

1. BPM 是多少？有没有变速？
2. 第一拍落在第几秒（offset）？
3. 段落结构：Intro / Verse / Pre-Chorus / Chorus / Bridge / Solo / Outro 各从第几秒到第几秒？
4. 每段的能量（RMS）与频谱亮度（centroid）如何变化？
5. 鼓点密度最高的是哪几段（onset 数/秒）？
6. 人声活跃区段在哪（决定 Hold 的位置）？
7. 全曲的"情绪峰值"在哪一拍？
8. 有没有静音/留白段（这是做"无声演出"的黄金位置）？
9. **歌词在讲什么？**关键词、重复句、叙事线是什么？
10. **每一句歌词落在第几拍？**哪几个字是重音？
11. **每段的情绪是什么？**用"张力 / 明亮 / 密度"三个分值描述。
12. **这首歌想让听众经历怎样的情绪旅程？**一句话。

---

## 2. 工具

```bash
pip install --break-system-packages librosa numpy scipy soundfile matplotlib
python3 tools/analyze_music.py song.mp3 -o analysis.json --plot analysis.png
```

`tools/analyze_music.py` 输出：

```json
{
  "duration_seconds": 140.2,
  "bpm": { "static": 129.2, "dynamic_min": 129.2, "dynamic_max": 129.2 },
  "beats": { "total": 295, "avg_interval_seconds": 0.469, "first_10_beats": [0.09, 0.51, ...] },
  "onsets": { "default_count": 535, "superflux_count": 610, "drum_peaks": 550 },
  "energy": { "rms_db_max": 0.0, "rms_db_mean": -9.5, "high_energy_sections": 0, "silence_sections": 1 },
  "spectral": { "centroid_mean_hz": 2859.0 },
  "vocal": { "vocal_sections": 8 },
  "structure": { "segments": 3, "boundaries": [[0.0, 2.8], [2.8, 78.7], ...] }
}
```

---

## 3. 手工解析流程（脚本之外必须自己看）

### Step 1 · 听三遍

1. 第一遍：只听情绪，记下"哪里爽、哪里静、哪里转折"。
2. 第二遍：数拍子，跟着点头，标记段落切换。
3. 第三遍：听分轨——鼓在哪、人声在哪、有没有镲片/合成器点缀。

> 不做这一步，只靠 librosa 数字，会做出"对齐但没灵魂"的谱。

### Step 2 · 校准 BPM

librosa 平均误差约 1.5 BPM。误差来源：半拍/双拍误判。

**校准方法**：以检测值为中心，±5 范围做网格搜索，选"节拍网格与鼓点重合度最高"的值（脚本内已实现）。

手动校验公式：`beat_interval = 60 / bpm`，与 `beats.avg_interval_seconds` 对比，偏差 > 2% 就手动指定。

### Step 3 · 确定 offset

`beats.first_10_beats[0]` 就是第一个强拍的时间（秒）。

- 若约等于 0 → `offset: 0`
- 若为 0.09s → 建议 `offset: 0.09`（或 90ms 写在 META）
- **不要用第一下声音的起始点**，用"第一拍的中心"。

### Step 4 · 段落表

把 `structure.boundaries` 的结果人工修正成音乐段落（算法只给边界，命名靠人）：

| 段落 | 起(s) | 止(s) | 起(beat) | 情绪 | 能量 | 设计意图 |
|---|---|---|---|---|---|---|
| Intro | 0 | 15 | 0 | 神秘 | 低 | 单线、留白、氛围 |
| Verse | 15 | 45 | 32 | 克制 | 中 | 中密度、对称移动 |
| Pre-Chorus | 45 | 58 | 96 | 蓄力 | 中高 | 密度渐增、线上移 |
| Chorus | 58 | 90 | 124 | 爆发 | 高 | 高密度、多线、特效 |
| Bridge | 90 | 110 | 192 | 抽离 | 低 | 静音/极简/反差 |
| Final Chorus | 110 | 150 | 236 | 顶点 | 最高 | 全舞台、特写 |
| Outro | 150 | 161 | 320 | 收束 | 降 | 单线淡出 |

> 这张表就是整张谱的"剧本"。没有它，不要开始写。

### Step 5 · 特征 → 谱面映射

| 音频特征 | 映射到 | 具体做法 |
|---|---|---|
| 强拍 / 底鼓 | Tap + 判定线冲击 | 每拍 1 个 Tap，同时 `moveY` 下沉 10px 回弹 |
| 军鼓 / 拍手 | Flick 或第二层 Tap | 放在反拍，位置左右交替 |
| 踩镲 8/16 分 | Drag 流 | 低 `alpha`、小 `size`，做装饰 |
| 人声长音 | Hold | 长度 = 人声持续时长 |
| 人声短句 | Tap 连打 | 跟随音节，不要每个字都放 |
| 贝斯线条 | 判定线左右移动 | `moveX` 用低频节奏 |
| 合成器铺底 | 纹理线/淡入 | `alphaEvents` 缓慢起伏 |
| 能量峰值 | 舞台全开 | 多线 + 特效 + 高速 |
| 静音段 | **零音符纯演出** | 只用线动画，不给 note（高级技巧） |
| 频谱亮度高 | Flick/Drag 增多 | 高频碎点 |
| 段落切换 | 特效转场 | glitch / shockwave / 线重组 |

---

## 4. 关键技术细节

### 4.1 onset 检测

```python
import librosa, numpy as np

y, sr = librosa.load("song.mp3", sr=22050, mono=True)
onset_env = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, backtrack=True, units="time")
```

- `backtrack=True`：把 onset 回退到能量上升起点，**更贴合听觉**。
- `aggregate=np.median`：比默认更稳。
- 高精度可用 `superflux`：

```python
onset_env = librosa.onset.onset_strength_multi(y=y, sr=sr, channels=[0, -1], lag=2, max_size=3)
```

### 4.2 鼓点专用检测

```python
y_h, y_p = librosa.effects.hpss(y)
drum_onset = librosa.onset.onset_detect(y=y_p, sr=sr, backtrack=True, units="time")
```

`hpss` 把打击乐分离出来，鼓点更干净。要更准就上 `demucs` 分轨。

### 4.3 结构分析（自相似矩阵）

```python
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
rec = librosa.segment.recurrence_matrix(chroma, mode="affinity", sym=True)
boundaries = librosa.segment.agglomerative(chroma, k=8)
```

### 4.4 人声区段

没有 demucs 时，用"中频能量 + 谐波比例"近似：

```python
centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
rms = librosa.feature.rms(y=y)[0]
# 人声通常 centroid 在 1k~4kHz，rms 中高
```

有 demucs 时直接取 `vocals` 轨的能量包络，准确得多。

```bash
pip install --break-system-packages demucs
demucs --two-stems=vocals song.mp3 -o stems/
```

---

## 5. 歌词与情感（决定"灵魂"的部分）

> 节奏决定"什么时候打"，歌词与情感决定"为什么这样打"。
> 只做节奏，谱面是节拍器；做了歌词与情感，谱面才是叙事。

### 5.1 歌词从哪来

按可靠性排序：

| 来源 | 精度 | 做法 |
|---|---|---|
| 用户提供文本 | 语义 100%，时间 0% | 需要自己对齐 |
| LRC / SRT 文件 | 时间准，逐句 | 直接解析时间戳 |
| 本地 ASR（faster-whisper） | 时间准，逐词 | 拿 `word_timestamps` 做逐字对齐 |
| 纯人声区段推断 | 只有"有人在唱" | 只能定 Hold，不能定字 |

```bash
pip install --break-system-packages faster-whisper
python3 - <<'PY'
from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, info = m.transcribe("song.mp3", word_timestamps=True, language="zh")
for s in segs:
    print(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text.strip()}")
    for w in s.words:
        print(f"    {w.start:6.2f} {w.word}")
PY
```

> ASR 会写错字，但**时间戳是对的**。用 ASR 定时间，用人工/用户提供的文本定内容。
> 没有人声（纯音乐）就跳过本节，把情感分析做在配器上。

### 5.2 把歌词时间换成 beat

歌词时间戳是"秒"，谱面是"beat"。别手算，用工具：

```bash
# 有谱面时：自动读取 BPMList（支持变速）和 offset
python3 tools/lyrics_align.py lyrics.lrc --chart my-chart/chart.json -o lyrics.json

# 还没写谱时：先按固定 BPM 估
python3 tools/lyrics_align.py lyrics.lrc --bpm 140 --offset 0

# SRT 也支持
python3 tools/lyrics_align.py subs.srt --bpm 140
```

输出：

```
  #      time      beat  chars  notes  text
  1     18.40     42.93      8      3  窗外的雨 停在半空
  2     23.90     55.77      8      3  我还在等一句回答
  3     29.20     68.13      6      2  可你 早已 走远
```

`notes` 是"2~3 个字取一个落点"的经验值，直接当作这一句该放几个 note 的上限参考
（`--chars-per-note` 可调，默认 3）。

> beat 是小数没关系，落点要吸附到网格：写 note 时用 `bt()`，
> 它会自动吸附到常用音乐网格（1/2、1/3、1/4、1/6、1/8、1/12、1/16、1/24、1/32…）。
> 例如 `bt(42.93)` → `[42, 15, 16]`（1/16 网格），`bt(68.13)` → `[68, 1, 8]`。

手算公式（需要微调时用）：

```python
beat = (t - offset) * bpm / 60
```

**两个必须注意的偏移**：

1. 人声通常比鼓点**早 10–40ms**（尤其是咬字）。对齐以人声起始为准。
2. 玩家需要**先看到再听到**。所以落字的那一个 note，建议比歌词起始**晚 1/16 拍**（约 30–60ms），手感反而更"准"。

> 宁可让 note 晚一点点，也不要让玩家觉得"我打早了"。

### 5.3 逐句分析卡

对每一句歌词填一行（这是后面写谱的直接依据）：

| # | 时间 | 拍 | 原句 | 字数 | 关键词 | 演唱方式 | 情绪 |
|---|---|---|---|---|---|---|---|
| 1 | 0:18.4 | 43 | 窗外的雨 停在半空 | 9 | 雨 / 停 | 气声 | 悬停 |
| 2 | 0:23.9 | 56 | 我还在等一句回答 | 8 | 等 / 回答 | 真声渐强 | 期待 |
| 3 | 0:29.2 | 68 | 可你 早已 走远 | 6 | 走远 | 断句 + 停顿 | 失落 |

**演唱方式**这一列最容易被忽略，但它直接决定 note 类型：

- 气声 → 小 Drag、低 alpha
- 真声长音 → Hold
- 断句 / 顿音 → 短 Tap，句间留空
- 喊 / 嘶吼 → 大 Tap + 全屏冲击
- 念白 / rap → 密集小 Tap 或 Drag 流

### 5.4 情感三维打分

给每个段落打三个 0~1 的分值，写进段落表：

| 维度 | 0 | 1 | 判断依据 |
|---|---|---|---|
| **张力 tension** | 松弛、平稳 | 紧绷、即将爆发 | 和声紧张度、鼓点密度、旋律上行 |
| **明亮 brightness** | 暗、闷、低频 | 亮、锐、高频 | 频谱亮度、大调/小调、音色 |
| **密度 density** | 稀疏、留白 | 满、层次多 | 编曲层数、onset 数 |

> 三个值是**给视觉用的**，不是给 note 用的。它们的组合直接映射到舞台策略（见 5.6）。

### 5.5 歌词特征 → 谱面语言

| 歌词/演唱特征 | 谱面表达 | 具体做法 |
|---|---|---|
| 短促断句 | Tap 连打 | 2~3 个字取 1 个 Tap，句间留 1/4 拍空 |
| 长音拖腔 | Hold | 长度 = 元音持续时长 |
| 爆破音 / 重音字 | 大 note + 线冲击 | 单独放大 + `moveY` 下沉回弹 |
| 副歌重复句 | **母题图案** | 同一句用同一组坐标与手型（玩家会记住） |
| 念白 / rap | Drag 流 | 小 note、低 alpha、跟随音节 |
| 换气 / 停顿 | **空拍** | note 绝不落在换气处 |
| 意象：坠落 / 雨 | 向下运动 | 线与 note 同向加速下落 |
| 意象：飞 / 挣脱 | 向上 + 散开 | `moveY` 上行 + 线散向四角 |
| 意象：困住 / 循环 | 闭环运动 | 线绕圈或 note 在同一 x 往返 |
| 疑问句 | 上扬弧线 | 线末端轻微抬起 |
| 呐喊 / 高潮句 | 全屏 + 冲击 | 多线炸开 + shockwave |
| 结尾最后一句 | 落地 | 一记重音后立刻静止/淡出 |

**铁律**：不要"每个字一个 note"。中文一句话 8 个字，全打成 Tap 就是"打字机"。
一般 **2~3 个字取 1 个重音**，其余用 Drag 或留白带过。

### 5.6 情绪三维 → 舞台策略

| tension | brightness | density | 舞台策略 |
|---|---|---|---|
| 低 | 低 | 低 | 单线、缓慢漂移、大留白（Intro / 尾奏） |
| 低 | 高 | 中 | 明亮色彩、多条短线点缀、轻快律动 |
| 高 | 低 | 中 | 暗色 + 慢速大幅移动，压抑感（Verse 常用） |
| 高 | 低 | 高 | 密集 note + 线贴身抖动 + vignette（Build） |
| 高 | 高 | 高 | 全屏爆发、多线炸开、特效峰值（Drop） |
| 中 | 高 | 低 | 抒情副歌、长 Hold、线柔和起伏 |

> 这张表是**起点**，不是答案。真正的判断来自你听过之后觉得"这里应该怎样"。

### 5.7 关于字幕

**Phira 没有原生"文字事件"**。想要屏幕上出现歌词，只有三条路：

1. 把文字**预先渲染成图片**，作为贴图/着色器素材（最稳）
2. 写自定义 GLSL 用 uniform 绘制（复杂，效果上限高）
3. 不做文字，用**情绪特效**代替（色偏、明暗、镜头呼吸）——很多高分谱就是这么做的

字幕若要做，原则：

- 只在**句首到句尾**显示，不要全程挂着
- 一行不超过 10 字，超了就拆两句
- 字幕放在画面下 1/5，且**不要压住 note 下落区**
- 歌词密集段（rap）不要做字幕，会糊

### 5.8 情感分析的反例

- ❌ 只看 BPM 不看歌词 → 悲伤的歌做出欢快的谱
- ❌ 把每个字都打成 note → 打字机
- ❌ 副歌重复句用完全不同的图案 → 玩家记不住，也失去了"母题"
- ❌ 全程高强度 → 没有对比，高潮不再是高潮
- ❌ 用"燃""高级"这类词写设计笔记 → 等于没写

---

## 6. 设计笔记模板

```markdown
# 《曲名》设计笔记

## 基本信息
- BPM: 128（检测 127.4，校准后 128）
- offset: 0.09s
- 时长: 3:12

## 段落（含情绪三维）
| 段落 | 时间 | 拍 | 能量 | tension | brightness | density | 设计 |
|---|---|---|---|---|---|---|---|
| Intro | 0:00-0:15 | 0-32 | 低 | 0.2 | 0.3 | 0.2 | ... |

## 歌词（有则填）
| # | 时间 | 拍 | 原句 | 关键词 | 演唱方式 | 落点设计 |
|---|---|---|---|---|---|---|
| 1 | 0:18.4 | 43 | 窗外的雨 停在半空 | 雨 / 停 | 气声 | Drag 横移，低 alpha |

## 舞台设计
- 主线：1 条，承载 80% note
- 表演线：2 条，副歌启用
- 纹理线：1 条，花瓣

## 难度曲线
- Verse NPS 2.5 → Chorus NPS 6.0 → Bridge 1.0 → Final 7.0

## 关键演出节点
- beat 124：判定线炸开 + shockwave
- beat 192（Bridge）：**零音符**，只有线飘移
- beat 236：全舞台

## 母题（重复出现的视觉语言）
- 副歌第一句 → 左右对称的双 Drag 弧线，三次副歌复用
```

---

## 7. 反例（我们真实犯过的错）

- ❌ 只看了 BPM 就开始堆音符 → 段落没层次，全曲一个密度
- ❌ 把 librosa 检测的 112.35 当成绝对真理 → 实际曲子是 112.5，越到后面越偏
- ❌ 没听静音段 → 把最该留白的地方塞满了 Drag
- ❌ 人声段用 Tap 硬砸 → 玩家感觉在"打字"而不是"跟唱"
- ❌ 有歌词却完全不看 → 歌词在哭，谱面在蹦迪
- ❌ 每一句歌词都重新设计一套手型 → 玩家记不住，副歌失去"母题"

**记住：脚本给你数据，音乐给你判断。**
