<template>
  <Teleport to="body">
    <Transition name="rhine-boot">
      <div v-if="visible" class="rhine-boot-layer" :class="{ 'is-blocking': blocking }">
        <section
          class="rhine-boot-panel"
          :class="{ 'is-error': !!error }"
          :aria-label="t('launch.statusLabel')"
        >
          <header class="boot-head">
            <span class="boot-serial" aria-hidden="true">{{ error ? 'X-ERR' : 'X-000' }}</span>
            <div class="boot-title-group">
              <span class="boot-kicker" aria-hidden="true">{{
                error ? 'SYSTEM // CONNECTION INTERRUPTED' : 'SYSTEM // BOOT SEQUENCE'
              }}</span>
              <strong class="boot-title">{{
                error
                  ? t('launch.failed')
                  : coreReady
                    ? t('launch.coreReady')
                    : t('launch.starting')
              }}</strong>
            </div>
            <span v-if="!error" class="boot-progress-value" aria-hidden="true"
              >{{ progressPercent }}%</span
            >
          </header>

          <div
            v-if="!error"
            class="boot-progress"
            role="progressbar"
            :aria-valuenow="progressPercent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <i
              v-for="tick in PROGRESS_TICKS"
              :key="tick"
              :class="{ 'is-on': tick <= filledTicks }"
              aria-hidden="true"
            ></i>
          </div>

          <div v-if="error" class="boot-error" role="alert">
            <span class="boot-error-mark" aria-hidden="true">!</span>
            <span class="boot-error-text">{{ error }}</span>
          </div>

          <div class="boot-log-head">
            <span aria-hidden="true">LOG // TAIL {{ logLines.length }}</span>
            <button type="button" class="boot-link" @click="collapsed = !collapsed">
              {{ collapsed ? t('launch.expandLogs') : t('launch.collapseLogs') }}
            </button>
          </div>
          <div v-if="!collapsed" class="boot-logs" role="log">
            <template v-if="logLines.length">
              <div
                v-for="(line, index) in logLines"
                :key="index"
                class="boot-log-line"
                :class="`level-${line.level}`"
              >
                {{ line.text }}
              </div>
            </template>
            <div v-else class="boot-log-line level-info">{{ t('launch.waitingLogs') }}</div>
          </div>

          <footer class="boot-actions">
            <a-button size="small" @click="openLaunchLogWindow('后端启动面板')">{{
              t('launch.viewLog')
            }}</a-button>
            <a-button
              v-if="error"
              type="primary"
              size="small"
              :loading="isBootstrapping"
              @click="retry"
              >{{ t('launch.reconnect') }}</a-button
            >
          </footer>
        </section>
      </div>
    </Transition>
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
// 主界面尚未进入时出错，背后只有空白页：改为居中故障面板并遮住空白；已进入时仍停靠右上角不打断操作
const blocking = computed(() => !!error.value && !isInitialized.value)

const PROGRESS_TICKS = Array.from({ length: 24 }, (_, index) => index + 1)
const progressPercent = computed(() => Math.max(0, Math.min(100, Math.round(progress.value))))
const filledTicks = computed(() =>
  Math.round((progressPercent.value / 100) * PROGRESS_TICKS.length)
)

type LogLevel = 'debug' | 'info' | 'success' | 'warning' | 'error'
const LOG_LEVEL_PATTERN = /\|\s*(DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|/
// 按日志级别着色，便于在故障面板里一眼找到警告和错误行
const logLines = computed(() =>
  logs.value
    .split('\n')
    .filter(Boolean)
    .map(text => {
      const matched = LOG_LEVEL_PATTERN.exec(text)?.[1]
      const level: LogLevel =
        matched === 'CRITICAL'
          ? 'error'
          : ((matched?.toLowerCase() as LogLevel | undefined) ?? 'info')
      return { text, level }
    })
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
/* 默认：停靠在顶栏下方右侧，不遮挡导航 */
.rhine-boot-layer {
  position: fixed;
  top: 76px;
  right: 24px;
  z-index: 9998;
  width: min(500px, calc(100vw - 32px));
  pointer-events: none;
}

/* 主界面未进入且出错：全屏磨砂遮罩 + 居中故障面板 */
.rhine-boot-layer.is-blocking {
  inset: 0;
  width: auto;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--app-rhine-modal-backdrop);
  backdrop-filter: blur(10px);
}

.rhine-boot-panel {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px 16px;
  color: var(--ant-color-text);
  background: var(--ant-color-bg-elevated);
  border: 1px solid var(--app-rhine-hairline);
  border-top: 2px solid var(--app-rhine-rule);
  box-shadow: 0 24px 60px -30px rgba(8, 10, 8, 0.45);
  background-image: linear-gradient(var(--app-rhine-accent), var(--app-rhine-accent));
  background-size: 40px 2px;
  background-position: 0 0;
  background-repeat: no-repeat;
}

.is-blocking .rhine-boot-panel {
  width: min(720px, 100%);
  padding: 28px 32px 24px;
  gap: 16px;
}

.rhine-boot-panel.is-error {
  background-image: linear-gradient(var(--ant-color-error), var(--ant-color-error));
}

/* ── 抬头 ─────────────────────────────────────────────────────────────── */
.boot-head {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ant-color-border-secondary);
}

