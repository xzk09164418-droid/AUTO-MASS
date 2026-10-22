# 浏览器版

使用 Node.js 22 与 Yarn 4.18.1，在 `frontend/` 执行：

```powershell
yarn install --immutable --mode=skip-build
yarn build:web
yarn start:web
```

默认通过本机浏览器打开 <http://127.0.0.1:36162/>。静默启动可执行
`node server.js --no-browser`；连接已启动的独立后端可加 `--no-spawn-backend`。
前端端口用 `--port`，Python 后端端口用 `--backend-port` 设置。

浏览器入口是 `browser.html`，构建目录为 `dist-browser/`。
Node.js 提供静态页面、HTTP/WebSocket 代理及受同源限制的本机文件服务。
业务逻辑、任务执行、配置校验、热键与远程桌面仍由独立 Python 后端负责。
构建及启动命令均不编译、启动或加载 Electron 运行时。

托管管理、脚本分组、账号行、新建弹窗和各专项的二级编辑页直接沿用仓库中的
AUTO-MAS Vue 页面，使用相同的 Ant Design Vue 组件、主题与业务 API。
文件选择在浏览器弹窗中浏览本机磁盘，保留原来的路径校验和自动保存行为。
“本机与热键”页集中管理本地部署专有的远程桌面、热键、任务切换与外部借用。

`web/services.ts` 只复用原项目中的纯 Node 工具函数；构建器禁止其导入 Electron。
原页面的 `window.electronAPI` 名称仅作为兼容接口，通过 HTTP 接入 Node.js 服务。
窗口和浏览器开发工具由本机浏览器管理。

界面配置继续保存在 `config/frontend_config.json`，任务与脚本配置使用原后端数据目录。
浏览器资源包放在 `data/browser/`，不使用浏览器存储替代任务配置。

维护时运行 `yarn lint --max-warnings 1`、`yarn typecheck`、
`yarn test --maxWorkers=4` 和 `yarn build:web`。
端到端测试遵循项目入口 `yarn e2e`；测试工具和临时参考源码不属于运行所需文件。
