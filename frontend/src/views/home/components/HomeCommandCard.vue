<template>
  <a-card class="command-card">
    <section class="command-panel" :aria-label="t('home.command.aria')">
      <div class="command-main">
        <!-- PV 圆环刻度装饰：静态细线 + 一圈缓慢转动的虚线环 -->
        <svg class="command-rings" viewBox="0 0 240 240" aria-hidden="true" focusable="false">
          <circle cx="120" cy="120" r="112" class="ring-thin" />
          <circle cx="120" cy="120" r="88" class="ring-dash" />
          <circle cx="120" cy="120" r="56" class="ring-thin" />
          <circle cx="120" cy="120" r="6" class="ring-core" />
          <path d="M120 0v28M120 212v28M0 120h28M212 120h28" class="ring-thin" />
        </svg>
        <span class="command-kicker" aria-hidden="true">TRANSMISSION // DAILY NOTE</span>
        <div class="command-content">
          <ShatterText v-if="!isBootstrapping" :text="commandTitle" class="command-title" />
        </div>
        <div v-if="!isBootstrapping" class="command-footer">
          <a-tooltip
            :title="t('home.command.refresh')"
            :open="refreshTipOpen"
            @open-change="refreshTipOpen = $event"
          >
            <a-button
              type="text"
              size="small"
              class="command-refresh"
              :aria-label="t('home.command.refresh')"
              @click="onRefreshGreeting"
            >
              <template #icon>
                <ReloadOutlined :key="spinKey" class="command-refresh-icon" />
              </template>
            </a-button>
          </a-tooltip>
          <span v-if="commandAuthor" class="command-author">—— {{ commandAuthor }}</span>
        </div>
      </div>

      <div class="scheduler-launcher">
        <div class="scheduler-content">
          <div class="launcher-header">
            <span class="launcher-code" aria-hidden="true">ACCESS // SCHEDULER</span>
            <div class="launcher-title">{{ t('home.command.title') }}</div>
          </div>

          <div class="launcher-controls">
            <a-select
              v-model:value="selectedTaskIds"
              class="launcher-select"
              mode="multiple"
              :options="schedulerTaskOptions"
              :loading="schedulerTasksLoading"
              size="large"
              :max-tag-count="'responsive'"
              :placeholder="t('home.command.placeholder')"
              @dropdown-visible-change="$emit('dropdown-visible-change', $event)"
            >
              <!-- 拉取失败时列表为空：说明原因，展开下拉本身就会重试 -->
              <template v-if="schedulerTasksUnavailable" #notFoundContent>
                <span class="launcher-select-hint">{{ t('home.quickStart.listUnavailable') }}</span>
              </template>
            </a-select>
            <a-button
              type="primary"
              size="large"
              class="launcher-start"
              :loading="startingHomeTask"
              :disabled="schedulerTasksLoading || selectedTaskIds.length === 0"
              @click="$emit('start')"
            >
              <template #icon>
                <PlayCircleOutlined />
              </template>
              {{ t('home.command.start') }}
            </a-button>
          </div>
        </div>
      </div>
    </section>
  </a-card>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import type { ComboBoxItem } from '@/api'
import ShatterText from '@/views/home/components/ShatterText.vue'

const { t } = useI18n()

const props = defineProps<{
  isBootstrapping: boolean
  commandTitle: string
  commandAuthor: string
  schedulerTaskOptions: ComboBoxItem[]
  schedulerTasksLoading: boolean
  schedulerTasksUnavailable: boolean
  startingHomeTask: boolean
  selectedTaskIds: string[]
}>()

const emit = defineEmits<{
  'update:selectedTaskIds': [value: string[]]
  'dropdown-visible-change': [open: boolean]
  start: []
  'refresh-greeting': []
}>()

// 靠 key 变化重挂载图标来重放旋转动画，比手动增删 class 稳
const spinKey = ref(0)

// 提示只认鼠标进出：主页一滚，按钮就从鼠标底下滑走，可鼠标没动，浏览器不会补发
// mouseleave，提示便一直挂在屏幕上——滚动时自己关掉，鼠标再进按钮才会重新出现。
const refreshTipOpen = ref(false)

