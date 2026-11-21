# AUTO-MASS

版本 **0.1.0**，基于 AUTO-MAS 的个人派生项目。当前发布基线为本仓库 QT 分支。

## 来源与署名

本项目继承 [AUTO-MAS](https://github.com/AUTO-MAS-Project/AUTO-MAS) 的后端、任务调度与配置管理能力，原作者为 DLmaster361 与 AUTO-MAS Team，其他贡献者见上游项目及文件版权声明。

本次派生版主要提供 General 通用脚本入口、Windows 本地远程桌面与热键/外部占用控制，以及 PySide6/QML 桌面界面。原始项目说明保存在 [README-UPSTREAM.md](README-UPSTREAM.md)。

项目在2026 年 10 月 21 日开始构建，最初为了解决automas原有脚本无法使用本地远程rdp进行后台操作，以及脚本运行的暂停问题（目前automas已有相关方向，详情移步至https://github.com/AUTO-MAS-Project/AUTO-MAS ）

日常运行无需拉取源码，本构建禁用遥测。获取活动信息、社区签到、邮箱控制、发送远程通知和下载可选的增强视觉组件时会使用网络。外部脚本和游戏的联网行为由各自程序决定。
同时，本项目参考Better Genshin Impact（项目地址 https://github.com/babalae/better-genshin-impact ）的子session实现
## 对于原版的破坏性改动

以下对比以 2026 年 10 月 21 日的上游提交 `9d27abe` 为基准。

- **移除 13 个内置专项适配器**：BAAH、BetterGI、HSR、M9A、MAA、MSS、MaaEnd、MaaFW、OkNte、Okww、SRC、Whimbox 和 ZzzOd。当前仅保留 General 通用脚本入口。原先依赖专项的用户需要在 General 中配置外部脚本的启动方式；原专项提供的能力（如 BetterGI 的账号切换、一条龙计划和掉落统计）不会随之迁移。
- **桌面主界面改用 PySide6/QML**：当前版本以 Qt 作为唯一图形界面，已移除浏览器控制台与 Node 前端宿主，并支持在无界面模式下按队列 ID 或脚本 ID 启动任务。

在保留的 General 入口基础上，本版新增以下运行方式：

- **本地远程桌面**：外部脚本可以在独立的 Windows 子会话中操作桌面，宿主窗口支持隐藏到托盘或按需显示。也可以通过命令行单独启动脚本，指定参数、超时和最大尝试次数（含首次）。
- **运行控制与桌面借用**：可用热键控制任务启停或切换任务，其中热键启停的设计参考了维护者的 [windows-script-scheduler](https://github.com/xzk09164418-droid/windows-script-scheduler) 项目。外部程序可申请借用远程桌面，队列会在子任务之间让出桌面，用完后由借用方释放。

具体命令见[远程桌面与启动说明](README-RELEASE.md)。

维护者已获得上游作者同意开设 fork。相关沟通记录由维护者私下保留。项目继续按根目录 [LICENSE](LICENSE) 中的 AGPL-3.0 条款发布，文件内已有的版权及许可证声明一并保留。第三方来源见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。

## 从源码运行 Qt 界面

需要 Windows 和 Python 3.12。先准备开发环境标记，再安装依赖。

```powershell
Copy-Item .env.example .env
py -3.12 -m pip install uv
uv sync --locked --python 3.12
uv pip install --python .venv\Scripts\python.exe -r qt/requirements.txt
.venv\Scripts\python.exe qt/main.py
```

Qt 启动选项与增强组件说明见 [qt/README.md](qt/README.md)。界面预览可使用 `--no-backend`。本地远程桌面宿主需要按 [README-RELEASE.md](README-RELEASE.md) 的 Windows 安装步骤准备。

## 版本与发布

AUTO-MASS 使用独立版本号 `0.1.0`。继承的上游更新历史保存在 `CHANGELOG.md` 和 `res/version.json` 的历史条目中。源代码发布应包含许可证、对应构建脚本及第三方声明。

配置、邮件授权码、调用方密钥、运行日志和恢复备份保存在本地忽略目录中。首次公开仓库应使用经过检查的 QT 发布范围或源码快照。其他本地分支历史曾提交私人配置，避免使用 --all 或 --mirror 推送。

Qt 关闭窗口后保留托盘与后端；托盘支持仅退出前端、停止队列和完整退出。隔离后端已验证窗口关闭/重建与完整退出；真实游戏任务及 RDP 注销仍需在对应运行环境验证。已修复的问题见 [RELEASE-NOTES.md](RELEASE-NOTES.md)。
