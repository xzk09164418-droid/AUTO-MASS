// 浏览器版运行日志与旧桌面日志分开保存，时间固定为北京时间。
const fs = require('node:fs')
const path = require('node:path')
const { format } = require('node:util')

function beijingTime(date = new Date()) {
  return new Date(date.getTime() + 8 * 3600000).toISOString().replace('T', ' ').replace('Z', '')
}

function createRuntimeLogs(root, reader) {
  const directory = path.join(root, 'debug')
  const archiveDirectory = path.join(directory, 'log-archive')
  fs.mkdirSync(archiveDirectory, { recursive: true })
  const startedAt = beijingTime()
  const stamp = startedAt.replace(/[: .]/g, '-')
  const frontendPath = path.join(directory, 'node-frontend.log')
  for (const [file, kind] of [
    [path.join(root, 'logs', 'frontend.log'), 'legacy-electron-logs'],
    [path.join(directory, 'frontend.log'), 'legacy-electron-debug'],
    [frontendPath, 'node-frontend'],
  ]) {
    if (fs.existsSync(file)) {
      fs.renameSync(file, path.join(archiveDirectory, `${kind}-${stamp}-${process.pid}.log`))
    }
  }
  fs.writeFileSync(frontendPath, '')
  const write = (level, module, ...args) => {
    if (!['DEBUG', 'INFO', 'WARNING', 'ERROR'].includes(level)) throw new Error('无效的日志级别')
    const text = format(...args)
    fs.appendFileSync(frontendPath, `${beijingTime()} | ${level.padEnd(8)} | ${module} | ${text}\n`)
  }
  write('INFO', 'Node 前端', `本次启动时间: ${startedAt} 北京时间 (UTC+08:00)，PID: ${process.pid}`)
  write('INFO', 'Node 前端', `Node版本: ${process.versions.node}，前后端分离浏览器模式`)

  let backendPosition = 0
  let backendBoundary = 0
  let backendStartedAt = ''
  let backendIdentity = ''
  let carry = ''
  let initialScan = true
  const backendPath = path.join(directory, 'app.log')
  async function scanBackend() {
    if (!fs.existsSync(backendPath)) {
      backendPosition = backendBoundary = 0
      backendStartedAt = backendIdentity = carry = ''
      initialScan = true
      return
    }
    const stat = fs.statSync(backendPath)
    const identity = `${stat.dev}:${stat.ino}:${stat.birthtimeMs}`
    if (identity !== backendIdentity || stat.size < backendPosition) {
      backendPosition = backendBoundary = 0
      backendStartedAt = carry = ''
      backendIdentity = identity
      initialScan = true
    }
    const delta = await reader.readLogIncrement(backendPath, backendPosition)
    const text = carry + delta.content
    const base = backendPosition - Buffer.byteLength(carry)
    const matches = [
      ...text.matchAll(
        /^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})[^\n]*\| 配置管理 \| AUTO-MAS 后端应用程序\r?$/gm
      ),
    ]
    if (matches.length) {
      const match = matches.at(-1)
      backendBoundary = base + Buffer.byteLength(text.slice(0, match.index))
      backendStartedAt = match[1]
    }
    backendPosition = delta.size
    carry = Array.from(text).slice(-4096).join('')
    if ((initialScan || matches.length) && backendBoundary > 0) {
      const archive = path.join(
        archiveDirectory,
        `backend-before-${backendStartedAt.replace(/[: .]/g, '-')}-${backendBoundary}.log`
      )
      if (!fs.existsSync(archive)) {
        const buffer = Buffer.alloc(backendBoundary)
        const fd = fs.openSync(backendPath, 'r')
        try {
          fs.readSync(fd, buffer, 0, buffer.length, 0)
        } finally {
          fs.closeSync(fd)
        }
        fs.writeFileSync(archive, buffer, { flag: 'wx' })
      }
    }
    initialScan = false
  }
  let backendScan = Promise.resolve()

  async function read(selection = 'app', offset = 0, sourceId = '') {
    if (!Number.isSafeInteger(offset) || offset < 0) throw new Error('无效的日志读取位置')
    let file,
      boundary = 0,
      start = startedAt,
      label
    if (selection === 'frontend') {
      file = frontendPath
      label = 'Node 前端 · 本次运行'
    } else if (selection === 'app') {
      backendScan = backendScan.then(scanBackend, scanBackend)
      await backendScan
      file = backendPath
      boundary = backendBoundary
      start = backendStartedAt
      label = 'Python 后端 · 最近一次启动'
    } else {
      if (!/^archive:[\w.-]+\.log$/.test(selection)) throw new Error('无效的归档日志')
      file = path.join(archiveDirectory, selection.slice(8))
      if (!fs.existsSync(file)) throw new Error('归档日志不存在')
      label = selection.includes('legacy-electron')
        ? '旧版 Electron 日志（归档）'
        : '历史运行日志（归档）'
      start = ''
    }
    const stat = fs.existsSync(file) ? fs.statSync(file) : null
    const id = `${selection}:${stat?.ino}:${stat?.birthtimeMs}:${boundary}`
    const changed = id !== sourceId
    const delta = await reader.readLogIncrement(file, boundary + (changed ? 0 : offset))
    return {
      ...delta,
      size: Math.max(0, delta.size - boundary),
      reset: changed || delta.reset,
      sourceId: id,
      source: label,
      startedAt: start,
      timeZone: 'Asia/Shanghai (UTC+08:00)',
    }
  }
  return {
    write,
    read,
    list: () =>
      fs
        .readdirSync(archiveDirectory)
        .filter(name => name.endsWith('.log'))
        .sort()
        .reverse()
        .map(name => ({
          value: `archive:${name}`,
          label: `${name.startsWith('legacy-electron') ? '旧版 Electron' : '历史运行'} · ${name}`,
        })),
  }
}

module.exports = { createRuntimeLogs, beijingTime }
