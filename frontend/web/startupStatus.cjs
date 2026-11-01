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
  let coreCompleted = false
  const completedSteps = new Set()
  const coreSteps = [
    '本地远程桌面分身',
    '桌面显示输出守卫',
    '全局热键服务',
    '通知渠道',
    '活动关卡信息获取',
    '主业务定时器',
  ]
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
      const cleanLines = lines.map(line => line.replace(terminalCodes, ''))
      // 仅消费本轮 MAS 自身的明确完成事件，API 可响应不等于核心初始化完成。
      for (const line of cleanLines) {
        if (line.includes('后端核心服务已就绪，继续配置按需服务入口')) coreCompleted = true
        for (const step of coreSteps) {
          if (line.includes(`后台初始化步骤结束: ${step}，`)) completedSteps.add(step)
        }
      }
      logs = [...logs, ...cleanLines].slice(-60)
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
    const reachable = !!health?.ready && (!expectedId || health.instanceId === expectedId)
    if (!reachable) {
      coreCompleted = false
      completedSteps.clear()
    }
    const coreReady = reachable && (coreCompleted || health.backgroundStatus === 'ready')
    let recoveryError = ''
    if (!reachable) {
      try {
        const recovery = JSON.parse(
          await fs.promises.readFile(path.join(root, 'data/desktop_recovery/control.json'), 'utf8')
        )
        if (recovery.phase === 'paused')
          recoveryError =
            '远程桌面恢复已暂停，后端尚未启动。可通过托盘“强制重启 MAS（清空运行状态）”放弃旧进度并重新启动；普通启动不会解除暂停。'
      } catch (error) {
        if (error.code !== 'ENOENT') recoveryError = '无法读取远程桌面恢复状态，请检查恢复记录。'
      }
    }
    return {
      runId,
      progress: coreReady
        ? 70
        : reachable
          ? 20 + Math.round((completedSteps.size / coreSteps.length) * 40)
          : 10,
      backendReachable: !!health && (!expectedId || health.instanceId === expectedId),
      coreReady,
      backgroundStatus: health?.backgroundStatus || 'starting',
      error:
        health && expectedId && health.instanceId !== expectedId
          ? '端口上的后端不属于本安装实例'
          : recoveryError || health?.backgroundError || launchError() || '',
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
