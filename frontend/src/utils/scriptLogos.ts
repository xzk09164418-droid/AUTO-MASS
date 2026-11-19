import type { ScriptType } from '@/types/script'
import generalIcon from '@/assets/AUTO-MAS.ico'

/** 脚本类型 → 图标资源，Vite 处理后的 URL。本版本只保留通用脚本 */
export const SCRIPT_LOGOS: Record<ScriptType, string> = {
  General: generalIcon,
}

/** 脚本类型 → 展示名（图片 alt；可见名称走 i18n 词表） */
export const SCRIPT_LABELS: Record<ScriptType, string> = {
  General: 'AUTO-MAS',
}
