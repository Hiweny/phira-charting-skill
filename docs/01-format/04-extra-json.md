# 04 · extra.json（特效 / 着色器）

`extra.json` 可选。没有它谱面照样能玩。有它，可以做出"演唱会"级别的视觉。

官方文档：<https://teamflos.github.io/phira-docs/chart-standard/extra/effect/>

## 1. 顶层结构

```json
{
  "bpm": [
    { "time": [0, 0, 1], "bpm": 112.35 }
  ],
  "effects": [ { ...Effect... } ]
}
```

> `bpm` 字段在 extra.json 里**不是必需**，但建议与 `chart.json` 的 BPMList 保持一致。
> 若不一致，不同渲染器（Phira / prpr）表现可能不同。

## 2. Effect

```json
{
  "shader": "chromatic",
  "start": [2, 0, 1],
  "end": [4, 0, 1],
  "global": false,
  "vars": {
    "power": [
      {
        "startTime": [2, 0, 1],
        "endTime": [4, 0, 1],
        "easingType": 2,
        "start": 0.0,
        "end": 0.1
      }
    ],
    "sampleCount": 5
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `shader` | string | ✅ | 内置着色器名，或自定义着色器文件名 |
| `start` | **beat 三元组** | ✅ | 开始时间。**不是数字！** |
| `end` | **beat 三元组** | ✅ | 结束时间 |
| `global` | bool | ❌ | 是否影响 UI（连击数/暂停键），默认 `false` |
| `vars` | object | ❌ | 参数名 → 动画变量 |

> 我们的实战谱面里还出现过 `"line": -1` 与 `"order": 0`。官方文档未列出，Phira 会容忍；
> **照官方文档写最安全**，不要依赖未文档化字段。

## 3. 动画变量（vars 的值）

两种写法：

### 3.1 常量

```json
"sampleCount": 5
```

### 3.2 动画（数组）

```json
"power": [
  { "startTime": [2,0,1], "endTime": [4,0,1], "easingType": 2, "start": 0.0, "end": 0.1 }
]
```

- `startTime` / `endTime`：beat 三元组（整数）
- `start` / `end`：数值，或二维数组（如 `pos: [[0.5, 0.5], [0.5, 0.5]]`）
- `easingType`：同 chart.json 缓动序号

**关键技巧**：想做一个"脉冲"（如底鼓冲击波），用两个事件拼出来：

```json
"power": [
  { "startTime":[21,0,1], "endTime":[21,0,2], "easingType":18, "start":0.0, "end":0.5 },
  { "startTime":[21,0,2], "endTime":[21,1,1], "easingType":18, "start":0.5, "end":0.0 }
]
```

第一个事件把参数推到峰值，第二个立刻回落。这就是"卡点冲击波"。

## 4. 常用内置着色器

| shader | 主要参数 | 视觉 | 适合段落 |
|---|---|---|---|
| `vignette` | `extend`, `radius` | 四角暗角 | 全曲打底，Drop 加深 |
| `chromatic` | `power`, `sampleCount` | RGB 色差 | build-up / 电子段落 |
| `shockwave` | `power`, `pos` | 中心冲击波 | 重鼓点、Drop 第一拍 |
| `glitch` | `power` | 画面撕裂 | 故障风、转场 |
| `grayscale` | `factor` | 灰度化 | 情绪低谷、回忆段 |
| `fisheye` | `power`, `radius` | 鱼眼 | 眩晕、失重 |
| `liquid` | `speed`, `scale` | 液体扭曲 | 梦幻、迷幻 |
| `snow` | `power`, `speed` | 雪花 | 冬日、抒情 |
| `flare` | `power` | 眩光 | 高潮爆点 |
| `camera` | 位移/缩放参数 | 镜头推拉 | 开场、收尾 |

> 内置着色器的完整参数表以官方 **builtin** 页为准：
> <https://teamflos.github.io/phira-docs/chart-standard/extra/effect/builtin/>
> 自定义 GLSL：<https://teamflos.github.io/phira-docs/chart-standard/extra/effect/custom-shader.html>

## 5. 设计原则（踩坑总结）

1. **一个段落最多 1~2 个特效**。全曲同时挂 5 个 = 画面糊成一锅粥。
2. **特效要有动机**：底鼓 → shockwave；转场 → glitch；副歌 → chromatic 渐强；结束 → vignette 加深。
3. **默认值必须是"无效果"**：让参数大部分时间是 0，只在需要的几拍推到峰值。
4. **`global: true` 会作用于 UI**，可能让连击数字看不清。需要干净 UI 时用 `false`。
5. **不要在 note 密集段叠强 glitch/chromatic**，玩家会看不清判定。
6. **先做判定线表演，再考虑特效**。3 张精品谱里有两张几乎不用 extra.json。

## 6. 完整可运行示例

用 `chart_builder` 生成一个合法的 extra.json：

```python
from chart_builder import Chart, bt

c = Chart(bpm=140.0, song="song.mp3", name="曲名", charter="谱师名", level="IN 14", difficulty=14.0)
c.add_effect("shockwave", bt(60, 0), bt(61, 0), vars={"power": 0.8})
c.save_extra("extra.json")
```

> `save_extra()` 在没有任何 effect 时**不会创建文件**（返回 `None`）——这是正确的：
> 不需要特效的谱就不该带 extra.json。

更复杂的五段式配置见 [`docs/03-workflow/04-effects.md`](../03-workflow/04-effects.md) 的分层表
（Stage Vignette / Danger Chromatic / Beat Shockwave / Peak Shockwave / Bridge Glitch）。
