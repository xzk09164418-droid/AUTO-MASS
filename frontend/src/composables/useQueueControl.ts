import { ref } from 'vue'
import { invokeBrowserHost } from './useBrowserHost'

export interface QueueControlState {
  queues: { id: string; name: string; isCycle: boolean }[]
  selectedQueueId: string | null
  controls: {
    taskId: string
    queueId: string | null
    selectedTask: string
    index: number
    revision: number
    paused: boolean
    cleaning: boolean
    error: string
    allBlocked: boolean
    state: string
    prompt: { token: string; message: string; deadline: number | null; buttons: boolean } | null
  }[]
}
const state = ref<QueueControlState>({ queues: [], selectedQueueId: null, controls: [] })
export function useQueueControl() {
  async function refresh() {
    state.value = await invokeBrowserHost<QueueControlState>(
      'localControl',
      'queueControlState',
      {}
    )
  }
  async function select(queueId: string) {
    await invokeBrowserHost('localControl', 'queueControl', { action: 'select', queueId })
    await refresh()
  }
  async function respond(taskId: string, token: string, action: 'pause' | 'continue') {
    await invokeBrowserHost('localControl', 'queueControl', { taskId, token, action })
    await refresh()
  }
  return { state, refresh, select, respond }
}
