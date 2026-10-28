<template>
  <div class="scripts-grid">
    <!-- 使用vuedraggable包装脚本列表 -->
    <draggable
      v-model="localScripts"
      item-key="id"
      :animation="200"
      :disabled="props.searching"
      ghost-class="script-ghost"
      chosen-class="script-chosen"
      drag-class="script-drag"
      handle=".script-drag-handle"
      class="draggable-scripts"
      @end="onScriptDragEnd"
    >
      <template #item="{ element: script }">
        <div :key="script.id" class="script-wrapper">
          <a-card :hoverable="false" class="script-card" :body-style="{ padding: '0' }">
            <!-- 脚本头部信息 -->
            <div class="script-header">
              <div class="script-info">
                <span
                  class="script-drag-handle"
                  :title="t('comp.dragReorder')"
                  :aria-label="t('comp.dragReorder')"
                >
                  <span class="script-drag-dots" aria-hidden="true"></span>
                </span>
                <div class="script-logo-container">
                  <img src="@/assets/AUTO-MAS.ico" alt="AUTO-MAS" class="script-logo" />
                </div>
                <div class="script-details">
                  <h3 class="script-name">{{ script.name }}</h3>
                </div>
              </div>
              <div class="header-actions">
                <a-button type="default" size="middle" @click="handleEdit(script)">
                  <template #icon>
                    <EditOutlined />
                  </template>
                  {{ t('comp.editScript') }}
                </a-button>
                <a-button
                  type="default"
                  size="middle"
                  class="action-button add-button"
                  @click="handleAddUser(script)"
                >
                  <template #icon>
                    <UserAddOutlined />
                  </template>
                  {{ t('comp.addUser') }}
                </a-button>
                <a-dropdown :trigger="['click']">
                  <a-button
                    size="middle"
                    class="action-button"
                    :loading="props.copyingScriptId === script.id"
                    :disabled="Boolean(props.copyingScriptId)"
                  >
                    <template #icon>
                      <EllipsisOutlined />
                    </template>
                    {{ t('comp.more') }}
                  </a-button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="copy" @click="handleCopy(script)">
                        <CopyOutlined />
                        {{ t('comp.copyScript') }}
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger @click="handleDeleteConfirm(script)">
                        <DeleteOutlined />
                        {{ t('comp.deleteScript') }}
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
                <a-tooltip
                  :title="
                    props.searching
                      ? t('comp.expandUsersWhileSearching')
                      : isUsersCollapsed(script.id)
                        ? t('comp.expandUsers')
                        : t('comp.collapseUsers')
                  "
                >
                  <a-button
                    size="middle"
                    class="action-button"
                    :disabled="props.searching"
                    :aria-label="
                      isUsersCollapsed(script.id) ? t('comp.expandUsers') : t('comp.collapseUsers')
                    "
                    @click="toggleUsersCollapsed(script.id)"
                  >
                    <template #icon>
                      <DownOutlined v-if="isUsersCollapsed(script.id)" />
                      <UpOutlined v-else />
                    </template>
                  </a-button>
                </a-tooltip>
              </div>
            </div>

            <!-- 用户列表 -->
            <div
              v-if="!isUsersCollapsed(script.id) && script.users && script.users.length > 0"
              class="users-section"
            >
              <!-- 使用vuedraggable包装用户列表 -->
              <draggable
                v-model="script.users"
                item-key="id"
                :animation="200"
                :disabled="props.searching"
                ghost-class="user-ghost"
                chosen-class="user-chosen"
                drag-class="user-drag"
                handle=".user-drag-handle"
                class="users-list"
                @end="onUserDragEnd(script)"
              >
                <template #item="{ element: user }">
                  <div :key="user.id" class="user-item">
                    <span
                      class="user-drag-handle"
                      :title="t('comp.dragReorder')"
                      :aria-label="t('comp.dragReorder')"
                    >
                      <span class="script-drag-dots" aria-hidden="true"></span>
                    </span>
                    <div class="user-info">
                      <div class="user-details-row">
                        <div class="user-name-section">
                          <span class="user-name">{{ user.Info.Name }}</span>
                        </div>
                        <div class="user-info-tags">
                          <a-tag
                            v-for="(tag, index) in parseStatusTagList(user.Info.Tag)"
                            :key="index"
                            :title="tag.text"
                            class="info-tag"
                            :color="tag.color"
                          >
                            {{ tag.text }}
                          </a-tag>
                        </div>
                      </div>
                    </div>

                    <div class="user-controls">
                      <div class="user-status">
                        <a-switch
                          :checked="user.Info.Status"
                          :checked-children="t('comp.enabled')"
                          :un-checked-children="t('comp.disabled')"
                          class="status-switch"
                          @click="handleToggleUserStatus(user)"
                        />
                      </div>

                      <div class="user-actions">
                        <a-tooltip :title="t('comp.editUserConfiguration')">
                          <a-button
                            type="default"
                            size="middle"
                            class="user-action-btn"
                            @click="handleEditUser(user)"
                          >
                            <template #icon>
                              <EditOutlined />
                            </template>
                            {{ t('comp.edit') }}
                          </a-button>
                        </a-tooltip>
                        <a-popconfirm
                          :title="t('comp.deleteThisUser')"
                          :description="t('comp.thisCannotBeUndone')"
                          :ok-text="t('comp.ok')"
                          :cancel-text="t('comp.cancel')"
                          @confirm="handleDeleteUser(user)"
                        >
                          <a-tooltip :title="t('comp.deleteUser')">
                            <a-button type="default" size="middle" danger class="user-action-btn">
                              <template #icon>
                                <DeleteOutlined />
                              </template>
                              {{ t('comp.delete') }}
                            </a-button>
                          </a-tooltip>
                        </a-popconfirm>
                      </div>
                    </div>
                  </div>
                </template>
              </draggable>
            </div>

            <!-- 空状态 -->
            <div v-else-if="!isUsersCollapsed(script.id)" class="empty-users">
              <div class="empty-content">
                <img src="@/assets/NoData.png" :alt="t('comp.noData')" class="empty-image" />
              </div>
            </div>
          </a-card>
        </div>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Script, User } from '../types/script'
