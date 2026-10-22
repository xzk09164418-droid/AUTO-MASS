import { reactive } from 'vue'

export const browserPicker = reactive({
  open: false,
  folder: false,
  extensions: [] as string[],
})
let resolveSelection: ((path: string | null) => void) | undefined

export function chooseLocalPath(folder: boolean, filters: unknown[] = []): Promise<string | null> {
  finishLocalSelection(null)
  browserPicker.folder = folder
  browserPicker.extensions = filters.flatMap(filter => {
    if (typeof filter !== 'object' || !filter || !('extensions' in filter)) return []
    return Array.isArray(filter.extensions)
      ? filter.extensions.filter(x => typeof x === 'string')
      : []
  })
  browserPicker.open = true
  return new Promise(resolve => {
    resolveSelection = resolve
  })
}

export function finishLocalSelection(path: string | null) {
  browserPicker.open = false
  resolveSelection?.(path)
  resolveSelection = undefined
}
