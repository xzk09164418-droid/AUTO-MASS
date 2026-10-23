// 启动状态由 Node 提供，Python 尚未监听时也能读取本轮日志。
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const terminalCodes = new RegExp(`${String.fromCharCode(27)}\\[[0-?]*[ -/]*[@-~]`, 'g')

function createStartupStatus(root, backendPort, launchError) {
  const files = ['app.log', 'backend-launcher.log'].map(name => {
    const file = path.join(root, 'debug', name)
    const stat = fs.existsSync(file) ? fs.statSync(file) : null
    return { file, position: stat?.size || 0, identity: stat?.ino, carry: '' }
  })
  const runId = `${Date.now()}-${process.pid}`
  let logs = []
  let pending = null
  async function read() {
    for (const state of files) {
      if (!fs.existsSync(state.file)) continue
      const stat = fs.statSync(state.file)
      if (stat.ino !== state.identity || stat.size < state.position) {
        state.position = 0
        state.carry = ''
        state.identity = stat.ino
      }
      const start = Math.max(state.position, stat.size - 16384)
      const buffer = Buffer.alloc(stat.size - start)
      const fd = fs.openSync(state.file, 'r')
      try {
        fs.readSync(fd, buffer, 0, buffer.length, start)
      } finally {
        fs.closeSync(fd)
      }
      const text = (start === state.position ? state.carry : '') + buffer.toString('utf8')
      const lines = text.split(/\r?\n/)
      state.carry = lines.pop().slice(-4096)
      state.position = stat.size
      // 标准流可能带终端颜色码；仅清理小窗展示，原日志和级别保持原样。
      logs = [...logs, ...lines.map(line => line.replace(terminalCodes, ''))].slice(-60)
    }
    const health = await new Promise(resolve => {
      const req = http.get(
        { host: '127.0.0.1', port: backendPort, path: '/api/core/health', timeout: 800 },
        res => {
          let body = ''
          res.on('data', chunk => {
            body += chunk
          })
          res.on('end', () => {
            try {
              resolve(res.statusCode === 200 ? JSON.parse(body) : null)
            } catch {
              resolve(null)
            }
          })
        }
      )
      req.on('error', () => resolve(null))
      req.on('timeout', () => {
        req.destroy()
        resolve(null)
      })
    })
    return {
      runId,
      coreReady: !!health?.ready,
      backgroundStatus: health?.backgroundStatus || 'starting',
      error: health?.backgroundError || launchError() || '',
      logs,
    }
  }
  return () => {
    if (!pending)
      pending = read().finally(() => {
        pending = null
      })
    return pending
  }
}

module.exports = { createStartupStatus }