import {
  CopyOutlined,
  DeleteOutlined,
  DownOutlined,
  EditOutlined,
  EllipsisOutlined,
  UpOutlined,
  UserAddOutlined,
} from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import { ref, watch } from 'vue'
import { Modal } from 'ant-design-vue'
import { useScriptApi } from '@/composables/useScriptApi'
import { useUserApi } from '@/composables/useUserApi'
import { parseStatusTagList } from '@/composables/useStatusTag'
const { t } = useI18n()

interface Props {
  scripts: Script[]
  activeConnections: Map<string, { subscriptionIds: string[]; taskId: string }>
  copyingScriptId?: string | null
  searching?: boolean
}

interface Emits {
  (e: 'edit', script: Script): void

  (e: 'delete', script: Script): void

  (e: 'copy', script: Script): void

  (e: 'addUser', script: Script): void

  (e: 'editUser', user: User): void

  (e: 'deleteUser', user: User): void

  (e: 'startMaaConfig', script: Script): void

  (e: 'startSrcConfig', script: Script): void

  (e: 'startMaaEndConfig', script: Script): void

  (e: 'startOkwwConfig', script: Script): void

  (e: 'startWhimboxConfig', script: Script): void

  (e: 'toggleUserStatus', user: User): void

  (e: 'scriptsReordered', scripts: Script[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 本地脚本列表状态
const localScripts = ref<Script[]>([])
// 脚本用户列表收起状态 - 持久化到 localStorage，切换页面后仍保持
const COLLAPSED_SCRIPTS_STORAGE_KEY = 'scripts.collapsedScriptIds'

const loadCollapsedScriptIds = (): Set<string> => {
  try {
    const raw = localStorage.getItem(COLLAPSED_SCRIPTS_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    return new Set(Array.isArray(parsed) ? parsed.filter(id => typeof id === 'string') : [])
  } catch {
    return new Set()
  }
}

const collapsedScriptIds = ref<Set<string>>(loadCollapsedScriptIds())

const saveCollapsedScriptIds = () => {
  try {
    localStorage.setItem(
      COLLAPSED_SCRIPTS_STORAGE_KEY,
      JSON.stringify([...collapsedScriptIds.value])
    )
  } catch {
    // 存储不可用时（如隐私模式）忽略，仅本次会话内生效
  }
}

const isUsersCollapsed = (scriptId: string) =>
  !props.searching && collapsedScriptIds.value.has(scriptId)

// 监听 props 变化，更新本地状态。只关心数组引用（增删、父级回写的新顺序），
// 不能 deep：父级改共享对象（启停用户、删用户）时会用未重排的父数组把拖拽顺序覆盖回去
watch(
  () => props.scripts,
  newScripts => {
    localScripts.value = [...newScripts]
  },
  { immediate: true }
)

const handleEdit = (script: Script) => {
  emit('edit', script)
}

const handleDelete = (script: Script) => {
  emit('delete', script)
}

const handleCopy = (script: Script) => {
  emit('copy', script)
}

const handleDeleteConfirm = (script: Script) => {
  Modal.confirm({
    title: t('comp.deleteThisScript'),
    content: t('comp.thisCannotBeUndone2'),
    okText: t('comp.ok'),
    okType: 'danger',
    cancelText: t('comp.cancel'),
    onOk: () => handleDelete(script),
  })
}

const toggleUsersCollapsed = (scriptId: string) => {
  const next = new Set(collapsedScriptIds.value)
  if (next.has(scriptId)) {
    next.delete(scriptId)
  } else {
    next.add(scriptId)
  }
  collapsedScriptIds.value = next
  saveCollapsedScriptIds()
}

const collapseAllUsers = () => {
  collapsedScriptIds.value = new Set(localScripts.value.map(script => script.id))
  saveCollapsedScriptIds()
}

const expandAllUsers = () => {
  collapsedScriptIds.value = new Set()
  saveCollapsedScriptIds()
}

defineExpose({ collapseAllUsers, expandAllUsers })

const handleAddUser = (script: Script) => {
  emit('addUser', script)
}

const handleEditUser = (user: User) => {
  emit('editUser', user)
}

const handleDeleteUser = (user: User) => {
  emit('deleteUser', user)
}

const handleToggleUserStatus = (user: User) => {
  emit('toggleUserStatus', user)
}

const { reorderScript } = useScriptApi()
const { reorderUser } = useUserApi()

const onScriptDragEnd = async () => {
  const scriptIds = localScripts.value.map(s => s.id)
  const success = await reorderScript(scriptIds)
  if (success) {
    emit('scriptsReordered', localScripts.value)
  }
}

const onUserDragEnd = async (script: Script) => {
  const userIds = script.users.map(u => u.id)
  await reorderUser(script.id, userIds)
}
</script>

<style scoped>
.scripts-grid {
  width: 100%;
}

/* 拖拽样式 */
.draggable-scripts {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.script-wrapper {
  width: 100%;
  cursor: auto;
}

.script-ghost {
  opacity: 0 !important;
  background: transparent !important;
  border-color: transparent !important;
  box-shadow: none !important;
}

.script-chosen {
  cursor: move !important;
}

.script-drag {
  transform: rotate(2deg);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  opacity: 1 !important;
  cursor: all-scroll !important;
}

.script-drag * {
  cursor: all-scroll !important;
}

.script-drag .script-card {
  opacity: 1 !important;
  transition: none !important;
}

.users-list {
  width: 100%;
}

.user-ghost {
  opacity: 0 !important;
  background: transparent !important;
  border-color: transparent !important;
  box-shadow: none !important;
}

.user-chosen {
  cursor: move !important;
  background: var(--ant-color-primary-bg) !important;
}

.user-drag {
  transform: rotate(1deg);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 999;
  background: var(--ant-color-bg-container) !important;
  opacity: 1 !important;
  cursor: all-scroll !important;
}

.user-drag * {
  cursor: all-scroll !important;
}

.script-drag .script-drag-handle {
  cursor: grabbing !important;
}

.script-drag .script-drag-handle * {
  cursor: grabbing !important;
}

.user-drag .user-drag-handle {
  cursor: grabbing !important;
}

.user-drag .user-drag-handle * {
  cursor: grabbing !important;
}

/* 拖拽时禁用某些交互 */
.script-ghost .script-card:hover,
.script-drag .script-card:hover {
  transform: none !important;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2) !important;
}

.user-ghost:hover,
.user-drag:hover {
  background: var(--ant-color-primary-bg) !important;
}

/* 脚本卡片 */
.script-card {
  border-radius: 16px;
  border: 1px solid var(--ant-color-border-secondary);
  background: var(--ant-color-bg-container);
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.script-card:hover {
  border-color: var(--ant-color-primary);
}

/* 脚本头部 */
.script-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--ant-color-border-secondary);
}

.script-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.script-drag-handle {
  width: 16px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--ant-color-text-tertiary);
  background: transparent;
  border: none;
  cursor: move;
  flex-shrink: 0;
  user-select: none;
}

.script-drag-handle:active {
  cursor: move;
}

.script-drag-dots {
  width: 10px;
  height: 16px;
  display: block;
  background-image: radial-gradient(currentColor 1.2px, transparent 1.2px);
  background-size: 5px 5px;
  background-position: 0 0;
  opacity: 0.65;
}

.script-logo-container {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ant-color-bg-layout);
  border: 1px solid var(--ant-color-border);
  overflow: hidden;
  flex-shrink: 0;
}

.script-logo {
  width: 36px;
  height: 36px;
  object-fit: contain;
}

.script-details {
  flex: 1;
  min-width: 0;
  padding: 0 12px;
  text-align: center;
}

.script-name {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--ant-color-text);
  line-height: 1.3;
  word-break: break-word;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.action-button {
  border-radius: 8px;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.add-button {
  border-color: var(--ant-color-primary);
  color: var(--ant-color-primary);
}

.add-button:hover {
  background: var(--ant-color-primary-bg);
  border-color: var(--ant-color-primary-hover);
  color: var(--ant-color-primary-hover);
}

/* 用户区域 */
.users-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--ant-color-border-secondary);
  min-height: 80px;
}

