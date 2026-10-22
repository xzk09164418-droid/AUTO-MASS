export interface LocalConfig {
  ChildSession: {
    Enabled: boolean
    HostPort: number
    Resolution: string
    StartHidden: boolean
    WatchMode: boolean
  }
  Hotkey: { Enabled: boolean; ToggleStartStop: string; PreviousTask: string; NextTask: string }
}
export interface DesktopLease {
  leaseId: string
  caller: string
  status: string
  requestedAt?: string
}
export interface DesktopStatus {
  enabled?: boolean
  hostConnected?: boolean
  childSessionId?: number | null
  inSubtaskExecution?: boolean
  hostStatus?: {
    ok?: boolean
    trayMode?: boolean
    watchMode?: boolean
    smartSizing?: boolean
    topmost?: boolean
  }
  activeLeases?: DesktopLease[]
}
