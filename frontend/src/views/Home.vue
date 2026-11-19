<template>
  <div class="home-page">
    <!-- PV 档案抬头：编号 + 问候大标题 + 日期刻度行 -->
    <header class="home-hero">
      <div class="home-hero-main">
        <div class="home-hero-meta" aria-hidden="true">
          <span class="home-hero-index">X-001</span>
          <span class="home-hero-kicker">OVERVIEW // OPERATIONAL DASHBOARD</span>
        </div>
        <h1 class="home-hero-title">{{ greeting }}</h1>
        <div class="home-hero-date" aria-hidden="true">
          <span>{{ heroDate.date }}</span>
          <i></i>
          <span>{{ heroDate.weekday }}</span>
          <i></i>
          <span>WEEK {{ heroDate.week }}</span>
        </div>
      </div>

      <div class="header-actions">
        <a-button
          :type="layoutDrawerOpen ? 'primary' : 'default'"
          class="layout-edit-button"
          @click="layoutDrawerOpen = !layoutDrawerOpen"
        >
          <template #icon>
            <EditOutlined />
          </template>
          {{ t('home.editLayout') }}
        </a-button>
        <a-button
          type="primary"
          ghost
          :loading="noticeLoading"
          class="notice-button"
          @click="showNotice"
        >
          <template #icon>
            <BellOutlined />
          </template>
          {{ t('home.viewNotice') }}
        </a-button>
      </div>
    </header>

    <NoticeModal
      v-model:visible="noticeVisible"
      :notice-data="noticeData"
      @confirmed="onNoticeConfirmed"
    />

    <HomeLayoutDrawer
      v-model:open="layoutDrawerOpen"
      :modules="homeModules"
      :activity-modules="homeActivityModules"
      :scroll-hint-hidden="scrollHintHidden"
      :carousel-autoplay="carouselAutoplay"
      :activity-notes-visible="activityNotesVisible"
      :hidden-activity-notes="hiddenActivityNotes"
      @reorder="reorderHomeModules"
      @reorder-activities="reorderActivityModules"
      @visibility-change="setHomeModuleShown"
      @scroll-hint-change="setScrollHintHidden"
      @autoplay-change="setCarouselAutoplay"
      @activity-note-visibility-change="setActivityNoteShown"
    />

    <div v-if="layoutReady" class="home-content">
      <template v-for="moduleKey in homeTopLevelOrder" :key="moduleKey">
        <section v-if="isHomeModuleVisible(moduleKey)" class="home-module">
          <!-- 模块按用户排序后的可见次序编号，标题沿用布局设置里的模块名 -->
          <div class="home-module-head">
            <span class="home-module-index" aria-hidden="true">{{ moduleSerial(moduleKey) }}</span>
            <span class="home-module-code" aria-hidden="true">{{
              MODULE_CODES[moduleKey] ?? 'ARCHIVE'
            }}</span>
            <h2 class="home-module-title">{{ moduleTitle(moduleKey) }}</h2>
            <span class="home-module-rule" aria-hidden="true"></span>
          </div>
          <HomeCommandCard
            v-if="moduleKey === 'command'"
            :selected-task-ids="selectedHomeTaskIds"
            :is-bootstrapping="isBootstrapping"
            :command-title="commandTitle"
            :command-author="commandAuthor"
            :scheduler-task-options="schedulerTaskOptions"
            :scheduler-tasks-loading="schedulerTasksLoading"
            :scheduler-tasks-unavailable="schedulerTasksUnavailable"
            :starting-home-task="startingHomeTask"
            @update:selected-task-ids="updateSelectedHomeTaskIds"
            @dropdown-visible-change="onSchedulerDropdownVisibleChange"
            @start="startHomeTask"
            @refresh-greeting="refreshGreeting"
          />

          <HomeQuickActionsCard v-else-if="moduleKey === 'quick'" />

          <HomeProxyCard
            v-else-if="moduleKey === 'proxy'"
            :loading="loading"
            :proxy-data="proxyData"
          />

          <!-- 各游戏共用主视觉与活动侧栏，卡池、资源关卡等补充内容按需放在下方。 -->
          <HomeActivityCarousel
            v-else-if="moduleKey === 'activities'"
            :items="activities.panels.value"
            :autoplay="carouselAutoplay"
            @refresh="activities.refresh"
            @select="activities.select"
            @action="activities.action"
            @dismiss="clearOverviewError"
          >
            <template #community="{ moduleKey: gameKey }">
              <!-- 社区信息紧跟游戏切换条，两者都不吸顶，跟着页面一起滚 -->
              <HomeActivityNotes
                v-if="activityNotesVisible && isActivityNoteVisible(gameKey)"
                :active-key="gameKey"
              />
            </template>
          </HomeActivityCarousel>
        </section>
      </template>
    </div>

    <HomeScrollHint v-if="!scrollHintHidden" />
    <HomeBackToTop />
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, onMounted, watch } from 'vue'
import { BellOutlined, EditOutlined } from '@ant-design/icons-vue'
import NoticeModal from '@/components/NoticeModal.vue'
import { useAppInitialization } from '@/composables/useAppInitialization'
import HomeActivityCarousel from '@/views/home/components/HomeActivityCarousel.vue'
import HomeBackToTop from '@/views/home/components/HomeBackToTop.vue'
import HomeActivityNotes from '@/views/home/components/HomeActivityNotes.vue'
import HomeCommandCard from '@/views/home/components/HomeCommandCard.vue'
import HomeLayoutDrawer from '@/views/home/components/HomeLayoutDrawer.vue'
import HomeProxyCard from '@/views/home/components/HomeProxyCard.vue'
import HomeQuickActionsCard from '@/views/home/components/HomeQuickActionsCard.vue'
import HomeScrollHint from '@/views/home/components/HomeScrollHint.vue'
import { useHomeActivities } from '@/views/home/useHomeActivities'
import { useHomeLayout } from '@/views/home/useHomeLayout'
import { useHomeNotice } from '@/views/home/useHomeNotice'
import { useHomeOverview } from '@/views/home/useHomeOverview'
import { useHomeQuickStart } from '@/views/home/useHomeQuickStart'

