# 04 · 特效设计

格式细节见 [`docs/01-format/04-extra-json.md`](../01-format/04-extra-json.md)。本文只讲**怎么用得好**。

---

## 1. 先问一句：真的需要特效吗？

三张精品谱的答案：

| 谱面 | extra.json 特效 | 结论 |
|---|---|---|
| 声嘶力竭 | 6 个内置着色器 | 需要，配合 69 线 |
| Night Drawmers | 4 个**自定义 GLSL** | 需要，是核心叙事 |
| 探窗 | **0 个** | 不需要，判定线动画已经足够 |

> **特效是调味料，不是主菜。** 判定线编排不到位，加特效只会更乱。

---

## 2. 特效的三种动机

| 动机 | 特效 | 时机 |
|---|---|---|
| 强化节奏 | shockwave / flare | 底鼓、Drop 第一拍 |
| 转场 | glitch / chromatic | 段落切换 |
| 氛围 | vignette / grayscale / snow / liquid | 全曲打底、抒情段 |

没有动机的特效 = 噪音。

---

## 3. 参数设计：默认 0，峰值短暂

```json
"power": [
  { "startTime":[60,0,1], "endTime":[60,0,2], "easingType":18, "start":0.0, "end":0.8 },
  { "startTime":[60,0,2], "endTime":[60,1,1], "easingType":18, "start":0.8, "end":0.0 }
]
```

- 冲击波只持续 1 拍
- 峰值 0.8（不要 1.0，会全白）
- `easingType: 18`（easeInOutQuint 类）让起落更"弹"

---

## 4. 分层配置（推荐）

| 层 | 特效 | 覆盖 | 参数 |
|---|---|---|---|
| 底噪层 | vignette | 全曲 | extend 0.2~0.5 缓慢起伏 |
| 情绪层 | chromatic / grayscale | 段落 | 随能量强弱 |
| 爆点层 | shockwave / flare | 单拍 | 只在重音 |
| 转场层 | glitch | 2~4 拍 | 段落交界 |

**同时最多 3 层**。

---

## 5. 自定义 GLSL（进阶）

Night Drawmers 用了 4 个自定义着色器：摄像机、雪花、炫光、液体。

流程：
1. 写 `xxx.glsl`（fragment shader，遵循 Phira 着色器规范）
2. 放进谱面 zip 根目录
3. `extra.json` 里 `"shader": "xxx.glsl"`
4. `vars` 可以传 uniform

规范：<https://teamflos.github.io/phira-docs/chart-standard/extra/effect/custom-shader.html>

> 提示：自定义 shader 是"叙事工具"。先想清楚"我要表达什么画面"，再写代码。

---

## 6. 性能与兼容

- 同时生效的特效越多，低端机越卡。
- 移动端尤其注意：`chromatic` 的 `sampleCount`、`shockwave` 的分辨率。
- 不同渲染器（Phira / prpr / phira-render）对自定义 shader 支持不完全一致，**上线前用 Phira 本体验证**。

---

## 7. 验收

- [ ] 每个特效都能说出"为什么在这里"
- [ ] 关掉特效后谱面依然成立
- [ ] note 密集段没有强干扰特效
- [ ] UI 在特效下仍然可读（`global` 检查）
- [ ] 低端设备不卡
