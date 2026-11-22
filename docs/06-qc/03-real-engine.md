# 03 · 真实引擎验证（Real-Engine Validation）

> 本地 `preview_render.py` 只能验证"结构与大致构图"，验证不了：
> note 皮肤、打击特效、Hold 身体、真实判定、掉帧、线的混合模式。
> 所以交付前应该至少过一次 **Phira 本体**。
>
> 本页记录：怎么下载、怎么在无显示器环境跑、以及我们踩到的坑。

---

## 1. 下载 Phira 本体

- Releases：<https://github.com/TeamFlos/phira/releases>
- 本环境对应包（Linux x86_64，v0.8.3）：
  `Phira-linux-x86_64-v0.8.3.tar.gz`

```bash
curl -L -o /tmp/Phira.tar.gz \
  https://github.com/TeamFlos/phira/releases/download/v0.8.3/Phira-linux-x86_64-v0.8.3.tar.gz
mkdir -p /opt/phira && tar -xzf /tmp/Phira.tar.gz -C /opt/phira
./phira-main
```

Windows / macOS / Android 直接下对应包即可；谱面格式完全一致。

---

## 2. 无显示器环境（CI / 服务器）

Phira 是 GUI（miniquad + OpenGL），没有 GPU 时可以用 **Xvfb + Mesa 软件渲染**：

```bash
apt-get update
apt-get install -y xvfb mesa-vulkan-drivers libxkbcommon-x11-0 \
  libxrandr2 libxi6 libxcursor1 libxinerama1 libasound2t64

Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
cd /opt/phira
DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe ./phira-main
```

截图：

```bash
DISPLAY=:99 ffmpeg -f x11grab -video_size 1920x1080 -i :99 -frames:v 1 shot.png
```

日志里如果出现：

```text
Failed to initialize audio backend, running in silent mode
```

属于正常（容器没有声卡），不影响画面。

---

## 3. 把谱面放进 Phira

Phira 的数据目录是**可执行文件旁边的 `data/`**：

```text
data/
├── charts/
│   ├── custom/        # 本地自制谱（推荐放这里）
│   └── download/      # 在线下载
├── collections/
└── respack/           # 皮肤/资源包
```

```bash
mkdir -p /opt/phira/data/charts/custom/shiluozhiyu
cp /workspace/ref/shiluozhiyu/{info.yml,38960633.json,38960633.mp3,illustration.png} \
   /opt/phira/data/charts/custom/shiluozhiyu/
```

也可以启动后在游戏内"导入谱面"选择 zip。
谱面 zip 结构参考 `tools/package_chart.sh`。

---

## 4. 已知坑：软件渲染下黑屏

本环境（v0.8.3 + Xvfb + llvmpipe）实测：

```text
Audio backend: ... silent mode
ERROR phira{err=add renderer ... buffer is full}: global error
```

窗口能创建，但画面全黑，进程随后退出。
`MESA_GL_VERSION_OVERRIDE`、`RUST_LOG=trace`、换分辨率/换 GL 驱动都没有解决。
判断是 miniquad/渲染后端在软件 GL 下的限制，不是谱面问题。

**结论**：

- 有条件时，在**有 GPU 的桌面/手机**上跑 Phira 验证；
- 无 GPU 的 CI 环境，用本地 `preview_render.py` 做结构/构图回归，
  把"皮肤、打击特效、手感"留到真机；
- 也可以让主人在自己的设备上导入 zip 做最终确认
  （交付时附上"请看这三段：0:15 / 1:20 / 2:45"）。

> 不要因为本地预览"看起来还行"就跳过真机；
> 也不要因为 CI 跑不起 Phira 就放弃验证——两者是互补的。

---

## 5. 真机验收清单

