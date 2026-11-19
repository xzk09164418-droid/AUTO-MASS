<template>
  <!-- 主要内容 -->
  <div class="scripts-header">
    <div class="header-left">
      <h1 class="page-title">{{ t('scripts.title') }}</h1>
      <DocLink :url="MAS_DOC_URLS.scripts" />
      <a-input
        v-model:value="scriptSearchKeyword"
        allow-clear
        class="script-search"
        :placeholder="t('scripts.searchPlaceholder')"
        :aria-label="t('scripts.searchAria')"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
    </div>
    <div class="header-actions">
      <a-space size="middle">
        <a-tooltip :title="t('scripts.collapseAllTip')">
          <a-button
            size="large"
            :disabled="scripts.length === 0 || isSearching"
            @click="handleCollapseAll"
          >
            <template #icon><UpOutlined /></template>
            {{ t('scripts.collapseAll') }}
          </a-button>
        </a-tooltip>
        <a-tooltip :title="t('scripts.expandAllTip')">
          <a-button
            size="large"
            :disabled="scripts.length === 0 || isSearching"
            @click="handleExpandAll"
          >
            <template #icon><DownOutlined /></template>
            {{ t('scripts.expandAll') }}
          </a-button>
        </a-tooltip>
        <a-button type="primary" size="large" class="link" @click="handleAddScript">
          <template #icon>
            <PlusOutlined />
          </template>
          {{ t('scripts.create.title') }}
        </a-button>
      </a-space>
    </div>
  </div>

  <!-- 空状态 -->
  <!-- 增加 loadedOnce 条件，避免初始渲染时闪烁 -->
  <div v-if="!addLoading && loadedOnce && scripts.length === 0" class="empty-state">
    <div class="empty-content">
      <div class="empty-image-container">
        <img src="@/assets/NoData.png" :alt="t('scripts.empty.alt')" class="empty-image" />
      </div>
      <div class="empty-text-content">
        <h3 class="empty-title">{{ t('scripts.empty.title') }}</h3>
        <p class="empty-description">{{ t('scripts.empty.desc') }}</p>
      </div>
    </div>
  </div>

  <div v-else-if="!addLoading && loadedOnce && filteredScripts.length === 0" class="empty-state">
    <a-empty :description="t('scripts.empty.noMatch')">
      <a-button @click="scriptSearchKeyword = ''">{{ t('scripts.clearSearch') }}</a-button>
    </a-empty>
  </div>

  <ScriptTable
    v-else
    ref="scriptTableRef"
    :scripts="filteredScripts"
    :searching="isSearching"
    :copying-script-id="copyingScriptId"
    @edit="handleEditScript"
    @copy="handleCopyScript"
    @delete="handleDeleteScript"
    @add-user="handleAddUser"
    @edit-user="handleEditUser"
    @delete-user="handleDeleteUser"
    @toggle-user-status="handleToggleUserStatus"
    @scripts-reordered="handleScriptsReordered"
  />

  <ScriptCreateDialog
    v-model:open="scriptCreateVisible"
    :templates="templates"
    :submitting="addLoading || templateLoading"
    :template-loading="templateLoading"
    :template-error="templateError"
    :template-page="templatePage"
    :template-page-size="TEMPLATE_PAGE_SIZE"
    :template-total="templateTotal"
    @submit="handleSubmitScriptCreate"
  />
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { DownOutlined, PlusOutlined, SearchOutlined, UpOutlined } from '@ant-design/icons-vue'
import ScriptTable from '@/components/ScriptTable.vue'
import ScriptCreateDialog from '@/views/scripts/components/ScriptCreateDialog.vue'
import type { Script, ScriptType, User } from '@/types/script'
import type {
  ScriptCreateRequest,
  TemplateRequest,
} from '@/views/scripts/components/scriptCreateFlow'
import { useScriptApi } from '@/composables/useScriptApi'
import { useUserApi } from '@/composables/useUserApi'
import { onTaskRuntimeEvent } from '@/composables/useTaskRuntimeState'
import {
  TEMPLATE_PAGE_SIZE,
  useTemplateApi,
  type ShareTemplateItem,
} from '@/composables/useTemplateApi'
import DocLink from '@/components/DocLink.vue'
import { MAS_DOC_URLS } from '@/utils/openExternal'
import { filterScriptsByKeyword } from '@/views/scripts/scriptSearch'

