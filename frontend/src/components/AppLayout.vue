<template>
  <a-layout class="rhine-app-shell">
    <a-layout-sider :width="SIDER_WIDTH" :theme="isDark ? 'dark' : 'light'" class="rhine-sider">
      <div class="sider-content">
        <!-- 莱茵生命风格终端品牌区 -->
        <div class="rhine-brand-header" aria-label="AUTO-MAS Analysis OS">
          <div class="rhine-brand-top">
            <svg
              class="rhine-emblem"
              viewBox="0 0 310 145"
              fill="none"
              aria-hidden="true"
              focusable="false"
            >
              <path
                d="M156 75C127 48 103 15 70 15C37 15 15 39 15 70S38 128 70 128C103 128 127 96 176 52M155 75C182 99 208 128 240 128C273 128 295 105 295 73S273 15 240 15C221 15 207 23 192 38"
                stroke="currentColor"
                stroke-width="26"
              />
              <path
                d="M44 70h50M69 45v50M219 70h44"
                stroke="currentColor"
                stroke-width="16"
              />
            </svg>
            <span class="rhine-brand-serial">RL-MAS</span>
          </div>
          <div class="rhine-brand-wordmark">
            <span class="rhine-brand-title">AUTO-MAS</span>
            <span class="rhine-brand-sub">SYNTHESIZE AUTOMATION</span>
            <span class="rhine-brand-os">
              <span>ANALYSIS</span>
              <strong>OS</strong>
            </span>
          </div>
        </div>

        <div class="rhine-nav-section-label">DEPARTMENT INDEX</div>

        <a-menu
          v-model:selected-keys="selectedKeys"
          mode="inline"
          :theme="isDark ? 'dark' : 'light'"
          class="rhine-nav-menu"
          :items="mainMenuItems"
          @click="onMenuClick"
        />
        <!-- 测试路由分隔区域 -->
        <a-menu
          v-if="isDevelopment"
          v-model:selected-keys="selectedKeys"
          mode="inline"
          :theme="isDark ? 'dark' : 'light'"
          class="rhine-nav-menu dev-menu"
          :items="devMenuItems"
          @click="onMenuClick"
        />
        <a-menu
          v-model:selected-keys="selectedKeys"
          mode="inline"
          :theme="isDark ? 'dark' : 'light'"
          class="rhine-nav-menu bottom-menu"
          :items="bottomMenuItems"
          @click="onMenuClick"
        />

        <div class="rhine-sider-footer">
          <span class="rhine-status-dot" aria-hidden="true"></span>
          <span class="rhine-status-text">SESSION AUTHORIZED</span>
        </div>
      </div>
    </a-layout-sider>

    <a-layout class="rhine-main-column">
      <!-- 顶部档案遥测信息栏（只读状态展示，不遮挡页面内容） -->
      <header class="rhine-telemetry-bar" aria-hidden="true">
        <div class="telemetry-left">
          <span class="telemetry-kicker">RL / ARCHIVE</span>
          <span class="telemetry-sep">//</span>
          <span class="telemetry-index">{{ currentRouteIndex }}</span>
          <span class="telemetry-name">{{ currentRouteLabel }}</span>
        </div>
        <div class="telemetry-right">
          <span class="telemetry-meta">INTERNAL TERMINAL</span>
          <span class="telemetry-dot"></span>
          <span class="telemetry-clock">{{ liveClock }}</span>
          <span class="telemetry-powered">
            POWERED BY <strong>AUTO-MAS</strong>
            <i class="telemetry-bar-mark"></i>
          </span>
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
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
import { useI18n } from 'vue-i18n'
import {
  BugOutlined,
  CalendarOutlined,
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
import type { Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '../composables/useTheme.ts'
import { useRouteLock } from '../composables/useRouteLock.ts'
import type { MenuProps } from 'ant-design-vue'
import type { AppearanceMenuIconKey } from '@/types/appearance'
import { createAppearanceMenuIcon } from './appearanceMenuIcon'
import { useAppInitialization } from '@/composables/useAppInitialization'

const { t } = useI18n()
const { isAppReady } = useAppInitialization()

const SIDER_WIDTH = 204

const router = useRouter()
const route = useRoute()
const { isDark, activeAppearance } = useTheme()
const { isRouteLocked, triggerBlockCallback } = useRouteLock()

// 菜单图标依次使用外观包的专属图标、默认图标和内置图标。
const icon =
  (key: AppearanceMenuIconKey, Comp: Component, menuIcons = activeAppearance.value?.menuIconUrls) =>
  () =>
    createAppearanceMenuIcon(key, Comp, menuIcons)

// 判断是否为开发环境。必须与 router/index.ts 里注册调试路由的条件保持一致，
// 否则菜单项会指向未注册的路由。之前这里还额外判断了 hostname === 'localhost'，
// 生产环境走 loadFile（file:// 协议，hostname 为空）不会命中，但用 vite preview
// 预览生产构建时会命中，导致菜单显示了实际不存在的路由。
const isDevelopment = computed(() => import.meta.env.DEV)

const mainMenuItems = computed(() => [
  { key: '/home', label: t('comp.home'), icon: icon('home', HomeOutlined) },
  { key: '/scripts', label: t('comp.scripts'), icon: icon('scripts', FileTextOutlined) },
  { key: '/plans', label: t('comp.plans'), icon: icon('plans', CalendarOutlined) },
  { key: '/emulators', label: t('comp.emulators'), icon: icon('emulators', DatabaseOutlined) },
  { key: '/queue', label: t('comp.queue'), icon: icon('queue', UnorderedListOutlined) },
  { key: '/scheduler', label: t('comp.scheduler'), icon: icon('scheduler', ControlOutlined) },
  ...(window.__AUTO_MAS_BROWSER_HOST__
    ? [
        {
          key: '/local-controls',
          label: t('localControls.title'),
          icon: icon('tools', ControlOutlined),
        },
      ]
    : []),
])

// 开发环境专用菜单项
const devMenuItems = computed(() => [
  { key: '/TestRouter', label: t('comp.testRoute'), icon: icon('testRouter', SettingOutlined) },
  {
    key: '/OverlayMaskDev',
    label: t('comp.overlayEasterEggTest'),
    icon: icon('overlayMaskDev', SettingOutlined),
  },
  ...(import.meta.env.DEV
    ? [
        {
          key: '/update-download-dev',
          label: t('comp.updateDownloadTest'),
          icon: icon('updateDownloadDev', BugOutlined),
        },
      ]
    : []),
])

const bottomMenuItems = computed(() => [
  { key: '/gamesign', label: t('comp.checkIns'), icon: icon('gameSign', CarryOutOutlined) },
  { key: '/history', label: t('comp.history'), icon: icon('history', HistoryOutlined) },
  ...(!window.__AUTO_MAS_BROWSER_HOST__
    ? [{ key: '/theme-store', label: t('comp.themeStore'), icon: icon('themeStore', SkinOutlined) }]
    : []),
  { key: '/settings', label: t('comp.settings'), icon: icon('settings', SettingOutlined) },
])

type MenuEntry = NonNullable<MenuProps['items']>[number]
type KeyedMenuEntry = Exclude<MenuEntry, null> & { key: string | number }

const hasMenuKey = (item: MenuEntry): item is KeyedMenuEntry =>
  item !== null && 'key' in item && item.key !== undefined

const flattenMenuItems = (items: readonly MenuEntry[]): MenuEntry[] => {
  const flattened: MenuEntry[] = []
  for (const item of items) {
    if (!item) continue
    flattened.push(item)
    if ('children' in item && item.children) {
      flattened.push(...flattenMenuItems(item.children))
    }
  }
  return flattened
}

const allItems = computed(() => [
  ...mainMenuItems.value,
  ...(isDevelopment.value ? devMenuItems.value : []),
  ...bottomMenuItems.value,
])

const flatItems = computed(() => flattenMenuItems(allItems.value))

// 选中项：优先精确匹配，再按路径边界匹配当前菜单。
const selectedKeys = computed(() => {
  const path = route.path
  const matched = flatItems.value
    .filter(hasMenuKey)
    .filter(item => {
      const key = String(item.key)
      return path === key || path.startsWith(`${key}/`)
    })
    .sort((left, right) => String(right.key).length - String(left.key).length)[0]
  return [matched?.key || '/home']
})

const ROUTE_INDEX_MAP: Record<string, string> = {
  '/home': '01',
  '/scripts': '02',
  '/plans': '03',
  '/emulators': '04',
  '/queue': '05',
  '/scheduler': '06',
  '/local-controls': '07',
  '/gamesign': '08',
  '/history': '09',
  '/theme-store': '10',
  '/settings': '11',
}

const currentRouteIndex = computed(() => {
  const key = String(selectedKeys.value[0] || '/home')
  return ROUTE_INDEX_MAP[key] ?? '00'
})

const currentRouteLabel = computed(() => {
  const key = String(selectedKeys.value[0] || '/home')
  const matched = flatItems.value
    .filter(hasMenuKey)
    .find(item => String(item.key) === key)
  if (matched && 'label' in matched && typeof matched.label === 'string') {
    return matched.label
  }
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

const onMenuClick: MenuProps['onClick'] = info => {
  const target = String(info.key)

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
  overflow: hidden;
  background: transparent;
}

.rhine-sider {
  background: var(--app-rhine-sider-bg) !important;
  border-right: 1px solid var(--app-rhine-sider-border);
}

:global(html.appearance-background-custom) .rhine-sider {
  background: var(--app-appearance-elevated-surface-bg) !important;
}

.rhine-main-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.sider-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

/* ── 莱茵生命终端品牌抬头 ────────────────────────────────────────────── */
.rhine-brand-header {
  padding: 16px 14px 12px;
  border-bottom: 1px solid var(--app-rhine-sider-border);
  user-select: none;
}

.rhine-brand-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.rhine-emblem {
  width: 44px;
  height: 21px;
  color: var(--ant-color-text);
  display: block;
}

.rhine-brand-serial {
  font-family: var(--app-rhine-font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--app-rhine-accent);
  padding: 2px 5px;
  border: 1px solid var(--app-rhine-accent-border);
  line-height: 1;
}

.rhine-brand-wordmark {
  display: flex;
  flex-direction: column;
  gap: 1px;
  color: var(--ant-color-text);
}

.rhine-brand-title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.06em;
  line-height: 1.05;
}

.rhine-brand-sub {
  font-size: 8.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--ant-color-text-secondary);
  line-height: 1.3;
}

.rhine-brand-os {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 2px;
  font-size: 13px;
  letter-spacing: 0.22em;
  line-height: 1.1;
}

.rhine-brand-os strong {
  font-weight: 800;
  letter-spacing: 0.08em;
}

.rhine-nav-section-label {
  padding: 10px 14px 4px;
  font-family: var(--app-rhine-font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

/* ── 导航菜单 ─────────────────────────────────────────────────────────── */
.sider-content :deep(.ant-menu) {
  border-inline-end: none !important;
  background: transparent !important;
}

.sider-content :deep(.ant-menu .ant-menu-item) {
  color: var(--ant-color-text-secondary);
  margin: 2px 8px;
  width: calc(100% - 16px);
  border-radius: 1px;
  padding: 0 12px !important;
  line-height: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.03em;
  transition:
    background-color 0.14s ease,
    color 0.14s ease,
    box-shadow 0.14s ease;
  text-align: left;
}

.sider-content :deep(.ant-menu .ant-menu-submenu) {
  width: calc(100% - 16px);
  margin: 2px 8px;
  border-radius: 1px;
}

.sider-content :deep(.ant-menu .ant-menu-submenu-title) {
  height: 36px;
  margin: 0;
  padding: 0 12px !important;
  line-height: 36px;
  border-radius: 1px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ant-color-text-secondary);
  transition:
    background-color 0.14s ease,
    color 0.14s ease;
}

.sider-content :deep(.ant-menu .ant-menu-submenu-title .anticon) {
  color: var(--ant-color-text-secondary);
  font-size: 16px;
}

.sider-content :deep(.ant-menu .ant-menu-submenu-title:hover) {
  background: var(--app-rhine-hover-bg);
  color: var(--ant-color-text);
}

.sider-content :deep(.ant-menu .ant-menu-submenu > .ant-menu) {
  background: transparent !important;
}

.sider-content :deep(.ant-menu .ant-menu-submenu .ant-menu-item) {
  width: calc(100% - 8px);
  margin: 2px 4px;
  padding-left: 36px !important;
  height: 34px;
  line-height: 34px;
}

.sider-content :deep(.ant-menu .ant-menu-item .anticon) {
  color: var(--ant-color-text-secondary);
  font-size: 16px;
  line-height: 1;
  transition: color 0.14s ease;
  margin-right: 0;
}

.sider-content :deep(.appearance-menu-icon) {
  width: 22px;
  height: 22px;
  object-fit: contain;
  flex: 0 0 22px;
}

.sider-content :deep(.appearance-menu-icon + .ant-menu-title-content) {
  margin-inline-start: 0 !important;
}

/* Hover */
.sider-content :deep(.ant-menu .ant-menu-item:hover) {
  background: var(--app-rhine-hover-bg);
  color: var(--ant-color-text);
}

.sider-content :deep(.ant-menu .ant-menu-item:hover .anticon) {
  color: var(--ant-color-text);
}

/* Selected: 莱茵生命经典左竖条激活指示 */
.sider-content :deep(.ant-menu .ant-menu-item-selected) {
  background: var(--app-rhine-active-bg);
  box-shadow: inset 3px 0 0 var(--app-rhine-accent);
  color: var(--ant-color-text) !important;
  font-weight: 700;
}

.sider-content :deep(.ant-menu .ant-menu-item-selected .anticon) {
  color: var(--app-rhine-accent);
}

.sider-content :deep(.ant-menu-light .ant-menu-item::after),
.sider-content :deep(.ant-menu-dark .ant-menu-item::after) {
  display: none;
}

/* 开发菜单区域 - 细线分隔 */
.dev-menu {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--ant-color-border);
}

.bottom-menu {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--ant-color-border);
}

/* 侧栏底部状态标牌 */
.rhine-sider-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 6px;
  border-top: 1px solid var(--ant-color-border);
  font-family: var(--app-rhine-font-mono);
  font-size: 9px;
  letter-spacing: 0.12em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

.rhine-status-dot {
  width: 5px;
  height: 5px;
  background: var(--app-rhine-olive);
  flex-shrink: 0;
}

.rhine-status-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 顶部工作区档案遥测栏 ──────────────────────────────────────────────── */
.rhine-telemetry-bar {
  height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 32px;
  background: var(--app-rhine-surface-subtle);
  border-bottom: 1px solid var(--ant-color-border);
  font-family: var(--app-rhine-font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

.telemetry-left,
.telemetry-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.telemetry-kicker {
  color: var(--app-rhine-accent);
  font-weight: 700;
}

.telemetry-sep {
  opacity: 0.5;
}

.telemetry-index {
  font-weight: 700;
  color: var(--ant-color-text);
}

.telemetry-name {
  font-family: var(--app-rhine-font-sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--ant-color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.telemetry-dot {
  width: 5px;
  height: 5px;
  background: var(--app-rhine-olive);
  display: inline-block;
}

.telemetry-clock {
  font-variant-numeric: tabular-nums;
  color: var(--ant-color-text-secondary);
}

.telemetry-powered {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
  color: var(--ant-color-text-secondary);
}

.telemetry-powered strong {
  color: var(--ant-color-text);
  font-weight: 700;
}

.telemetry-bar-mark {
  display: inline-block;
  width: 16px;
  height: 4px;
  background: var(--app-rhine-rule);
}

.content-area {
  min-height: 0;
  flex: 1;
  overflow: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  padding: 28px 32px;
}

.content-area::-webkit-scrollbar {
  display: none;
}

@media (max-width: 960px) {
  .telemetry-meta,
  .telemetry-powered {
    display: none;
  }

  .rhine-telemetry-bar {
    padding: 0 16px;
  }

  .content-area {
    padding: 20px 16px;
  }
}
</style>

<!-- 使用标准 Sider 布局，保留原有导航、路由锁与滚动行为，融合莱茵生命终端视觉语言 -->
