import { ref } from 'vue'
import { Service, type ExternalControlSettingsIn, type ExternalControlSnapshotOut } from '@/api'

/** 页面只管理交互；接口错误在这里统一处理，不用成功 HTTP 状态掩盖业务失败。 */
export function useExternalControl() {
  const snapshot = ref<ExternalControlSnapshotOut>()
  const schemas = ref<Record<string, unknown>>({})
  const loading = ref(false)
  const error = ref('')
  const backendUrl = ref('')

  async function run<T>(operation: () => Promise<T>): Promise<T> {
    loading.value = true
    error.value = ''
    try {
      return await operation()
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '外部控制操作失败'
      throw reason
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    return run(async () => {
      const result = await Service.getExternalControlSnapshotApiDispatchExternalHoldsManagementGet()
      if (result.code !== 200) throw new Error(result.message)
      snapshot.value = result
      if (!Object.keys(schemas.value).length) {
        const contract =
          await Service.getExternalControlContractApiDispatchExternalHoldsContractGet()
        if (contract.code !== 200) throw new Error(contract.message)
        schemas.value = contract.schemas || {}
        backendUrl.value = contract.backendUrl || ''
      }
    })
  }

  async function save(settings: ExternalControlSettingsIn) {
    await run(async () => {
      const result =
        await Service.saveExternalControlSettingsApiDispatchExternalHoldsSettingsPost(settings)
      if (result.code !== 200) throw new Error(result.message)
    })
    await refresh()
  }

  async function release(callerId: string, holdId: string) {
    await run(async () => {
      const result = await Service.forceReleaseExternalHoldApiDispatchExternalHoldsForceReleasePost(
        { callerId, holdId }
      )
      if (result.code !== 200) throw new Error(result.message)
    })
    await refresh()
  }

  async function testMail() {
    return run(async () => {
      const result = await Service.testExternalMailConnectionApiDispatchExternalHoldsMailTestPost()
      if (result.code !== 200) throw new Error(result.message)
      return result.message
    })
  }

  return { snapshot, schemas, backendUrl, loading, error, refresh, save, release, testMail }
}
