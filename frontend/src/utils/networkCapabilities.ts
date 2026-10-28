/** 本机构建固定停用的联网功能；与用户旧配置分开，防止旧开关重新触发请求。 */
export const networkCapabilities = {
  updates: false,
  telemetry: false,
  onlineResources: false,
  communityAccounts: true,
  communityActivity: false,
  activity: true,
  notifications: true,
  mailControl: true,
} as const

export const NETWORK_DISABLED_MESSAGE =
  '本机构建已停用该联网功能，仅保留活动内容、社区签到、邮箱控制和远程通知'
