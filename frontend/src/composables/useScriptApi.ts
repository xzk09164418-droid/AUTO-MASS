import { translate as t } from '@/i18n'
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  type ScriptUpdateIn,
  type ScriptGetOut,
  type ScriptCreateIn,
  type ScriptReorderIn,
  Service,
} from '@/api'
import type { ScriptDetail, ScriptType, User } from '@/types/script'
import { useAudioPlayer } from '@/composables/useAudioPlayer'
import { getTaskRuntimeStates } from '@/composables/useTaskRuntimeState'
import { isScriptConfigLocked } from '@/utils/scriptConfigLock'
import { mapScriptUsers } from './scriptUserMapping'

const logger = window.hostAPI.getLogger('脚本API')

// 首页卫星与活动区共用在途的列表请求，完成后释放，后续读取仍取最新数据。
let scriptListRequest: Promise<ScriptGetOut> | null = null

type ScriptWithUsers = ScriptDetail & { users: User[] }
// 本版本只保留通用脚本
const SCRIPT_CREATE_TYPE_BY_SCRIPT_TYPE: Record<ScriptType, ScriptCreateIn['type']> = {
  General: 'General',
}

const SCRIPT_TYPE_BY_CONFIG_TYPE: Record<string, ScriptType> = {}

const resolveScriptType = (configType: string): ScriptType => {
  return SCRIPT_TYPE_BY_CONFIG_TYPE[configType] ?? 'General'
}

const scriptDetailsFromResponse = (response: ScriptGetOut): ScriptDetail[] =>
  response.index.map(indexItem => ({
    uid: indexItem.uid,
    type: resolveScriptType(indexItem.type),
    activityGame: indexItem.activityGame,
    name: response.data[indexItem.uid]?.Info?.Name || `${indexItem.type}脚本`,
    config: response.data[indexItem.uid],
  }))

