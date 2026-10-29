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
- 关闭或重启前端服务不会结束后端任务。托盘提供“仅退出前端”“暂停后端服务（停止队列）”“完全退出”：暂停项停止当前全部队列并保留后端与定时调度；完全退出等待后端清理、注销远程桌面子会话后再关闭前端和托盘。仅退出前端后，可通过托盘重新打开浏览器控制台。
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

## 4. 桌面恢复与受保护的实机测试

恢复控制运行在主桌面，任务后端运行在子会话。每个队列项开始前将 MAS 队列位置保存到
`data/desktop_recovery/`，不推测脚本内部断点。恢复时 General 优先使用完整 `Restart`
清单，未填写时使用原启动入口；损坏的进度记录回退到旧记录，两份都不可用时从对应队列开头运行。
队列身份清单或防重复重启标记损坏时保持暂停，不猜测队列或重置重启额度。

连接尝试共三次、间隔五秒；失败后由主桌面注销并重建子会话。重建仍失败时显示六十秒重启提示，
确认立即重启，取消或关闭窗口则保持暂停，超时自动重启。同一未解决故障最多自动重启电脑一次。
普通进度保存失败不阻止升级，但防重复重启标记必须可靠保存，否则无法保证不循环重启。
异常沿用已启用通知渠道；恢复成功不额外发送恢复通知。

日常无人值守恢复在注销和重启前检查 UU 服务正在运行且自动启动，不依赖聊天回复或临时测试看门狗。
该检查不能证明另一设备实际可连接。六十秒重启确认及同一故障最多重启一次的限制仍然有效。

实机测试另须由操作者通过另一设备确认 UU 实际可用，并启用独立 SYSTEM 回退看门狗。
测试启动进程必须设置 `AUTO_MAS_RECOVERY_TEST_ROOT` 为本仓库绝对路径（会传给子会话）；
此模式下缺失、失效或取消看门狗均禁止注销和重启，不能自动降级为日常模式。

在**管理员 PowerShell**中准备测试前备份；此命令不启用倒计时、不修改登录设置：

```powershell
$recoveryRoot = (Get-Location).Path
$recoveryBaseline = git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/rdp-recovery-guard.ps1 -Action Prepare -Root $recoveryRoot -Baseline $recoveryBaseline
```

确认另一设备能够实际通过 UU 控制本机后启用本轮保护：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/rdp-recovery-guard.ps1 -Action Arm -Root $recoveryRoot -UUVerified
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/rdp-recovery-guard.ps1 -Action Status -Root $recoveryRoot
```

必须看到 `ready: true` 才能开始实机测试。三十分钟从 Arm 开始，电脑重启不重置期限。
到期恢复清单内的测试前文件、登录白名单设置和 MAS 自启任务，并只重启一次；不修改 UU 服务、
UU 配置、账号密码或未列入清单的用户文件。备份校验失败时记录 `failed`，不带着未知回退结果重启。
不要在保护期间修改清单内文件或开始另一轮测试。

保持本地账号空密码的自动登录配置也必须在保护有效时执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/rdp-unattended-setup.ps1 -Root $recoveryRoot -Apply
```

该命令验证空密码的本地交互登录，不改账户密码或 NLA；存在已有自动登录密码配置时拒绝覆盖。
配置完成不等于开机验收通过，仍须验证 Windows 自动进入桌面、MAS 自启、子会话建立和队列恢复。

取消本轮测试保护时使用 Prepare/Arm 输出的 `runId`，只有返回 `cancelled` 才算确认取消：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/rdp-recovery-guard.ps1 -Action Cancel -Root $recoveryRoot -RunId '<本轮 runId>'
```

聊天回复取消由当前聊天的监护自动任务转发到上述入口；它依赖 Codex 能继续运行和读取消息。
如果重启后 Codex 尚未启动，须通过 UU 在本机执行 Cancel，不能把“已发送消息”当作本机已收到取消。
六十秒重启弹窗的取消只取消故障升级，不会替代三十分钟测试看门狗的取消。

故障处理后可查看状态，并明确重置一次自动重启额度以请求人工恢复：

```powershell
.venv/Scripts/python.exe scripts/rdp-recovery-state.py status
.venv/Scripts/python.exe scripts/rdp-recovery-state.py resume --acknowledge-fault-resolved
```

外部桌面借用可在请求中登记 `process: {pid, createdAt, sessionId}`，或给
`remote_script_controller.py acquire-desktop` 同时传入 `--process-pid`、`--process-created-at`、
`--process-session-id`。超时只关闭已验证的绑定进程树，先正常关闭窗口再强制结束；UU 组件和 MAS
监督进程不能登记。旧客户端未登记进程时，到期保持暂停并通知，必须明确归还，绝不按进程名猜测后杀进程。
