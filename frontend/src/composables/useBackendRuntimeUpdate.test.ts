import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { NETWORK_DISABLED_MESSAGE } from '@/utils/networkCapabilities'

// ==================== 全局桩 ====================

const logger = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() }

const beginWindow = vi.fn()
const endWindow = vi.fn()

vi.mock('@/composables/useAppLifecycle', () => ({
  beginIntentionalBackendRestart: (reason: string) => beginWindow(reason),
  endIntentionalBackendRestart: (reason: string) => endWindow(reason),
}))

vi.mock('@/services/websocket/connection', () => ({
  reconnectNow: vi.fn(async () => true),
}))

vi.mock('./useVersionService', () => ({
  getBackendVersion: vi.fn(async () => undefined),
}))

const updateBackendViaRuntime = vi.fn()
const retryBackendUpdate = vi.fn()

const loadModule = async () => {
  vi.resetModules()
  const mod = await import('./useBackendRuntimeUpdate')
  return mod.useBackendRuntimeUpdate()
}

describe('useBackendRuntimeUpdate · 本构建禁用更新', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('window', {
      hostAPI: {
        getLogger: () => logger,
        updateBackendViaRuntime,
        retryBackendUpdate,
        onBackendUpdateProgress: vi.fn(),
        removeBackendUpdateProgressListener: vi.fn(),
      },
    })
  })

  it('拒绝安装更新，不调用 IPC 或开启后端重启窗口', async () => {
    const runtimeUpdate = await loadModule()
    await expect(runtimeUpdate.start('v5.5.0')).rejects.toThrow(NETWORK_DISABLED_MESSAGE)
    expect(updateBackendViaRuntime).not.toHaveBeenCalled()
    expect(beginWindow).not.toHaveBeenCalled()
    expect(endWindow).not.toHaveBeenCalled()
  })

  it('拒绝单步重试，不调用 IPC 或开启后端重启窗口', async () => {
    const runtimeUpdate = await loadModule()
    await expect(runtimeUpdate.retry('workspace-sync')).rejects.toThrow(NETWORK_DISABLED_MESSAGE)
    expect(retryBackendUpdate).not.toHaveBeenCalled()
    expect(beginWindow).not.toHaveBeenCalled()
    expect(endWindow).not.toHaveBeenCalled()
  })
})