export function useScriptApi() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 添加脚本（支持从已有脚本复制创建）
  const addScript = async (type: ScriptType, scriptId?: string) => {
    loading.value = true
    error.value = null

    try {
      const requestData: ScriptCreateIn = {
        type: SCRIPT_CREATE_TYPE_BY_SCRIPT_TYPE[type],
        scriptId: scriptId || null,
      }

      const response = await Service.addScriptApiScriptsAddPost(requestData)

      if (response.code !== 200) {
        const errorMsg = response.message || '添加脚本失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      scriptListRequest = null
      // 成功提示音异步播放，不阻塞已持久化的创建结果。
      const { playSound } = useAudioPlayer()
      void playSound('add_script_instance')

      return {
        scriptId: response.scriptId,
        message: response.message || '脚本添加成功',
        data: response.data,
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '添加脚本失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return null
    } finally {
      loading.value = false
    }
  }

  // 获取脚本列表（可选择是否管理 loading 状态，避免嵌套调用时提前结束 loading）
  const getScripts = async (manageLoading: boolean = true): Promise<ScriptDetail[]> => {
    if (manageLoading) {
      loading.value = true
      error.value = null
    } else {
      // 仅清理错误，不改变外部 loading
      error.value = null
    }

    try {
      if (!scriptListRequest) {
        const request = Service.getScriptApiScriptsGetPost({}).finally(() => {
          if (scriptListRequest === request) scriptListRequest = null
        })
        scriptListRequest = request
      }
      const response = await scriptListRequest

      if (response.code !== 200) {
        const errorMsg = response.message || '获取脚本列表失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      // 将API响应转换为ScriptDetail数组
      return scriptDetailsFromResponse(response)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '获取脚本列表失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return []
    } finally {
      if (manageLoading) {
        loading.value = false
      }
    }
  }

  // 获取脚本列表及其用户数据（统一管理一次 loading）
  const getScriptsWithUsers = async (): Promise<ScriptWithUsers[]> => {
    loading.value = true
    error.value = null

    try {
      // 一次读取脚本及其用户，避免列表为每个脚本再发起请求。
      const response = await Service.getScriptApiScriptsGetPost({ includeUsers: true })
      if (response.code !== 200) {
        throw new Error(response.message || '获取脚本列表失败')
      }
      const scriptDetails = scriptDetailsFromResponse(response)

      // 为每个脚本获取用户数据
      const scriptsWithUsers = await Promise.all(
        scriptDetails.map(async script => {
          try {
            // 获取该脚本下的用户列表
            // 连接旧后端时沿用逐脚本读取，不把缺失的新字段当成空用户列表。
            const userResponse =
              response.users?.[script.uid] ??
              (await Service.getUserApiScriptsUserGetPost({ scriptId: script.uid }))

            if (userResponse.code === 200) {
              // 将用户数据转换为User格式
              const users = mapScriptUsers(userResponse)

              return {
                ...script,
                users,
              }
            } else {
              // 如果获取用户失败，返回空用户列表的脚本
              return {
                ...script,
                users: [],
              }
            }
          } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err)
            logger.warn(`获取脚本 ${script.uid} 的用户数据失败: ${errorMsg}`)
            return {
              ...script,
              users: [],
            }
          }
        })
      )

      return scriptsWithUsers
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '获取脚本列表失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return []
    } finally {
      loading.value = false
    }
  }

  // 获取单个脚本
  const getScript = async (scriptId: string): Promise<ScriptDetail | null> => {
    loading.value = true
    error.value = null

    try {
      const response = await Service.getScriptApiScriptsGetPost({ scriptId })

      if (response.code !== 200) {
        const errorMsg = response.message || '获取脚本详情失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      // 检查是否有数据返回
      if (response.index.length === 0) {
        throw new Error('脚本不存在')
      }

      const item = response.index[0]
      const config = response.data[item.uid]
      const scriptType = resolveScriptType(item.type)

      return {
        uid: item.uid,
        type: scriptType,
        activityGame: item.activityGame,
        name: config?.Info?.Name || `${item.type}脚本`,
        config,
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '获取脚本详情失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return null
    } finally {
      loading.value = false
    }
  }

  // 删除脚本
  const deleteScript = async (scriptId: string): Promise<boolean> => {
    loading.value = true
    error.value = null

    try {
      const response = await Service.deleteScriptApiScriptsDeletePost({ scriptId })

      if (response.code !== 200) {
        const errorMsg = response.message || '删除脚本失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      scriptListRequest = null
      // 成功提示音异步播放，不阻塞已持久化的删除结果。
      const { playSound } = useAudioPlayer()
      void playSound('delete_script_instance')

      return true
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '删除脚本失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return false
    } finally {
      loading.value = false
    }
  }

  // 更新脚本
  const updateScript = async (
    scriptId: string,
    data: Record<string, unknown>
  ): Promise<boolean> => {
    if (isScriptConfigLocked(getTaskRuntimeStates(), scriptId)) {
      const errorMsg = t('edit.configLocked')
      error.value = errorMsg
      message.warning(errorMsg)
      return false
    }

    loading.value = true
    error.value = null

    try {
      // 创建数据副本并移除 SubConfigsInfo 字段
      const dataToSend = { ...data }
      delete dataToSend.SubConfigsInfo

      const response = await Service.updateScriptApiScriptsUpdatePost({
        scriptId,
        data: dataToSend as ScriptUpdateIn['data'],
      })

      if (response.code !== 200) {
        const errorMsg = response.message || '更新脚本失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      scriptListRequest = null
      return true
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '更新脚本失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return false
    } finally {
      loading.value = false
    }
  }

  // 重新排序脚本
  const reorderScript = async (scriptIds: string[]): Promise<boolean> => {
    // loading.value = true // 排序通常不需要全屏loading，或者可以使用局部loading
    error.value = null

    try {
      const requestData: ScriptReorderIn = {
        indexList: scriptIds,
      }

      const response = await Service.reorderScriptApiScriptsOrderPost(requestData)

      if (response.code !== 200) {
        const errorMsg = response.message || '脚本排序失败'
        message.error(errorMsg)
        throw new Error(errorMsg)
      }

      scriptListRequest = null
      return true
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '脚本排序失败'
      error.value = errorMsg
      if (err instanceof Error && !err.message.includes('HTTP error')) {
        message.error(errorMsg)
      }
      return false
    } finally {
      // loading.value = false
    }
  }

  return {
    loading,
    error,
    addScript,
    getScripts,
    getScriptsWithUsers,
    getScript,
    deleteScript,
    updateScript,
    reorderScript,
  }
}
