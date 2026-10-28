import type { App } from 'vue'
import type { Router } from 'vue-router'

// 本机构建不加载远程遥测 SDK。应用自身的日志及 Vue 错误处理保持原样。
export const setTelemetryEnabled = (_enabled: boolean): void => {}
export const configureSentry = (_app: App, _router: Router, _enabled: boolean): void => {}
export const recordRendererStartup = (_durationMs: number): void => {}