.user-drag-handle {
  width: 16px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--ant-color-text-tertiary);
  background: transparent;
  border: none;
  cursor: move;
  flex-shrink: 0;
  user-select: none;
}

.user-drag-handle:active {
  cursor: move;
}

.user-drag-handle:hover .script-drag-dots {
  opacity: 0.85;
}

.user-item:last-child {
  border-bottom: none;
}

.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-details-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-name-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--ant-color-text);
}

.user-info-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.user-config-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 18px;
  color: var(--ant-color-text-secondary);
  white-space: nowrap;
}

.user-config-summary__label {
  color: var(--ant-color-text-tertiary);
}

.user-config-summary__sep {
  color: var(--ant-color-text-quaternary);
}

.user-config-summary__dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: var(--ant-color-text-quaternary);
}

.user-config-summary.is-overlay-on .user-config-summary__dot {
  background: var(--ant-color-success);
}

.info-tag {
  display: inline-block;
  max-width: 120px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  margin: 0;
  border: 1px solid rgba(0, 0, 0, 0.15);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.server-tag {
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.15);
}

.user-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  height: 100%;
  justify-content: center;
}

.user-status {
  display: flex;
  align-items: center;
}

.status-switch {
  font-size: 12px;
}

.status-switch :deep(.ant-switch-inner) {
  font-size: 11px;
  font-weight: 500;
}

