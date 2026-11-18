<template>
  <a-card class="shortcut-card" :title="t('home.quick.title')">
    <section class="quick-actions" :aria-label="t('home.quick.aria')">
      <button
        v-for="action in quickActions"
        :key="action.path"
        type="button"
        class="quick-action"
        @click="navigateTo(action.path)"
      >
        <span class="quick-action-icon">
          <component :is="action.icon" />
        </span>
        <span class="quick-action-text">
          <span class="quick-action-title">{{ action.title }}</span>
          <span class="quick-action-desc">{{ action.description }}</span>
        </span>
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
    icon: FileTextOutlined,
  },
  {
    title: t('home.quick.plans'),
    description: t('home.quick.plansDesc'),
    path: '/plans',
    icon: CalendarOutlined,
  },
  {
    title: t('home.quick.emulators'),
    description: t('home.quick.emulatorsDesc'),
    path: '/emulators',
    icon: DatabaseOutlined,
  },
  {
    title: t('home.quick.queue'),
    description: t('home.quick.queueDesc'),
    path: '/queue',
    icon: UnorderedListOutlined,
  },
  {
    title: t('home.quick.scheduler'),
    description: t('home.quick.schedulerDesc'),
    path: '/scheduler',
    icon: ControlOutlined,
  },
])
</script>

<style scoped>
.shortcut-card {
  border-radius: 2px;
  box-shadow: var(--app-rhine-card-shadow);
}

.shortcut-card :deep(.ant-card-body) {
  padding: 0;
}

.shortcut-card :deep(.ant-card-head-title) {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
}

.quick-action {
  min-height: 102px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  text-align: left;
  color: var(--ant-color-text);
  background: transparent;
  border: none;
  border-right: 1px solid var(--ant-color-border-secondary);
  cursor: pointer;
  transition:
    background-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

.quick-action:last-child {
  border-right: none;
}

.quick-action:hover {
  background: var(--app-rhine-hover-bg);
  color: var(--app-rhine-accent);
  box-shadow: inset 0 -2px 0 var(--app-rhine-accent);
}

.quick-action:hover .quick-action-icon {
  color: var(--app-rhine-accent);
  border-color: var(--app-rhine-accent-border);
  background: var(--app-rhine-accent-soft);
}

.quick-action:focus-visible {
  outline: 2px solid var(--app-rhine-accent);
  outline-offset: -2px;
}

.quick-action-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 40px;
  color: var(--ant-color-text);
  background: var(--app-rhine-surface-subtle);
  border: 1px solid var(--ant-color-border);
  border-radius: 2px;
  font-size: 18px;
  transition:
    color 0.16s ease,
    border-color 0.16s ease,
    background-color 0.16s ease;
}

.quick-action-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.quick-action-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ant-color-text);
}

.quick-action-desc {
  font-size: 13px;
  color: var(--ant-color-text-tertiary);
  white-space: normal;
}

@media (max-width: 1240px) {
  .quick-actions {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .quick-action:nth-child(3n) {
    border-right: none;
  }

  .quick-action:nth-child(n + 4) {
    border-top: 1px solid var(--ant-color-border-secondary);
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
    border-right: 1px solid var(--ant-color-border-secondary);
  }

  .quick-action:nth-child(n + 3) {
    border-top: 1px solid var(--ant-color-border-secondary);
  }
}

@media (max-width: 560px) {
  .quick-actions {
    grid-template-columns: 1fr;
  }

  .quick-action {
    min-height: 82px;
    border-right: none;
    border-top: 1px solid var(--ant-color-border-secondary);
  }

  .quick-action:nth-child(3n) {
    border-right: none;
  }

  .quick-action:first-child {
    border-top: none;
  }
}
</style>
