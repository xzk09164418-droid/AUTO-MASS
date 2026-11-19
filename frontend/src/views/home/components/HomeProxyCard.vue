<template>
  <section class="overview-grid" :aria-label="t('home.proxy.aria')">
    <!-- 模块标题由首页档案分节给出；卡片顶部只保留记录条与展开按钮 -->
    <a-card class="proxy-card">
      <div class="proxy-bar">
        <span class="proxy-bar-meta" aria-hidden="true">
          RECORD // ACCOUNTS
          <strong>{{ String(Object.keys(proxyData).length).padStart(2, '0') }}</strong>
        </span>
        <a-button type="text" size="small" :aria-expanded="expanded" @click="expanded = !expanded">
          <template #icon>
            <UpOutlined v-if="expanded" />
            <DownOutlined v-else />
          </template>
          {{ t(expanded ? 'home.proxy.collapse' : 'home.proxy.expand') }}
        </a-button>
      </div>
      <a-skeleton v-if="expanded && loading" active class="proxy-skeleton" />
      <div v-else-if="expanded && Object.keys(proxyData).length > 0" class="proxy-list">
        <a-row :gutter="[16, 16]">
          <a-col v-for="(proxy, username) in proxyData" :key="username" :xs="24" :lg="12" :xl="8">
            <div class="proxy-item">
              <div class="proxy-header">
                <div class="proxy-username">
                  <UserOutlined class="user-icon" />
                  <span class="username">{{ username }}</span>
                </div>
              </div>

              <div class="proxy-stats">
                <div class="stat-item full-width">
                  <a-statistic
                    :title="t('home.proxy.lastTime')"
                    :value="formatProxyDisplay(proxy.LastProxyDate)"
                  />
                </div>
                <div class="stat-pair">
                  <a-statistic :title="t('home.proxy.times')" :value="proxy.ProxyTimes" />
                  <a-statistic
                    :title="t('home.proxy.errors')"
                    :value="proxy.ErrorTimes"
                    :value-style="{
                      color: proxy.ErrorTimes > 0 ? 'var(--ant-color-error)' : undefined,
                    }"
                  />
                </div>
              </div>
            </div>
          </a-col>
        </a-row>
      </div>

      <div v-else-if="expanded && !loading" class="empty-state">
        <img src="@/assets/NoData.png" :alt="t('home.empty.noData')" class="empty-image" />
      </div>
    </a-card>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ref } from 'vue'
import { DownOutlined, UpOutlined, UserOutlined } from '@ant-design/icons-vue'
import { formatBackendDateTime } from '@/utils/dateDisplay'
import type { ProxyInfo } from '@/types/home'

defineOptions({
  name: 'HomeProxyCard',
})

interface Props {
  loading: boolean
  proxyData: Record<string, ProxyInfo>
}

defineProps<Props>()

const { t } = useI18n()
const expanded = ref(false)

const formatProxyDisplay = (dateString: string) => {
  if (dateString === '暂无代理数据') {
    return t('home.proxy.noData')
  }
  return formatBackendDateTime(dateString)
}
</script>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  align-items: start;
}

.proxy-card {
  width: 100%;
}

.proxy-card :deep(.ant-card-body) {
  padding: 0;
}

.proxy-bar {
  min-height: 44px;
  padding: 0 12px 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.proxy-bar-meta {
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--app-rhine-muted-index);
  user-select: none;
}

.proxy-bar-meta strong {
  margin-left: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-rhine-accent);
  font-variant-numeric: tabular-nums;
}

.proxy-skeleton,
.proxy-list,
.empty-state {
  border-top: 1px solid var(--app-rhine-hairline);
}

.proxy-skeleton {
  padding: 20px;
}

.proxy-list {
  padding: 20px;
}

.empty-state {
  padding: 40px 0;
  text-align: center;
}

.empty-image {
  width: 48%;
  max-width: 180px;
  opacity: 0.82;
}

.proxy-list .proxy-item {
  min-height: 164px;
  padding: 16px;
  border: 1px solid var(--app-rhine-hairline);
  border-left: 2px solid var(--app-rhine-accent);
}

.proxy-header {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.proxy-username {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-icon {
  color: var(--ant-color-text-secondary);
}

.username {
  min-width: 0;
  overflow: hidden;
  color: var(--ant-color-text);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.proxy-stats {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.stat-item.full-width {
  grid-column: 1 / -1;
}

.stat-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 560px) {
  .stat-pair {
    grid-template-columns: 1fr;
  }
}
</style>