const closeRefreshTip = () => {
  refreshTipOpen.value = false
}

watch(refreshTipOpen, open => {
  if (open) {
    // 主页内容区的滚动不会冒泡到 window，只能靠捕获阶段拿
    window.addEventListener('scroll', closeRefreshTip, true)
  } else {
    window.removeEventListener('scroll', closeRefreshTip, true)
  }
})

onBeforeUnmount(() => window.removeEventListener('scroll', closeRefreshTip, true))

const onRefreshGreeting = () => {
  spinKey.value += 1
  emit('refresh-greeting')
}

const selectedTaskIds = computed({
  get: () => props.selectedTaskIds,
  set: value => emit('update:selectedTaskIds', value),
})
</script>

<style scoped>
.command-card {
  border-top: 2px solid var(--app-rhine-rule);
}

.command-card :deep(.ant-card-body) {
  padding: 0;
}

.command-panel {
  min-height: 188px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  color: var(--ant-color-text);
}

/* ── 左：每日寄语 ─────────────────────────────────────────────────────── */
.command-main {
  min-width: 0;
  position: relative;
  padding: 22px 28px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  overflow: hidden;
  isolation: isolate;
}

.command-rings {
  position: absolute;
  right: -40px;
  top: 50%;
  width: 260px;
  height: 260px;
  transform: translateY(-50%);
  z-index: 0;
  pointer-events: none;
  opacity: 0.55;
}

.ring-thin,
.ring-dash {
  fill: none;
  stroke: var(--app-rhine-hairline);
  stroke-width: 1;
}

.ring-dash {
  stroke: var(--app-rhine-accent-border);
  stroke-dasharray: 2 6;
  transform-origin: 120px 120px;
  animation: command-ring-turn 60s linear infinite;
}

.ring-core {
  fill: var(--app-rhine-accent);
}

@keyframes command-ring-turn {
  to {
    transform: rotate(360deg);
  }
}

.command-kicker {
  position: relative;
  z-index: 1;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

.command-content {
  position: relative;
  z-index: 1;
  padding-right: 160px;
}

.command-title {
  font-size: 30px;
  line-height: 1.3;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--ant-color-text);
}

.command-footer {
  position: absolute;
  left: 28px;
  right: 28px;
  bottom: 16px;
  z-index: 1;
  /* 刷新按钮压在作者名上方，两者都贴右边：作者名长短只影响它自己向左伸出的宽度，
     按钮右边不动，鼠标停在按钮上的 tooltip 才不会因为按钮挪位而丢掉 mouseleave。 */
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.command-author {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--ant-color-text-tertiary);
  font-size: 13px;
  line-height: 1.5;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.command-refresh {
  color: var(--ant-color-text-tertiary);
  transition: color 0.2s ease;
}

.command-refresh:hover {
  color: var(--app-rhine-accent);
}

.command-refresh-icon {
  animation: command-refresh-spin 0.5s ease;
}

@keyframes command-refresh-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

/* ── 右：调度访问终端 ─────────────────────────────────────────────────── */
.scheduler-launcher {
  min-width: 0;
  padding: 22px 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid var(--app-rhine-hairline);
  background: var(--app-rhine-surface-header);
}

.launcher-header {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.launcher-code {
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-accent);
  user-select: none;
}

/* 模块标题已在首页档案分节显示，这里只保留给读屏的标题，视觉上隐藏避免重复 */
.launcher-title {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.launcher-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 112px;
  gap: 12px;
}

.launcher-select,
.launcher-start {
  width: 100%;
}

.launcher-select-hint {
  color: var(--ant-color-text-tertiary);
}

@media (max-width: 1240px) {
  .command-panel {
    grid-template-columns: 1fr;
  }

  .scheduler-launcher {
    border-left: none;
    border-top: 1px solid var(--app-rhine-hairline);
  }
}

@media (max-width: 800px) {
  .command-main {
    padding: 18px 18px 56px;
  }

  .command-content {
    padding-right: 0;
  }

  .command-rings {
    display: none;
  }

  .command-title {
    font-size: 24px;
  }
}

@media (max-width: 560px) {
  .launcher-controls {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ring-dash,
  .command-refresh-icon {
    animation: none;
  }
}
</style>
