const fs = require('node:fs')
const path = require('node:path')
const { spawn } = require('node:child_process')

// 运行在主桌面的 Node 宿主；后台任务在 RDP 中也不会把提示发到子桌面。
function startQueueControlNotices(root, port, instanceId, logs) {
  if (process.platform !== 'win32') return () => {}
  const seen = new Map()
  let stopped = false
  let timer
  const directory = path.join(root, 'data', 'queue-control-notices')
  const python = [
    path.join(root, 'python', 'python.exe'),
    path.join(root, '.venv', 'Scripts', 'python.exe'),
  ].find(fs.existsSync)
  async function poll() {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/dispatch/navigation/state`, {
        headers: { 'X-AUTO-MAS-Instance': instanceId },
        signal: AbortSignal.timeout(2000),
      })
      const result = await response.json()
      if (!response.ok || result.code !== 200) throw new Error(result.message || '后端未就绪')
      const { queues, controls } = result.data
      for (const control of controls) {
        const prompt = control.prompt
        if (!prompt || seen.get(control.taskId) === prompt.token) continue
        seen.set(control.taskId, prompt.token)
        if (!python) throw new Error('原生控制通知缺少 Python 运行时')
        fs.mkdirSync(directory, { recursive: true })
        const file = path.join(directory, `${control.taskId}.json`)
        fs.writeFileSync(
          file,
          JSON.stringify({
            ...prompt,
            port,
            instanceId,
            taskId: control.taskId,
            title: `${queues.find(q => q.id === control.queueId)?.name || 'AUTO-MAS'} · ${control.selectedTask}`,
            message: `${prompt.message}${prompt.deadline ? '\n30 秒到期仍保持暂停；点击跳过等待可尝试继续。' : ''}`,
          })
        )
        await new Promise((resolve, reject) => {
          const child = spawn(python, [path.join(root, 'scripts', 'control-toast.py'), file], {
            cwd: root,
            windowsHide: true,
            stdio: ['ignore', 'ignore', 'pipe'],
          })
          let error = ''
          child.stderr.on('data', data => {
            error += data.toString().slice(-2000)
          })
          child.once('error', error => reject(new Error(`原生控制通知发送失败：${error.message}`)))
          child.once('exit', code =>
            code === 0 ? resolve() : reject(new Error(`原生控制通知发送失败：${error || code}`))
          )
        })
      }
      const ids = new Set(controls.map(control => control.taskId))
      for (const id of seen.keys()) if (!ids.has(id)) seen.delete(id)
    } catch (error) {
      // 结果失败不会触发队列继续；顶部控制面板仍可使用。
      if (error.message?.includes('原生')) logs?.write('WARNING', '队列控制通知', error.message)
    } finally {
      if (!stopped) timer = setTimeout(poll, 500)
    }
  }
  void poll()
  return () => {
    stopped = true
    clearTimeout(timer)
  }
}
module.exports = { startQueueControlNotices }
