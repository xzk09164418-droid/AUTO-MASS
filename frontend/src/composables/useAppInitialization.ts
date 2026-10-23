import { computed, ref } from 'vue'

const logger = window.hostAPI.getLogger('应用初始化')

const isInitialized = ref(false)
const isBootstrapping = ref(false)
// 页面框架可以先显示，业务请求必须等后端连接完成。
const isUiReady = computed(
  () => isInitialized.value || isBootstrapping.value || !!startupError.value
)
const isAppReady = computed(() => isInitialized.value)
const startupError = ref('')

export function markAsInitialized() {
  startupError.value = ''
  isInitialized.value = true
  isBootstrapping.value = false
  logger.info('应用已标记为初始化完成')
}

export function beginBootstrap() {
  startupError.value = ''
  isBootstrapping.value = true
  logger.info('应用启动过渡状态已开启')
}

export function finishBootstrap() {
  isBootstrapping.value = false
  logger.info('应用启动过渡状态已结束')
}

export function resetInitializationStatus() {
  isInitialized.value = false
  isBootstrapping.value = false
  logger.info('应用初始化状态已重置')
}

export function useAppInitialization() {
  return {
    isInitialized,
    isBootstrapping,
    isAppReady,
    isUiReady,
    startupError,
    markAsInitialized,
    beginBootstrap,
    finishBootstrap,
    resetInitializationStatus,
  }
}
