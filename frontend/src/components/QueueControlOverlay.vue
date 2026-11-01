<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useQueueControl } from '@/composables/useQueueControl'
import { subscribe, unsubscribe } from '@/services/websocket/subscriptions'
import { WS_ID_MAIN, WS_TASK_NOTICE } from '@/services/websocket/types'
import { t } from '@/i18n'

const { state, refresh, respond } = useQueueControl()
const notice = ref('')
const now = ref(Date.now())
const current = computed(() =>
  state.value.controls.find(c => c.queueId === state.value.selectedQueueId)
)
const queue = computed(() => state.value.queues.find(q => q.id === state.value.selectedQueueId))
const remaining = computed(() =>
  Math.max(0, Math.ceil(((current.value?.prompt?.deadline ?? 0) * 1000 - now.value) / 1000))
)
watch(
  () => queue.value?.id,
  () => {
    if (queue.value?.isCycle) {
      notice.value = t('localControls.controlCycleNotice')
      clearTimeout(noticeTimer)
      noticeTimer = setTimeout(() => {
        notice.value = ''
      }, 5000)
    }
  }
)
let timer: ReturnType<typeof setTimeout> | undefined
let noticeTimer: ReturnType<typeof setTimeout> | undefined
let subscription = ''
let disposed = false
async function poll() {
  try {
    await refresh()
  } catch {
    /* 后端启动期间下一轮重试。 */
  }
  now.value = Date.now()
  if (!disposed) timer = setTimeout(poll, 250)
}
async function act(action: 'pause' | 'continue') {
  const c = current.value
  if (!c?.prompt) return
  try {
    await respond(c.taskId, c.prompt.token, action)
  } catch (error) {
    notice.value = String(error)
  }
}
onMounted(() => {
  subscription = subscribe({ id: WS_ID_MAIN, type: WS_TASK_NOTICE }, message => {
    notice.value = message.data.message
    clearTimeout(noticeTimer)
    noticeTimer = setTimeout(() => {
      notice.value = ''
    }, 5000)
    void refresh().catch(() => {})
  })
  void poll()
})
onUnmounted(() => {
  disposed = true
  clearTimeout(timer)
  clearTimeout(noticeTimer)
  unsubscribe(subscription)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="notice || current?.paused || current?.cleaning || current?.error"
      class="queue-control-overlay"
      role="status"
      aria-live="polite"
    >
      <a-card size="small">
        <a-space direction="vertical">
          <strong
            >{{ queue?.name
            }}<template v-if="current">
              · {{ current.selectedTask }} · {{ current.state }}</template
            ></strong
          >
          <span v-if="notice">{{ notice }}</span>
          <a-typography-text v-if="current?.error" type="danger">{{
            current.error
          }}</a-typography-text>
          <template v-if="current?.prompt">
            <span>{{ current.prompt.message }}</span>
            <span v-if="current.prompt.deadline">{{
              remaining > 0 ? `${remaining}s` : t('localControls.controlWaiting')
            }}</span>
            <a-space v-if="current.prompt.buttons">
              <a-button @click="act('pause')">{{ t('localControls.controlPause') }}</a-button>
              <a-button
                type="primary"
                :disabled="current.cleaning || !!current.error"
                @click="act('continue')"
                >{{ t('localControls.controlSkipWait') }}</a-button
              >
            </a-space>
          </template>
        </a-space>
      </a-card>
    </div>
  </Teleport>
</template>

<style scoped>
.queue-control-overlay {
  position: fixed;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1100;
  width: min(560px, calc(100vw - 32px));
}
</style>
