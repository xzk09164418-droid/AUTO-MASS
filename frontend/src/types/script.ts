// 脚本类型定义。本版本只保留通用脚本，MAA / MaaFW / MaaEnd 等专项已移除。
import type { GeneralConfig_Output } from '@/api'

export type ScriptType = 'General'

export interface GeneralScriptConfig {
  Game: {
    Arguments: string
    Enabled: boolean
    IfForceClose: boolean
    Path: string
    Type: string
    WaitTime: number
    EmulatorId: string
    EmulatorIndex: string
    URL: string
    ProcessName: string
  }
  Info: {
    Name: string
    RootPath: string
  }
  Run: {
    HardTimeLimit: number
    ProxyTimesLimit: number
    RunTimeLimit: number
    RunTimesLimit: number
  }
  Script: {
    TaskKill?: { Name: string; Path: string }[]
    TaskKillMode?: 'Tracked' | 'Session' | 'Force'
    Restart?: {
      Path: string
      Arguments: string
      WorkingDirectory: string
      WaitSeconds: number
      IsMain: boolean
    }[]
    Arguments: string
    ConfigPath: string
    ConfigPathMode: string
    ErrorLog: string
    IfTrackProcess: boolean
    TrackProcessName: string
    TrackProcessExe: string
    TrackProcessCmdline: string
    LogPath: string
    LogPathFormat: string
    LogTimeEnd: number
    LogTimeStart: number
    LogTimeFormat: string
    LogHookEnabled: boolean
    LogHookRules: string
    PushLogEnabled: boolean
    PushLogPatterns: string
    ScriptPath: string
    SuccessLog: string
    SuccessLogMode: string
    ErrorLogMode: string
    UpdateConfigMode: string
  }
  SubConfigsInfo: {
    UserData: {
      instances: unknown[]
    }
  }
}

// 脚本基础信息
export interface Script {
  id: string
  type: ScriptType
  name: string
  config: GeneralConfig_Output
  users: User[]
}

// 用户配置（通用脚本用户）
export interface User {
  id: string
  name: string
  Data: {
    LastProxyDate: string
    ProxyTimes: number
  }
  Info: {
    Name: string
    Status: boolean
    RemainedDay: number
    Notes: string
    Tag?: string | null // 用户标签列表（JSON字符串，TagItem的dict列表）
    Base?: string
    IfQuickConfig?: boolean
    IfUseMasConfig?: boolean
    IfScriptBeforeTask?: boolean
    ScriptBeforeTask?: string
    IfScriptAfterTask?: boolean
    ScriptAfterTask?: string
  }
  Notify: {
    Enabled: boolean
    IfSendMail: boolean
    IfSendStatistic: boolean
    IfServerChan: boolean
    ServerChanKey: string
    ToAddress: string
  }
}

// 脚本索引项
export interface ScriptIndexItem {
  uid: string
  type: 'GeneralConfig'
}

// 脚本详情（用于前端展示）
export interface ScriptDetail {
  uid: string
  type: ScriptType
  activityGame?: string | null
  name: string
  config: GeneralConfig_Output
  users?: User[]
  createTime?: string
}
