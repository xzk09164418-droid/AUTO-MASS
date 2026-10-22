# 本地构建和启动

本分支使用独立 Python 后端、Node.js 前端宿主与本机浏览器。

```powershell
Set-Location frontend
yarn install --immutable
yarn build:web
Set-Location ..
pwsh -NoProfile -File scripts/install_release.ps1
```

`install_release.ps1` 编译原生无窗口启动器和远程桌面宿主，并创建本地快捷方式。
它不构建或启动 Electron。旧的桌面安装包构建脚本已移除。

构建 Windows 分发目录可运行 `scripts/build-web-package.ps1`，输出到
`frontend/dist/win-unpacked`，包含 Node.js、浏览器资源、原生启动器与后端源码。
新机器仍需 Python 3.12，并运行安装脚本配置后端依赖；包内不携带用户配置和日志。

需要静默运行时使用 `AUTO-MAS.exe --no-browser`。前端和后端各自独立退出，
使用托盘菜单区分“仅退出前端”“暂停后端服务”和“完全退出”。

前端构建及日志说明见 [WEB.md](../frontend/WEB.md)。实际队列运行属于有副作用的
业务操作，只有明确要求时才执行，不作为普通页面测试的一部分。
