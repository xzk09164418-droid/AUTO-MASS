// 启动状态由 Node 提供，Python 尚未监听时也能读取本轮日志。
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const { StringDecoder } = require('node:string_decoder')
const terminalCodes = new RegExp(`${String.fromCharCode(27)}\\[[0-?]*[ -/]*[@-~]`, 'g')

function createStartupStatus(root, backendPort, launchError, expectedId) {
  const files = ['app.log', 'backend-launcher.log'].map(name => {
    const file = path.join(root, 'debug', name)
    const stat = fs.existsSync(file) ? fs.statSync(file) : null
    return {
      file,
      position: stat?.size || 0,
      identity: stat?.ino,
      carry: '',
      decoder: new StringDecoder('utf8'),
    }
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
        state.decoder = new StringDecoder('utf8')
        state.identity = stat.ino
      }
      if (stat.size === state.position) continue
      const start = Math.max(state.position, stat.size - 16384)
      const buffer = Buffer.alloc(stat.size - start)
      const file = await fs.promises.open(state.file, 'r')
      try {
        await file.read(buffer, 0, buffer.length, start)
      } finally {
        await file.close()
      }
      let offset = 0
      if (start !== state.position) {
        state.carry = ''
        state.decoder = new StringDecoder('utf8')
        // 限长截取可能落在汉字中间，跳过开头不完整的 UTF-8 字节。
        while (offset < buffer.length && (buffer[offset] & 0xc0) === 0x80) offset++
      }
      const text = state.carry + state.decoder.write(buffer.subarray(offset))
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
      coreReady: !!health?.ready && (!expectedId || health.instanceId === expectedId),
      backgroundStatus: health?.backgroundStatus || 'starting',
      error:
        health && expectedId && health.instanceId !== expectedId
          ? '端口上的后端不属于本安装实例'
          : health?.backgroundError || launchError() || '',
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
