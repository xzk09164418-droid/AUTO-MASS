<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useTheme } from '@/composables/useTheme'
import { t } from '@/i18n'

const props = defineProps<{
  ready: boolean
  progress: number
  error: string
  setupRequired: boolean
  label?: string
}>()
const { isDark } = useTheme()
const marker = 'auto-mas.startup-animation.version'
const version = import.meta.env.VITE_APP_VERSION || 'development'
let previous: string | null = null
try {
  previous = localStorage.getItem(marker)
} catch {
  /* 浏览器禁用存储时使用冷启动。 */
}
const mode = previous === version && !props.setupRequired ? 'warm' : 'cold'
const visible = ref(true)
const frameReady = ref(false)
const frame = ref<HTMLIFrameElement>()
let loaded = false
let failSafe: ReturnType<typeof setTimeout>
function frameLoaded() {
  loaded = true
  void update()
}

async function update() {
  if (props.setupRequired) {
    try {
      localStorage.removeItem(marker)
    } catch {
      /* 不阻断初始化页面。 */
    }
  }
  if (props.error) {
    visible.value = false
    return
  }
  if (!loaded) return
  await nextTick()
  if (props.ready) {
    await new Promise<void>(resolve =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
    )
  }
  frame.value?.contentWindow?.postMessage(
    {
      type: 'mas-splash-state',
      version,
      dark: isDark.value,
      ready: props.ready || props.setupRequired,
      progress: props.ready ? 100 : props.progress,
      label: props.ready ? 'READY' : props.label || t('startupAnimation.waiting'),
    },
    '*'
  )
}
function receive(event: MessageEvent) {
  if (event.source !== frame.value?.contentWindow || event.origin !== location.origin) return
  if (event.data?.type === 'mas-splash-loaded') {
    frameReady.value = true
    loaded = true
    void update()
  }
  if (event.data?.type === 'mas-splash-ready') {
    window.dispatchEvent(new CustomEvent('automas:ready'))
  }
  if (event.data?.type === 'mas-splash-closed') {
    visible.value = false
    window.dispatchEvent(new CustomEvent('automas:closed'))
    if (props.ready && !props.setupRequired) {
      try {
        localStorage.setItem(marker, version)
      } catch {
        /* 仅影响下次动画类型。 */
      }
    }
  }
}
watch(
  () => [props.ready, props.progress, props.error, props.setupRequired, props.label, isDark.value],
  update
)
onMounted(() => {
  window.addEventListener('message', receive)
  // 加载失败时让用户看到现有启动诊断面板，不用动画遮挡错误或重连按钮。
  failSafe = setTimeout(() => {
    if (!loaded) visible.value = false
  }, 20000)
  void update()
})
onBeforeUnmount(() => {
  clearTimeout(failSafe)
  window.removeEventListener('message', receive)
})
</script>

<template>
  <iframe
    v-if="visible"
    ref="frame"
    class="startup-animation"
    :class="{ 'startup-animation-pending': !frameReady }"
    :src="`/startup/${mode}.html`"
    title="AUTO-MAS"
    @load="frameLoaded"
  />
</template>

<style scoped>
.startup-animation {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100dvh;
  border: 0;
  z-index: 10000;
  background: transparent;
}
.startup-animation-pending {
  background: #e8e5e1;
}
:global(html.dark) .startup-animation-pending {
  background: #111619;
}
</style>
