# 03 · 社区取样：从别人的谱面里偷师

> 只看代码学不会演出，只看视频学不会结构。
> **正确顺序是：先看画面 → 再看代码 → 最后对指标。**

Phira 官方社区是公开可搜索的。本技能内置
[`tools/phira_community.py`](../../tools/phira_community.py) 用于检索与下载。

---

## 1. 接口速查

| 用途 | 地址 |
|---|---|
| 谱面列表/搜索 | `https://api.phira.cn/chart?page=1&search=<关键词>&sort=rating&tag=<标签>` |
| 单谱详情 | `https://api.phira.cn/chart/<id>`（返回 JSON，`file` 字段是 zip 直链） |
| 文件托管 | `https://phira.5wyxi.com/files/<uuid>`（下载即 zip） |

返回字段：`id / name / level / difficulty / charter / composer / illustrator /
rating / ratingCount / tags / description / file / illustration / preview`

> 无需登录，属公开只读接口。**请低频访问**（脚本默认每次请求间隔 0.4s），不要批量爬全站。

---

## 2. 命令

```bash
# 搜关键词，按好评度排序
python3 tools/phira_community.py search "探窗" -n 10 --sort rating

# 按标签筛（标签来自谱面自身，如 regular / 明日方舟）
python3 tools/phira_community.py search "" --tag regular --sort rating

# 看详情（拿到 file 直链与简介）
python3 tools/phira_community.py info 61048

# 下载并解压（得到 chart.json + 音频 + 曲绘 + info.yml）
python3 tools/phira_community.py download 61048 -o samples/tanchuang

# 按评分批量取前 N 张（学习用）
python3 tools/phira_community.py top -n 5 -o samples/
```

下载完立刻跑自检，把画面拉出来：

```bash
bash tools/selfcheck.sh samples/tanchuang samples/tanchuang/_qc
```

---

## 3. 取样策略

不要随手下 50 张。**按"我想学什么"来选**：

| 你想学 | 取样条件 |
|---|---|
| 节奏与判定线基础 | `--sort rating` 前 10 中 **难度 10–13** 的 |
| 高密度演出 | 难度 15–16，且 `notes > 800` |
| 特效叙事 | 详情里带自定义 shader 的（解压后看是否有 `.glsl`） |
| 抒情 / 慢歌 | 时长 > 3 分钟、BPM < 100 |
| 同曲多版本对照 | `search "<曲名>"`，同一首歌不同谱师的版本 |
| 你的目标曲风 | 用曲名/作曲家搜索 |

**一次只精读 1 张，泛读 3–5 张。** 精读一张要 2 小时，泛读一张 15 分钟。

---

## 4. 精读流程（视觉优先）

### Step 1 · 先看画面，不看代码

```bash
python3 tools/preview_render.py samples/tanchuang --contact-sheet tc_sheet.png \
  --times 0,15,30,45,60,75,90,105,120
```

对着联系表回答：

1. 全曲有几种"视觉基调"？分别在哪几段？
2. 判定线在**哪些段落离开过画面中心**？离开多远？
3. 有没有一段是"零音符纯演出"？
4. 高潮段的画面，和安静段的画面，**差异有多大**？
5. 有没有一条反复出现的"视觉母题"（同一种抖动、同一种旋转、同一种散开）？

### Step 2 · 再看结构代码

```bash
python3 tools/preview_render.py samples/tanchuang --stats > st.json
python3 - <<'PY'
import json; d=json.load(open('samples/tanchuang/'+[f for f in __import__('os').listdir('samples/tanchuang') if f.endswith('.json')][0]))
print('线数', len(d['judgeLineList']))
print('BPM', d['BPMList'])
for i,L in enumerate(d['judgeLineList'][:8]):
    print(i, 'group', L.get('Group'), 'notes', len(L.get('notes', [])), 'floor', L.get('zOrder'))
PY
```

只看三件事：**线怎么分组、note 挂在哪条线、事件密度分布**。

### Step 3 · 最后对指标

| 指标 | 这张谱 | 说明 |
|---|---|---|
| `lines` | 32 | 演出复杂度 |
| `avg_nps` / `peak_nps_1s` | 10.02 / 24 | 密度级别 |
| `line_x_cover` | `[-1355, 1355]` | **超出 ±675 是允许的**——线可以飞出屏幕再回来 |
| `x_std` | 286 | 音符横向铺开程度 |
| `hidden_notes` | 200 | 隐藏 note 是高级技巧，不一定是 bug |
| `effects` | — | 特效数量 |

> ⚠️ 这是真实数据（社区评分 0.935 的《folern》）：**顶级谱面的指标经常"违反"本技能的推荐阈值**。
> 阈值是给新手的护栏，不是艺术的上限。你超标时只要能解释"为什么这样更好"，就可以超标。

### Step 4 · 写拆解卡片

每精读一张，写一张卡片存进 `docs/04-reference/`（或你自己的笔记）：

```markdown
## 《曲名》· chart_id

- 难度 / 时长 / BPM：
- 线数 / note 数 / 峰值 NPS：
- **视觉母题**：一句话概括这张谱"长什么样"
- **结构手法**：
  - Intro：
  - 主歌：
  - 副歌：
  - 收尾：
- **可复用的技巧**（3 条以内，要具体到字段）：
- **不打算学的地方**（为什么）：
```

---

## 5. "高级感"到底来自哪

把看过的精品谱归纳下来，反复出现的就这几条：

| 来源 | 具体表现 | 对应字段 |
|---|---|---|
| **反差** | 极静 → 极炸；零音符 → 满屏 | `alphaEvents` 阶跃、密度突变 |
| **克制** | 高潮前留 1 拍空 | 最后一个 note 与爆发点的时间差 |
| **母题** | 同一种运动在多个段落重现 | 复用的 easing + 位移曲线 |
| **空间** | 线真的飞出屏幕再回来 | `moveX` 到 ±1000 以上 |
| **层次** | 前景 note / 中景线 / 背景纹理分离 | `zOrder` + `alpha` |
| **同步** | 每个大动作都踩在重音上 | 事件 startTime 对齐 onset |
| **收束** | 结尾有一个"落地"动作 | 最后一拍的冲击 + 淡出 |
| **不完美** | 手工感（不完全对称、有微小延迟） | 故意的偏移 |

**没有一条是"堆更多特效"。**

---

## 6. 边界与礼貌

- 下载的谱面**只用于本地分析**，不要二次上传、不要改个名字发出去。
- 引用别人的技巧时，在 `info.yml` 的 `description` 里注明灵感来源是加分项。
- 不要把整张谱的 `chart.json` 直接改几个 note 当自己的作品。
- 批量下载请控制频率，别给社区服务器添麻烦。

---

## 7. 常见坑

- ❌ 用 `search` 时关键词为空字符串 + 没有 `--tag` → 返回的是最新而非最好
- ❌ 只看 `--stats` 不看联系表 → 数据漂亮但画面难看
- ❌ 把别人的坐标体系（如 ±908）直接搬进自己的谱 → 你的曲绘构图不同，会撞脸
- ❌ 学"特效数量"而不是"特效动机"
- ❌ 下载目录混在仓库里被提交 → 用 `samples/` 并在 `.gitignore` 里排除