const { t } = useI18n()

defineOptions({ name: 'ScriptsPage' })

const logger = window.hostAPI.getLogger('脚本管理')

const router = useRouter()
const { addScript, deleteScript, getScriptsWithUsers } = useScriptApi()
const { updateUser, deleteUser } = useUserApi()
const { getShareTemplates, importScriptFromTemplate, error: templateError } = useTemplateApi()

const scripts = ref<Script[]>([])
const scriptSearchKeyword = ref('')
const isSearching = computed(() => Boolean(scriptSearchKeyword.value.trim()))
const filteredScripts = computed(() =>
  filterScriptsByKeyword(scripts.value, scriptSearchKeyword.value)
)
const scriptTableRef = ref<InstanceType<typeof ScriptTable> | null>(null)
// 增加：标记是否已经完成过一次脚本列表加载（成功或失败都算一次）
const loadedOnce = ref(false)
const scriptCreateVisible = ref(false)
const templates = ref<ShareTemplateItem[]>([])
const templatePage = ref(1)
const templateTotal = ref(0)
let templateRequestId = 0
const addLoading = ref(false)
const copyingScriptId = ref<string | null>(null)
const templateLoading = ref(false)
// 定时队列等别处发起的任务结束后，用户的代理状态已在后端更新，防抖后重新拉一次列表；
// removed 是断线期间结束、没收到完成通知的任务
const TASK_COMPLETED_RELOAD_DELAY_MS = 1000
let taskCompletedReloadTimer: ReturnType<typeof setTimeout> | undefined
let disposeTaskRuntimeListener: (() => void) | undefined

onMounted(() => {
  loadScripts()
  disposeTaskRuntimeListener = onTaskRuntimeEvent(event => {
    const ended =
      event.type === 'removed' ||
      (event.type === 'completed' && event.state.mode !== 'ScriptConfig')
    if (!ended) return
    clearTimeout(taskCompletedReloadTimer)
    taskCompletedReloadTimer = setTimeout(() => void loadScripts(), TASK_COMPLETED_RELOAD_DELAY_MS)
  })
})

onUnmounted(() => {
  disposeTaskRuntimeListener?.()
  clearTimeout(taskCompletedReloadTimer)
})

const loadScripts = async () => {
  try {
    const scriptDetails = await getScriptsWithUsers()

    // 将 ScriptDetail 转换为 Script 格式（为了兼容现有的表格组件）
    scripts.value = scriptDetails.map(detail => ({
      id: detail.uid,
      type: detail.type as ScriptType,
      name: detail.name,
      config: detail.config,
      users: (detail.users || []).filter((user): user is NonNullable<typeof user> => user !== null),
    }))
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    logger.error(`加载脚本列表失败: ${errorMsg}`)
    message.error(t('scripts.toast.loadListFailed', { error: errorMsg }))
  } finally {
    // 首次加载结束（不论成功失败）后置位，避免初始闪烁
    loadedOnce.value = true
  }
}

const handleAddScript = () => {
  scriptCreateVisible.value = true
}

const handleCollapseAll = () => {
  scriptTableRef.value?.collapseAllUsers()
}

const handleExpandAll = () => {
  scriptTableRef.value?.expandAllUsers()
}

// 拖拽排序已写回后端，父级列表同步成新顺序，否则后续共享对象改动会把顺序弹回去
const handleScriptsReordered = (reordered: Script[]) => {
  scripts.value = [...reordered]
}

// 本版本只保留通用脚本：新建后直接进通用脚本编辑页
const navigateToCreatedScript = (
  scriptId: string,
  type: ScriptType,
  data?: Record<string, unknown>
) => {
  router.push({
    path: `/scripts/${scriptId}/edit/general`,
    ...(data
      ? { state: { scriptData: { id: scriptId, type, config: JSON.parse(JSON.stringify(data)) } } }
      : {}),
  })
}

const handleSubmitScriptCreate = async (request: ScriptCreateRequest) => {
  addLoading.value = true
  try {
    const type: ScriptType = 'General'
    const result = await addScript(type)
    if (!result) return

    if (request.kind === 'general-template') {
      const imported = await importScriptFromTemplate(result.scriptId, request.template)
      // 导入失败就把刚建出来的空脚本删掉，不给用户留一个没有配置的壳
      if (!imported) {
        await deleteScript(result.scriptId)
        await loadScripts()
        return
      }
      message.success(
        t('scripts.toast.createdFromTemplate', { name: request.template.displayName })
      )
      await loadScripts()
      scriptCreateVisible.value = false
      navigateToCreatedScript(result.scriptId, 'General')
      return
    }

    scriptCreateVisible.value = false
    navigateToCreatedScript(result.scriptId, type, result.data)
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    logger.error(`创建脚本失败: ${errorMsg}`)
  } finally {
    addLoading.value = false
  }
}

