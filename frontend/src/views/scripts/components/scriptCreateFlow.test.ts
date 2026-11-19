import { describe, expect, it } from 'vite-plus/test'

import { buildCreateRequest, buildCreateSteps, SCRIPT_TYPE_OPTIONS } from './scriptCreateFlow'

describe('scriptCreateFlow · 类型卡片', () => {
  it('本构建只开放 General 入口', () => {
    expect(SCRIPT_TYPE_OPTIONS.map(option => [option.value, option.group])).toEqual([
      ['General', 'general'],
    ])
  })
})

describe('scriptCreateFlow · 通用脚本', () => {
  it('通用脚本有第二步「配置来源」', () => {
    expect(buildCreateSteps({ type: 'General' }).map(step => step.key)).toEqual(['type', 'config'])
  })

  it('自定义配置直接新建；模板未选中时不提交', () => {
    const base = { type: 'General' as const, template: null }
    expect(buildCreateRequest({ ...base, configMode: 'custom' })).toEqual({
      kind: 'general-custom',
    })
    expect(buildCreateRequest({ ...base, configMode: 'template' })).toBeNull()
  })
})
