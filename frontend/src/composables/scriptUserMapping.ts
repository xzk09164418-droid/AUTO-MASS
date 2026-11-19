import type { UserGetOut } from '@/api'
import type { User } from '@/types/script'

type LooseSection = Record<string, unknown>

const section = (value: unknown): LooseSection =>
  value && typeof value === 'object' ? (value as LooseSection) : {}

const pick = <T>(source: LooseSection, key: string, fallback: T): T => {
  const value = source[key]
  return value === undefined || value === null ? fallback : (value as T)
}

const optional = <T>(source: LooseSection, key: string): T | undefined => {
  const value = source[key]
  return value === undefined ? undefined : (value as T)
}

// 只转换后端数据与兼容默认值；请求、错误提示和加载状态由 API composable 负责。
// 本版本只保留通用脚本，其余专项用户类型已移除。
export function mapScriptUsers(userResponse: UserGetOut): User[] {
  const users: User[] = []
  for (const userIndex of userResponse.index) {
    const userData = userResponse.data[userIndex.uid]
    if (userIndex.type !== 'GeneralUserConfig' || !userData) continue

    const raw = userData as unknown as LooseSection
    const info = section(raw.Info)
    const notify = section(raw.Notify)
    const data = section(raw.Data)
    const name = pick(info, 'Name', `用户${userIndex.uid}`)

    users.push({
      id: userIndex.uid,
      name: name || `用户${userIndex.uid}`,
      Info: {
        Name: name,
        Status: pick(info, 'Status', true),
        RemainedDay: pick(info, 'RemainedDay', -1),
        Notes: pick(info, 'Notes', ''),
        Tag: pick<string | null>(info, 'Tag', null),
        Base: optional<string>(info, 'Base'),
        IfQuickConfig:
          typeof info.IfQuickConfig === 'boolean' ? (info.IfQuickConfig as boolean) : undefined,
        IfUseMasConfig: pick(info, 'IfUseMasConfig', true),
        IfScriptBeforeTask: pick(info, 'IfScriptBeforeTask', false),
        ScriptBeforeTask: pick(info, 'ScriptBeforeTask', ''),
        IfScriptAfterTask: pick(info, 'IfScriptAfterTask', false),
        ScriptAfterTask: pick(info, 'ScriptAfterTask', ''),
      },
      Notify: {
        Enabled: pick(notify, 'Enabled', false),
        IfSendStatistic: pick(notify, 'IfSendStatistic', false),
        IfSendMail: pick(notify, 'IfSendMail', false),
        ToAddress: pick(notify, 'ToAddress', ''),
        IfServerChan: pick(notify, 'IfServerChan', false),
        ServerChanKey: pick(notify, 'ServerChanKey', ''),
      },
      Data: {
        LastProxyDate: pick(data, 'LastProxyDate', '2000-01-01'),
        ProxyTimes: pick(data, 'ProxyTimes', 0),
      },
    })
  }
  return users
}
