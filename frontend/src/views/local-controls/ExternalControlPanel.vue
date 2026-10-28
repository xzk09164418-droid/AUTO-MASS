<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { ExternalHoldInfo } from '@/api'
import { useExternalControl } from '@/composables/useExternalControl'
import { useScriptApi } from '@/composables/useScriptApi'
import { externalControlExamples } from './externalControlExamples'

const { snapshot, schemas, backendUrl, loading, error, refresh, save, release, testMail } =
  useExternalControl()
const { getScripts } = useScriptApi()
const { t } = useI18n()
const frontendAddress = window.location.origin
const frontendPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
const scripts = ref<{ label: string; value: string }[]>([])
const scriptId = ref('')
const callerId = ref('external_program')
const holdId = ref(crypto.randomUUID())
const section = ref('desktop')
const holdRowKey = (row: ExternalHoldInfo) => `${row.callerId}:${row.holdId}`
const form = reactive({
  enabled: false,
  email: '',
  authorizationCode: '',
  callerId: '',
  callerSecret: '',
})
const base = computed(() => backendUrl.value.replace(/\/$/, ''))
const backendPort = computed(() => {
  try {
    return new URL(base.value).port || '80'
  } catch {
    return '—'
  }
})
const example = computed(() =>
  externalControlExamples(base.value, scriptId.value || '<脚本 ID>', callerId.value, holdId.value)
)
const samples = computed(() =>
  section.value === 'desktop'
    ? [
        {
          title: 'POST /api/child-session/acquire（/request 为兼容别名）',
          text: example.value.desktopAcquire,
        },
        {
          title: '申请响应示例',
          text: JSON.stringify(
            { code: 200, leaseId: '<租约 ID>', leaseStatus: 'pending', childSessionId: null },
            null,
            2
          ),
        },
        { title: 'GET /api/child-session/status', text: `${base.value}/api/child-session/status` },
        { title: 'POST /api/child-session/release', text: example.value.desktopRelease },
      ]
    : [
        {
          title: '脚本占用接口地址',
          text: `${example.value.url}/acquire\n${example.value.url}/release\n${example.value.url}/status`,
        },
        { title: '签名前的 JSON（申请时 ttlSeconds 必填）', text: example.value.command },
        {
          title: 'HTTP / 邮件正文格式（用 Python 示例生成实际签名）',
          text: example.value.envelope,
        },
        { title: 'Python 签名与调用示例', text: example.value.python },
        { title: 'cURL（先将已签名正文保存为 envelope.json）', text: example.value.curl },
        {
          title: '回执示例：[AUTO-MAS RECEIPT v1]',
          text: JSON.stringify(
            {
              code: 200,
              requestId: '<请求 ID>',
              hold: {
                holdId: holdId.value,
                callerId: callerId.value,
                scriptId: scriptId.value,
                state: 'active',
                expiresAt: '<UTC Unix 秒>',
              },
              remainingHolds: 1,
            },
            null,
            2
          ),
        },
      ]
)

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch {
    message.error('复制失败，请手动选择文本复制')
  }
}
async function load() {
  try {
    await refresh()
    Object.assign(form, {
      enabled: snapshot.value?.settings?.enabled,
      email: snapshot.value?.settings?.email,
    })
    scripts.value = (await getScripts()).map(script => ({
      label: `${script.name} (${script.uid})`,
      value: script.uid,
    }))
    scriptId.value ||= scripts.value[0]?.value || ''
  } catch {
    /* composable 的错误区域保留具体原因。 */
  }
}
async function saveForm(removeCaller = false) {
  try {
    await save({
      ...form,
      callerId: form.callerId || null,
      callerSecret: form.callerSecret || null,
      authorizationCode: form.authorizationCode || null,
      removeCaller,
    })
    form.authorizationCode = ''
    form.callerSecret = ''
    message.success('设置已保存')
  } catch {
    /* 保留输入供修正，密钥不进入通知或日志。 */
  }
}
function forceRelease(hold: ExternalHoldInfo) {
  Modal.confirm({
    title: '解除外部占用？',
    content: '请确认外部程序已停止使用。解除最后一项占用后，等待中的项目会继续运行。',
    okType: 'danger',
    onOk: () => release(hold.callerId, hold.holdId),
  })
}
async function testConnection() {
  try {
    message.success(await testMail())
  } catch {
    /* 错误由 composable 展示。 */
  }
}
onMounted(load)
</script>

