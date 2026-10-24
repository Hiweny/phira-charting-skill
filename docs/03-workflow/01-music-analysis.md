# 01 · 音乐分析流程

> **铁律：拿到一首曲子，先分析音乐，再分析谱面，最后才写谱。**
> 顺序反了，做出来的就是"音符堆积"，不是谱面。

---

## 1. 目标产出

分析完必须能回答这 8 个问题，并写成"设计笔记"：

1. BPM 是多少？有没有变速？
2. 第一拍落在第几秒（offset）？
3. 段落结构：Intro / Verse / Pre-Chorus / Chorus / Bridge / Solo / Outro 各从第几秒到第几秒？
4. 每段的能量（RMS）与频谱亮度（centroid）如何变化？
5. 鼓点密度最高的是哪几段（onset 数/秒）？
6. 人声活跃区段在哪（决定 Hold 的位置）？
7. 全曲的"情绪峰值"在哪一拍？
8. 有没有静音/留白段（这是做"无声演出"的黄金位置）？

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

## 5. 设计笔记模板

```markdown
# 《曲名》设计笔记

## 基本信息
- BPM: 128（检测 127.4，校准后 128）
- offset: 0.09s
- 时长: 3:12

## 段落
| 段落 | 时间 | 拍 | 能量 | 设计 |
|---|---|---|---|---|
| Intro | 0:00-0:15 | 0-32 | 低 | ... |

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
```

---

## 6. 反例（我们真实犯过的错）

- ❌ 只看了 BPM 就开始堆音符 → 段落没层次，全曲一个密度
- ❌ 把 librosa 检测的 112.35 当成绝对真理 → 实际曲子是 112.5，越到后面越偏
- ❌ 没听静音段 → 把最该留白的地方塞满了 Drag
- ❌ 人声段用 Tap 硬砸 → 玩家感觉在"打字"而不是"跟唱"

**记住：脚本给你数据，音乐给你判断。**
