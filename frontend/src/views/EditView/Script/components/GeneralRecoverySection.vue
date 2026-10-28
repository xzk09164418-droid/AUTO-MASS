<template>
  <div class="form-section general-recovery">
    <div class="section-header">
      <h3>{{ t('generalRecovery.title') }}</h3>
    </div>
    <a-alert type="info" show-icon :message="t('generalRecovery.policy')" />
    <h4>{{ t('generalRecovery.taskKill') }}</h4>
    <p>{{ t('generalRecovery.emptyCleanup') }}</p>
    <a-form-item v-if="draft.TaskKill.length" :label="t('generalRecovery.mode')">
      <a-select v-model:value="draft.TaskKillMode" :options="modeOptions" />
    </a-form-item>
    <a-alert
      v-if="draft.TaskKill.length && draft.TaskKillMode === 'Force'"
      type="warning"
      show-icon
      :message="t('generalRecovery.forceWarning')"
    />
    <div v-for="(item, index) in draft.TaskKill" :key="index" class="recovery-item">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item :label="t('generalRecovery.processName')" required>
            <a-input v-model:value="item.Name" placeholder="example.exe" />
          </a-form-item>
        </a-col>
        <a-col :span="16">
          <a-form-item :label="t('generalRecovery.path')" required>
            <a-input v-model:value="item.Path" :placeholder="t('generalRecovery.pathHint')" />
          </a-form-item>
        </a-col>
      </a-row>
      <a-button danger @click="draft.TaskKill.splice(index, 1)">{{
        t('generalRecovery.remove')
      }}</a-button>
    </div>
    <a-button @click="draft.TaskKill.push({ Name: '', Path: '' })">{{
      t('generalRecovery.addCleanup')
    }}</a-button>

    <h4>{{ t('generalRecovery.restart') }}</h4>
    <p>{{ t('generalRecovery.restartHint') }}</p>
    <div v-for="(item, index) in draft.Restart" :key="index" class="recovery-item">
      <a-space>
        <strong>{{ index + 1 }}</strong>
        <a-radio :checked="item.IsMain" @change="selectMain(index)">{{
          t('generalRecovery.main')
        }}</a-radio>
        <a-button :disabled="index === 0" @click="move(index, -1)">{{
          t('generalRecovery.up')
        }}</a-button>
        <a-button :disabled="index === draft.Restart.length - 1" @click="move(index, 1)">{{
          t('generalRecovery.down')
        }}</a-button>
        <a-button danger @click="draft.Restart.splice(index, 1)">{{
          t('generalRecovery.remove')
        }}</a-button>
      </a-space>
      <a-row :gutter="16">
        <a-col :span="16">
          <a-form-item :label="t('generalRecovery.path')" required>
            <a-input v-model:value="item.Path" :placeholder="t('generalRecovery.pathHint')" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item :label="t('generalRecovery.wait')" required>
            <a-input-number
              v-model:value="item.WaitSeconds"
              :min="item.IsMain ? 10 : 0"
              :max="9999"
              :precision="0"
            />
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('generalRecovery.arguments')"
            ><a-input v-model:value="item.Arguments"
          /></a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item :label="t('generalRecovery.cwd')"
            ><a-input v-model:value="item.WorkingDirectory"
          /></a-form-item>
        </a-col>
      </a-row>
    </div>
    <a-button @click="addRestart">{{ t('generalRecovery.addRestart') }}</a-button>
    <a-alert v-if="error" type="error" show-icon :message="error" />
    <a-button type="primary" :loading="saving" @click="save">{{
      t('generalRecovery.save')
    }}</a-button>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useScriptApi } from '@/composables/useScriptApi'
import type { GeneralScriptConfig } from '@/types/script'

type RecoveryConfig = Required<
  Pick<GeneralScriptConfig['Script'], 'TaskKill' | 'TaskKillMode' | 'Restart'>
>
const props = defineProps<{ scriptId: string; config: GeneralScriptConfig['Script'] }>()
const emit = defineEmits<{ saved: [patch: RecoveryConfig] }>()
const { t } = useI18n()
const { updateScript } = useScriptApi()
const draft = reactive<RecoveryConfig>({ TaskKill: [], TaskKillMode: 'Force', Restart: [] })
const saving = ref(false)
const error = ref('')
const savedValue = ref('')
watch(
  () => [props.config.TaskKill, props.config.TaskKillMode, props.config.Restart],
  () => {
    Object.assign(
      draft,
      JSON.parse(
        JSON.stringify({
          TaskKill: props.config.TaskKill ?? [],
          TaskKillMode: props.config.TaskKillMode ?? 'Force',
          Restart: props.config.Restart ?? [],
        })
      )
    )
    savedValue.value = JSON.stringify(draft)
  },
  { immediate: true }
)
onBeforeRouteLeave(() => {
  if (JSON.stringify(draft) === savedValue.value) return true
  return new Promise<boolean>(resolve => {
    Modal.confirm({
      title: t('generalRecovery.unsaved'),
      content: t('generalRecovery.unsavedHint'),
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
})
const modeOptions = computed(() => [
  { value: 'Tracked', label: t('generalRecovery.tracked') },
  { value: 'Session', label: t('generalRecovery.session') },
  { value: 'Force', label: t('generalRecovery.force') },
])
function selectMain(index: number) {
  draft.Restart.forEach((item, i) => {
    item.IsMain = i === index
    if (item.IsMain) item.WaitSeconds = Math.max(10, item.WaitSeconds)
  })
}
function move(index: number, delta: number) {
  const [item] = draft.Restart.splice(index, 1)
  draft.Restart.splice(index + delta, 0, item)
}
function addRestart() {
  draft.Restart.push({
    Path: '',
    Arguments: '',
    WorkingDirectory: '',
    WaitSeconds: 50,
    IsMain: draft.Restart.length === 0,
  })
}
function absolutePath(value: string) {
  return /^(?:[a-z]:[\\/]|\\\\[^\\]+\\[^\\]+)/i.test(value) && !/[*?"]/.test(value)
}
async function save() {
  error.value = ''
  if (
    draft.TaskKill.some(
      item =>
        !absolutePath(item.Path) ||
        item.Path.split(/[\\/]/).pop()?.toLowerCase() !== item.Name.toLowerCase()
    )
  ) {
    error.value = t('generalRecovery.invalidCleanup')
    return
  }
  if (
    draft.Restart.length &&
    (draft.Restart.filter(item => item.IsMain).length !== 1 ||
      draft.Restart.some(
        item =>
          !absolutePath(item.Path) ||
          (item.WorkingDirectory && !absolutePath(item.WorkingDirectory)) ||
          !Number.isInteger(item.WaitSeconds) ||
          item.WaitSeconds < (item.IsMain ? 10 : 0) ||
          item.WaitSeconds > 9999
      ))
  ) {
    error.value = t('generalRecovery.invalidRestart')
    return
  }
  saving.value = true
  try {
    const patch: RecoveryConfig = JSON.parse(JSON.stringify(draft))
    if (await updateScript(props.scriptId, { Script: patch })) {
      savedValue.value = JSON.stringify(patch)
      emit('saved', patch)
      message.success(t('generalRecovery.saved'))
    } else {
      error.value = t('generalRecovery.saveFailed')
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.general-recovery > * + * {
  margin-top: 16px;
}
.recovery-item {
  padding: 16px 0;
  border-bottom: 1px solid var(--ant-color-border);
}
</style>
