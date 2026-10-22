#!/usr/bin/env node
/**
 * AUTO-MAS 前后端分离 Node.js 前端宿主与系统浏览器启动器 (frontend/server.js)
 *
 * 功能特性：
 * 1. 前后端分离架构：独立监听前端端口（默认 36162），承载与 Auto-MAS 一致的 Web UI，
 *    并将 /api/* HTTP 请求与 /api/core/ws WebSocket 实时流透明反向代理至 Python 后端（默认 36163）。
 * 2. 自动守护与拉起后端：若检测到 Python 后端尚未运行，自动以无黑框模式 (windowsHide: true)
 *    后台拉起 Python 后端服务（远程桌面默认最小化在系统托盘运行，避免打扰主桌面）。
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

function parseArgs(argv) {
  const opts = {
    frontendPort: Number(process.env.AUTO_MAS_FRONTEND_PORT || 36162),
    backendPort: Number(process.env.AUTO_MAS_HTTP_PORT || 36163),
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
      opts.frontendPort = Number(argv[++i]) || 36162;
    } else if (arg === '--backend-port' && i + 1 < argv.length) {
      opts.backendPort = Number(argv[++i]) || 36163;
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
    path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe'),
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

function checkBackendHealth(host, port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host,
        port,
        path: '/api/core/health',
        timeout: timeoutMs,
      },
      (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          resolve(res.statusCode === 200);
        });
      }
    );
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function ensureBackendStarted(opts) {
  const alreadyUp = await checkBackendHealth(opts.backendHost, opts.backendPort);
  if (alreadyUp) {
    console.log(`[AUTO-MAS] 检测到 Python 后端已在 http://${opts.backendHost}:${opts.backendPort} 运行`);
    return null;
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
    const backendProc = spawn(pyExe, pyArgs, {
      cwd: ROOT_DIR,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        AUTO_MAS_HTTP_PORT: String(opts.backendPort),
        AUTO_MAS_DEV: '1',
      },
    });

    backendProc.stdout.on('data', (data) => {
      process.stdout.write(`[Backend] ${data}`);
    });
    backendProc.stderr.on('data', (data) => {
      process.stderr.write(`[Backend] ${data}`);
    });

    for (let attempt = 0; attempt < 90; attempt++) {
      const ok = await checkBackendHealth(opts.backendHost, opts.backendPort, 1000);
      if (ok) {
        console.log(`[AUTO-MAS] Python 后端已就绪 (http://${opts.backendHost}:${opts.backendPort})`);
        return backendProc;
      }
      await new Promise((r) => setTimeout(r, 400));
    }
    console.warn('[AUTO-MAS] 警告：等待后端健康检查超时，前端服务仍将继续启动');
    return backendProc;
  }

  return null;
}

function openSystemBrowser(url, appMode = false) {
  console.log(`[AUTO-MAS] 正在通过 Node.js 调用系统浏览器打开: ${url}`);
  if (process.platform === 'win32') {
    if (appMode) {
      exec(`start "" msedge --app="${url}"`, (err) => {
        if (err) {
          exec(`cmd /c start "" "${url}"`);
        }
      });
    } else {
      exec(`cmd /c start "" "${url}"`);
    }
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

function startFrontendServer(opts, backendProc) {
  const handleHost = createBrowserHost(ROOT_DIR, opts.backendPort);
  const server = http.createServer(async (req, res) => {
    const reqUrl = req.url || '/';
    if (await handleHost(req, res)) return;

    // 前端配置探测端点
    if (reqUrl === '/__frontend_config') {
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(
        JSON.stringify({
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
      const proxyReq = http.request(
        {
          host: opts.backendHost,
          port: opts.backendPort,
          path: reqUrl,
          method: req.method,
          headers: {
            ...req.headers,
            host: `${opts.backendHost}:${opts.backendPort}`,
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
    fs.readFile(filePath, (err, content) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('500 Internal Server Error');
        return;
      }
      res.writeHead(200, {
        'Content-Type': contentType,
        'Cache-Control': 'no-cache',
      });
      res.end(content);
    });
  });

  // 透明代理 WebSocket 升级请求 (/api/core/ws 等)
  server.on('upgrade', (req, clientSocket, head) => {
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
      headers.push('', '');
      backendSocket.write(headers.join('\r\n'));
      if (head && head.length > 0) {
        backendSocket.write(head);
      }
      clientSocket.pipe(backendSocket);
      backendSocket.pipe(clientSocket);
    });

    backendSocket.on('error', () => clientSocket.destroy());
    clientSocket.on('error', () => backendSocket.destroy());
  });

  server.on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
      console.log(`[AUTO-MAS] 控制台端口 ${opts.frontendPort} 已有服务，复用现有控制台`);
      if (opts.openBrowser && !opts.headless) {
        openSystemBrowser(`http://127.0.0.1:${opts.frontendPort}`, opts.appMode);
      }
      return;
    }
    console.error('[AUTO-MAS] 控制台监听失败:', error);
    if (backendProc && !backendProc.killed) backendProc.kill();
    process.exitCode = 1;
  });

  server.listen(opts.frontendPort, '127.0.0.1', () => {
    const url = `http://127.0.0.1:${opts.frontendPort}`;
    console.log(`[AUTO-MAS] 前端 Web 服务已启动: ${url}`);
    console.log(`[AUTO-MAS] API 反向代理目标: http://${opts.backendHost}:${opts.backendPort}`);
    if (opts.openBrowser && !opts.headless) {
      openSystemBrowser(url, opts.appMode);
    } else {
      console.log('[AUTO-MAS] 当前为无窗口/静默运行模式，未打开浏览器窗口。');
    }
  });

  const cleanup = () => {
    try {
      server.close();
    } catch (_) {}
    if (backendProc && !backendProc.killed) {
      try {
        backendProc.kill();
      } catch (_) {}
    }
    process.exit(0);
  };

  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
}

async function main() {
  const opts = parseArgs(process.argv);
  const backendProc = await ensureBackendStarted(opts);
  startFrontendServer(opts, backendProc);
}

main().catch((err) => {
  console.error('[AUTO-MAS] 启动异常:', err);
  process.exit(1);
});
