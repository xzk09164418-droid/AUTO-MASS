// 安装实例的唯一端口配置源；托盘和 Node 启动器共用选择、持久化和归属核验。
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const http = require('node:http')
const net = require('node:net')
const { execFile } = require('node:child_process')
const DEFAULT_PORTS = require('../../res/host-instance-defaults.json')

function instanceId(root) {
  const canonical = fs.realpathSync(root).replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
  return crypto.createHash('sha256').update(canonical, 'utf8').digest('hex')
}

function readJson(host, port, endpoint, timeout = 1500) {
  return new Promise(resolve => {
    const request = http.get({ host, port, path: endpoint, timeout }, response => {
      let body = ''
      response.on('data', chunk => {
        body += chunk
        if (body.length > 65536) request.destroy()
      })
      response.on('end', () => {
        try {
          resolve(response.statusCode === 200 ? JSON.parse(body) : null)
        } catch {
          resolve(null)
        }
      })
      response.on('error', () => resolve(null))
    })
    request.on('error', () => resolve(null))
    request.on('timeout', () => {
      request.destroy()
      resolve(null)
    })
  })
}

async function ownsService(host, port, endpoint, expectedId) {
  const data = await readJson(host, port, endpoint)
  return !!data && data.instanceId === expectedId && data.ready !== false
}

function portAvailable(port) {
  return new Promise(resolve => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.listen({ host: '127.0.0.1', port, exclusive: true }, () =>
      server.close(() => resolve(true))
    )
  })
}

async function suggestPort(excluded) {
  for (let attempt = 0; attempt < 8; attempt++) {
    const port = await new Promise((resolve, reject) => {
      const server = net.createServer()
      server.once('error', reject)
      server.listen({ host: '127.0.0.1', port: 0, exclusive: true }, () => {
        const selected = server.address().port
        server.close(() => resolve(selected))
      })
    })
    if (!excluded.has(port)) return port
  }
  throw new Error('没有找到可用的本机端口')
}

function confirmPortChange(conflicts) {
  if (process.platform !== 'win32')
    throw new Error('端口被占用，请通过 --port 和 --backend-port 指定可用端口')
  const text =
    conflicts
      .map(item => `${item.label} ${item.port} 已被其他程序占用，建议改用 ${item.recommended}。`)
      .join('\n') + '\n是否保存新端口并继续启动？选择“否”取消本次启动。'
  const encodedText = Buffer.from(text, 'utf8').toString('base64')
  const script = `Add-Type -AssemblyName System.Windows.Forms; $message = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('${encodedText}')); $choice = [Windows.Forms.MessageBox]::Show($message, 'AUTO-MAS 端口冲突', [Windows.Forms.MessageBoxButtons]::YesNo, [Windows.Forms.MessageBoxIcon]::Question, [Windows.Forms.MessageBoxDefaultButton]::Button2); if ($choice -eq [Windows.Forms.DialogResult]::Yes) { exit 0 } else { exit 3 }`
  return new Promise((resolve, reject) => {
    execFile(
      'powershell.exe',
      [
        '-NoProfile',
        '-NonInteractive',
        '-EncodedCommand',
        Buffer.from(script, 'utf16le').toString('base64'),
      ],
      { windowsHide: true },
      error => {
        if (!error) resolve(true)
        else if (error.code === 3) resolve(false)
        else reject(error)
      }
    )
  })
}

function validPort(value) {
  const port = Number(value)
  if (!Number.isInteger(port) || port < 1024 || port > 65535)
    throw new Error('端口必须为 1024～65535 的整数')
  return port
}

async function resolveInstance(root, args = [], options = {}) {
  const filename = path.join(root, 'config', 'HostInstance.json')
  const stored = fs.existsSync(filename) ? JSON.parse(fs.readFileSync(filename, 'utf8')) : {}
  const env = options.env ?? process.env
  const config = {
    instanceId: instanceId(root),
    frontendPort: validPort(
      env.AUTO_MAS_FRONTEND_PORT ?? stored.frontendPort ?? DEFAULT_PORTS.frontendPort
    ),
    backendPort: validPort(
      env.AUTO_MAS_HTTP_PORT ?? stored.backendPort ?? DEFAULT_PORTS.backendPort
    ),
  }
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--port' || args[i] === '-p') config.frontendPort = validPort(args[++i])
    else if (args[i] === '--backend-port') config.backendPort = validPort(args[++i])
  }
  const confirm = options.confirm ?? confirmPortChange
  for (let attempt = 0; attempt < 3; attempt++) {
    const conflicts = []
    const excluded = new Set([config.frontendPort, config.backendPort])
    for (const [key, endpoint, label] of [
      ['frontendPort', '/__frontend_config', '页面端口'],
      ['backendPort', '/api/core/health', '后端端口'],
    ]) {
      const port = config[key]
      const duplicate = key === 'backendPort' && config.frontendPort === port
      const running = await readJson('127.0.0.1', port, endpoint)
      const owned =
        running?.instanceId === config.instanceId &&
        running.ready !== false &&
        (key !== 'frontendPort' || running.backendPort === config.backendPort)
      if (!duplicate && (owned || (await portAvailable(port)))) continue
      const recommended = await suggestPort(excluded)
      excluded.add(recommended)
      conflicts.push({ key, label, port, recommended })
    }
    if (!conflicts.length) {
      fs.mkdirSync(path.dirname(filename), { recursive: true })
      const temporary = `${filename}.${process.pid}.tmp`
      fs.writeFileSync(temporary, JSON.stringify(config, null, 2))
      fs.renameSync(temporary, filename)
      return config
    }
    if (!(await confirm(conflicts))) return { cancelled: true }
    for (const conflict of conflicts) config[conflict.key] = conflict.recommended
  }
  throw new Error('推荐端口再次被占用，请稍后重新启动')
}

module.exports = {
  DEFAULT_PORTS,
  instanceId,
  ownsService,
  portAvailable,
  readJson,
  resolveInstance,
}
if (require.main === module) {
  resolveInstance(path.resolve(__dirname, '../..'), process.argv.slice(2))
    .then(result => process.stdout.write(JSON.stringify(result)))
    .catch(error => {
      process.stderr.write(error.message)
      process.exitCode = 1
    })
}
