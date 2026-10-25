const LABEL_HEIGHT = '--browser-form-label-height'
const LABEL_SELECTOR = '.ant-form-item-label, .form-label-wrapper'
const COLUMN_SELECTOR = '.ant-col:not(.ant-form-item-label):not(.ant-form-item-control)'
const ROW_TOLERANCE = 1

/** 按实际折行后的列分组，让同排控件共享最长标签的高度。 */
export function installBrowserFormAlignment() {
  let frame = 0
  let stopped = false
  const labels = new Set<HTMLElement>()
  const columns = new Set<Element>()
  const schedule = () => {
    if (!stopped && !frame) frame = requestAnimationFrame(align)
  }
  const resizeObserver = new ResizeObserver(schedule)

  function align() {
    frame = 0
    // 先恢复自然高度，缩短文字、收窄/放宽窗口后都能重新计算。
    for (const label of labels) label.style.removeProperty(LABEL_HEIGHT)
    labels.clear()
    for (const column of columns) {
      if (!column.isConnected) {
        resizeObserver.unobserve(column)
        columns.delete(column)
      }
    }

    const heights = new Map<HTMLElement, number>()
    for (const row of document.querySelectorAll('.ant-row')) {
      if (row.classList.contains('ant-form-item-row')) continue
      const groups = new Map<number, HTMLElement[][]>()
      for (const column of row.children) {
        if (!column.classList.contains('ant-col') || !column.getClientRects().length) continue
        if (!columns.has(column)) {
          columns.add(column)
          resizeObserver.observe(column)
        }
        const columnLabels = Array.from(
          column.querySelectorAll<HTMLElement>(LABEL_SELECTOR)
        ).filter(
          label => label.closest(COLUMN_SELECTOR) === column && label.getClientRects().length > 0
        )
        if (!columnLabels.length) continue
        const top = column.getBoundingClientRect().top
        const key = [...groups.keys()].find(value => Math.abs(value - top) <= ROW_TOLERANCE) ?? top
        const group = groups.get(key) ?? []
        group.push(columnLabels)
        groups.set(key, group)
      }
      for (const group of groups.values()) {
        if (group.length < 2) continue
        const count = Math.max(...group.map(items => items.length))
        for (let index = 0; index < count; index++) {
          const peers = group.flatMap(items => (items[index] ? [items[index]] : []))
          const height = Math.max(...peers.map(label => label.getBoundingClientRect().height))
          for (const label of peers) heights.set(label, height)
        }
      }
    }
    // 所有测量完成后再写入，避免前一列的调整影响下一列分组。
    for (const [label, height] of heights) {
      label.style.setProperty(LABEL_HEIGHT, `${height}px`)
      labels.add(label)
    }
  }

  const mutationObserver = new MutationObserver(records => {
    if (
      records.some(record => {
        const element =
          record.target instanceof Element ? record.target : record.target.parentElement
        if (!element?.closest('.ant-row, .ant-modal, .ant-drawer, #app')) return false
        // 只重新测量受表单行影响的变化；菜单、状态文字等更新不改变标签对齐。
        return (
          (record.type === 'attributes' && record.oldValue?.split(/\s+/).includes('ant-row')) ||
          element.closest('.ant-row') !== null ||
          element.querySelector('.ant-row') !== null ||
          Array.from(record.removedNodes).some(
            node =>
              node instanceof Element &&
              (node.matches('.ant-row') || node.querySelector('.ant-row') !== null)
          )
        )
      })
    ) {
      schedule()
    }
  })
  mutationObserver.observe(document.body, {
    childList: true,
    characterData: true,
    subtree: true,
    attributes: true,
    attributeOldValue: true,
    attributeFilter: ['class'],
  })
  window.addEventListener('resize', schedule)
  void document.fonts.ready.then(schedule)
  schedule()

  return () => {
    stopped = true
    cancelAnimationFrame(frame)
    mutationObserver.disconnect()
    resizeObserver.disconnect()
    window.removeEventListener('resize', schedule)
    for (const label of labels) label.style.removeProperty(LABEL_HEIGHT)
  }
}
