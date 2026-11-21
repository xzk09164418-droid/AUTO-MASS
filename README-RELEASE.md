# Qt 与本地远程桌面

当前只提供 Qt 图形界面，Web/Node 前端已移除；后端 HTTP 与 WebSocket 接口保持兼容。

## 安装与启动

使用 Python 3.12 环境运行 `scripts/install_release.ps1`，安装依赖、编译 Qt 启动器和原生桌面分身宿主。
日常双击 `AUTO-MAS.exe` 或 `Start-AUTO-MAS.bat`。源码启动方法见 [README.md](README.md)。

```powershell
.venv/Scripts/python.exe qt/main.py
.venv/Scripts/python.exe qt/main.py --headless
.venv/Scripts/python.exe qt/main.py --headless --run-queue first
.venv/Scripts/python.exe qt/main.py --headless --run-script <ScriptUUID>
```

`--headless`、`--no-window`、兼容参数 `--no-browser` 只启动托盘和后端。重复启动会唤起同一实例，任务参数转交已有实例。

## 两组托盘

主托盘提供打开 Qt、显示/隐藏远程桌面、任务启停、上/下任务、仅退出前端、停止队列、强制重启和完全退出。
关闭 Qt 窗口只隐藏界面；仅退出前端释放界面，托盘仍能重建窗口，后端继续工作。
停止队列仅调用后端停止全部队列；完全退出请求后端正常清理，确认服务退出后再注销已启用的子会话并移除托盘。超时和失败保留托盘并显示错误。
强制重启需确认，沿用已有身份核验和状态备份助手，完成后启动 Qt，不恢复旧队列。

桌面分身宿主继续提供显示窗口、观看模式、在分身中启动程序、重连、借出画面、注销和退出宿主。
它独立于 Qt 窗口，Qt 通过原有后端接口控制同一宿主；后台任务执行、借用规则和日志判定未改动。

## 数据与验证

原有 config/data/history 保留。Qt 使用同一实例身份、后端端口和配置；旧 Web 快速启动选择仅作为迁移读取来源。
隔离验证覆盖页面读取、设置读写、WebSocket 接管、托盘生命周期和完整后端退出；不代表已验证所有真实游戏与 RDP 场景。
