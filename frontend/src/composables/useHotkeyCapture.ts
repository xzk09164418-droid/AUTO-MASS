import { onUnmounted, ref } from 'vue'
import { invokeBrowserHost } from './useBrowserHost'
import { canonicalKeyName, HOTKEY_MODIFIERS, primaryKeyFromCode } from '@/utils/maafwHotkey'
import { t } from '@/i18n'

export function useHotkeyCapture(onRecorded: (field: string, value: string) => void) {
  const field = ref('')
  const ready = ref(false)
  const preview = ref('')
  const error = ref('')
  let token = ''
  let generation = 0
  let timeout: ReturnType<typeof setTimeout> | undefined
  const held = new Set<string>()
  const keys = new Set<string>()
  let invalid = false

  async function finish(value?: string) {
    const target = field.value
    generation++
    ready.value = false
    field.value = ''
    clearTimeout(timeout)
    window.removeEventListener('keydown', keydown, true)
    window.removeEventListener('keyup', keyup, true)
    window.removeEventListener('blur', cancel)
    document.removeEventListener('visibilitychange', visibility)
    const previousToken = token
    token = ''
    try {
      if (previousToken)
        await invokeBrowserHost('localControl', 'captureHotkey', {
          action: 'end',
          token: previousToken,
        })
      if (value) onRecorded(target, value)
    } catch (err) {
      error.value = String(err)
    }
  }
  function cancel() {
    void finish()
  }
  function visibility() {
    if (document.hidden) cancel()
  }
  function keydown(event: KeyboardEvent) {
    event.preventDefault()
    event.stopImmediatePropagation()
    if (event.key === 'Escape') {
      cancel()
      return
    }
    if (!ready.value || event.repeat) return
    held.add(event.code || event.key)
    const modifiers = [event.ctrlKey, event.metaKey, event.altKey, event.shiftKey]
    HOTKEY_MODIFIERS.forEach((key, index) => {
      if (modifiers[index]) keys.add(key)
    })
    const name = canonicalKeyName(event.key)
    if (!(HOTKEY_MODIFIERS as readonly string[]).includes(name)) {
      const primary =
        /^Key[A-Z]$/.test(event.code) && /^[a-z]$/i.test(event.key)
          ? event.key.toUpperCase()
          : primaryKeyFromCode(event.code)
      if (primary) keys.add(primary)
      else invalid = true
    }
    preview.value = [...keys].join('+')
  }
  function keyup(event: KeyboardEvent) {
    event.preventDefault()
    event.stopImmediatePropagation()
    held.delete(event.code || event.key)
    if (
      !ready.value ||
      held.size ||
      event.ctrlKey ||
      event.metaKey ||
      event.altKey ||
      event.shiftKey
    )
      return
    const modifiers = HOTKEY_MODIFIERS.filter(key => keys.has(key))
    const primary = [...keys].filter(key => !(HOTKEY_MODIFIERS as readonly string[]).includes(key))
    if (invalid || primary.length !== 1 || (!modifiers.length && !/^F\d+$/.test(primary[0]))) {
      error.value = t('localControls.captureInvalid')
      void finish()
      return
    }
    void finish([...modifiers, primary[0]].join('+'))
  }
  async function begin(target: string) {
    if (field.value) return
    const round = ++generation
    error.value = ''
    preview.value = ''
    field.value = target
    held.clear()
    keys.clear()
    invalid = false
    window.addEventListener('blur', cancel)
    document.addEventListener('visibilitychange', visibility)
    try {
      const result = await invokeBrowserHost<{ token: string }>('localControl', 'captureHotkey', {
        action: 'begin',
      })
      if (generation !== round) {
        await invokeBrowserHost('localControl', 'captureHotkey', {
          action: 'end',
          token: result.token,
        })
        return
      }
      token = result.token
      ready.value = true
      window.addEventListener('keydown', keydown, true)
      window.addEventListener('keyup', keyup, true)
      timeout = setTimeout(cancel, 25000)
    } catch (err) {
      if (generation === round) {
        error.value = String(err)
        await finish()
      }
    }
  }
  onUnmounted(cancel)
  return { field, ready, preview, error, begin, cancel }
}
