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

## 6. 本地预览器的定位与已知修正

`tools/preview_render.py` 是"结构与构图"工具，不是渲染器。已修正一处关键语义：

- **旧行为**：note alpha 乘上了判定线 alpha → 透明线上的音符在预览里假性消失。
- **现行为**：note alpha 独立（与 Phira 一致），透明线上的音符照常显示、照常判定。

仍然不覆盖：

- 自定义 note 皮肤、打击特效、Hold 材质；
- 真实判定窗口与手感；
- shader / 混合模式 / 后处理；
- 音频同步（预览按静音时间轴）。

> 因此：**结构用预览，观感与手感用真机。**