.user-actions {
  display: flex;
  flex-direction: row;
  gap: 8px;
  align-items: center;
}

.user-action-btn {
  border-radius: 6px;
  font-weight: 500;
  min-width: 60px;
  border: 1px solid var(--ant-color-border);
  background: var(--ant-color-bg-container);
}

.user-action-btn.ant-btn-dangerous {
  border-color: var(--ant-color-error);
  color: var(--ant-color-error);
}

/* 空状态 */
.empty-users {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .script-header {
    padding: 16px 16px 12px;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .script-name {
    font-size: 18px;
  }

  .header-actions {
    gap: 8px;
  }

  .action-button {
    font-size: 12px;
    height: 28px;
    padding: 0 8px;
  }

  .user-item {
    padding-left: 16px;
    padding-right: 16px;
  }

  .user-controls {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
  }

  .user-actions {
    flex-direction: column;
    gap: 4px;
  }

  .empty-users {
    padding: 30px 16px;
  }
}

@media (max-width: 576px) {
  .script-info {
    gap: 8px;
  }

  .script-logo-container {
    width: 40px;
    height: 40px;
  }

  .script-logo {
    width: 28px;
    height: 28px;
  }

  .script-name {
    font-size: 17px;
  }

  .header-actions {
    gap: 6px;
  }

  .action-button {
    font-size: 11px;
    height: 26px;
    padding: 0 6px;
  }

  .user-item {
    padding-left: 12px;
    padding-right: 12px;
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .user-details-row {
    gap: 6px;
  }

  .user-name-section {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .user-name {
    font-size: 16px;
  }

  .user-info-tags {
    gap: 4px;
  }

  .info-tag {
    font-size: 10px;
    max-width: 100px;
  }

  .clickable-tag {
    cursor: pointer;
    user-select: none;
    border: 1px solid rgba(0, 0, 0, 0.15);
  }
}
</style>