defineOptions({
  name: 'HomeView',
})

const { isBootstrapping } = useAppInitialization()
const {
  layoutReady,
  layoutDrawerOpen,
  homeTopLevelOrder,
  homeModules,
  homeActivityModules,
  visibleActivityKeys,
  scrollHintHidden,
  carouselAutoplay,
  activityNotesVisible,
  hiddenActivityNotes,
  loadHomeLayout,
  loadManagedActivityModules,
  reorderHomeModules,
  reorderActivityModules,
  setHomeModuleShown,
  setScrollHintHidden,
  setCarouselAutoplay,
  setActivityNoteShown,
  isActivityNoteVisible,
  isHomeModuleVisible,
} = useHomeLayout()
const { noticeVisible, noticeData, noticeLoading, fetchNoticeData, onNoticeConfirmed, showNotice } =
  useHomeNotice()
const {
  commandTitle,
  commandAuthor,
  refreshGreeting,
  schedulerTasksLoading,
  schedulerTasksUnavailable,
  startingHomeTask,
  schedulerTaskOptions,
  selectedHomeTaskIds,
  restoreSelectedHomeTaskIds,
  updateSelectedHomeTaskIds,
  fetchSchedulerTaskOptions,
  onSchedulerDropdownVisibleChange,
  startHomeTask,
} = useHomeQuickStart()
const {
  loading,
  error,
  hasSnapshot,
  /** 今日开放的资源收集关卡，给明日方舟卡片用 */
  resourceData,
  proxyData,
  clearOverviewError,
  fetchOverviewData,
} = useHomeOverview()

const { t } = useI18n()

const activities = useHomeActivities({
  visibleKeys: visibleActivityKeys,
  resources: resourceData,
  resourceError: error,
})

