<template>
  <a-layout class="rhine-app-shell">
    <!-- 顶部档案抬头：左侧品牌三行字，中部编号部门导航，右侧常用工具 -->
    <header class="rhine-masthead">
      <div class="rhine-brand" aria-label="AUTO-MAS Analysis OS">
        <svg
          class="rhine-mark"
          viewBox="0 0 48 48"
          fill="none"
          aria-hidden="true"
          focusable="false"
        >
          <circle cx="24" cy="24" r="15" stroke="currentColor" stroke-width="2.5" />
          <circle cx="24" cy="24" r="5" class="rhine-mark-core" />
          <path
            d="M24 2v8M24 38v8M2 24h8M38 24h8"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="square"
          />
          <path d="M35 13l6-6" stroke="currentColor" stroke-width="2" />
        </svg>
        <div class="rhine-brand-lines" aria-hidden="true">
          <span class="rhine-brand-title">AUTO-MAS</span>
          <span class="rhine-brand-os">
            <span>ANALYSIS</span>
            <strong>OS</strong>
          </span>
        </div>
      </div>

      <nav class="rhine-dept-nav" :aria-label="t('comp.mainNavigation')">
        <button
          v-for="item in primaryNavItems"
          :key="item.key"
          type="button"
          class="rhine-dept-item"
          :class="{ 'is-active': item.key === activeKey }"
          :aria-current="item.key === activeKey ? 'page' : undefined"
          :data-route="item.key"
          @click="navigate(item.key)"
        >
          <span class="rhine-dept-index" aria-hidden="true">{{ item.index }}</span>
          <span v-if="hasAppearanceMenuIcons" class="rhine-dept-icon" aria-hidden="true">
            <component :is="item.icon" />
          </span>
          <span class="rhine-dept-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="rhine-utility-nav" role="group" :aria-label="t('comp.utilityNavigation')">
        <a-tooltip
          v-for="item in utilityNavItems"
          :key="item.key"
          :title="item.label"
          placement="bottom"
        >
          <button
            type="button"
            class="rhine-utility-item"
            :class="{ 'is-active': item.key === activeKey, 'is-dev': item.dev }"
            :aria-label="item.label"
            :aria-current="item.key === activeKey ? 'page' : undefined"
            :data-route="item.key"
            @click="navigate(item.key)"
          >
            <component :is="item.icon" />
          </button>
        </a-tooltip>
      </div>
    </header>

    <a-layout-content class="content-area">
      <a-result v-if="!isAppReady" status="info" :title="t('launch.starting')" />
      <router-view v-else v-slot="{ Component, route: currentRoute }">
        <keep-alive :include="['SchedulerPage']">
          <component :is="Component" :key="currentRoute.path" />
        </keep-alive>
      </router-view>
    </a-layout-content>

    <!-- 底部档案刻度栏：会话状态、页面刻度（可点击跳转）、当前档案编号与时钟 -->
    <footer class="rhine-ledger">
      <div class="rhine-ledger-session" aria-hidden="true">
        <span class="rhine-ledger-key">SESSION</span>
        <span class="rhine-ledger-dot"></span>
        <span class="rhine-ledger-value">AUTHORIZED</span>
      </div>

      <div class="rhine-ledger-ruler" role="group" :aria-label="t('comp.pageRuler')">
        <button
          v-for="item in rulerItems"
          :key="item.key"
          type="button"
          class="rhine-ledger-tick"
          :class="{ 'is-active': item.key === activeKey }"
          :aria-label="item.label"
          :title="item.label"
          @click="navigate(item.key)"
        >
          <i aria-hidden="true"></i>
          <span class="rhine-ledger-tick-index" aria-hidden="true">{{ item.index }}</span>
        </button>
      </div>

      <div class="rhine-ledger-current" aria-hidden="true">
        <span class="rhine-ledger-serial">X-0{{ currentRouteIndex }}</span>
        <span class="rhine-ledger-name">{{ currentRouteLabel }}</span>
      </div>

      <div class="rhine-ledger-right" aria-hidden="true">
        <span class="rhine-ledger-clock">{{ liveClock }}</span>
        <span class="rhine-ledger-powered"> POWERED BY <strong>AUTO-MAS</strong> </span>
      </div>
    </footer>
  </a-layout>
</template>

<script lang="ts" setup>
import { useI18n } from 'vue-i18n'
import {
  BugOutlined,
  CarryOutOutlined,
  ControlOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  HistoryOutlined,
  HomeOutlined,
  SettingOutlined,
  SkinOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons-vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Component, VNode } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '../composables/useTheme.ts'
