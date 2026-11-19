import type { ShareTemplateItem } from '@/composables/useTemplateApi'
import type { ScriptType } from '@/types/script'
import { SCRIPT_LOGOS } from '@/utils/scriptLogos'

export type ConfigMode = 'template' | 'custom'
export type CreateStepKey = 'type' | 'config'

type ScriptTypeGroup = 'all' | 'specialized' | 'general'

interface ScriptTypeOption {
  value: ScriptType
  titleKey: string
  descriptionKey: string
  /** 搜索别名。刻意保留中文：译成英文中文用户就搜不到了，英文用户用 latin 别名一样能命中 */
  keywords: string[]
  group: Exclude<ScriptTypeGroup, 'all'>
  icon: string
}

export interface TemplateRequest {
  page: number
  keyword: string
}

interface CreateStep {
  key: CreateStepKey
  titleKey: string
}

interface CreateRequestState {
  type: ScriptType
  configMode: ConfigMode
  template: ShareTemplateItem | null
}

// 本版本只保留通用脚本
export type ScriptCreateRequest =
  | { kind: 'general-custom' }
  | { kind: 'general-template'; template: ShareTemplateItem }

export const SCRIPT_TYPE_OPTIONS: ScriptTypeOption[] = [
  {
    value: 'General',
    titleKey: 'scripts.type.General',
    descriptionKey: 'scripts.create.typeDesc.General',
    keywords: ['general', '通用', '自定义'],
    group: 'general',
    icon: SCRIPT_LOGOS.General,
  },
]

export const buildCreateSteps = ({ type }: Pick<CreateRequestState, 'type'>): CreateStep[] => {
  const steps: CreateStep[] = [{ key: 'type', titleKey: 'scripts.create.step.type' }]
  if (type === 'General') {
    steps.push({ key: 'config', titleKey: 'scripts.create.step.config' })
  }
  return steps
}

type TypeSearchFields = Pick<ScriptTypeOption, 'titleKey' | 'descriptionKey' | 'keywords'>

/** translate 缺省时按 key 原样参与匹配，别名（keywords）永远参与匹配 */
export const filterScriptTypeOptions = <T extends TypeSearchFields>(
  options: T[],
  keyword: string,
  translate: (key: string) => string = key => key
): T[] => {
  const normalizedKeyword = keyword.trim().toLowerCase()
  return options.filter(option => {
    const searchableText = [
      translate(option.titleKey),
      translate(option.descriptionKey),
      ...option.keywords,
    ]
      .join(' ')
      .toLowerCase()
    return !normalizedKeyword || searchableText.includes(normalizedKeyword)
  })
}

export const splitScriptTypeOptions = <T extends Pick<ScriptTypeOption, 'group'>>(
  options: T[]
) => ({
  specialized: options.filter(option => option.group === 'specialized'),
  general: options.filter(option => option.group === 'general'),
})

export const getScriptEditSegment = (_type: ScriptType) => 'general'

export const buildCreateRequest = (state: CreateRequestState): ScriptCreateRequest | null => {
  if (state.configMode === 'custom') {
    return { kind: 'general-custom' }
  }
  return state.template ? { kind: 'general-template', template: state.template } : null
}
