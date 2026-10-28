// Node.js 本机能力宿主：浏览器 UI 与 Python 业务后端保持独立。
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { spawn } = require('node:child_process')

function createBrowserHost(root, backendPort, lifecycle = {}) {
  const services = require('../dist-host/services.cjs')
  const configPath = path.join(root, 'config', 'frontend_config.json')
  const userData = path.join(root, 'data', 'browser')
  // 在线资源在本机构建中停用；本地外观导入、预览和删除仍走原来的服务。
  const onlineService = () => {
    throw new Error('本机构建已停用在线外观下载，请使用本地导入')
  }
  const exportZip = async (name, creator) => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-mas-browser-export-'))
    const filename = `${name}-${new Date().toISOString().slice(0, 10)}.zip`
    const output = path.join(directory, filename)
    try {
      const result = await creator(output)
      return result.success
        ? {
            ...result,
            zipPath: filename,
            filename,
            fileBase64: fs.readFileSync(output).toString('base64'),
          }
        : result
    } finally {
      // 此目录由本次导出创建，只删除本次输出与空目录。
      if (fs.existsSync(output)) fs.unlinkSync(output)
      fs.rmdirSync(directory)
    }
  }
  const loadConfig = () =>
    fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath, 'utf8')) : null
  const saveConfig = (patch, defaults = {}) => services.patchConfigFile(configPath, patch, defaults)
  const openLocalPath = (target, reveal = false) =>
    new Promise((resolve, reject) => {
      const resolved = path.resolve(target)
      if (!fs.existsSync(resolved)) throw new Error('文件或文件夹不存在')
      const child = spawn('explorer.exe', reveal ? ['/select,', resolved] : [resolved], {
        windowsHide: true,
        stdio: 'ignore',
      })
      child.once('error', reject)
      child.once('spawn', () => resolve({ success: true }))
    })
  const api = {
    getStartupStatus: () => lifecycle.startupStatus(),
    getRuntimeLogs: (...args) => lifecycle.runtimeLogs.read(...args),
    listLogArchives: () => lifecycle.runtimeLogs.list(),
    writeFrontendLog(level, module, args) {
      const levels = { debug: 'DEBUG', info: 'INFO', warn: 'WARNING', error: 'ERROR' }
      if (!Object.hasOwn(levels, level) || typeof module !== 'string' || !Array.isArray(args))
        throw new Error('无效的前端日志')
      lifecycle.runtimeLogs.write(levels[level], module, ...args)
    },
    frontendStop: () => {
      if (!lifecycle.stopFrontend) throw new Error('当前宿主未配置前端停止能力')
      return lifecycle.stopFrontend()
    },
    backendStart: async () => {
      if (!lifecycle.startBackend) throw new Error('当前宿主未配置后端启动能力')
      return lifecycle.startBackend()
    },
    async localControl(action, payload) {
      const routes = {
        status: ['GET', '/api/child-session/status'],
        connect: ['POST', '/api/child-session/connect'],
        window: ['POST', '/api/child-session/window'],
        logoff: ['POST', '/api/child-session/logoff'],
        acquire: ['POST', '/api/child-session/acquire'],
        release: ['POST', '/api/child-session/release'],
        toggle: ['POST', '/api/dispatch/navigation/toggle'],
        previous: ['POST', '/api/dispatch/navigation/previous'],
        next: ['POST', '/api/dispatch/navigation/next'],
        reloadHotkeys: ['POST', '/api/dispatch/hotkey/reload'],
      }
      if (!Object.hasOwn(routes, action)) throw new Error('未知本机操作')
      const [method, endpoint] = routes[action]
      await lifecycle.requireBackendOwnership?.()
      const response = await fetch(`http://127.0.0.1:${backendPort}${endpoint}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        ...(method === 'POST' ? { body: JSON.stringify(payload) } : {}),
      })
      const result = await response.json()
      if (!response.ok || result.code !== 200)
        throw new Error(result.message || response.statusText)
      return result.data || result
    },
    loadConfig,
    saveConfig,
    resetConfig: () => {
      if (fs.existsSync(configPath)) fs.unlinkSync(configPath)
    },
    syncBackendConfig(settings) {
      const current = loadConfig() || {}
      const patch = {}
      for (const key of ['UI', 'Start', 'Update', 'Function']) {
        if (settings[key]) patch[key] = { ...current[key], ...settings[key] }
      }
      saveConfig(patch)
      return true
    },
    updateTraySettings: settings => {
      saveConfig({ UI: { ...loadConfig()?.UI, ...settings } })
      return true
    },
    getInitializedVersion: () => loadConfig()?.initializedVersion || null,
    setInitializedVersion: version => {
      saveConfig({ initializedVersion: version })
      return true
    },
    getRuntimeLaunchMode: () => ({ persisted: 'off', mode: 'development', source: 'development' }),
    fileExists: file => fs.existsSync(path.resolve(file)),
    readFile: file => fs.readFileSync(path.resolve(file), 'utf8'),
    readFileBase64(file, maxBytes = 20 * 1024 * 1024) {
      const resolved = path.resolve(file)
      const size = fs.statSync(resolved).size
      return { size, base64: size > maxBytes ? '' : fs.readFileSync(resolved).toString('base64') }
    },
    getAppPath: name =>
      ({
        exe: process.execPath,
        userData,
        home: os.homedir(),
        desktop: path.join(os.homedir(), 'Desktop'),
        documents: path.join(os.homedir(), 'Documents'),
      })[name] || root,
    browseFiles(directory = '', extensions = []) {
      if (!directory) {
        const drives =
          process.platform === 'win32'
            ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                .split('')
                .map(letter => `${letter}:\\`)
                .filter(drive => fs.existsSync(drive))
            : ['/']
        return {
          directory: '',
          parent: '',
          entries: drives.map(drive => ({ name: drive, path: drive, folder: true })),
        }
      }
      const resolved = path.resolve(directory)
      const allowed = extensions.map(extension => `.${extension.toLowerCase()}`)
      const entries = fs
        .readdirSync(resolved, { withFileTypes: true })
        .filter(
          entry =>
            entry.isDirectory() ||
            !allowed.length ||
            allowed.includes('.*') ||
            allowed.includes(path.extname(entry.name).toLowerCase())
        )
        .map(entry => ({
          name: entry.name,
          path: path.join(resolved, entry.name),
          folder: entry.isDirectory(),
        }))
        .sort((a, b) => Number(b.folder) - Number(a.folder) || a.name.localeCompare(b.name))
      return {
        directory: resolved,
        parent: path.dirname(resolved) === resolved ? '' : path.dirname(resolved),
        entries,
      }
    },
    validatePath(file, folder, extensions = []) {
      const resolved = path.resolve(file)
      const stats = fs.statSync(resolved)
      if (folder ? !stats.isDirectory() : !stats.isFile())
        throw new Error(folder ? '请选择文件夹' : '请选择文件')
      if (
        !folder &&
        extensions.length &&
        !extensions.includes('*') &&
        !extensions.includes(path.extname(resolved).slice(1).toLowerCase())
      )
        throw new Error('文件类型不符合要求')
      return resolved
    },
    openFile: file => openLocalPath(file),
    showItemInFolder: file => openLocalPath(file, true),
    getLogs(lines = 0, fileName = 'app.log', fromOffset) {
      if (!['app.log', 'frontend.log'].includes(fileName)) throw new Error('无效的日志文件')
      if (fromOffset !== undefined && (!Number.isSafeInteger(fromOffset) || fromOffset < 0))
        throw new Error('无效的日志读取位置')
      if (lifecycle.runtimeLogs) {
        return lifecycle.runtimeLogs
          .read(fileName === 'app.log' ? 'app' : 'frontend', fromOffset || 0)
          .then(result => (typeof fromOffset === 'number' ? result : result.content))
      }
      const candidates = ['logs', 'debug'].map(directory => path.join(root, directory, fileName))
      const logPath = candidates.find(file => fs.existsSync(file)) || candidates[0]
      return typeof fromOffset === 'number'
        ? services.readLogIncrement(logPath, fromOffset)
        : services.readLogContent(logPath, lines)
    },
    discoverOkwwPath: services.discoverOkwwPath,
    discoverWutheringWavesPath: services.discoverWutheringWavesPath,
    listAppearances: () => services.listAppearances(userData),
    listOnlineAppearances: (query, category) => onlineService(category).list(query || {}),
    getOnlineAppearance: (key, category) => onlineService(category).detail(key),
    prepareOnlineAppearance: (key, version, category) =>
      onlineService(category).prepare(key, version),
    installOnlineAppearance: (token, replace, category) =>
      onlineService(category).install(token, replace),
    discardOnlineAppearance: (token, category) => onlineService(category).discard(token),
    getOnlineAppearanceCover: (key, version, category) =>
      onlineService(category).cover(key, version),
    getAppearance: id => services.getAppearance(userData, id),
    importAppearance: (file, replace) => services.importAppearancePackage(userData, file, replace),
    removeAppearance: id => services.removeAppearance(userData, id),
    inspectLocalAppearance(file, category) {
      const { manifest, previewUrl } =
        category === 'mascot'
          ? services.inspectMascotPackage(file)
          : services.inspectAppearancePackage(file)
      return {
        success: true,
        fileSize: fs.statSync(file).size,
        appearance: {
          id: manifest.id,
          name: manifest.name,
          description: manifest.description,
          mode: manifest.mode,
          tokens: manifest.tokens,
          previewUrl,
        },
      }
    },
    inspectAppearanceCover(file) {
      if (fs.statSync(file).size > 8 * 1024 * 1024)
        return { success: false, error: '封面图片不能超过 8 MB' }
      const data = fs.readFileSync(file)
      const mime = services.imageMimeFromMagic(data)
      return mime
        ? { success: true, dataUrl: `data:${mime};base64,${data.toString('base64')}` }
        : { success: false, error: '封面只支持 PNG、JPEG 或 WebP 图片' }
    },
    clearInvalidAppearance: id =>
      services.clearAppearanceConfigIfCurrent(configPath, id, () =>
        services.isAppearanceGone(userData, id)
      ),
    listMascots: () => services.listMascots(userData),
    importMascot: (file, replace) => services.importMascotPackage(userData, file, replace),
    removeMascot: id => services.removeMascot(userData, id),
    listMaaFWIssueReportScripts: types => services.listMaaFWIssueReportScripts(root, types || []),
    exportLogs: () =>
      exportZip('AUTO-MAS-logs', output => {
        const AdmZip = require('adm-zip')
        const zip = new AdmZip()
        const state = { zip, entries: [], archiveBytes: 0 }
        if (fs.existsSync(path.join(root, 'logs')))
          services.addDirectory(state, path.join(root, 'logs'), 'logs')
        services.addDirectory(state, path.join(root, 'debug'), 'debug')
        zip.writeZip(output)
        return { success: true }
      }),
  }
  for (const [method, creator] of Object.entries({
    exportMaaIssueReport: 'createMaaIssueReport',
    exportMaaEndIssueReport: 'createMaaEndIssueReport',
    exportMaaFWIssueReport: 'createMaaFWIssueReport',
    exportM9AIssueReport: 'createM9AIssueReport',
    exportMSSIssueReport: 'createMSSIssueReport',
    exportOkwwIssueReport: 'createOkwwIssueReport',
    exportOkNteIssueReport: 'createOkNteIssueReport',
    exportBetterGIIssueReport: 'createBetterGIIssueReport',
    exportZzzOdIssueReport: 'createZzzOdIssueReport',
    exportWhimboxIssueReport: 'createWhimboxIssueReport',
  })) {
    api[method] = scriptId =>
      exportZip(method.replace('export', ''), output =>
        services[creator](
          root,
          output,
          method === 'exportMaaEndIssueReport' ? `http://127.0.0.1:${backendPort}` : scriptId
        )
      )
  }
  return async function handle(req, res) {
    if (req.url !== '/__host/invoke') return false
    const send = (status, value) => {
      res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
      })
      res.end(JSON.stringify(value))
    }
    const origin = `http://${req.headers.host}`
    if (
      !/^127\.0\.0\.1:\d+$/.test(req.headers.host || '') ||
      (req.headers.origin && req.headers.origin !== origin)
    ) {
      send(403, { success: false, error: '拒绝跨站本机访问' })
      return true
    }
    if (req.method !== 'POST' || !req.headers['content-type']?.startsWith('application/json')) {
      send(405, { success: false, error: '仅接受 JSON POST 请求' })
      return true
    }
    try {
      let body = ''
      for await (const chunk of req) {
        body += chunk
        if (body.length > 1024 * 1024) throw new Error('请求内容过大')
      }
      const { method, args } = JSON.parse(body)
      if (!Object.hasOwn(api, method) || !Array.isArray(args))
        throw new Error(`浏览器宿主不支持此桌面操作：${method}`)
      const data = await api[method](...args)
      send(200, { success: true, data })
    } catch (error) {
      send(400, { success: false, error: error.message })
    }
    return true
  }
}
module.exports = { createBrowserHost }