import { useRouteLock } from '../composables/useRouteLock.ts'
import type { AppearanceMenuIconKey } from '@/types/appearance'
import { createAppearanceMenuIcon } from './appearanceMenuIcon'
import { useAppInitialization } from '@/composables/useAppInitialization'

interface ShellNavItem {
  key: string
  label: string
  index: string
  icon: () => VNode
  dev?: boolean
}

const { t } = useI18n()
const { isAppReady } = useAppInitialization()

const router = useRouter()
const route = useRoute()
const { activeAppearance } = useTheme()
const { isRouteLocked, triggerBlockCallback } = useRouteLock()

// 菜单图标依次使用外观包的专属图标、默认图标和内置图标。
const icon =
  (key: AppearanceMenuIconKey, Comp: Component, menuIcons = activeAppearance.value?.menuIconUrls) =>
  () =>
    createAppearanceMenuIcon(key, Comp, menuIcons)

// PV 风格的主导航只排编号与文字；外观包提供了专属菜单图标时再显示图标，保留外观包能力。
const hasAppearanceMenuIcons = computed(() => {
  const icons = activeAppearance.value?.menuIconUrls
  return !!icons && Object.values(icons).some(Boolean)
})

// 判断是否为开发环境。必须与 router/index.ts 里注册调试路由的条件保持一致，
// 否则菜单项会指向未注册的路由。
const isDevelopment = computed(() => import.meta.env.DEV)

const ROUTE_INDEX_MAP: Record<string, string> = {
  '/home': '01',
  '/scripts': '02',
  '/emulators': '03',
  '/queue': '04',
  '/scheduler': '05',
  '/local-controls': '06',
  '/gamesign': '07',
  '/history': '08',
  '/theme-store': '09',
  '/settings': '10',
}

const indexOf = (key: string) => ROUTE_INDEX_MAP[key] ?? '00'

const primaryNavItems = computed<ShellNavItem[]>(() => [
  { key: '/home', label: t('comp.home'), index: '01', icon: icon('home', HomeOutlined) },
  {
    key: '/scripts',
    label: t('comp.scripts'),
    index: '02',
    icon: icon('scripts', FileTextOutlined),
  },
  {
    key: '/emulators',
    label: t('comp.emulators'),
    index: '03',
    icon: icon('emulators', DatabaseOutlined),
  },
  {
    key: '/queue',
    label: t('comp.queue'),
    index: '04',
    icon: icon('queue', UnorderedListOutlined),
  },
  {
    key: '/scheduler',
    label: t('comp.scheduler'),
    index: '05',
    icon: icon('scheduler', ControlOutlined),
  },
  ...(window.__AUTO_MAS_BROWSER_HOST__
    ? [
        {
          key: '/local-controls',
          label: t('localControls.title'),
          index: '06',
          icon: icon('tools', ControlOutlined),
        },
      ]
    : []),
])

// 开发环境专用入口，并入右侧工具组
const devNavItems = computed<ShellNavItem[]>(() =>
  isDevelopment.value
    ? [
        {
          key: '/TestRouter',
          label: t('comp.testRoute'),
          index: '00',
          icon: icon('testRouter', SettingOutlined),
          dev: true,
        },
        {
          key: '/OverlayMaskDev',
          label: t('comp.overlayEasterEggTest'),
          index: '00',
          icon: icon('overlayMaskDev', SettingOutlined),
          dev: true,
        },
        {
          key: '/update-download-dev',
          label: t('comp.updateDownloadTest'),
          index: '00',
          icon: icon('updateDownloadDev', BugOutlined),
          dev: true,
        },
      ]
    : []
)

const utilityNavItems = computed<ShellNavItem[]>(() => [
  {
    key: '/gamesign',
    label: t('comp.checkIns'),
    index: '07',
    icon: icon('gameSign', CarryOutOutlined),
  },
  {
    key: '/history',
    label: t('comp.history'),
    index: '08',
    icon: icon('history', HistoryOutlined),
  },
  ...(!window.__AUTO_MAS_BROWSER_HOST__
    ? [
        {
          key: '/theme-store',
          label: t('comp.themeStore'),
          index: '09',
          icon: icon('themeStore', SkinOutlined),
        },
      ]
    : []),
  {
    key: '/settings',
    label: t('comp.settings'),
    index: '10',
    icon: icon('settings', SettingOutlined),
  },
  ...devNavItems.value,
])

