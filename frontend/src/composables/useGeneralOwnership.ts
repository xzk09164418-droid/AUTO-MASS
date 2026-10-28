import { onMounted, onUnmounted, ref } from 'vue'
import { GeneralOwnershipService } from '@/api/services/GeneralOwnershipService'
import type { GeneralOwnershipPromptData } from '@/api/models/GeneralOwnershipPromptData'

export function useGeneralOwnership() {
  const prompt = ref<GeneralOwnershipPromptData | null>(null)
  const error = ref('')
  const busy = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let active = false
  let revision = 0

  async function refresh() {
    const startedRevision = revision
    try {
      const response =
        await GeneralOwnershipService.getOwnershipPromptsApiScriptsOwnershipPromptsGet()
      if (active && !busy.value && startedRevision === revision && response.code === 200) {
        const next = response.data[0] ?? null
        if (next?.requestId !== prompt.value?.requestId) error.value = ''
        prompt.value = next
      }
    } catch {
      // 后端重连时保留当前提示；只在用户提交选择失败时显示错误。
    } finally {
      if (active) timer = setTimeout(refresh, 2000)
    }
  }

  async function answer(edit: boolean): Promise<string | null> {
    const current = prompt.value
    if (!current || busy.value) return null
    busy.value = true
    revision++
    error.value = ''
    try {
      const result =
        await GeneralOwnershipService.answerOwnershipPromptApiScriptsOwnershipAnswerPost({
          requestId: current.requestId,
          edit,
        })
      if (result.code !== 200) throw new Error(result.message)
      if (prompt.value?.requestId === current.requestId) prompt.value = null
      return edit ? current.scriptId : null
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
      return null
    } finally {
      busy.value = false
    }
  }

  onMounted(() => {
    active = true
    void refresh()
  })
  onUnmounted(() => {
    active = false
    clearTimeout(timer)
  })
  return { prompt, error, busy, answer }
}
