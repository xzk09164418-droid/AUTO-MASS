<template>
  <!-- 模块标题由首页档案分节统一给出，这里不再重复卡片标题 -->
  <a-card class="shortcut-card">
    <section class="quick-actions" :aria-label="t('home.quick.aria')">
      <button
        v-for="action in quickActions"
        :key="action.path"
        type="button"
        class="quick-action"
        @click="navigateTo(action.path)"
      >
        <span class="quick-action-top" aria-hidden="true">
          <span class="quick-action-index">{{ action.index }}</span>
          <span class="quick-action-icon">
            <component :is="action.icon" />
          </span>
        </span>
        <span class="quick-action-text">
          <span class="quick-action-title">{{ action.title }}</span>
          <span class="quick-action-desc">{{ action.description }}</span>
        </span>
        <span class="quick-action-go" aria-hidden="true">ACCESS →</span>
      </button>
    </section>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  CalendarOutlined,
  ControlOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons-vue'
import { navigateTo } from '@/router'

const { t } = useI18n()

const quickActions = computed(() => [
  {
    title: t('home.quick.scripts'),
    description: t('home.quick.scriptsDesc'),
    path: '/scripts',
    index: '02',
    icon: FileTextOutlined,
  },
  {
    title: t('home.quick.plans'),
    description: t('home.quick.plansDesc'),
    path: '/plans',
    index: '03',
    icon: CalendarOutlined,
  },
  {
    title: t('home.quick.emulators'),
    description: t('home.quick.emulatorsDesc'),
    path: '/emulators',
    index: '04',
    icon: DatabaseOutlined,
  },
  {
    title: t('home.quick.queue'),
    description: t('home.quick.queueDesc'),
    path: '/queue',
    index: '05',
    icon: UnorderedListOutlined,
  },
  {
    title: t('home.quick.scheduler'),
    description: t('home.quick.schedulerDesc'),
    path: '/scheduler',
    index: '06',
    icon: ControlOutlined,
  },
])
</script>

<style scoped>
.shortcut-card :deep(.ant-card-body) {
  padding: 0;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

/* 编号与顶部导航一致，形成 PV 档案索引 */
.quick-action {
  position: relative;
  min-height: 150px;
  padding: 18px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
  color: var(--ant-color-text);
  background: transparent;
  border: none;
  border-right: 1px solid var(--app-rhine-hairline);
  cursor: pointer;
  font: inherit;
  transition: background-color 0.18s ease;
}

.quick-action::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: var(--app-rhine-accent);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
}

.quick-action:last-child {
  border-right: none;
}

.quick-action:hover {
  background: var(--app-rhine-hover-bg);
}

.quick-action:hover::after {
  transform: scaleX(1);
}

.quick-action:focus-visible {
  outline: 1px solid var(--app-rhine-accent);
  outline-offset: -4px;
}

.quick-action-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.quick-action-index {
  font-size: 34px;
  line-height: 1;
  font-weight: 300;
  letter-spacing: 0.02em;
  color: var(--ant-color-text-tertiary);
  font-variant-numeric: tabular-nums;
  transition: color 0.18s ease;
}

.quick-action:hover .quick-action-index {
  color: var(--app-rhine-accent);
}

.quick-action-icon {
  font-size: 18px;
  color: var(--ant-color-text-secondary);
}

.quick-action-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.quick-action-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ant-color-text);
}

.quick-action-desc {
  font-size: 13px;
  color: var(--ant-color-text-tertiary);
  white-space: normal;
}

.quick-action-go {
  margin-top: auto;
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-muted-index);
  transition: color 0.18s ease;
}

.quick-action:hover .quick-action-go {
  color: var(--app-rhine-accent);
}

@media (max-width: 1240px) {
  .quick-actions {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .quick-action:nth-child(3n) {
    border-right: none;
  }

  .quick-action:nth-child(n + 4) {
    border-top: 1px solid var(--app-rhine-hairline);
  }
}

@media (max-width: 800px) {
  .quick-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick-action:nth-child(2n) {
    border-right: none;
  }

  .quick-action:nth-child(3n) {
    border-right: 1px solid var(--app-rhine-hairline);
  }

  .quick-action:nth-child(n + 3) {
    border-top: 1px solid var(--app-rhine-hairline);
  }
}

@media (max-width: 560px) {
  .quick-actions {
    grid-template-columns: 1fr;
  }

  .quick-action {
    min-height: 0;
    border-right: none;
    border-top: 1px solid var(--app-rhine-hairline);
  }

  .quick-action:nth-child(3n) {
    border-right: none;
  }

  .quick-action:first-child {
    border-top: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .quick-action::after {
    transition: none;
  }
}
</style>
