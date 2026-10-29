#!/usr/bin/env node
/**
 * AUTO-MAS 前后端分离 Node.js 前端宿主与系统浏览器启动器 (frontend/server.js)
 *
 * 功能特性：
 * 1. 前后端分离架构：独立监听前端端口（默认 36262），承载与 Auto-MAS 一致的 Web UI，
 *    并将 /api/* HTTP 请求与 /api/core/ws WebSocket 实时流透明反向代理至 Python 后端（默认 36263）。
 * 2. 按需独立拉起后端：若 Python 后端尚未运行，以无黑框模式后台启动；
 *    前端退出不结束后端，后端输出独立写入 debug/backend-launcher.log。
 * 3. 调用系统浏览器：后端健康检查就绪后，通过 Node.js 自动调用系统默认浏览器打开前端控制台。
 * 4. 支持启动参数直接无窗口运行：
 *    - `node frontend/server.js`                    -> 启动后端 + 前端服务并自动调用系统浏览器打开 UI
 *    - `node frontend/server.js --no-browser`       -> 仅后台启动服务，不弹出浏览器窗口
 *    - `node frontend/server.js --headless --auto-run` -> 无窗口直接运行后端并立即启动默认队列
 *    - `node frontend/server.js --headless --run-queue <QueueId>` -> 无窗口直接运行指定队列
 *    - `node frontend/server.js --headless --run-script <ScriptId>` -> 无窗口直接运行指定脚本
 */

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const { spawn, exec } = require('child_process');

const ROOT_DIR = path.resolve(__dirname, '..');
const DIST_DIR = path.join(__dirname, 'dist-browser');
const { createBrowserHost } = require('./web/host.cjs');
const { createRuntimeLogs } = require('./web/runtimeLogs.cjs');
const { createStartupStatus } = require('./web/startupStatus.cjs');
const { DEFAULT_PORTS, resolveInstance, ownsService, portAvailable, readJson } = require('./web/instance.cjs');
let backendStartPromise = null;
let backendProcess = null;
let backendLaunchError = null;