// 底部刻度只覆盖正式页面，调试入口不进刻度
const rulerItems = computed(() => [
  ...primaryNavItems.value,
  ...utilityNavItems.value.filter(item => !item.dev),
])

const allNavItems = computed(() => [...primaryNavItems.value, ...utilityNavItems.value])

// 选中项：优先精确匹配，再按路径边界匹配当前导航。
const activeKey = computed(() => {
  const path = route.path
  const matched = allNavItems.value
    .filter(item => path === item.key || path.startsWith(`${item.key}/`))
    .sort((left, right) => right.key.length - left.key.length)[0]
  return matched?.key || '/home'
})

const currentRouteIndex = computed(() => indexOf(activeKey.value))

const currentRouteLabel = computed(() => {
  const matched = allNavItems.value.find(item => item.key === activeKey.value)
  if (matched) return matched.label
  return typeof route.meta?.title === 'string' ? route.meta.title : 'AUTO-MAS'
})

const formatClock = () => {
  const now = new Date()
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  const ss = String(now.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

const liveClock = ref(formatClock())
let clockTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  clockTimer = setInterval(() => {
    liveClock.value = formatClock()
  }, 1000)
})

onUnmounted(() => {
  if (clockTimer) {
    clearInterval(clockTimer)
    clockTimer = null
  }
})

const navigate = (target: string) => {
  // 检查路由是否被锁定
  if (isRouteLocked.value) {
    // 如果路由被锁定，触发回调而不进行路由跳转
    triggerBlockCallback(target)
    return
  }

  if (
    target === '/update-download-dev' &&
    import.meta.env.DEV &&
    !router.hasRoute('UpdateDownloadDev')
  ) {
    router.addRoute({
      path: '/update-download-dev',
      name: 'UpdateDownloadDev',
      component: () => import('@/views/UpdateDownloadDev.vue'),
      meta: { title: t('comp.updateDownloadTest'), skipGuard: true },
    })
  }

  if (route.path !== target) router.push(target)
}
</script>

<style scoped>
.rhine-app-shell {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
}

/* ── 顶部抬头 ─────────────────────────────────────────────────────────── */
.rhine-masthead {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: stretch;
  gap: 28px;
  height: 80px;
  padding: 0 24px 0 28px;
  background: var(--app-rhine-chrome-bg);
  border-bottom: 1px solid var(--app-rhine-rule);
  user-select: none;
}

:global(html.appearance-background-custom) .rhine-masthead,
:global(html.appearance-background-custom) .rhine-ledger {
  background: var(--app-appearance-elevated-surface-bg);
}

.rhine-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--ant-color-text);
}

.rhine-mark {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: block;
}

.rhine-mark-core {
  fill: var(--app-rhine-accent);
}

.rhine-brand-lines {
  display: flex;
  flex-direction: column;
  white-space: nowrap;
}

.rhine-brand-title {
  font-size: 26px;
  line-height: 28px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.rhine-brand-os {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  line-height: 18px;
  letter-spacing: 0.3em;
  color: var(--ant-color-text-secondary);
}

.rhine-brand-os strong {
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ant-color-text);
}

/* ── 部门导航 ─────────────────────────────────────────────────────────── */
.rhine-dept-nav {
  display: flex;
  align-items: stretch;
  gap: 4px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.rhine-dept-nav::-webkit-scrollbar {
  display: none;
}

.rhine-dept-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 0 14px;
  border: 0;
  background: transparent;
  color: var(--ant-color-text-secondary);
  font: inherit;
  font-size: 16px;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: color 0.18s ease;
}

.rhine-dept-item::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 3px;
  background: var(--app-rhine-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1);
}

.rhine-dept-item:hover {
  color: var(--ant-color-text);
}

.rhine-dept-item:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: -6px;
}

.rhine-dept-item.is-active {
  color: var(--ant-color-text);
  font-weight: 600;
}

.rhine-dept-item.is-active::after {
  transform: scaleX(1);
}

.rhine-dept-index {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.04em;
  color: var(--app-rhine-muted-index);
  font-variant-numeric: tabular-nums;
  align-self: flex-start;
  margin-top: 26px;
}

.rhine-dept-item.is-active .rhine-dept-index {
  color: var(--app-rhine-accent);
}

.rhine-dept-icon {
  display: inline-flex;
  font-size: 16px;
}

.rhine-dept-icon :deep(.appearance-menu-icon) {
  width: 20px;
  height: 20px;
}

.rhine-dept-label {
  white-space: nowrap;
}

