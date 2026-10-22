<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { t } from '@/i18n'
import { useLocalControls } from '@/composables/useLocalControls'
import type { LocalConfig } from '@/types/localControls'

const { loading, error, status, getConfig, saveConfig, refreshStatus, action } = useLocalControls()
const saving = ref(false)
const loaded = ref(false)
const tab = ref('settings')
const leaseOpen = ref(false)
const formRef = ref()
const form = reactive<LocalConfig>({
  ChildSession: {
    Enabled: false,
    HostPort: 36165,
    Resolution: '2560x1440',
    StartHidden: false,
    WatchMode: true,
  },
  Hotkey: {
    Enabled: true,
    ToggleStartStop: 'Ctrl+Alt+S',
    PreviousTask: 'Ctrl+Alt+Left',
    NextTask: 'Ctrl+Alt+Right',
  },
})
const lease = reactive({
  caller: '',
  disconnectRdpView: true,
  timeoutSeconds: 3600,
  waitForGrant: false,
  waitTimeout: 300,
})
const connected = computed(() => status.value.hostConnected === true)
let timer: ReturnType<typeof setInterval> | undefined

async function load() {
  loading.value = true
  error.value = ''
  try {
    const config = await getConfig()
    Object.assign(form.ChildSession, config.ChildSession)
    Object.assign(form.Hotkey, config.Hotkey)
    loaded.value = true
    await refreshStatus()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}
async function save() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  error.value = ''
  try {
    await saveConfig(form)
    message.success(t('localControls.saved'))
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
function confirmAction(name: string, payload: object = {}) {
  Modal.confirm({
    title: t('localControls.confirm'),
    content: t(`localControls.${name}`),
    okType: 'danger',
    onOk: async () => {
      if (!(await action(name, payload))) throw new Error(error.value)
    },
  })
}
async function acquire() {
  if (!lease.caller.trim()) {
    message.error(t('localControls.callerRequired'))
    return
  }
  if (await action('acquire', { ...lease, caller: lease.caller.trim() })) leaseOpen.value = false
}
onMounted(async () => {
  await load()
  timer = setInterval(() => {
    void refreshStatus().catch(err => {
      error.value = String(err)
    })
  }, 5000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="local-controls">
    <div class="page-heading">
      <h1>{{ t('localControls.title') }}</h1>
      <a-button :loading="loading" @click="load">{{ t('localControls.reload') }}</a-button>
    </div>
    <a-alert v-if="error" :message="error" type="error" show-icon />
    <a-tabs v-model:active-key="tab">
      <a-tab-pane key="settings" :tab="t('localControls.settings')">
        <a-spin :spinning="loading">
          <a-form
            ref="formRef"
            :model="form"
            layout="vertical"
            class="local-form"
            :disabled="!loaded || saving"
          >
            <div class="form-section">
              <div class="section-header">
                <h3>{{ t('localControls.desktop') }}</h3>
              </div>
              <a-row :gutter="24">
                <a-col :xs="24" :lg="12"
                  ><a-form-item :label="t('localControls.enabled')"
                    ><a-switch v-model:checked="form.ChildSession.Enabled" /></a-form-item
                ></a-col>
                <a-col :xs="24" :lg="12"
                  ><a-form-item :label="t('localControls.hidden')"
                    ><a-switch v-model:checked="form.ChildSession.StartHidden" /></a-form-item
                ></a-col>
                <a-col :xs="24" :lg="12"
                  ><a-form-item
                    :label="t('localControls.resolution')"
                    :name="['ChildSession', 'Resolution']"
                    :rules="[
                      {
                        required: true,
                        pattern: /^\d{3,5}x\d{3,5}$/,
                        message: t('localControls.resolutionHint'),
                      },
                    ]"
                    ><a-auto-complete
                      v-model:value="form.ChildSession.Resolution"
                      :options="
                        ['1280x720', '1600x900', '1920x1080', '2560x1440', '3840x2160'].map(
                          value => ({ value })
                        )
                      " /></a-form-item
                ></a-col>
                <a-col :xs="24" :lg="12"
                  ><a-form-item
                    :label="t('localControls.port')"
                    :name="['ChildSession', 'HostPort']"
                    :rules="[{ required: true, type: 'number', min: 1024, max: 65535 }]"
                    ><a-input-number
                      v-model:value="form.ChildSession.HostPort"
                      :min="1024"
                      :max="65535"
                      class="full-width" /></a-form-item
                ></a-col>
                <a-col :xs="24" :lg="12"
                  ><a-form-item :label="t('localControls.watch')"
                    ><a-switch v-model:checked="form.ChildSession.WatchMode" /></a-form-item
                ></a-col>
              </a-row>
            </div>
            <div class="form-section">
              <div class="section-header">
                <h3>{{ t('localControls.hotkeys') }}</h3>
              </div>
              <a-form-item :label="t('localControls.hotkeysEnabled')"
                ><a-switch v-model:checked="form.Hotkey.Enabled"
              /></a-form-item>
              <a-row :gutter="24">
                <a-col
                  v-for="key in ['ToggleStartStop', 'PreviousTask', 'NextTask'] as const"
                  :key="key"
                  :xs="24"
                  :lg="8"
                >
                  <a-form-item
                    :label="t(`localControls.${key}`)"
                    :name="['Hotkey', key]"
                    :rules="[{ required: form.Hotkey.Enabled, whitespace: true }]"
                  >
                    <a-input
                      v-model:value="form.Hotkey[key]"
                      :disabled="!form.Hotkey.Enabled"
                      placeholder="Ctrl+Alt+S"
                    />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-typography-paragraph type="secondary">{{
                t('localControls.hotkeysHint')
              }}</a-typography-paragraph>
            </div>
            <a-button type="primary" :loading="saving" :disabled="!loaded" @click="save">{{
              t('localControls.save')
            }}</a-button>
          </a-form>
        </a-spin>
      </a-tab-pane>
      <a-tab-pane key="desktop" :tab="t('localControls.controls')">
        <a-descriptions bordered :column="2" class="status-grid">
          <a-descriptions-item :label="t('localControls.connection')">{{
            t(connected ? 'localControls.connected' : 'localControls.disconnected')
          }}</a-descriptions-item>
          <a-descriptions-item :label="t('localControls.session')">{{
            status.childSessionId ?? '—'
          }}</a-descriptions-item>
          <a-descriptions-item :label="t('localControls.running')">{{
            t(status.inSubtaskExecution ? 'localControls.busy' : 'localControls.idle')
          }}</a-descriptions-item>
          <a-descriptions-item :label="t('localControls.window')">{{
            status.hostStatus?.ok
              ? t(status.hostStatus.trayMode ? 'localControls.inTray' : 'localControls.visible')
              : t('localControls.unavailable')
          }}</a-descriptions-item>
        </a-descriptions>
        <div class="control-actions">
          <a-button
            type="primary"
            :loading="loading"
            @click="action('window', { visible: true })"
            >{{ t('localControls.show') }}</a-button
          >
          <a-button :disabled="loading" @click="action('window', { visible: false })">{{
            t('localControls.hide')
          }}</a-button>
          <a-button :loading="loading" @click="action('connect')">{{
            t('localControls.connect')
          }}</a-button>
          <a-button danger :disabled="loading" @click="confirmAction('logoff')">{{
            t('localControls.logoff')
          }}</a-button>
        </div>
        <div class="control-actions">
          <a-button
            :disabled="loading || !connected"
            @click="action('window', { watchMode: !status.hostStatus?.watchMode })"
            >{{ t('localControls.toggleWatch') }}</a-button
          >
          <a-button
            :disabled="loading || !connected"
            @click="action('window', { smartSizing: !status.hostStatus?.smartSizing })"
            >{{ t('localControls.smartSizing') }}</a-button
          >
          <a-button
            :disabled="loading || !connected"
            @click="action('window', { topmost: !status.hostStatus?.topmost })"
            >{{ t('localControls.topmost') }}</a-button
          >
          <a-button
            :disabled="loading || !connected"
            @click="action('window', { shortcut: 'Win+Tab' })"
            >Win+Tab</a-button
          >
          <a-button
            :disabled="loading || !connected"
            @click="action('window', { shortcut: 'Win+D' })"
            >Win+D</a-button
          >
        </div>
        <div class="form-section">
          <div class="section-header">
            <h3>{{ t('localControls.navigation') }}</h3>
          </div>
          <a-space wrap
            ><a-button
              v-for="name in ['toggle', 'previous', 'next']"
              :key="name"
              :loading="loading"
              @click="confirmAction(name)"
              >{{ t(`localControls.${name}`) }}</a-button
            ></a-space
          >
        </div>
        <div class="section-header">
          <h3>{{ t('localControls.leases') }}</h3>
          <a-button :disabled="loading" @click="leaseOpen = true">{{
            t('localControls.acquire')
          }}</a-button>
        </div>
        <a-table
          :data-source="status.activeLeases || []"
          row-key="leaseId"
          :pagination="false"
          :scroll="{ x: 700 }"
        >
          <a-table-column key="caller" data-index="caller" :title="t('localControls.caller')" />
          <a-table-column key="leaseId" data-index="leaseId" :title="t('localControls.leaseId')" />
          <a-table-column key="status" data-index="status" :title="t('localControls.status')" />
          <a-table-column key="action" :title="t('localControls.action')"
            ><template #default="{ record }"
              ><a-button
                danger
                :disabled="loading"
                @click="confirmAction('release', { leaseId: record.leaseId })"
                >{{ t('localControls.release') }}</a-button
              ></template
            ></a-table-column
          >
        </a-table>
      </a-tab-pane>
    </a-tabs>
    <a-modal
      v-model:open="leaseOpen"
      :title="t('localControls.acquire')"
      :confirm-loading="loading"
      @ok="acquire"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('localControls.caller')" required
          ><a-input v-model:value="lease.caller"
        /></a-form-item>
        <a-form-item :label="t('localControls.disconnect')"
          ><a-switch v-model:checked="lease.disconnectRdpView"
        /></a-form-item>
        <a-form-item :label="t('localControls.timeout')"
          ><a-input-number v-model:value="lease.timeoutSeconds" :min="1" :max="86400"
        /></a-form-item>
        <a-form-item :label="t('localControls.wait')"
          ><a-switch v-model:checked="lease.waitForGrant"
        /></a-form-item>
        <a-form-item :label="t('localControls.waitTimeout')"
          ><a-input-number
            v-model:value="lease.waitTimeout"
            :min="1"
            :max="7200"
            :disabled="!lease.waitForGrant"
        /></a-form-item>
      </a-form>
      <a-alert v-if="error" :message="error" type="error" show-icon />
    </a-modal>
  </div>
</template>

<style scoped>
.local-controls {
  max-width: 1440px;
  margin: 0 auto;
}
.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.page-heading h1 {
  margin: 0;
  font-size: 28px;
  color: var(--ant-color-text);
}
.local-form {
  padding-top: 16px;
}
.full-width {
  width: 100%;
}
.status-grid {
  margin: 16px 0 24px;
}
.control-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
}
</style>
