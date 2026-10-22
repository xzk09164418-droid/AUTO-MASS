# 浏览器版

使用 Node.js 22 与 Yarn 4.18.1，在 `frontend/` 执行：

```powershell
yarn install --immutable --mode=skip-build
yarn build:web
yarn start:web
```

默认通过本机浏览器打开 <http://127.0.0.1:36162/>。静默启动可执行
`node server.js --no-browser`；连接已启动的独立后端可加 `--no-spawn-backend`。
日常从桌面“AUTO-MAS 控制台”快捷方式或 `AUTO-MAS.exe` 启动，Node.js 与
Python 均在后台运行，打开浏览器也不会弹出命令行窗口。`Start-AUTO-MAS.bat` 会优先
转交此无窗口启动器并立即返回；双击 `.bat` 时 Windows 自身仍可能短暂显示
命令行窗口，因此需要完全无黑框时使用上述快捷方式或 `.exe` 入口。
前端端口用 `--port`，Python 后端端口用 `--backend-port` 设置。
后端按需独立启动，关闭或重启 Node.js 前端服务不会结束后端任务。
后端启动输出写入 `debug/backend-launcher.log`；停止后端请使用程序内的后端控制。
托盘提供“仅退出前端”“暂停后端服务（停止队列）”“完全退出”三个独立操作。
仅退出前端后托盘继续保留，可通过“打开浏览器控制台”重新启动前端；
暂停项停止当前全部队列，保留后端与定时调度；完全退出等待后端清理后再关闭前端与托盘。
浏览器宿主为 Python 设置 `AUTO_MAS_BROWSER_HOST=1`，使显式关闭请求在源码环境中
同样完成完整退出，同时保留 `.env` 的开发环境与遥测设置。

浏览器入口是 `browser.html`，构建目录为 `dist-browser/`。
Node.js 提供静态页面、HTTP/WebSocket 代理及受同源限制的本机文件服务。
业务逻辑、任务执行、配置校验、热键与远程桌面仍由独立 Python 后端负责。
构建及启动命令均不编译、启动或加载 Electron 运行时。

托管管理、脚本分组、账号行、新建弹窗和各专项的二级编辑页直接沿用仓库中的
AUTO-MAS Vue 页面，使用相同的 Ant Design Vue 组件、主题与业务 API。
文件选择在浏览器弹窗中浏览本机磁盘，保留原来的路径校验和自动保存行为。
“本机与热键”页集中管理本地部署专有的远程桌面、热键、任务切换与外部借用。
“历史记录”默认展示本机日志，优先读取程序目录 `logs/` 下的 `app.log`、
`frontend.log`，不存在时读取现有 `debug/` 中的同名文件，支持自动更新和自由浏览。
“运行记录”分页继续读取 `history/` 中的任务记录及对应日志。浏览器不显示资源商店入口。
浏览器不显示桌面标题栏、主程序自动更新、Runtime 启动模式和启动最小化入口。
通用脚本已移除配置回写，对应的配置文件路径、回写时机、配置来源、配置会话及恢复入口
同步移除，保留启动参数、日志、超时、账号、通知和前后置脚本配置。

`web/services.ts` 只复用原项目中的纯 Node 工具函数；构建器禁止其导入 Electron。
原页面的 `window.electronAPI` 名称仅作为兼容接口，通过 HTTP 接入 Node.js 服务。
窗口和浏览器开发工具由本机浏览器管理。

界面配置继续保存在 `config/frontend_config.json`，任务与脚本配置使用原后端数据目录。
浏览器资源包放在 `data/browser/`，不使用浏览器存储替代任务配置。

维护时运行 `yarn lint --max-warnings 1`、`yarn typecheck`、
`yarn test --maxWorkers=4` 和 `yarn build:web`。
端到端测试遵循项目入口 `yarn e2e`；测试工具和临时参考源码不属于运行所需文件。
