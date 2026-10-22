# AUTO-MAS · BetterGI 本地远程桌面重构版 (Release 发行版)

本发行版基于 `better-genshin-impact` (BetterGI) 的本地远程桌面（Windows Child Session）功能对 `AUTO-MAS` 进行了深度重构，采用 **Node.js + FastAPI 前后端分离 + C# 原生远程桌面宿主** 架构，仅需运行一次安装脚本即可立即投入使用。

## 1. 快速开始（仅需安装一遍）

1. 解压本发行包到任意目录（建议路径不含特殊符号），并安装 Python 3.12。已有其他版本创建的 `.venv` 时，请先将它移走，再运行安装程序。
2. 双击运行 **`Install-AUTO-MAS.bat`**（会自动请求管理员权限完成一次性配置）：
   - 使用 Windows 10/11 系统自带的 `.NET Framework` 编译器 (`csc.exe`) 自动编译：
     - `res/ChildSessionHost/AutoMas.ChildSessionHost.exe`（复刻 BetterGI 桌面分身 UI，默认系统托盘化静默运行）
     - `AUTO-MAS.exe`（原生无黑框系统托盘启动器）
   - 自动检测并配置 Python 虚拟环境与依赖。
   - 初始化默认配置 `config/Config.json`（默认启用本地远程桌面且默认隐藏到系统托盘运行，避免打扰主桌面）。
   - 在桌面生成两个快捷方式：**`AUTO-MAS 控制台`** 与 **`AUTO-MAS 静默后台运行`**。

## 2. 三种运行方式

移动安装目录前，先运行 `uninstall.bat`。脚本会停止此目录启动的服务、移除对应桌面快捷方式，并删除记录旧绝对路径的 `.venv`；配置和用户数据会保留。移动完成后，在新目录运行 `Install-AUTO-MAS.bat` 重建环境和快捷方式。

### 方式一：前后端分离 + Node.js 调用系统浏览器（常规图形控制台）
- 双击桌面 **`AUTO-MAS 控制台`** 快捷方式，或双击 **`Start-AUTO-MAS.bat`**，或运行：
  ```bash
  node frontend/server.js
  ```
- Node.js 前端服务独立监听 `http://127.0.0.1:36162`（并将 `/api/*` 与 WebSocket `/api/core/ws` 反向代理至 Python 后端 `http://127.0.0.1:36163`），自动拉起后端并**调用系统默认浏览器**打开与 Auto-MAS 一致的 Web 控制台。
- 关闭或重启前端服务不会结束后端任务。托盘提供“仅退出前端”“暂停后端服务（停止队列）”“完全退出”：暂停项停止当前全部队列并保留后端与定时调度；完全退出等待后端清理后再关闭前端和托盘。仅退出前端后，可通过托盘重新打开浏览器控制台。
- 本地远程桌面宿主 (`AutoMas.ChildSessionHost.exe`) **默认最小化在系统托盘静默运行**，不会在主桌面弹窗或抢占焦点；双击托盘图标或在 Web 控制台点击「显示 BGI 远程桌面窗口」即可随时查看与 BetterGI 远程桌面一致的暗色 Fluent 控制窗口。

### 方式二：通过启动参数直接调用后端无窗口运行（Headless 静默直跑）
- 双击桌面 **`AUTO-MAS 静默后台运行`**，或使用命令行参数直接调用后端，**不弹出任何浏览器或远程桌面窗口**：
  ```bash
  # 启动后端并立即自动运行第一个调度队列（全程无窗口，远程桌面在托盘静默运行）
  Start-Headless.bat --auto-run
  python main.py --headless --run-queue first

  # 启动后端并立即运行指定队列 ID 或脚本 ID
  python main.py --headless --run-queue <QueueUUID>
  python main.py --headless --run-script <ScriptUUID>

  # 仅通过 Node.js 启动前后端服务但不打开浏览器
  node frontend/server.js --no-browser --auto-run
  ```

### 方式三：独立脚本控制器 CLI (`remote_script_controller.py`)
```bash
# 直接在本地远程桌面中通过包装器运行单个外部脚本（无日志模式：上限时间内自行退出即判成功）
python remote_script_controller.py run-script "C:\Scripts\MyTask.exe" --args --daily --hard-timeout 120 --retries 3

# 外部程序申请借用本地远程桌面（队列将在相邻子任务间隔自动释放让渡）
python remote_script_controller.py acquire-desktop --caller "OtherProgram" --wait

# 外部程序停止使用远程桌面后回传释放（恢复 AUTO-MAS 队列运行）
python remote_script_controller.py release-desktop --caller "OtherProgram"

# 命令行触发启停或上/下一个任务
python remote_script_controller.py control toggle
python remote_script_controller.py control prev
python remote_script_controller.py control next
```

## 3. 核心重构与精简要点说明

1. **BetterGI 风格本地远程桌面（默认托盘化运行）**：
   - 完整复用 BetterGI `ChildSession` 核心实现（`WTSEnableChildSessions` + `MsRdpClient10` ActiveX `ConnectToChildSession` + `Schedule.Service` `TASK_RUN_USE_SESSION_ID`）。
   - 远程桌面 UI 复刻 BetterGI `ChildSessionWindow.xaml`（顶部暗色工具栏：状态指示灯、启动程序、托盘隐藏、发送 `Win+Tab` 切换窗口、观看模式/普通鼠标切换、控制中心下拉菜单、静音、置顶，以及未连接/让渡时的居中诊断卡片）。
   - 默认以系统托盘模式（离屏保活 ActiveX 句柄）启动，完全避免干扰主桌面。
2. **外部程序借用与子任务间隔让渡接口**：
   - 队列在相邻两个子任务之间自动调用 `ChildSessionManager.wait_if_external_requested()`。
   - 外部程序调用 `POST /api/child-session/acquire` 时，队列在当前子任务结束后暂停并释放 RDP 预览连接，待外部程序调用 `POST /api/child-session/release` 回传后自动重连并继续下一子任务。
3. **跨会话包装器 (`child_session_wrapper.py`)**：
   - 在 Child Session 内拉起包装器进程，实时将目标脚本的 PID、运行状态与退出码 (`returncode`) 同步回主进程。
4. **双模超时与无日志/有日志判定**：
   - **总上限时间 (`HardTimeLimit`)**：从任务开始到结束（包含所有重试）的总时间上限。
   - **无日志模式（日志路径为空）**：日志未刷新超时 (`RunTimeLimit`) 自动失效，只要脚本在总上限时间内自行退出（不限返回码）即视为成功；超过总上限时间视为失败。
   - **有日志模式（填写了日志路径）**：保留原 Auto-MAS 日志监控逻辑（命中 `SuccessLog` 判成功；命中 `ErrorLog` 或日志未刷新超过 `RunTimeLimit` 或超过 `HardTimeLimit` 判失败；未配 `SuccessLog` 则进程正常退出判成功）。
   - **强制清理**：任务结束、中止或超时时，直接调用 **`taskkill /F /T` 连续强杀 3 遍**。
   - **移除配置回写**：不再修改或回写外部脚本的本地配置文件，纯粹通过外部程序自身的启动参数 (`Arguments`) 控制启停。
5. **系统全局热键**：
   - 默认支持 `Ctrl+Alt+S`（启停切换）、`Ctrl+Alt+Left`（上一个任务）、`Ctrl+Alt+Right`（下一个任务），可在 Web 控制台「全局设置」中自定义。