function parseArgs(argv) {
  const opts = {
    frontendPort: Number(process.env.AUTO_MAS_FRONTEND_PORT || DEFAULT_PORTS.frontendPort),
    backendPort: Number(process.env.AUTO_MAS_HTTP_PORT || DEFAULT_PORTS.backendPort),
    backendHost: '127.0.0.1',
    openBrowser: true,
    headless: false,
    appMode: false,
    runQueue: '',
    runScript: '',
    autoRun: false,
    externalBackendOnly: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const arg = String(argv[i] || '');
    if ((arg === '--port' || arg === '-p') && i + 1 < argv.length) {
      opts.frontendPort = Number(argv[++i]) || DEFAULT_PORTS.frontendPort;
    } else if (arg === '--backend-port' && i + 1 < argv.length) {
      opts.backendPort = Number(argv[++i]) || DEFAULT_PORTS.backendPort;
    } else if (arg === '--no-browser') {
      opts.openBrowser = false;
    } else if (arg === '--headless' || arg === '--no-window') {
      opts.headless = true;
      opts.openBrowser = false;
    } else if (arg === '--app' || arg === '--app-window') {
      opts.appMode = true;
    } else if (arg === '--run-queue' && i + 1 < argv.length) {
      opts.runQueue = String(argv[++i]);
    } else if (arg === '--run-script' && i + 1 < argv.length) {
      opts.runScript = String(argv[++i]);
    } else if (arg === '--auto-run') {
      opts.autoRun = true;
    } else if (arg === '--no-spawn-backend') {
      opts.externalBackendOnly = true;
    }
  }
  return opts;
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

function resolvePythonExecutable() {
  const candidates = [
    path.join(ROOT_DIR, '.venv', 'Scripts', 'pythonw.exe'),
    path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe'),
    path.join(ROOT_DIR, 'venv', 'Scripts', 'pythonw.exe'),
    path.join(ROOT_DIR, 'venv', 'Scripts', 'python.exe'),
    path.join(ROOT_DIR, 'python', 'python.exe'),
    path.join(ROOT_DIR, '.venv', 'bin', 'python'),
    path.join(ROOT_DIR, 'venv', 'bin', 'python'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

function checkBackendHealth(host, port, expectedId) {
  return ownsService(host, port, '/api/core/health', expectedId);
}

async function requireBackendOwnership(opts) {
  if (!await checkBackendHealth(opts.backendHost, opts.backendPort, opts.instanceId)) {
    throw new Error('后端尚未就绪或不属于本安装实例，已拒绝连接');
  }
}

function ensureBackendStarted(opts) {
  if (backendStartPromise) return backendStartPromise;
  backendStartPromise = startBackendOnce(opts).finally(() => { backendStartPromise = null; });
  return backendStartPromise;
}

async function startBackendOnce(opts) {
  const alreadyUp = await checkBackendHealth(opts.backendHost, opts.backendPort, opts.instanceId);
  if (alreadyUp) {
    console.log(`[AUTO-MAS] 检测到 Python 后端已在 http://${opts.backendHost}:${opts.backendPort} 运行`);
    return null;
  }

  if (!await portAvailable(opts.backendPort)) {
    throw new Error(`后端端口 ${opts.backendPort} 被其他实例占用，请重新启动并选择新端口`);
  }
  if (opts.externalBackendOnly) {
    console.log('[AUTO-MAS] 等待外部 Python 后端就绪...');
  } else {
    const pyExe = resolvePythonExecutable();
    const mainPy = path.join(ROOT_DIR, 'main.py');
    const pyArgs = [
      mainPy,
      '--port',
      String(opts.backendPort),
      '--no-admin-restart',
    ];
    if (opts.headless) {
      pyArgs.push('--headless');
    }
    if (opts.runQueue) {
      pyArgs.push('--run-queue', opts.runQueue);
    }
    if (opts.runScript) {
      pyArgs.push('--run-script', opts.runScript);
    }
    if (opts.autoRun) {
      pyArgs.push('--auto-run');
    }

    console.log(`[AUTO-MAS] 正在后台启动 Python 后端: ${pyExe} ${pyArgs.join(' ')}`);
    const logDir = path.join(ROOT_DIR, 'debug');
    fs.mkdirSync(logDir, { recursive: true });
    let backendProc = backendProcess;
    if (!backendProc || backendProc.exitCode !== null || backendLaunchError) {
      const logFd = fs.openSync(path.join(logDir, 'backend-launcher.log'), 'a');
      try {
        // 后端及其远程桌面桥接独立于 Node，不能继承随前端关闭的输出管道。
        // 由 Python 主桌面监督器统一建立子会话、恢复检查点和处理故障升级。
        backendProc = spawn(pyExe, pyArgs, {
          cwd: ROOT_DIR,
          detached: true,
          windowsHide: true,
          stdio: ['ignore', logFd, logFd],
          env: {
            ...process.env,
            AUTO_MAS_HTTP_PORT: String(opts.backendPort),
            AUTO_MAS_DEV: '1',
            AUTO_MAS_BROWSER_HOST: '1',
          },
        });
      } finally {
        fs.closeSync(logFd);
      }
      backendProcess = backendProc;
      backendLaunchError = null;
      backendProc.on('error', (error) => { backendLaunchError = error; });
      backendProc.unref();
    }

    // 子会话冷启动可能超过一分钟；等待期间仍复用同一个启动进程。
    for (let attempt = 0; attempt < 300; attempt++) {
      if (backendLaunchError) throw backendLaunchError;
      if (backendProc.exitCode !== null) {
        throw new Error(`Python 后端已退出 (${backendProc.exitCode})，请查看 debug/backend-launcher.log`);
      }
      const ok = await checkBackendHealth(opts.backendHost, opts.backendPort, opts.instanceId);
      if (ok) {
        console.log(`[AUTO-MAS] Python 后端已就绪 (http://${opts.backendHost}:${opts.backendPort})`);
        return;
      }
      await new Promise((r) => setTimeout(r, 400));
    }
    throw new Error('后端启动尚未完成，请查看 debug/backend-launcher.log；再次连接会等待现有进程，不重复启动');
  }

  return null;
}

function openSystemBrowser(url, appMode = false) {
  console.log(`[AUTO-MAS] 正在通过 Node.js 调用系统浏览器打开: ${url}`);
  if (process.platform === 'win32') {
    const edge = [process.env['ProgramFiles(x86)'], process.env.ProgramFiles, process.env.LOCALAPPDATA]
      .filter(Boolean).map(base => path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'))
      .find(candidate => fs.existsSync(candidate));
    const openDefault = () => {
      const child = spawn('explorer.exe', [url], { windowsHide: true, stdio: 'ignore' });
      child.on('error', error => console.error('[AUTO-MAS] 打开浏览器失败:', error.message));
    };
    if (edge) {
      const child = spawn(edge, [
        '--disable-extensions', '--no-first-run', '--no-default-browser-check',
        `--user-data-dir=${path.join(ROOT_DIR, 'data', 'browser-profile')}`,
        appMode ? `--app=${url}` : url,
      ], { windowsHide: true, stdio: 'ignore' });
      child.on('error', openDefault);
    } else openDefault();
  } else if (process.platform === 'darwin') {
    exec(`open "${url}"`);
  } else {
    exec(`xdg-open "${url}"`);
  }
}

function resolveStaticFile(requestPath) {
  let cleanPath;
  try { cleanPath = decodeURIComponent(requestPath.split('?')[0] || '/'); }
  catch { return null; }
  if (cleanPath === '/' || cleanPath === '') {
    cleanPath = '/browser.html';
  }

  // 特殊静态图标映射
  if (cleanPath === '/favicon.ico' || cleanPath === '/AUTO-MAS.ico') {
    const iconCandidate = path.join(ROOT_DIR, 'res', 'icons', 'AUTO-MAS.ico');
    if (fs.existsSync(iconCandidate)) {
      return iconCandidate;
    }
  }

  const roots = [DIST_DIR];
  for (const base of roots) {
    if (!fs.existsSync(base)) continue;
    const target = path.resolve(base, '.' + cleanPath);
    if (target.startsWith(base + path.sep) && fs.existsSync(target) && fs.statSync(target).isFile()) {
      return target;
    }
  }

  // 缺失的资源应返回 404，避免音频和脚本收到 HTML 后被误判为存在。
  if (path.extname(cleanPath)) return null;
  // SPA History 路由回退到浏览器入口。
  for (const base of roots) {
    const indexFile = path.join(base, 'browser.html');
    if (fs.existsSync(indexFile)) {
      return indexFile;
    }
  }
  return null;
}

async function startFrontendServer(opts, runtimeLogs) {
  const existing = await readJson('127.0.0.1', opts.frontendPort, '/__frontend_config');
  if (existing?.instanceId === opts.instanceId && existing.backendPort === opts.backendPort) {
    if (opts.openBrowser && !opts.headless) openSystemBrowser(`http://127.0.0.1:${opts.frontendPort}`, opts.appMode);
    return false;
  }
  const startupStatus = createStartupStatus(ROOT_DIR, opts.backendPort, () => backendLaunchError?.message, opts.instanceId);
  const handleHost = createBrowserHost(ROOT_DIR, opts.backendPort, {
    runtimeLogs,
    startupStatus,
    requireBackendOwnership: () => requireBackendOwnership(opts),
    stopFrontend() {
      // 先返回托盘请求，再关闭 HTTP 与 WebSocket；不触碰 Python 后端。
      setTimeout(() => process.exit(0), 250);
      return { success: true };
    },
    async startBackend() {
      try {
        await ensureBackendStarted(opts);
        return { success: true };
      } catch (error) { return { success: false, error: error.message }; }
    },
  });
  const server = http.createServer(async (req, res) => {
    const reqUrl = req.url || '/';
    if (req.headers['x-auto-mas-instance'] && req.headers['x-auto-mas-instance'] !== opts.instanceId) {
      res.writeHead(409, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ code: 409, status: 'error', message: '前端不属于请求指定的安装实例' }));
      return;
    }
    if (await handleHost(req, res)) return;

    // 前端配置探测端点
    if (reqUrl === '/__frontend_config') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(
        JSON.stringify({
          instanceId: opts.instanceId,
          frontendPort: opts.frontendPort,
          backendPort: opts.backendPort,
          backendBaseUrl: `http://${opts.backendHost}:${opts.backendPort}`,
          wsBaseUrl: `ws://${opts.backendHost}:${opts.backendPort}`,
        })
      );
      return;
    }

    // 反向代理 /api/* 到 Python FastAPI 后端
    if (reqUrl.startsWith('/api/')) {
      try { await requireBackendOwnership(opts); }
      catch (error) {
        res.writeHead(503, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ code: 503, status: 'error', message: error.message }));
        return;
      }
      const proxyReq = http.request(
        {
          host: opts.backendHost,
          port: opts.backendPort,
          path: reqUrl,
          method: req.method,
          headers: {
            ...req.headers,
            host: `${opts.backendHost}:${opts.backendPort}`,
            'X-Auto-Mas-Instance': opts.instanceId,
          },
        },
        (proxyRes) => {
          res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
          proxyRes.pipe(res, { end: true });
        }
      );

      proxyReq.on('error', (err) => {
        res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(
          JSON.stringify({
            code: 502,
            status: 'error',
            message: `无法连接到 Python 后端 (${opts.backendHost}:${opts.backendPort}): ${err.message}`,
          })
        );
      });

      req.pipe(proxyReq, { end: true });
      return;
    }

    // 静态文件服务 (SPA)
    const filePath = resolveStaticFile(reqUrl);
    if (!filePath) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('404 Not Found');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    fs.stat(filePath, (err, stat) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('500 Internal Server Error');
        return;
      }
      // 每次核对文件版本，未变化时复用浏览器缓存；更新部署后立即重新加载。
      const etag = `W/"${stat.size.toString(16)}-${stat.mtimeMs.toString(16)}"`;
      const headers = {
        'Content-Type': contentType,
        'Cache-Control': 'no-cache',
        ETag: etag,
      };
      const ifNoneMatch = req.headers['if-none-match'];
      if ((req.method === 'GET' || req.method === 'HEAD') && ifNoneMatch &&
          ifNoneMatch.split(',').some(value => value.trim() === '*' ||
            value.trim().replace(/^W\//, '') === etag.replace(/^W\//, ''))) {
        res.writeHead(304, headers);
        res.end();
        return;
      }
      fs.readFile(filePath, (readError, content) => {
        if (readError) {
          res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('500 Internal Server Error');
          return;
        }
        res.writeHead(200, headers);
        res.end(content);
      });
    });
  });

  // 透明代理 WebSocket 升级请求 (/api/core/ws 等)
  server.on('upgrade', async (req, clientSocket, head) => {
    try { await requireBackendOwnership(opts); }
    catch { clientSocket.destroy(); return; }
    clientSocket.setNoDelay(true);
    const backendSocket = net.connect(opts.backendPort, opts.backendHost, () => {
      const headers = [`${req.method} ${req.url} HTTP/${req.httpVersion}`];
      for (let i = 0; i < req.rawHeaders.length; i += 2) {
        const k = req.rawHeaders[i];
        const v = req.rawHeaders[i + 1];
        if (k.toLowerCase() === 'host') {
          headers.push(`Host: ${opts.backendHost}:${opts.backendPort}`);
        } else {
          headers.push(`${k}: ${v}`);
        }
      }
      headers.push(`X-Auto-Mas-Instance: ${opts.instanceId}`, '', '');
      backendSocket.write(headers.join('\r\n'));
      if (head && head.length > 0) {
        backendSocket.write(head);
      }
      clientSocket.pipe(backendSocket);
      backendSocket.pipe(clientSocket);
    });

    backendSocket.setNoDelay(true);
    backendSocket.on('error', () => clientSocket.destroy());
    clientSocket.on('error', () => backendSocket.destroy());
  });

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(opts.frontendPort, '127.0.0.1', resolve);
  });
  const url = `http://127.0.0.1:${opts.frontendPort}`;
  console.log(`[AUTO-MAS] 前端 Web 服务已启动: ${url}`);
  console.log(`[AUTO-MAS] API 反向代理目标: http://${opts.backendHost}:${opts.backendPort}`);
  if (opts.openBrowser && !opts.headless) openSystemBrowser(url, opts.appMode);

  const cleanup = () => {
    try {
      server.close();
    } catch (_) {}
    process.exit(0);
  };

  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
  return true;
}

async function main() {
  const instance = await resolveInstance(ROOT_DIR, process.argv.slice(2));
  if (instance.cancelled) return;
  const opts = { ...parseArgs(process.argv), ...instance };
  const runtimeLogs = createRuntimeLogs(ROOT_DIR, require('./dist-host/services.cjs'));
  for (const [method, level] of Object.entries({ log: 'INFO', info: 'INFO', debug: 'DEBUG', warn: 'WARNING', error: 'ERROR' })) {
    const original = console[method].bind(console);
    console[method] = (...args) => { runtimeLogs.write(level, 'Node 前端', ...args); original(...args); };
  }
  if (!await startFrontendServer(opts, runtimeLogs)) return;
  try { await ensureBackendStarted(opts); }
  catch (error) { console.error('[AUTO-MAS] 后端启动未完成:', error.message); }
}

module.exports = { checkBackendHealth, requireBackendOwnership };
if (require.main === module) {
  main().catch((err) => {
    console.error('[AUTO-MAS] 启动异常:', err);
    process.exit(1);
  });
}
