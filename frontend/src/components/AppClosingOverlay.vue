<template>
  <Teleport to="body">
    <div v-if="visible" class="app-closing-overlay">
      <div class="closing-content">
        <div class="closing-spinner">
          <LoadingOutlined />
        </div>
        <div class="closing-text">{{ t('comp.closingBackend') }}</div>
        <div class="closing-subtitle">{{ t('comp.pleaseWaitAppClosing') }}</div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { LoadingOutlined } from '@ant-design/icons-vue'

const { t } = useI18n()

defineProps<{
  visible: boolean
}>()
</script>

<style scoped>
.app-closing-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--app-rhine-modal-backdrop);
  backdrop-filter: blur(8px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease-out;
}

.closing-content {
  text-align: center;
  color: var(--ant-color-text);
  padding: 32px 40px;
  border-radius: 2px;
  background: var(--ant-color-bg-elevated);
  border: 1px solid var(--ant-color-border);
  border-top: 3px solid var(--app-rhine-rule);
  box-shadow: var(--app-rhine-card-shadow);
  min-width: 300px;
}

.closing-spinner {
  font-size: 30px;
  margin-bottom: 16px;
  color: var(--app-rhine-accent);
  animation: spin 1s linear infinite;
}

.closing-text {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
  color: var(--ant-color-text);
}

.closing-subtitle {
  font-size: 13px;
  color: var(--ant-color-text-secondary);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
