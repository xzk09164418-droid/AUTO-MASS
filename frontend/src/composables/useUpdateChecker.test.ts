import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { NETWORK_DISABLED_MESSAGE } from '@/utils/networkCapabilities'

const getSettingsMock = vi.fn()
vi.mock('@/api', async importOriginal => ({
  ...(await importOriginal<typeof import('@/api')>()),
  Service: {
    checkUpdateApiUpdateCheckPost: vi.fn(),
    getScriptsApiSettingGetPost: (...args: unknown[]) => getSettingsMock(...args),
  },
}))
vi.mock('ant-design-vue', () => ({
  message: { info: vi.fn() },
}))

const { useUpdateChecker, requestUpdateCheck } = await import('./useUpdateChecker')
const { Service } = await import('@/api')
const { message } = await import('ant-design-vue')

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  vi.spyOn(globalThis, 'setInterval')
  vi.spyOn(globalThis, 'setTimeout')
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('useUpdateChecker · 本构建禁用更新', () => {
  it('并发启动、停止和重新启动均不建立轮询或读取设置', async () => {
    const checker = useUpdateChecker()
    await Promise.all([checker.startPolling(), checker.startPolling()])
    checker.stopPolling()
    await checker.restartPolling()
    expect(setInterval).not.toHaveBeenCalled()
    expect(setTimeout).not.toHaveBeenCalled()
    expect(getSettingsMock).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(8 * 60 * 60 * 1000)
    expect(Service.checkUpdateApiUpdateCheckPost).not.toHaveBeenCalled()
  })

  it('手动强制检查只提示禁用，不请求更新', async () => {
    await useUpdateChecker().checkUpdate(false, true)
    expect(message.info).toHaveBeenCalledWith(NETWORK_DISABLED_MESSAGE)
    expect(Service.checkUpdateApiUpdateCheckPost).not.toHaveBeenCalled()
  })

  it('静默检查不联网也不提示', async () => {
    await useUpdateChecker().checkUpdate(true)
    expect(message.info).not.toHaveBeenCalled()
    expect(Service.checkUpdateApiUpdateCheckPost).not.toHaveBeenCalled()
  })

  it('请求入口返回明确的禁用结果', async () => {
    await expect(requestUpdateCheck(true)).resolves.toMatchObject({
      code: 403,
      if_need_update: false,
      message: NETWORK_DISABLED_MESSAGE,
    })
    expect(Service.checkUpdateApiUpdateCheckPost).not.toHaveBeenCalled()
  })

  it('不能通过更新弹窗绕过禁用边界', () => {
    const checker = useUpdateChecker()
    checker.showUpdateModal({}, 'v5.5.0')
    expect(checker.updateVisible.value).toBe(false)
    expect(message.info).toHaveBeenCalledWith(NETWORK_DISABLED_MESSAGE)
  })
})
