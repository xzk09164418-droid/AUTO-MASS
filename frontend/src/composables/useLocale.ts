//   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
//   Copyright © 2025-2026 AUTO-MAS Team

import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/en'
import 'dayjs/locale/ja'
import antdEnUS from 'ant-design-vue/es/locale/en_US'
import antdJaJP from 'ant-design-vue/es/locale/ja_JP'
import antdZhCN from 'ant-design-vue/es/locale/zh_CN'
import { message } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'

import { i18n, normalizeLocale, t, type AppLocale } from '@/i18n'
import { getConfig, saveConfig, type FrontendConfig } from '@/utils/config'

const logger = window.hostAPI.getLogger('语言设置')

const DAYJS_LOCALE: Record<AppLocale, string> = {
  'zh-CN': 'zh-cn',
  'en-US': 'en',
  'ja-JP': 'ja',
}

const ANTD_LOCALE = {
  'zh-CN': antdZhCN,
  'en-US': antdEnUS,
  'ja-JP': antdJaJP,
}

// 模块级单例，与 useTheme 保持同一模式
const locale = ref<AppLocale>('zh-CN')
let initialized = false

/** 语言只影响展示层：vue-i18n 词表、dayjs 与 antd 组件内置文案。 */
function applyLocale(next: AppLocale): void {
  i18n.global.locale.value = next
  dayjs.locale(DAYJS_LOCALE[next])
}

watch(locale, applyLocale, { immediate: true })

/**
 * 首次启动默认简体中文，之后以用户在设置里的选择为准。
 * 语言存在前端配置（Electron 侧）里，不经过后端。
 */
async function initLocale(preloadedConfig?: FrontendConfig): Promise<void> {
  if (initialized) return
  initialized = true
  try {
    const config = preloadedConfig ?? (await getConfig())
    if (config.language) {
      locale.value = normalizeLocale(config.language)
      return
    }
    locale.value = 'zh-CN'
  } catch (error) {
    logger.warn(`读取语言设置失败，改用简体中文: ${error instanceof Error ? error.message : error}`)
    locale.value = 'zh-CN'
  }
}

// saveConfig 是「读全量 → 合并 → 写回」，并发调用会让先发的后完成从而覆盖后发的选择，
// 所以语言写入必须串行。
let savePending: Promise<void> = Promise.resolve()

async function setLocale(next: AppLocale): Promise<void> {
  // 不在此处按当前值早退：用户显式选择默认语言时也要持久化该选择。
  const previous = locale.value
  locale.value = next

  savePending = savePending.catch(() => {}).then(() => saveConfig({ language: next }))
  try {
    await savePending
  } catch (error) {
    // 存不下就退回原值：否则界面显示的语言与重启后的语言不一致，且用户毫不知情。
    // 只在自己仍是最新选择时回退，避免踩掉后一次切换。
    if (locale.value === next) locale.value = previous
    logger.error(`保存语言设置失败: ${error instanceof Error ? error.message : error}`)
    message.error(t('common.languageSaveFailed'))
  }
}

export function useLocale() {
  return {
    // 只读：改语言必须走 setLocale，否则会跳过持久化
    locale: computed(() => locale.value),
    antdLocale: computed(() => ANTD_LOCALE[locale.value]),
    initLocale,
    setLocale,
  }
}