/* ── 右侧常用工具 ─────────────────────────────────────────────────────── */
.rhine-utility-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  padding-left: 16px;
  border-left: 1px solid var(--app-rhine-hairline);
  margin: 20px 0;
}

.rhine-utility-item {
  position: relative;
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ant-color-text-secondary);
  font-size: 17px;
  cursor: pointer;
  transition:
    color 0.18s ease,
    border-color 0.18s ease;
}

.rhine-utility-item :deep(.appearance-menu-icon) {
  width: 20px;
  height: 20px;
}

.rhine-utility-item:hover {
  color: var(--ant-color-text);
  border-color: var(--app-rhine-hairline);
}

.rhine-utility-item:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: 1px;
}

.rhine-utility-item.is-active {
  color: var(--app-rhine-accent);
  border-color: var(--app-rhine-accent-border);
}

.rhine-utility-item.is-dev {
  color: var(--ant-color-text-tertiary);
  border-style: dashed;
  border-color: var(--ant-color-border-secondary);
}

/* ── 内容区 ───────────────────────────────────────────────────────────── */
.content-area {
  min-height: 0;
  flex: 1;
  overflow: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 24px 32px;
}

.content-area::-webkit-scrollbar {
  display: none;
}

/* ── 底部刻度栏 ───────────────────────────────────────────────────────── */
.rhine-ledger {
  flex-shrink: 0;
  height: 40px;
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 24px;
  padding: 0 24px 0 28px;
  background: var(--app-rhine-chrome-bg);
  border-top: 1px solid var(--app-rhine-hairline);
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--app-rhine-muted-index);
  font-variant-numeric: tabular-nums;
  user-select: none;
}

.rhine-ledger-session {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rhine-ledger-key {
  color: var(--ant-color-text);
}

.rhine-ledger-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--app-rhine-accent);
  animation: rhine-ledger-pulse 2.4s ease-in-out infinite;
}

@keyframes rhine-ledger-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.rhine-ledger-ruler {
  display: flex;
  align-items: flex-end;
  height: 100%;
  gap: 0;
}

.rhine-ledger-tick {
  width: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  padding: 0 0 4px;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.rhine-ledger-tick i {
  display: block;
  width: 1px;
  height: 10px;
  background: var(--ant-color-text-tertiary);
  transition:
    height 0.4s cubic-bezier(0.2, 0.9, 0.3, 1),
    background-color 0.2s ease;
}

.rhine-ledger-tick-index {
  font-size: 9px;
  line-height: 10px;
  letter-spacing: 0.04em;
  color: var(--app-rhine-muted-index);
  transition: color 0.2s ease;
}

.rhine-ledger-tick:hover .rhine-ledger-tick-index {
  color: var(--ant-color-text);
}

.rhine-ledger-tick.is-active .rhine-ledger-tick-index {
  color: var(--app-rhine-accent);
  font-weight: 600;
}

.rhine-ledger-tick:hover i {
  height: 14px;
  background: var(--ant-color-text-secondary);
}

.rhine-ledger-tick.is-active i {
  width: 2px;
  height: 20px;
  background: var(--app-rhine-accent);
}

.rhine-ledger-tick:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: -2px;
}

.rhine-ledger-current {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.rhine-ledger-serial {
  color: var(--app-rhine-accent);
}

.rhine-ledger-name {
  color: var(--ant-color-text-secondary);
  letter-spacing: 0.08em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rhine-ledger-right {
  display: flex;
  align-items: center;
  gap: 18px;
}

.rhine-ledger-clock {
  color: var(--ant-color-text);
}

.rhine-ledger-powered strong {
  color: var(--ant-color-text);
  font-weight: 700;
}

@media (max-width: 1180px) {
  .rhine-masthead {
    gap: 16px;
    padding: 0 16px;
  }

  .rhine-brand-lines {
    display: none;
  }

  .rhine-dept-item {
    padding: 0 10px;
  }

  .rhine-dept-item::after {
    left: 10px;
    right: 10px;
  }
}

@media (max-width: 960px) {
  .rhine-dept-index,
  .rhine-ledger-powered,
  .rhine-ledger-session {
    display: none;
  }

  .rhine-ledger {
    grid-template-columns: auto minmax(0, 1fr) auto;
    padding: 0 16px;
  }

  .content-area {
    padding: 20px 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .rhine-ledger-dot {
    animation: none;
  }

  .rhine-dept-item::after,
  .rhine-ledger-tick i {
    transition: none;
  }
}
</style>