const loadTemplates = async (query: TemplateRequest = { page: 1, keyword: '' }) => {
  const requestId = ++templateRequestId
  templateLoading.value = true
  try {
    const result = await getShareTemplates({
      page: query.page,
      pageSize: TEMPLATE_PAGE_SIZE,
      keyword: query.keyword,
    })
    // 快速改关键字时请求可能乱序返回，只认最后一次
    if (requestId !== templateRequestId) return
    templates.value = result.items
    templatePage.value = result.page
    templateTotal.value = result.total
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    logger.error(`加载模板列表失败: ${errorMsg}`)
  } finally {
    if (requestId === templateRequestId) templateLoading.value = false
  }
}

const handleEditScript = (script: Script) => {
  router.push(`/scripts/${script.id}/edit/general`)
}

const handleDeleteScript = async (script: Script) => {
  const result = await deleteScript(script.id)
  if (result) {
    // 后端已删除，本地直接移除即可，不必整份重拉
    scripts.value = scripts.value.filter(item => item.id !== script.id)
  }
}

const handleCopyScript = async (script: Script) => {
  addLoading.value = true
  copyingScriptId.value = script.id
  try {
    const result = await addScript(script.type, script.id)
    if (result) {
      await loadScripts()
      message.success(t('scripts.toast.copied', { name: script.name }))
    }
  } finally {
    addLoading.value = false
    copyingScriptId.value = null
  }
}

const handleAddUser = (script: Script) => {
  router.push(`/scripts/${script.id}/users/add/general`)
}

const handleEditUser = (user: User) => {
  const script = scripts.value.find(s => s.users.some(u => u.id === user.id))
  if (!script) {
    message.error(t('scripts.toast.scriptNotFound'))
    return
  }
  router.push(`/scripts/${script.id}/users/${user.id}/edit/general`)
}

const handleDeleteUser = async (user: User) => {
  // 从用户数据中找到对应的脚本
  const script = scripts.value.find(s => s.users.some(u => u.id === user.id))
  if (!script) {
    message.error(t('scripts.toast.scriptNotFound'))
    return
  }

  const result = await deleteUser(script.id, user.id)
  if (result) {
    // 删除成功后，从本地数据中移除用户
    const userIndex = script.users.findIndex(u => u.id === user.id)
    if (userIndex > -1) {
      script.users.splice(userIndex, 1)
    }
  }
}

const handleToggleUserStatus = async (user: User) => {
  try {
    // 找到该用户对应的脚本
    const script = scripts.value.find(s => s.users.some(u => u.id === user.id))
    if (!script) {
      message.error(t('scripts.toast.scriptNotFound'))
      return
    }
    const newStatus = !user.Info.Status

    // 后端是单字段 set：只发送 Status，避免 Info.Tag 等虚拟字段混入触发后端报错
    const result = await updateUser(script.id, user.id, {
      Info: { Status: newStatus },
    })

    if (result) {
      message.success(t('scripts.toast.userStatusUpdated'))
      // 更新本地用户状态
      user.Info.Status = newStatus
    }
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    logger.error(`更新用户状态失败: ${errorMsg}`)
    message.error(t('scripts.toast.userStatusFailed', { error: errorMsg }))
  }
}
</script>

<style scoped>
.scripts-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 24px;
  padding: 0 0 14px;
  border-bottom: 2px solid var(--app-rhine-rule);
}

.header-left {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: center;
  gap: 20px;
}

.script-search {
  width: min(360px, 40vw);
}

.header-actions {
  flex-shrink: 0;
  margin-left: 16px;
}

@media (max-width: 768px) {
  .page-title {
    font-size: 24px;
  }

  .scripts-header {
    align-items: stretch;
    flex-direction: column;
    gap: 16px;
    padding: 0 0 12px;
  }

  .header-left {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .script-search {
    width: 100%;
  }

  .header-actions {
    margin-left: 0;
  }
}

.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--ant-color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
