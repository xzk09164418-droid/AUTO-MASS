# 本地构建和启动

本分支使用 Qt 前端、独立 Python 后端与原生 Windows 桌面分身宿主，不依赖 Node 或浏览器。

```powershell
uv sync --locked --python 3.12
uv pip install --python .venv/Scripts/python.exe -r qt/requirements.txt pip
pwsh -NoProfile -File scripts/install_release.ps1
```

`install_release.ps1` 编译 Qt 无窗口启动器和远程桌面宿主，并创建快捷方式。
构建 Windows 分发目录使用 `build-qt-portable.py --python-runtime <完整 Python 3.12 运行时> --output <新目录>`，详见 [Qt 便携运行包](../docs/QT-PORTABLE.md)。
CI 输出为 `dist/win-unpacked`。构建只复制跟踪的源码白名单和已安装的依赖，不包含用户数据。

静默运行使用 `AUTO-MAS.exe --headless`。托盘菜单区分仅退出前端、停止队列和完全退出；强制重启沿用 `force-restart.ps1`，结束后只启动 Qt。
