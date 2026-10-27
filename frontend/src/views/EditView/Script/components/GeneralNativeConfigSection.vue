<template>
  <div class="general-native-config">
    <h3>源程序配置</h3>
    <a-form-item label="原生配置类型">
      <a-select :value="configMode" :disabled="busy || configLocked" @change="saveMode">
        <a-select-option value="File">单个配置文件</a-select-option>
        <a-select-option value="Folder">配置目录</a-select-option>
      </a-select>
    </a-form-item>
    <a-form-item label="原生配置路径">
      <a-input :value="configPath" readonly />
      <a-space wrap class="native-actions">
        <a-button :disabled="busy || configLocked" @click="pickPath">选择配置路径</a-button>
        <a-button :loading="busy" :disabled="configLocked" @click="openEditor"
          >编辑并写回原文件</a-button
        >
        <a-button
          :loading="session.configLoading.value"
          :disabled="busy || configLocked"
          @click="openProgram"
          >打开源程序设置</a-button
        >
      </a-space>
    </a-form-item>
    <a-alert
      type="info"
      show-icon
      message="文本编辑支持 UTF-8 配置，保存前自动备份。源程序设置界面中的修改，请先在源程序内保存，再结束设置会话。"
    />
    <a-modal
      v-model:open="editorOpen"
      title="编辑原生配置"
      width="min(1000px, 95vw)"
      :confirm-loading="busy"
      :mask-closable="false"
      ok-text="保存到原文件"
      @ok="saveFile"
    >
      <a-form layout="vertical">
        <a-form-item v-if="files.length" label="配置文件">
          <a-select
            :value="selected"
            :options="files.map(file => ({ value: file, label: file }))"
            :disabled="busy"
            @change="loadFile"
          />
        </a-form-item>
        <p>{{ selected }}</p>
        <a-textarea
          v-model:value="content"
          :rows="20"
          :disabled="busy || !revision"
          spellcheck="false"
          aria-label="原生配置内容"
        />
        <a-alert
          v-if="saveError"
          type="error"
          show-icon
          :message="saveError"
          class="native-actions"
        />
      </a-form>
    </a-modal>
    <GuiSessionMask
      :open="session.showConfigMask.value"
      title="源程序设置已打开"
      description="请在远程桌面中的源程序界面完成配置并保存。结束会话后，原生配置文件中的修改会保留。"
    >
      <template #actions>
        <a-button
          type="primary"
          :disabled="false"
          :loading="session.stopping.value"
          @click="session.saveSession"
          >已在源程序保存，结束会话</a-button
        >
      </template>
    </GuiSessionMask>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import GuiSessionMask from '@/components/GuiSessionMask.vue'
import { useGeneralNativeConfig } from '@/composables/useGeneralNativeConfig'
import { useNativeGuiSession } from '@/composables/useNativeGuiSession'
import { useScriptApi } from '@/composables/useScriptApi'
import { useScriptConfigLock } from '@/composables/useScriptConfigLock'

const props = defineProps<{ scriptId: string; configPath: string; configMode: string }>()
const emit = defineEmits<{
  saved: [patch: { ConfigPath?: string; ConfigPathMode?: 'File' | 'Folder' }]
}>()
const api = useGeneralNativeConfig()
const { updateScript } = useScriptApi()
const { configLocked } = useScriptConfigLock(() => props.scriptId)
const logger = window.hostAPI.getLogger('通用原生配置')
const busy = ref(false)
const editorOpen = ref(false)
const files = ref<string[]>([])
const selected = ref('')
const content = ref('')
const originalContent = ref('')
const revision = ref('')
const saveError = ref('')
const session = useNativeGuiSession({
  loggerName: '通用原生设置',
  keys: {
    stopFailed: 'generalNative.stopFailed',
    startFailed: 'generalNative.startFailed',
    setupFailed: 'generalNative.setupFailed',
    opened: 'generalNative.opened',
    viewOpened: 'generalNative.opened',
    timeoutWarn: 'generalNative.timeoutWarn',
    saved: 'generalNative.saved',
    saveFailed: 'generalNative.saveFailed',
  },
})
const report = (error: unknown) => {
  const text = error instanceof Error ? error.message : String(error)
  logger.error(text)
  saveError.value = text
  message.error(text)
}
const saveMode = async (mode: 'File' | 'Folder') => {
  busy.value = true
  try {
    const patch = { ConfigPathMode: mode, ConfigPath: '' }
    if (await updateScript(props.scriptId, { Script: patch })) emit('saved', patch)
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
const pickPath = async () => {
  busy.value = true
  try {
    const path =
      props.configMode === 'Folder'
        ? await window.hostAPI.selectFolder()
        : (await window.hostAPI.selectFile())[0]
    if (path && (await updateScript(props.scriptId, { Script: { ConfigPath: path } })))
      emit('saved', { ConfigPath: path })
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
const loadFile = async (file: string) => {
  const previous = selected.value
  if (revision.value && content.value !== originalContent.value) {
    const discard = await new Promise<boolean>(resolve =>
      Modal.confirm({
        title: '切换文件会丢弃尚未保存的修改，是否继续？',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    )
    if (!discard) {
      selected.value = previous
      return
    }
  }
  busy.value = true
  revision.value = ''
  saveError.value = ''
  try {
    const result = await api.read(props.scriptId, file)
    selected.value = result.file || file
    content.value = result.content || ''
    originalContent.value = content.value
    revision.value = result.revision || ''
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
const openEditor = async () => {
  busy.value = true
  saveError.value = ''
  try {
    const result = await api.read(props.scriptId)
    files.value = result.files || []
    selected.value = result.file || ''
    content.value = result.content || ''
    originalContent.value = content.value
    revision.value = result.revision || ''
    editorOpen.value = true
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
const saveFile = async () => {
  if (!revision.value) {
    message.warning('请先选择一个配置文件')
    return
  }
  busy.value = true
  saveError.value = ''
  try {
    const result = await api.write(props.scriptId, selected.value, content.value, revision.value)
    revision.value = result.revision || ''
    originalContent.value = content.value
    message.success('已写入源程序配置文件')
    editorOpen.value = false
  } catch (error) {
    report(error)
  } finally {
    busy.value = false
  }
}
const openProgram = () => session.startSession(props.scriptId)
onBeforeUnmount(() => {
  void session.stopSession()
})
</script>

<style scoped>
.general-native-config {
  margin-bottom: 24px;
}
.native-actions {
  margin-top: 12px;
}
</style>
