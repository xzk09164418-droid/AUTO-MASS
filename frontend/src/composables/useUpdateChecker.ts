import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { CancelablePromise, type UpdateCheckOut } from '@/api'
import type { ChangelogData } from '@/utils/changelog'
import { NETWORK_DISABLED_MESSAGE } from '@/utils/networkCapabilities'

// 保留页面消费的状态和方法，移除更新轮询、网络请求与更新提示音。
const updateVisible = ref(false)
const updateData = ref<ChangelogData>({})
const latestVersion = ref('')

export const requestUpdateCheck = (_forceCheck = false): CancelablePromise<UpdateCheckOut> =>
  new CancelablePromise(resolve =>
    resolve({
      code: 403,
      status: 'error',
      message: NETWORK_DISABLED_MESSAGE,
      if_need_update: false,
      latest_version: '',
      update_info: {},
    })
  )

export const readUpdatePauseState = async (): Promise<boolean> => true

export function useUpdateChecker() {
  const onUpdateConfirmed = () => {
    updateVisible.value = false
  }
  const showUpdateModal = (_data: ChangelogData, _version: string) => {
    message.info(NETWORK_DISABLED_MESSAGE)
  }
  const checkUpdate = async (silent = false, _forceCheck = false) => {
    if (!silent) message.info(NETWORK_DISABLED_MESSAGE)
  }
  const startPolling = async () => {}
  const stopPolling = () => {}
  return {
    updateVisible,
    updateData,
    latestVersion,
    showUpdateModal,
    checkUpdate,
    onUpdateConfirmed,
    startPolling,
    stopPolling,
    restartPolling: startPolling,
  }
}

export function useUpdateModal() {
  const { updateVisible, updateData, latestVersion, showUpdateModal, onUpdateConfirmed } =
    useUpdateChecker()
  return { updateVisible, updateData, latestVersion, showUpdateModal, onUpdateConfirmed }
}