.boot-serial {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--app-rhine-accent);
  padding-bottom: 4px;
  font-variant-numeric: tabular-nums;
  user-select: none;
}

.is-error .boot-serial {
  color: var(--ant-color-error);
}

.is-blocking .boot-serial {
  font-size: 30px;
  line-height: 1;
  font-weight: 700;
  padding-bottom: 2px;
}

.boot-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.boot-kicker {
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

.boot-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.is-blocking .boot-title {
  font-size: 22px;
}

.boot-progress-value {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  padding-bottom: 2px;
}

/* ── 进度刻度 ─────────────────────────────────────────────────────────── */
.boot-progress {
  display: grid;
  grid-template-columns: repeat(24, 1fr);
  gap: 3px;
  height: 10px;
}

.boot-progress i {
  display: block;
  background: var(--ant-color-border-secondary);
  transition: background-color 0.3s ease;
}

.boot-progress i.is-on {
  background: var(--app-rhine-accent);
}

/* ── 错误信息 ─────────────────────────────────────────────────────────── */
.boot-error {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--ant-color-error-border);
  border-left: 3px solid var(--ant-color-error);
  background: var(--ant-color-error-bg);
}

.boot-error-mark {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  color: var(--ant-color-bg-elevated);
  background: var(--ant-color-error);
}

.boot-error-text {
  font-size: 14px;
  line-height: 20px;
  overflow-wrap: anywhere;
}

/* ── 日志 ─────────────────────────────────────────────────────────────── */
.boot-log-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--app-rhine-muted-index);
}

.boot-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--app-rhine-accent);
  font: inherit;
  font-size: 12px;
  letter-spacing: 0.04em;
  cursor: pointer;
}

.boot-link:hover {
  text-decoration: underline;
}

.boot-link:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: 2px;
}

.boot-logs {
  max-height: 220px;
  overflow: auto;
  padding: 8px 0;
  border-top: 1px solid var(--app-rhine-hairline);
  border-bottom: 1px solid var(--app-rhine-hairline);
  font-family: var(--app-rhine-font-mono);
  font-size: 11.5px;
  line-height: 18px;
}

.is-blocking .boot-logs {
  max-height: min(320px, 40vh);
}

.boot-log-line {
  padding: 1px 8px;
  border-left: 2px solid transparent;
  color: var(--ant-color-text-secondary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.boot-log-line.level-debug {
  color: var(--ant-color-text-tertiary);
}

.boot-log-line.level-success {
  color: var(--ant-color-success);
}

.boot-log-line.level-warning {
  color: var(--ant-color-warning);
  border-left-color: var(--ant-color-warning);
}

.boot-log-line.level-error {
  color: var(--ant-color-error);
  border-left-color: var(--ant-color-error);
  background: var(--ant-color-error-bg);
}

/* ── 操作 ─────────────────────────────────────────────────────────────── */
.boot-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* PV 弹窗节奏：300ms 入场、200ms 退出，位移 12px / 8px */
.rhine-boot-enter-active {
  transition: opacity 0.3s ease;
}

.rhine-boot-leave-active {
  transition: opacity 0.2s ease;
}

.rhine-boot-enter-active .rhine-boot-panel {
  transition: transform 0.3s cubic-bezier(0.2, 0.9, 0.3, 1);
}

.rhine-boot-leave-active .rhine-boot-panel {
  transition: transform 0.2s ease;
}

.rhine-boot-enter-from,
.rhine-boot-leave-to {
  opacity: 0;
}

.rhine-boot-enter-from .rhine-boot-panel {
  transform: translateY(12px);
}

.rhine-boot-leave-to .rhine-boot-panel {
  transform: translateY(8px);
}

@media (prefers-reduced-motion: reduce) {
  .rhine-boot-enter-active,
  .rhine-boot-leave-active,
  .rhine-boot-enter-active .rhine-boot-panel,
  .rhine-boot-leave-active .rhine-boot-panel,
  .boot-progress i {
    transition: none;
  }
}
</style>
