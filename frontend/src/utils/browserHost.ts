import type { HostAPI } from '@/types/host'
import { invokeBrowserHost } from '@/composables/useBrowserHost'
import { chooseLocalPath } from './browserFilePicker'

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}

if (!window.hostAPI) {
  window.__AUTO_MAS_BROWSER_HOST__ = true
  document.documentElement.classList.add('browser-host')
  const listeners = new Map<string, Set<(value: unknown) => void>>()
  const changes = new BroadcastChannel('auto-mas.browser-host')
  const notify = (event: string, value?: unknown) =>
    listeners.get(event)?.forEach(callback => callback(value))
  changes.onmessage = event => notify(event.data.event, event.data.value)
  async function invoke<T>(key: string, args: unknown[]): Promise<T> {
    const result = await invokeBrowserHost<T>(key, ...args)
    const succeeded =
      typeof result !== 'object' ||
      result === null ||
      !('success' in result) ||
      result.success !== false
    if (succeeded) {
      const events =
        key === 'saveConfig'
          ? ['onThemeConfigChanged']
          : ['importAppearance', 'removeAppearance', 'installOnlineAppearance'].includes(key)
            ? ['onAppearanceChanged', 'onMascotChanged']
            : ['importMascot', 'removeMascot'].includes(key)
              ? ['onMascotChanged']
              : []
      for (const event of events) {
        notify(event, result)
        changes.postMessage({ event, value: result })
      }
    }
    return result
  }
  const browserMethods: Record<string, unknown> = {
    // 断线恢复只确保后端存在；不会先停止仍在执行任务的独立后端。
    backendRestart: () => invoke('backendStart', []),
    startBackend: () => invoke('backendStart', []),
    appQuit: async () => {
      await invoke('frontendStop', [])
      window.close()
    },
    isMacOS: false,
    getLogger: (name: string) =>
      Object.fromEntries(
        ['debug', 'info', 'warn', 'error'].map(level => [
          level,
          async (...args: unknown[]) => {
            const writer = console[level as 'debug' | 'info' | 'warn' | 'error']
            writer(`[${name}]`, ...args)
            // 由 Node 宿主统一写入北京时间；保留调用方原有级别。
            void invoke('writeFrontendLog', [
              level,
              name,
              args.map(arg => (arg instanceof Error ? arg.stack || arg.message : arg)),
            ]).catch(error => console.error('保存浏览器日志失败:', error))
          },
        ])
      ),
    getApiEndpoint: async (key: string) =>
      key === 'websocket'
        ? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
        : location.origin,
    selectFolder: () => chooseLocalPath(true),
    selectFile: async (filters: unknown[]) => {
      const selected = await chooseLocalPath(false, filters)
      return selected ? [selected] : []
    },
    windowFocus: async () => window.focus(),
    windowIsMaximized: async () => false,
    appRestart: async () => location.reload(),
    getWindowActivity: async () => (document.hidden ? 'background' : 'visible'),
    onWindowActivityChange: (callback: (state: string) => void) => {
      const listener = () => callback(document.hidden ? 'background' : 'visible')
      document.addEventListener('visibilitychange', listener)
      return () => document.removeEventListener('visibilitychange', listener)
    },
    openUrl: async (url: string) => {
      if (!/^https?:\/\//i.test(url)) throw new Error('仅支持 HTTP/HTTPS 链接')
      window.open(url, '_blank', 'noopener,noreferrer')
      return { success: true }
    },
    openLogWindow: async (file = 'app') => {
      window.open(`/#/logs?file=${encodeURIComponent(file)}`, '_blank', 'noopener,noreferrer')
      return { success: true }
    },
    backendStatus: async () => {
      const response = await fetch('/api/core/health')
      return { isRunning: response.ok, runtimeSupervised: false }
    },
    powerWarningStart: async () => window.focus(),
    powerWarningEnd: async () => undefined,
    exportDataBackup: async () => {
      const response = await fetch('/api/setting/backup')
      if (!response.ok) throw new Error(response.statusText)
      const filename = `AUTO-MAS-backup-${new Date().toISOString().slice(0, 10)}.zip`
      download(await response.blob(), filename)
      return { success: true, zipPath: filename }
    },
  }
  // 保留原版页面的接口类型；这里是 HTTP 浏览器适配器，不导入或启动 Electron。
  window.hostAPI = new Proxy(browserMethods, {
    get(target, key: string) {
      if (key in target) return target[key]
      // 原生窗口事件在浏览器中由浏览器管理，不注册桌面窗口或托盘。
      if (key.startsWith('on'))
        return (callback: (value: unknown) => void) => {
          if (!listeners.has(key)) listeners.set(key, new Set())
          listeners.get(key)!.add(callback)
          return () => listeners.get(key)?.delete(callback)
        }
      if (key.startsWith('remove') && key.endsWith('Listener')) return () => undefined
      if (key.startsWith('export'))
        return async (...args: unknown[]) => {
          const result = await invoke<{
            success: boolean
            filename?: string
            fileBase64?: string
          }>(key, args)
          if (result.success && result.filename && result.fileBase64) {
            const bytes = Uint8Array.from(atob(result.fileBase64), char => char.charCodeAt(0))
            download(new Blob([bytes], { type: 'application/zip' }), result.filename)
            delete result.fileBase64
          }
          return result
        }
      return (...args: unknown[]) => invoke(key, args)
    },
  }) as unknown as HostAPI
}
