# Qt 便携运行包

打开 `AUTO-MASS-0.1.0-Qt-windows-x64.exe`，选择一个有写入权限的目录解压，然后双击目录中的 `AUTO-MAS.exe`。
请保留完整目录，不要只移动启动 EXE。自解压程序不注册系统服务、不配置自动登录，也不安装到系统目录。
建议解压至 `C:\Apps` 等短目录；过深目录可能导致 Qt 资源路径超过 Windows 260 字符限制，解压失败时应换短目录重试。
包内 `AUTO-MAS.exe` 是同一个 Qt 启动器的兼容副本，供原有自启或重启入口使用。

包含 Python 3.12、PySide6 Essentials 6.9.3、后端生产依赖、RDP 宿主与通知组件。
标准 Qt 界面无需另装 Python、Node.js 或 Git。增强 3D 是可选组件，未预装。
Windows x64 系统需要自带的 .NET Framework 和 RDP 组件；外部游戏、脚本和 UU 需要自行安装。

发行包从脱敏源码与依赖文件清单构建，不携带用户配置、账号、密钥、日志、检查点或 Git 数据。
首次启动创建全新配置。没有迁移原电脑的自动登录、系统自启、通知协议注册或远程连接设置。

## 构建

使用已安装 `pyproject.toml` 生产依赖、`qt/requirements.txt` 和 pip 的 Python 3.12 环境：

```powershell
python scripts/build-qt-portable.py --python-runtime C:\build\python312 --output C:\build\AUTO-MASS-0.1.0-Qt
```

构建机需 Git 和 Windows .NET Framework C# 编译器。`--python-runtime` 指可搬移的完整 Python 3.12 运行时，而非含绝对路径的 venv。
输出目录必须不存在。只按已跟踪源码白名单和生产依赖的安装清单复制文件，不复制本机配置。
用 7-Zip 的 `7z.sfx` 封装目录可得到自解压 EXE，分发时须附带 7-Zip 的许可证与来源。

## 验证范围

已在清理 Python、Node 和 Git 的 PATH 环境下验证包内依赖导入、配置读取/保存/回读、Qt EXE 自动拉起后端，以及中文和空格路径。
测试关闭 RDP、全局热键和签到，并且没有真实队列。真实任务运行时退出 Qt 的 RDP 清理仍未完成实机验证。