// 布局加载后只启动可见模块；隐藏或卸载时由各数据源停止重试与请求。
for (const [moduleKey, source] of activities.sources) {
  watch(
    () => layoutReady.value && isHomeModuleVisible('activities') && isHomeModuleVisible(moduleKey),
    visible => (visible ? source.start() : source.stop()),
    { immediate: true }
  )
}

// 顶层模块的 PV 档案代号，仅作装饰
const MODULE_CODES: Record<string, string> = {
  command: 'COMMAND TERMINAL',
  quick: 'DEPARTMENT INDEX',
  proxy: 'OPERATION RECORD',
  activities: 'FIELD INTELLIGENCE',
}

const visibleTopLevelKeys = computed(() =>
  homeTopLevelOrder.value.filter(key => isHomeModuleVisible(key))
)

const moduleSerial = (key: string) =>
  `A-${String(visibleTopLevelKeys.value.indexOf(key as never) + 1).padStart(2, '0')}`

const moduleTitle = (key: string) =>
  homeModules.value.find(module => module.key === key)?.title ?? key

const WEEKDAYS = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY']

// 抬头日期行：首页打开期间跨日较少，进入页面时取一次即可
const heroDate = (() => {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7)
  return {
    date: `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`,
    weekday: WEEKDAYS[now.getDay()],
    week: String(week).padStart(2, '0'),
  }
})()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour >= 5 && hour < 11) {
    return t('home.greeting.morning')
  } else if (hour >= 11 && hour < 14) {
    return t('home.greeting.noon')
  } else if (hour >= 14 && hour < 18) {
    return t('home.greeting.afternoon')
  } else if (hour >= 18 && hour < 23) {
    return t('home.greeting.evening')
  } else {
    return t('home.greeting.night')
  }
})

const loadHomeData = async () => {
  void loadManagedActivityModules()
  await restoreSelectedHomeTaskIds()
  fetchSchedulerTaskOptions({ quiet: true })
  fetchOverviewData()
  fetchNoticeData()
}

onMounted(async () => {
  await loadHomeLayout()

  if (isBootstrapping.value) {
    // 已有快照时直接展示内容，刷新不再用骨架遮挡；无快照时显示加载态
    if (!hasSnapshot.value) {
      loading.value = true
    }
    noticeLoading.value = true

    const stopWatching = watch(isBootstrapping, bootstrapping => {
      if (bootstrapping) {
        return
      }

      stopWatching()
      loadHomeData()
    })
    return
  }

  loadHomeData()
})
</script>

<style scoped>
.home-page {
  max-width: 1600px;
  margin: 0 auto;
}

/* ── 档案抬头 ─────────────────────────────────────────────────────────── */
.home-hero {
  margin-bottom: 28px;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--app-rhine-rule);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
}

.home-hero-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.home-hero-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  letter-spacing: 0.16em;
  user-select: none;
}

.home-hero-index {
  color: var(--app-rhine-accent);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.home-hero-kicker {
  color: var(--app-rhine-muted-index);
}

.home-hero-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ant-color-text);
}

.home-hero-date {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--ant-color-text-tertiary);
  font-variant-numeric: tabular-nums;
  user-select: none;
}

.home-hero-date i {
  width: 18px;
  height: 1px;
  background: var(--app-rhine-hairline);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.layout-edit-button {
  min-width: 104px;
}

.notice-button {
  min-width: 120px;
}

/* ── 模块档案分节 ─────────────────────────────────────────────────────── */
.home-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.home-module {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.home-module-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.home-module-index {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--app-rhine-accent);
  font-variant-numeric: tabular-nums;
  user-select: none;
}

.home-module-code {
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-muted-index);
  white-space: nowrap;
  user-select: none;
}

.home-module-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--ant-color-text);
  white-space: nowrap;
}

.home-module-rule {
  flex: 1;
  height: 1px;
  align-self: center;
  background: var(--app-rhine-hairline);
}

@media (max-width: 800px) {
  .home-hero {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }

  .home-hero-title {
    font-size: 26px;
  }

  .header-actions {
    justify-content: flex-start;
  }

  .home-module-code {
    display: none;
  }
}
</style>