<template>
  <section class="external-control-panel">
    <a-alert v-if="error" type="error" show-icon :message="error" />
    <a-descriptions :title="t('hostPorts.title')" bordered :column="1">
      <a-descriptions-item :label="t('hostPorts.frontend')">
        <code>{{ frontendAddress }}</code> · {{ t('hostPorts.port') }} {{ frontendPort }}
      </a-descriptions-item>
      <a-descriptions-item :label="t('hostPorts.backend')">
        <code>{{ base }}</code> · {{ t('hostPorts.port') }} {{ backendPort }}
      </a-descriptions-item>
    </a-descriptions>
    <a-alert
      type="info"
      show-icon
      message="以下地址是当前 Python 后端地址，不是远程桌面宿主端口。脚本占用接口仅接受本机签名请求；远程控制请使用 QQ 邮箱。"
    />
    <div class="external-actions">
      <code>{{ base }}</code
      ><a-button @click="copy(base)">复制后端地址</a-button
      ><a-button :loading="loading" @click="load">刷新状态</a-button>
    </div>
    <a-tabs v-model:active-key="section">
      <a-tab-pane key="desktop" tab="远程桌面借用">
        <p>
          申请后等待 leaseStatus=granted，再连接远程桌面；使用结束必须回传 leaseId 释放。pending
          表示等待当前子任务结束并让渡桌面，不会停止正在运行的项目。查询 /status 返回
          data，其中包含桌面和租约状态。
        </p>
      </a-tab-pane>
      <a-tab-pane key="holds" tab="脚本占用">
        <p>
          申请 → stopping（停止及清理）→ active（可以使用）→ released /
          expired。每个调用方只能释放自己的占用；全部解除后按完全释放顺序运行。当前项目会被停止，恢复时从头执行；手动停止的队列不会复活。
        </p>
      </a-tab-pane>
      <a-tab-pane key="mail" tab="QQ 邮箱指令">
        <p>
          自己发给自己，标题固定为 [AUTO-MAS COMMAND v1]，正文为签名后的 JSON。每 5
          秒检查一次新邮件；首次启用忽略历史邮件，之后断线补收。有效期从签发时间计算，超过 5
          分钟的指令拒绝执行。
        </p>
        <p>
          结果发送到同一邮箱，标题为 [AUTO-MAS RECEIPT v1]。必须收到 active
          结果才能使用项目；邮件延迟不等同于本机接口响应时间。
        </p>
        <a-form layout="vertical" class="external-settings">
          <a-form-item label="启用邮箱控制"
            ><a-switch v-model:checked="form.enabled"
          /></a-form-item>
          <a-form-item label="QQ 邮箱账号"
            ><a-input v-model:value="form.email" autocomplete="off"
          /></a-form-item>
          <a-form-item
            :label="`邮箱授权码${snapshot?.settings?.hasAuthorizationCode ? '（已配置，留空保留）' : ''}`"
            ><a-input-password v-model:value="form.authorizationCode" autocomplete="new-password"
          /></a-form-item>
          <a-form-item label="调用方 ID"><a-input v-model:value="form.callerId" /></a-form-item>
          <a-form-item label="调用方独立密钥（至少 32 字符，留空保留）"
            ><a-input-password v-model:value="form.callerSecret" autocomplete="new-password"
          /></a-form-item>
          <a-button :loading="loading" @click="testConnection">测试已保存的邮箱连接</a-button>
          <a-space wrap
            ><a-button type="primary" :loading="loading" @click="saveForm(false)"
              >保存设置 / 调用方</a-button
            ><a-popconfirm
              title="删除该调用方密钥？已有占用仍等待到期或手动解除。"
              @confirm="saveForm(true)"
              ><a-button danger :disabled="!form.callerId">删除调用方</a-button></a-popconfirm
            ></a-space
          >
        </a-form>
        <p>已配置调用方：{{ snapshot?.settings?.callers?.join('、') || '无' }}</p>
        <a-alert v-if="snapshot?.mailError" type="error" :message="snapshot.mailError" />
      </a-tab-pane>
    </a-tabs>
    <a-form layout="vertical" class="external-example-fields">
      <a-form-item v-if="section !== 'desktop'" label="示例项目（真实脚本 ID）"
        ><a-select v-model:value="scriptId" :options="scripts"
      /></a-form-item>
      <a-form-item label="示例调用方"><a-input v-model:value="callerId" /></a-form-item>
      <a-form-item v-if="section !== 'desktop'" label="示例占用 ID（申请、查询、释放必须一致）"
        ><a-input v-model:value="holdId"
      /></a-form-item>
    </a-form>
    <div v-for="sample in samples" :key="sample.title" class="external-sample">
      <div class="external-actions">
        <strong>{{ sample.title }}</strong
        ><a-button size="small" @click="copy(sample.text)">复制</a-button>
      </div>
      <pre>{{ sample.text }}</pre>
    </div>
    <a-collapse>
      <a-collapse-panel
        key="contract"
        header="字段类型、必填项、默认值与取值范围（来自当前后端契约）"
      >
        <pre>{{ JSON.stringify(schemas, null, 2) }}</pre>
      </a-collapse-panel>
    </a-collapse>
    <h3>外部占用状态</h3>
    <a-table
      :data-source="snapshot?.holds || []"
      :row-key="holdRowKey"
      :scroll="{ x: 950 }"
      size="small"
    >
      <a-table-column title="调用方" data-index="callerId" /><a-table-column
        title="脚本 ID"
        data-index="scriptId"
      /><a-table-column title="占用 ID" data-index="holdId" /><a-table-column
        title="状态"
        data-index="state"
      />
      <a-table-column title="到期时间"
        ><template #default="{ record }">{{
          new Date(record.expiresAt * 1000).toLocaleString()
        }}</template></a-table-column
      >
      <a-table-column title="操作"
        ><template #default="{ record }"
          ><a-button
            v-if="['active', 'stopping', 'failed'].includes(record.state)"
            danger
            size="small"
            @click="forceRelease(record)"
            >解除</a-button
          ></template
        ></a-table-column
      >
    </a-table>
    <a-collapse
      ><a-collapse-panel key="results" header="最近指令处理结果">
        <pre>{{ JSON.stringify(snapshot?.results || [], null, 2) }}</pre>
      </a-collapse-panel></a-collapse
    >
  </section>
</template>

<style scoped>
.external-control-panel {
  min-width: 0;
  display: grid;
  gap: 16px;
}
.external-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  overflow-wrap: anywhere;
}
.external-example-fields,
.external-settings {
  display: grid;
  gap: 0 24px;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
}
.external-sample {
  min-width: 0;
}
pre {
  max-width: 100%;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  padding: 16px;
  border: 1px solid var(--ant-color-border-secondary);
  border-radius: 8px;
  background: var(--ant-color-bg-container);
  color: var(--ant-color-text);
}
</style>
