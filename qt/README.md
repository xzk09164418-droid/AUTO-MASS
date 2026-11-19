# AUTO-MAS Qt 客户端

PySide6 + QML 重写的桌面前端，按「莱茵生命」PV 视觉组织。它只替代 Vue 前端：通过现有 HTTP 接口与 Python 后端通信，后端代码不改。

## 运行

```bash
.venv/Scripts/python.exe -m pip install -r qt/requirements.txt
.venv/Scripts/python.exe qt/main.py
```

| 参数 | 作用 |
| --- | --- |
| `--skip-boot` | 跳过启动动画 |
| `--no-backend` | 不探测、不拉起后端，只看界面 |
| `--section N` | 启动后直接进入第 N 个一级界面 |
| `--theme light/dark/system` | 主题，默认跟随系统 |
| `--capture out.png --after 3000` | 定时截图后退出（自检用） |

## 结构

| 文件 | 内容 |
| --- | --- |
| `main.py` | 入口，注入后端监督器 |
| `automas_qt/backend.py` | 探测 `/api/core/health`、校验 instanceId，必要时拉起 `main.py`，收集启动日志 |
| `qml/Theme.qml` | PV 色板（浅色/深色） |
| `qml/BootSequence.qml` + `Tracks.js` | 启动动画，复刻 PV 0–27 秒段落；画面是 25fps 帧号的纯函数，便于逐帧校准 |
| `qml/DepartmentHub.qml` + `Departments.js` | 一级界面 01–10 部门索引，入场编排参考 PV 1:00–1:12 |
| `qml/SectionHost.qml` | 方块原地展开成二级界面（目前为占位） |
| `qml/BackendPanel.qml` | 后端启动中 / 失败面板 |
| `qml/Ledger.qml` | 底部刻度栏 |

## 一级界面

01 主页 · 02 托管管理 · 03 模拟器管理 · 04 调度队列 · 05 调度中心 · 06 本地控制 · 07 签到（含游戏社区） · 08 历史记录 · 09 游戏活动 · 10 设置

计划管理、资源商店不再提供。
