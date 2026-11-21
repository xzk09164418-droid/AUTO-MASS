# Qt 客户端测试工具

## 性能（`perf_qt.py`）

启动 Qt 客户端（不连后端），跑完启动动画并停在一级索引，采样：

- CPU：客户端进程的单核百分比（psutil，每秒一次）
- GPU：`\GPU Engine(pid_*engtype_3D)\Utilization Percentage`（typeperf）
- 呈现：PresentMon 记录 PresentMode / SyncInterval / 帧间隔，用来确认垂直同步与撕裂

PresentMon 需自行从官方发布页下载（GameTechDev/PresentMon，v2.6.0 x64 控制台版），放到 `<tools_dir>`：

```bash
.venv/Scripts/python.exe qt/tools/perf_qt.py . <tools_dir> <out_dir>
```

## 分辨率与缩放

离屏渲染 + `QT_SCALE_FACTOR` 模拟 200% 缩放，`--size` 给逻辑尺寸：

```bash
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR="C:\Windows\Fonts" QT_SCALE_FACTOR=2 .venv/Scripts/python.exe qt/main.py --no-backend --skip-boot --size 960x540 --capture out.png --after 4500
```

覆盖组合：1080p / 1440p / 4K × 100% / 200%（逻辑尺寸 1920×1080、960×540、2560×1440、1280×720、3840×2160、1920×1080）。
