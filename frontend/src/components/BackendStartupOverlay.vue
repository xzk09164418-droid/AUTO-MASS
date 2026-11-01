<template>
  <Teleport to="body">
    <section v-if="visible" class="backend-startup-panel" :aria-label="t('launch.statusLabel')">
      <div class="startup-heading">
        <strong>{{
          error ? t('launch.failed') : coreReady ? t('launch.coreReady') : t('launch.starting')
        }}</strong>
        <a-button type="link" size="small" @click="collapsed = !collapsed">{{
          collapsed ? t('launch.expandLogs') : t('launch.collapseLogs')
        }}</a-button>
      </div>
      <div v-if="error" role="alert">{{ error }}</div>
      <pre v-if="!collapsed" class="startup-logs" role="log">{{
        logs || t('launch.waitingLogs')
      }}</pre>
      <a-space>
        <a-button type="link" size="small" @click="openLaunchLogWindow('后端启动面板')">{{
          t('launch.viewLog')
        }}</a-button>
        <a-button v-if="error" size="small" :loading="isBootstrapping" @click="retry">{{
          t('launch.reconnect')
        }}</a-button>
      </a-space>
    </section>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppInitialization } from '@/composables/useAppInitialization'
import { resumeStartupConnection } from '@/composables/useAppLifecycle'
import { openLaunchLogWindow } from '@/utils/launch'
import { startSkippedInitializationStartup } from '@/utils/skippedInitializationStartup'

defineOptions({ name: 'BackendStartupOverlay' })
const emit = defineEmits<{
  status: [state: { coreReady: boolean; progress: number; error: string; label: string }]
}>()
const { t } = useI18n()
const { isInitialized, isBootstrapping, startupError } = useAppInitialization()
const coreReady = ref(false)
const progress = ref(10)
const complete = ref(false)
const statusError = ref('')
const logs = ref('')
const collapsed = ref(false)
const error = computed(() => startupError.value || statusError.value)
const visible = computed(
  () =>
    window.__AUTO_MAS_BROWSER_HOST__ &&
    ((coreReady.value && (!complete.value || !isInitialized.value)) || !!error.value)
)
const needsPolling = computed(() => !complete.value || !isInitialized.value || !!error.value)
const STARTUP_POLL_INTERVAL_MS = 1000
const FAST_STARTUP_POLL_INTERVAL_MS = 100
const FAST_STARTUP_POLL_WINDOW_MS = 5000
let fastPollUntil = performance.now() + FAST_STARTUP_POLL_WINDOW_MS
let disposed = false
let polling = false
let refreshRequested = false
let timer: ReturnType<typeof setTimeout> | undefined

async function poll() {
  if (disposed || !window.__AUTO_MAS_BROWSER_HOST__) return
  if (polling) {
    refreshRequested = true
    return
  }
  polling = true
  clearTimeout(timer)
  try {
    const state = await window.hostAPI.getStartupStatus()
    if (disposed) return
    const becameReady = state.coreReady && !coreReady.value
    coreReady.value = state.coreReady
    progress.value = state.progress ?? (state.coreReady ? 70 : state.backendReachable ? 40 : 10)
    complete.value = state.backgroundStatus === 'ready'
    statusError.value = state.error
    logs.value = state.logs.slice(-20).join('\n')
    if (becameReady) resumeStartupConnection()
  } catch (cause) {
    if (!disposed) statusError.value = t('launch.statusUnavailable', { detail: String(cause) })
  } finally {
    polling = false
    if (!disposed)
      emit('status', {
        coreReady: coreReady.value,
        progress: progress.value,
        error: error.value,
        label: logs.value.split('\n').filter(Boolean).at(-1) || '',
      })
    // 启动前几秒及时发现就绪；失败或长时间未完成时恢复低频检查。
    let delay = STARTUP_POLL_INTERVAL_MS
    if (!error.value && performance.now() < fastPollUntil) delay = FAST_STARTUP_POLL_INTERVAL_MS
    if (refreshRequested) delay = 0
    refreshRequested = false
    if (!disposed && needsPolling.value) timer = setTimeout(poll, delay)
  }
}

// WebSocket 初始化完成后立即核对后台状态，不额外等待下一轮轮询。
watch(
  isInitialized,
  initialized => {
    if (initialized && needsPolling.value) void poll()
  },
  { immediate: true }
)

function retry() {
  statusError.value = ''
  fastPollUntil = performance.now() + FAST_STARTUP_POLL_WINDOW_MS
  void startSkippedInitializationStartup()
}

if (window.__AUTO_MAS_BROWSER_HOST__) void poll()
onUnmounted(() => {
  disposed = true
  clearTimeout(timer)
})
</script>

<style scoped>
.backend-startup-panel {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9998;
  width: min(480px, calc(100vw - 32px));
  padding: 16px;
  border: 1px solid var(--ant-color-border-secondary);
  border-radius: 8px;
  color: var(--ant-color-text);
  background: var(--ant-color-bg-elevated);
  box-shadow: var(--ant-box-shadow-secondary);
}
.startup-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.startup-logs {
  max-height: 220px;
  overflow: auto;
  margin: 8px 0;
  color: var(--ant-color-text-secondary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 12px;
}
</style>
