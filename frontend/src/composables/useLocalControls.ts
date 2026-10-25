import { ref } from 'vue'
import { invokeBrowserHost } from './useBrowserHost'
import { GetService, UpdateService, type GlobalConfig } from '@/api'
import type { LocalConfig, DesktopStatus } from '@/types/localControls'
import {
  canonicalHotkey,
  parseHotkey,
  HOTKEY_PRIMARY_KEYS,
  HOTKEY_MODIFIERS,
} from '@/utils/maafwHotkey'
import { t } from '@/i18n'

export function useLocalControls() {
  const error = ref('')
  const loading = ref(false)
  const status = ref<DesktopStatus>({})
  async function getConfig(): Promise<Partial<LocalConfig>> {
    const result = await GetService.getScriptsApiSettingGetPost()
    if (result.code !== 200 || !result.data) throw new Error(result.message)
    return result.data as GlobalConfig & Partial<LocalConfig>
  }
  async function saveConfig(config: LocalConfig) {
    if (config.Hotkey.Enabled) {
      const values = [
        config.Hotkey.ToggleStartStop,
        config.Hotkey.PreviousTask,
        config.Hotkey.NextTask,
      ]
      for (const value of values) {
        const keys = parseHotkey(value)
        if (
          !keys.length ||
          !HOTKEY_PRIMARY_KEYS.includes(keys[keys.length - 1]) ||
          !keys.slice(0, -1).every(key => (HOTKEY_MODIFIERS as readonly string[]).includes(key))
        )
          throw new Error(t('localControls.invalidHotkey'))
      }
      if (new Set(values.map(canonicalHotkey)).size !== values.length)
        throw new Error(t('localControls.duplicateHotkey'))
    }
    // 本地部署扩展字段由现有 Python 设置接口保存；原版生成客户端保持不变。
    const data: GlobalConfig & LocalConfig = { ...config }
    const result = await UpdateService.updateScriptApiSettingUpdatePost({ data })
    if (result.code !== 200) throw new Error(result.message)
  }
  async function refreshStatus() {
    status.value = await invokeBrowserHost<DesktopStatus>('localControl', 'status', {})
  }
  async function action(name: string, payload: object = {}) {
    loading.value = true
    error.value = ''
    try {
      await invokeBrowserHost('localControl', name, payload)
      await refreshStatus()
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      return false
    } finally {
      loading.value = false
    }
  }
  return { loading, error, status, getConfig, saveConfig, refreshStatus, action }
}
