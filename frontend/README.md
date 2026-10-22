# 本机浏览器前端

此分支使用 Vue + Node.js 本机服务，通过独立 HTTP/WebSocket API 连接 Python 后端。
不包含 Electron 主进程、预加载桥、运行时依赖或桌面安装包构建入口。

在本目录执行：

```powershell
yarn install --immutable
yarn build
yarn start:web
```

日常启动使用仓库根目录的 `AUTO-MAS.exe`。浏览器页面默认地址为
<http://127.0.0.1:36162/>，后端默认为 36163 端口。

`node/` 保存纯 Node 文件、配置及问题包服务；`web/` 提供本机 HTTP 宿主。
详细部署、日志及验证命令见 [WEB.md](WEB.md)。