| 项目 | 看什么 | 不合格的表现 |
|---|---|---|
| 皮肤 | note 类型是否一眼可分 | Tap/Drag 糊成一片 |
| 打击特效 | 是否遮住后续 note | 高密度段看不清落点 |
| Hold | 身体是否过粗/过亮 | 像第二条判定线 |
| 判定线 | 与背景是否打架 | 白线压过插画、读谱困难 |
| 透明度 | 断线段音符是否仍可见 | 音符跟着线一起消失 |
| 帧率 | 高潮段是否掉帧 | 线数量 > 20、事件过密 |
| offset | 第一下是否对得上 | 整体偏早/偏晚 |
| 手感 | 是否需要"背谱" | 换线/大旋转落在密集段 |

记录方式：每个问题截一张图 + 记时间点，回到工程里修，不要凭记忆。

---

## 6. 本地预览器的定位与已对齐项

`tools/preview_render.py` 是"结构 / 构图 / 运动"工具，不是像素级渲染器。
2026-11-22 已按 prpr 源码做了一轮语义对齐：

### 已对齐

- **note alpha 独立于线 alpha**（透明线上的音符照常显示、照常判定）；
- **note 位置公式**：`line_pos + R(line_rot) · (positionX, -height)`，
  不再错误地把 `positionX` 再减一次线坐标（发射器线/贴图线的位置现在正确）；
- **线长**：按 `info.yml lineLength`（默认 6）画 `2 × lineLength` 世界单位，
  即贯穿屏幕的超长线；
- **note 尺寸**：按 prpr `NOTE_WIDTH_RATIO_BASE`（0.2635 世界单位全宽）绘制，
  宽条 Tap / 细黄 Drag / 红 Flick / 白 Hold；
- **默认皮肤色**：Tap `(75,160,229)`、Hold 近白、Drag `(228,196,66)`、Flick `(213,30,30)`；
- **判定线默认色**：`color_perfect = 0xe1ffec9f`（暖白），并支持 `colorEvents`；
- **`above=2` 不再反向**（Phira 的 RPE 解析里它不影响下落方向）；
- **`alpha/size/pos/yControl` 改为按 note 行进距离求值**，用于距离雾/透视缩放/扇阵收放；
- **`visibleTime`**：小于 999999 时按提前秒数淡入；
- **10 个内置 shader**（grayscale / chromatic / glitch / vignette / circleBlur /
  shockwave / radialBlur / pixel / noise / fisheye）有近似实现；
- **贴图线 / GIF / 文字线 / 画笔线**；
- **`videos`**：用 `ffmpeg` 按时间抽帧合成，支持 `cropCenter/inside/fit` 与 `attach`（近似）。

### 仍是近似

- 真实 shader 的逐像素公式、采样数、混合模式（只用 numpy/PIL 近似）；
- 皮肤贴图、打击特效、Hold 中间材质；
- 真实判定窗口、手感、音频同步；
- 线/音符的排序细节（`isCover`、`draw_below`）与粒子。
- `attach` 视频的透视变换（简化为"旋转后的全屏图"）。

> 因此：**结构、构图、节奏、颜色层次用预览；皮肤、打击特效、手感、掉帧用真机。**
> 预览器抓不出的问题，必须在交付说明里写清楚"请重点看这几段"。

---

## 7. 特效/媒体验收（新增）

| 项目 | 怎么验 | 不合格 |
|---|---|---|
| shader 时间 | 联系表抽 shader 起止帧 | 切点不在乐句、闪频乱 |
| shader 叠加 | 抽高潮帧 | 叠 3 个以上、画面糊 |
| 无 shader 降级 | 临时删 effects 再渲染 | 画面无法读谱 |
| 贴图线 | 看尺寸/层级/遮挡 | 图过大、盖住 note |
| 文字线 | 看字号/停留时间 | 字太小、半天不消失 |
| 视频 | 看弱谱区是否被抢 | 爆发段还开视频 |
| attach 视频 | 看是否跟线旋转 | 视频飞出屏幕、比例失真 |

> 最后仍建议由主人在有 GPU 的设备上导入 zip 看一遍；
> 附上 2–3 个时间点（如 `0:13 / 1:56 / 3:26`）比"整体感觉"有效得多。
