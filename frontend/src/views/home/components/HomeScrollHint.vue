<template>
  <Transition name="scroll-hint">
    <button
      v-if="visible"
      class="scroll-hint"
      :aria-label="t('home.scrollHint.aria')"
      @click="scrollDown"
    >
      <span class="scroll-hint-text">{{ t('home.scrollHint.text') }}</span>
      <DownOutlined class="scroll-hint-arrow" />
    </button>
  </Transition>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { DownOutlined } from '@ant-design/icons-vue'

defineOptions({ name: 'HomeScrollHint' })

const visible = ref(false)
const THRESHOLD = 200
let scrollContainer: Element | null = null
let observer: MutationObserver | null = null
let checkFrame: number | null = null

const checkScroll = () => {
  if (!scrollContainer) return
  const el = scrollContainer
  const scrollable = el.scrollHeight > el.clientHeight + THRESHOLD
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - THRESHOLD
  visible.value = scrollable && !atBottom
}

// 同一帧内的异步内容更新合并检查，避免每次 DOM 变动都强制重新布局。
const scheduleCheckScroll = () => {
  if (!scrollContainer || checkFrame !== null) return
  checkFrame = requestAnimationFrame(() => {
    checkFrame = null
    checkScroll()
  })
}

const scrollDown = () => {
  scrollContainer?.scrollBy({ top: 400, behavior: 'smooth' })
}

onMounted(() => {
  scrollContainer = document.querySelector('.content-area')
  if (!scrollContainer) return
  scrollContainer.addEventListener('scroll', scheduleCheckScroll, { passive: true })
  observer = new MutationObserver(scheduleCheckScroll)
  observer.observe(scrollContainer, { childList: true, subtree: true })
  checkScroll()
})

onBeforeUnmount(() => {
  scrollContainer?.removeEventListener('scroll', scheduleCheckScroll)
  observer?.disconnect()
  if (checkFrame !== null) cancelAnimationFrame(checkFrame)
  checkFrame = null
  scrollContainer = null
})
</script>

<style scoped>
.scroll-hint {
  position: fixed;
  /* 外壳已无侧栏：水平居中，停在 40px 高的底部刻度栏之上 */
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 16px 32px 12px;
  border: none;
  cursor: pointer;
  background: linear-gradient(transparent, var(--ant-color-bg-layout) 70%);
  border-radius: 0;
  transition: opacity 0.3s;
}

.scroll-hint:hover {
  opacity: 0.8;
}

.scroll-hint:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: -2px;
}

.scroll-hint-text {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  letter-spacing: 0.12em;
  white-space: nowrap;
}

.scroll-hint-arrow {
  color: var(--app-rhine-accent);
  font-size: 16px;
  animation: bounce 1.5s ease-in-out infinite;
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(5px);
  }
}

.scroll-hint-enter-active,
.scroll-hint-leave-active {
  transition:
    opacity 0.4s ease,
    transform 0.4s ease;
}

.scroll-hint-enter-from,
.scroll-hint-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
</style>
