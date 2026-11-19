import { computed, ref, shallowRef, watch } from 'vue'
import { theme } from 'ant-design-vue'
import { getConfig, saveConfig, type FrontendConfig } from '@/utils/config'
import { createAppearanceCursorValue } from '@/components/appearanceCursor'
import { createAppearanceBackgroundApplier } from './appearanceBackground'
import { createAppearanceSurfaceColor, getAppearanceSurfaceOpacity } from './appearanceSurfaces'
import type { InstalledAppearance, OnlineAppearanceInstallResult } from '@/types/appearance'

type AntTokens = ReturnType<typeof theme.useToken>['token']['value']
const resolvedAntTokens = shallowRef<AntTokens>()

export type ThemeMode = 'system' | 'light' | 'dark'
export type ThemeColor =
  | 'blue'
  | 'purple'
  | 'cyan'
  | 'green'
  | 'magenta'
  | 'pink'
  | 'red'
  | 'orange'
  | 'yellow'
  | 'volcano'
  | 'geekblue'
  | 'lime'
  | 'gold'

const themeMode = ref<ThemeMode>('system')
const themeColor = ref<ThemeColor>('gold')
const appearanceId = ref<string | null>(null)
const activeAppearance = ref<InstalledAppearance | null>(null)
const appearances = ref<InstalledAppearance[]>([])
const isDark = ref(false)
const logger = window.hostAPI.getLogger('主题')
const applyAppearanceBackground = createAppearanceBackgroundApplier({ logger })
let appearanceListenerInitialized = false
let themeConfigListenerInitialized = false
let themeRevision = 0
let configRevision = 0
let appearanceLoadRevision = 0
let themeChangeQueue: Promise<void> = Promise.resolve()

// 连续操作按顺序完成状态变更和持久化，失败回退后再处理下一项设置。
const queueThemeChange = (change: () => Promise<void>): Promise<void> => {
  const pending = themeChangeQueue.then(change)
  themeChangeQueue = pending.catch(() => undefined)
  return pending
}
type ThemeSnapshot = {
  themeMode: ThemeMode
  themeColor: ThemeColor
  appearanceId: string | null
}

let persistedThemeSnapshot: ThemeSnapshot = {
  themeMode: 'system',
  themeColor: 'gold',
  appearanceId: null,
}

// 预设主题色（莱茵生命实验室低饱和精密色阶）
const themeColors: Record<ThemeColor, string> = {
  blue: '#2b7a9b',
  purple: '#6b5b9e',
  cyan: '#268fa3',
  green: '#4a7c59',
  magenta: '#b84c76',
  pink: '#c25b82',
  red: '#c43e38',
  orange: '#d96b27',
  yellow: '#c99a2e',
  volcano: '#cf5727',
  geekblue: '#395a8c',
  lime: '#729434',
  // 莱茵生命 PV 暖棕；深色下由 resolveThemeColor 换成琥珀 #c5a16b
  gold: '#9b7247',
}

// 主题色在深色下的替换值：PV 原作浅色用暖棕、深色用琥珀，其余预设色沿用同一值
const DARK_THEME_COLOR_OVERRIDES: Partial<Record<ThemeColor, string>> = {
  gold: '#c5a16b',
}

const resolveThemeColor = (color: ThemeColor, dark: boolean) =>
  (dark ? DARK_THEME_COLOR_OVERRIDES[color] : undefined) ?? themeColors[color]

// 莱茵生命（Rhine Lab）默认明暗表面与排版基准
const RHINE_FONT_FAMILY =
  "'AUTO-MAS MiSans', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif"
const RHINE_FONT_MONO =
  "'Cascadia Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace"

const RHINE_SURFACE_TOKENS = {
  light: {
    colorBgLayout: '#eae5e1',
    colorBgContainer: '#f4f1ed',
    colorBgElevated: '#f8f6f3',
    colorText: '#080a08',
    colorTextSecondary: '#5f5d56',
    colorTextTertiary: '#77756d',
    colorBorder: '#aaa59a',
    colorBorderSecondary: '#d3cec5',
    colorSuccess: '#55785a',
    colorWarning: '#b8752c',
    colorError: '#b6453c',
    colorInfo: '#4f7487',
  },
  dark: {
    colorBgLayout: '#11181b',
    colorBgContainer: '#162024',
    colorBgElevated: '#1c272c',
    colorText: '#e0e3dc',
    colorTextSecondary: '#a6b0b1',
    colorTextTertiary: '#7e8a8c',
    colorBorder: '#536166',
    colorBorderSecondary: '#2a363b',
    colorSuccess: '#7fa784',
    colorWarning: '#d39a55',
    colorError: '#d9695f',
    colorInfo: '#7ea7b9',
  },
} as const

const THEME_RESOLVED_STORAGE_KEY = 'auto-mas.theme.resolved'
let themeHydrated = false

const readCachedResolvedTheme = (): 'dark' | 'light' | null => {
  try {
    const value = localStorage.getItem(THEME_RESOLVED_STORAGE_KEY)
    return value === 'dark' || value === 'light' ? value : null
  } catch {
    return null
  }
}

const writeCachedResolvedTheme = (dark: boolean) => {
  try {
    localStorage.setItem(THEME_RESOLVED_STORAGE_KEY, dark ? 'dark' : 'light')
  } catch {
    // 浏览器禁用或受限存储时跳过，仅影响下次首屏预填充
  }
}

// 检测系统主题
const getSystemTheme = () => {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

// 更新主题
const updateTheme = () => {
  let shouldBeDark: boolean

  if (activeAppearance.value) {
    shouldBeDark = activeAppearance.value.mode === 'dark'
  } else if (!themeHydrated && themeMode.value === 'system') {
    // 配置尚未完成异步加载时沿用上次已解析的明暗结果，防止深色模式下首屏先闪成浅色再跳回深色
    const cached = readCachedResolvedTheme()
    shouldBeDark = cached !== null ? cached === 'dark' : getSystemTheme()
  } else if (themeMode.value === 'system') {
    shouldBeDark = getSystemTheme()
  } else {
    shouldBeDark = themeMode.value === 'dark'
  }

  isDark.value = shouldBeDark

  // 更新HTML类名
  if (shouldBeDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }

  if (themeHydrated) {
    writeCachedResolvedTheme(shouldBeDark)
  }

  // 更新CSS变量
  updateCSSVariables()
}

const commitPersistedThemeSnapshot = () => {
  persistedThemeSnapshot = {
    themeMode: themeMode.value,
    themeColor: themeColor.value,
    appearanceId: appearanceId.value,
  }
}

const setPersistedThemeSnapshot = (snapshot: ThemeSnapshot) => {
  persistedThemeSnapshot = { ...snapshot }
}

const restorePersistedThemeSnapshot = () => {
  themeMode.value = persistedThemeSnapshot.themeMode
  themeColor.value = persistedThemeSnapshot.themeColor
  appearanceId.value = persistedThemeSnapshot.appearanceId
  activeAppearance.value = persistedThemeSnapshot.appearanceId
    ? (appearances.value.find(item => item.id === persistedThemeSnapshot.appearanceId) ?? null)
    : null
  updateTheme()
}

// 更新CSS变量
const updateCSSVariables = () => {
  const root = document.documentElement
  const cursorUrls = activeAppearance.value?.cursorUrls
  const cursors = activeAppearance.value?.cursors
  if (cursors && Object.keys(cursors).length > 0) {
    root.classList.add('appearance-cursor-custom')
  } else {
    root.classList.remove('appearance-cursor-custom')
  }
  // 光标变量独立于 AntD token bridge，确保首屏、清除和回退立即恢复浏览器默认语义。
  root.style.setProperty(
    '--app-appearance-cursor-default',
    createAppearanceCursorValue('default', cursorUrls, cursors)
  )
  root.style.setProperty(
    '--app-appearance-cursor-pointer',
    createAppearanceCursorValue('pointer', cursorUrls, cursors)
  )
  root.style.setProperty(
    '--app-appearance-cursor-text',
    createAppearanceCursorValue('text', cursorUrls, cursors)
  )
  const surfaceOpacity = getAppearanceSurfaceOpacity(activeAppearance.value)
  if (surfaceOpacity !== undefined) {
    root.classList.add('appearance-background-custom')
  } else {
    root.classList.remove('appearance-background-custom')
  }
  // 素材和开关独立于 token bridge，清除外观时立即恢复，不依赖下一次组件渲染。
  // 背景只在图片真的变了时才写，避免每次换主题色都重新解码。
  applyAppearanceBackground(root.style, activeAppearance.value?.backgroundUrl)
  root.style.setProperty(
    '--app-appearance-background-opacity',
    String(activeAppearance.value?.background?.opacity ?? 1)
  )
  root.style.setProperty(
    '--app-appearance-background-position',
    activeAppearance.value?.background?.position ?? 'right bottom'
  )
  root.style.setProperty(
    '--app-appearance-background-size',
    activeAppearance.value?.background?.size ?? 'cover'
  )

  // ===== 莱茵生命（Rhine Lab）PV 语义变量 =====
  // 取自 PV 原作：暖灰白档案底、近黑正文、细线结构、暖棕（浅色）/琥珀（深色）选中信号，不使用绿色强调。
  // 与 rhineLab.css 的 :root 兜底值一一对应，保证首帧即呈现最终配色。
  const dark = isDark.value
  root.style.setProperty('--app-rhine-canvas-bg', dark ? '#11181b' : '#eae5e1')
  root.style.setProperty('--app-rhine-canvas-text', dark ? '#e0e3dc' : '#080a08')
  root.style.setProperty(
    '--app-rhine-chrome-bg',
    dark ? 'rgba(17, 24, 27, 0.92)' : 'rgba(234, 229, 225, 0.92)'
  )
  root.style.setProperty('--app-rhine-chrome-border', dark ? '#536166' : '#aaa59a')
  root.style.setProperty('--app-rhine-rule', dark ? '#e0e3dc' : '#080a08')
  root.style.setProperty('--app-rhine-hairline', dark ? '#536166' : '#aaa59a')
  root.style.setProperty(
    '--app-rhine-grid-line',
    dark ? 'rgba(224, 227, 220, 0.045)' : 'rgba(8, 10, 8, 0.05)'
  )
  root.style.setProperty('--app-rhine-accent', dark ? '#c5a16b' : '#9b7247')
  root.style.setProperty(
    '--app-rhine-accent-soft',
    dark ? 'rgba(197, 161, 107, 0.14)' : 'rgba(155, 114, 71, 0.12)'
  )
  root.style.setProperty(
    '--app-rhine-accent-border',
    dark ? 'rgba(197, 161, 107, 0.55)' : 'rgba(155, 114, 71, 0.55)'
  )
  root.style.setProperty('--app-rhine-solid-bg', dark ? '#e0e3dc' : '#080a08')
  root.style.setProperty('--app-rhine-solid-text', dark ? '#11181b' : '#eae5e1')
  root.style.setProperty('--app-rhine-olive', dark ? '#a6b0b1' : '#77756d')
  root.style.setProperty(
    '--app-rhine-surface-subtle',
    dark ? 'rgba(255, 255, 255, 0.025)' : 'rgba(255, 255, 255, 0.34)'
  )
  root.style.setProperty(
    '--app-rhine-surface-header',
    dark ? 'rgba(224, 227, 220, 0.04)' : 'rgba(8, 10, 8, 0.035)'
  )
  root.style.setProperty('--app-rhine-card-shadow', dark ? 'none' : 'none')
  root.style.setProperty(
    '--app-rhine-card-shadow-hover',
    dark ? '0 12px 30px -18px rgba(0, 0, 0, 0.8)' : '0 10px 28px -18px rgba(8, 10, 8, 0.45)'
  )
  root.style.setProperty('--app-rhine-subcard-shadow', dark ? 'none' : 'none')
  root.style.setProperty('--app-rhine-card-border-top', dark ? '#536166' : '#aaa59a')
  root.style.setProperty('--app-rhine-card-border-bottom', dark ? '#536166' : '#aaa59a')
  root.style.setProperty('--app-rhine-card-surface-sheen', dark ? 'none' : 'none')
  root.style.setProperty('--app-rhine-btn-shadow', dark ? 'none' : 'none')
  root.style.setProperty(
    '--app-rhine-modal-backdrop',
    dark ? 'rgba(10, 15, 17, 0.72)' : 'rgba(234, 229, 225, 0.66)'
  )
  root.style.setProperty(
    '--app-rhine-hover-bg',
    dark ? 'rgba(224, 227, 220, 0.055)' : 'rgba(8, 10, 8, 0.045)'
  )
  root.style.setProperty(
    '--app-rhine-active-bg',
    dark ? 'rgba(197, 161, 107, 0.12)' : 'rgba(155, 114, 71, 0.1)'
  )
  root.style.setProperty('--app-rhine-muted-index', dark ? '#7e8a8c' : '#77756d')
  root.style.setProperty('--app-rhine-corner-mark', dark ? '#e0e3dc' : '#080a08')
  root.style.setProperty('--app-rhine-font-sans', RHINE_FONT_FAMILY)
  root.style.setProperty('--app-rhine-font-mono', RHINE_FONT_MONO)

  if (!resolvedAntTokens.value) return
  const customTokens = activeAppearance.value?.tokens
  const primaryColor =
    customTokens?.colorPrimary ?? resolveThemeColor(themeColor.value, isDark.value)
  // 由 ConfigProvider 内的 ThemeTokenBridge 传入最终 token，包含包内的 alias overrides。
  const antTokens = resolvedAntTokens.value

  // 基础背景（用于估算混合）
  const baseLightBg = '#e8e5e1'
  const baseDarkBg = '#111619'
  const baseMenuBg = isDark.value ? baseDarkBg : baseLightBg

  // 改进：侧边栏背景使用 HSL 调整而不是简单线性混合，提高在不同主色下的可读性
  const siderBg = deriveSiderBg(primaryColor, baseMenuBg, isDark.value)
  const siderBorder = deriveSiderBorder(siderBg, primaryColor, isDark.value)

  // 基础文字候选色
  const candidateTextLight = 'rgba(255,255,255,0.88)'
  const candidateTextDark = 'rgba(0,0,0,0.88)'

  // 选菜单文字颜色：对 siderBg 计算对比度，优先满足 >=4.5
  const menuTextColor = pickAccessibleColor(candidateTextDark, candidateTextLight, siderBg)
  const iconColor = menuTextColor

  // ===== AntD token 变量 =====
  // 与 ConfigProvider 使用同一套 seed 和算法，避免 CSS 变量与组件主题分叉。
  root.style.setProperty('--ant-color-primary', antTokens.colorPrimary)
  root.style.setProperty('--ant-color-primary-hover', antTokens.colorPrimaryHover)
  root.style.setProperty('--ant-color-primary-active', antTokens.colorPrimaryActive)
  root.style.setProperty('--ant-color-primary-bg', antTokens.colorPrimaryBg)
  root.style.setProperty('--ant-color-primary-bg-hover', antTokens.colorPrimaryBgHover)
  root.style.setProperty('--ant-color-primary-border', antTokens.colorPrimaryBorder)

  root.style.setProperty('--ant-color-text', antTokens.colorText)
  root.style.setProperty('--ant-color-text-secondary', antTokens.colorTextSecondary)
  root.style.setProperty('--ant-color-text-tertiary', antTokens.colorTextTertiary)
  root.style.setProperty('--ant-color-text-quaternary', antTokens.colorTextQuaternary)
  root.style.setProperty('--ant-color-text-heading', antTokens.colorTextHeading)
  root.style.setProperty('--ant-color-text-description', antTokens.colorTextDescription)
  root.style.setProperty('--ant-color-text-placeholder', antTokens.colorTextPlaceholder)
  root.style.setProperty('--ant-color-text-disabled', antTokens.colorTextDisabled)

  root.style.setProperty('--ant-color-bg-container', antTokens.colorBgContainer)
  root.style.setProperty('--ant-color-bg-layout', antTokens.colorBgLayout)
  root.style.setProperty('--ant-color-bg-elevated', antTokens.colorBgElevated)
  root.style.setProperty('--ant-color-border', antTokens.colorBorder)
  root.style.setProperty('--ant-color-border-secondary', antTokens.colorBorderSecondary)
  root.style.setProperty('--ant-box-shadow-secondary', antTokens.boxShadowSecondary)
  root.style.setProperty('--ant-box-shadow-tertiary', antTokens.boxShadowTertiary)
  root.style.setProperty('--ant-color-bg-container-disabled', antTokens.colorBgContainerDisabled)
  root.style.setProperty('--ant-color-bg-mask', antTokens.colorBgMask)
  root.style.setProperty('--ant-color-split', antTokens.colorSplit)
  root.style.setProperty('--ant-border-color-split', antTokens.colorSplit)
  const surfaceBg = createAppearanceSurfaceColor(antTokens.colorBgContainer, surfaceOpacity)
  const elevatedSurfaceBg = createAppearanceSurfaceColor(antTokens.colorBgElevated, surfaceOpacity)
  root.style.setProperty('--app-appearance-surface-bg', surfaceBg)
  root.style.setProperty('--app-appearance-elevated-surface-bg', elevatedSurfaceBg)
  root.style.setProperty('--app-background-card-bg', surfaceBg)
  root.style.setProperty('--app-background-card-elevated-bg', elevatedSurfaceBg)
  root.style.setProperty(
    '--ant-font-family-code',
    'ui-monospace, SFMono-Regular, Consolas, monospace'
  )
  root.style.setProperty('--font-monospace', 'ui-monospace, SFMono-Regular, Consolas, monospace')

  root.style.setProperty('--ant-color-fill', antTokens.colorFill)
  root.style.setProperty('--ant-color-fill-secondary', antTokens.colorFillSecondary)
  root.style.setProperty('--ant-color-fill-tertiary', antTokens.colorFillTertiary)
  root.style.setProperty('--ant-color-fill-quaternary', antTokens.colorFillQuaternary)

  root.style.setProperty('--ant-color-error', antTokens.colorError)
  root.style.setProperty('--ant-error-color', antTokens.colorError)
  root.style.setProperty('--ant-color-error-bg', antTokens.colorErrorBg)
  root.style.setProperty('--ant-color-error-bg-hover', antTokens.colorErrorBgHover)
  root.style.setProperty('--ant-color-error-border', antTokens.colorErrorBorder)
  root.style.setProperty('--ant-color-success', antTokens.colorSuccess)
  root.style.setProperty('--ant-color-success-bg', antTokens.colorSuccessBg)
  root.style.setProperty('--ant-color-success-bg-hover', antTokens.colorSuccessBgHover)
  root.style.setProperty('--ant-color-success-border', antTokens.colorSuccessBorder)
  root.style.setProperty('--ant-color-warning', antTokens.colorWarning)
  root.style.setProperty('--ant-color-warning-text', antTokens.colorWarningText)
  root.style.setProperty('--ant-color-warning-bg', antTokens.colorWarningBg)
  root.style.setProperty('--ant-color-warning-bg-hover', antTokens.colorWarningBgHover)
  root.style.setProperty('--ant-color-warning-border', antTokens.colorWarningBorder)

  root.style.setProperty('--ant-color-info', antTokens.colorInfo)
  root.style.setProperty('--ant-color-info-hover', antTokens.colorInfoHover)
  root.style.setProperty('--ant-color-info-bg', antTokens.colorInfoBg)

  // ===== 自定义菜单配色 =====
  // 动态 Alpha：根据主色亮度调整透明度以保持区分度
  const lumPrim = getLuminance(primaryColor)
  const hoverAlphaBase = isDark.value ? 0.22 : 0.14
  const selectedAlphaBase = isDark.value ? 0.38 : 0.26
  const hoverAlpha = clamp01(
    hoverAlphaBase + (isDark.value ? (lumPrim > 0.65 ? -0.04 : 0) : lumPrim < 0.3 ? 0.04 : 0)
  )
  const selectedAlpha = clamp01(
    selectedAlphaBase + (isDark.value ? (lumPrim > 0.65 ? -0.05 : 0) : lumPrim < 0.3 ? 0.05 : 0)
  )

  // 估算最终选中背景（混合算实际颜色用于对比度计算）
  const estimatedSelectedBg = blendColors(baseMenuBg, primaryColor, selectedAlpha)
  const selectedTextColor = pickAccessibleColor(
    'rgba(0,0,0,0.90)',
    'rgba(255,255,255,0.92)',
    estimatedSelectedBg
  )
  const hoverTextColor = menuTextColor

  root.style.setProperty('--app-sider-bg', siderBg)
  root.style.setProperty('--app-sider-border-color', siderBorder)
  root.style.setProperty('--app-menu-text-color', menuTextColor)
  root.style.setProperty('--app-menu-icon-color', iconColor)
  root.style.setProperty('--app-menu-item-hover-text-color', hoverTextColor)
  root.style.setProperty('--app-menu-item-selected-text-color', selectedTextColor)

  // 背景同时提供 rgba 与 hex alpha（兼容处理）
  const hoverRgba = hexToRgba(primaryColor, hoverAlpha)
  const selectedRgba = hexToRgba(primaryColor, selectedAlpha)
  root.style.setProperty('--app-menu-item-hover-bg', hoverRgba)
  root.style.setProperty('--app-menu-item-hover-bg-hex', addAlpha(primaryColor, hoverAlpha))
  root.style.setProperty('--app-menu-item-selected-bg', selectedRgba)
  root.style.setProperty('--app-menu-item-selected-bg-hex', addAlpha(primaryColor, selectedAlpha))
}

// ===== 颜色辅助函数 =====
const addAlpha = (hex: string, alpha: number) => {
  const a = alpha > 1 ? alpha / 100 : alpha
  const clamped = Math.min(1, Math.max(0, a))
  const alphaHex = Math.round(clamped * 255)
    .toString(16)
    .padStart(2, '0')
  return `${hex}${alphaHex}`
}

const blendColors = (color1: string, color2: string, ratio: number) => {
  const r1 = hexToRgb(color1)
  const r2 = hexToRgb(color2)
  if (!r1 || !r2) return color1
  const r = Math.round(r1.r * (1 - ratio) + r2.r * ratio)
  const g = Math.round(r1.g * (1 - ratio) + r2.g * ratio)
  const b = Math.round(r1.b * (1 - ratio) + r2.b * ratio)
  return rgbToHex(r, g, b)
}

const getLuminance = (hex: string) => {
  const rgb = hexToRgb(hex)
  if (!rgb) return 0
  const transform = (v: number) => {
    const srgb = v / 255
    return srgb <= 0.03928 ? srgb / 12.92 : Math.pow((srgb + 0.055) / 1.055, 2.4)
  }
  const r = transform(rgb.r)
  const g = transform(rgb.g)
  const b = transform(rgb.b)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

// ===== 新增/改进的颜色工具 =====
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

const hexToRgb = (hex: string) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null
}

const rgbToHex = (r: number, g: number, b: number) => {
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)
}

// 新增：hex -> rgba 字符串
const hexToRgba = (hex: string, alpha: number) => {
  const rgb = hexToRgb(hex)
  if (!rgb) return 'rgba(0,0,0,0)'
  const a = alpha > 1 ? alpha / 100 : alpha
  return `rgba(${rgb.r},${rgb.g},${rgb.b},${clamp01(a)})`
}

// HSL 转换（感知更平滑）
const rgbToHsl = (r: number, g: number, b: number) => {
  r /= 255
  g /= 255
  b /= 255
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b)
  let h = 0,
    s = 0
  const l = (max + min) / 2
  const d = max - min
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0)
        break
      case g:
        h = (b - r) / d + 2
        break
      case b:
        h = (r - g) / d + 4
        break
    }
    h /= 6
  }
  return { h: h * 360, s, l }
}

const hslToRgb = (h: number, s: number, l: number) => {
  h /= 360
  if (s === 0) {
    const val = Math.round(l * 255)
    return { r: val, g: val, b: val }
  }
  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  const r = hue2rgb(p, q, h + 1 / 3)
  const g = hue2rgb(p, q, h)
  const b = hue2rgb(p, q, h - 1 / 3)
  return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) }
}

const hslAdjust = (hex: string, dl: number) => {
  const rgb = hexToRgb(hex)
  if (!rgb) return hex
  const { h, s, l } = rgbToHsl(rgb.r, rgb.g, rgb.b)
  const nl = clamp01(l + dl)
  const nrgb = hslToRgb(h, s, nl)
  return rgbToHex(nrgb.r, nrgb.g, nrgb.b)
}

const hslLighten = (hex: string, percent: number) => hslAdjust(hex, percent / 100)
const hslDarken = (hex: string, percent: number) => hslAdjust(hex, -percent / 100)

// 对比度 (WCAG)
const contrastRatio = (hex1: string, hex2: string) => {
  const L1 = getLuminance(hex1)
  const L2 = getLuminance(hex2)
  const light = Math.max(L1, L2)
  const dark = Math.min(L1, L2)
  return (light + 0.05) / (dark + 0.05)
}

const rgbaExtractHex = (color: string) => {
  // 只支持 hex(#rrggbb) 直接返回；若 rgba 则忽略 alpha 并合成背景为黑假设
  if (color.startsWith('#') && color.length === 7) return color
  // 简化：返回黑或白占位
  return '#000000'
}

const pickAccessibleColor = (c1: string, c2: string, bg: string, minRatio = 4.5) => {
  const hexBg = rgbaExtractHex(bg)
  const hex1 = rgbaExtractHex(
    c1 === 'rgba(255,255,255,0.88)' ? '#ffffff' : c1.includes('255,255,255') ? '#ffffff' : '#000000'
  )
  const hex2 = rgbaExtractHex(
    c2 === 'rgba(255,255,255,0.88)' ? '#ffffff' : c2.includes('255,255,255') ? '#ffffff' : '#000000'
  )
  const r1 = contrastRatio(hex1, hexBg)
  const r2 = contrastRatio(hex2, hexBg)
  // 优先满足 >= minRatio；都满足取更高；否则取更高
  if (r1 >= minRatio && r2 >= minRatio) return r1 >= r2 ? c1 : c2
  if (r1 >= minRatio) return c1
  if (r2 >= minRatio) return c2
  return r1 >= r2 ? c1 : c2
}

// 改进侧栏背景：如果深色模式，降低亮度并略增饱和；浅色模式提高亮度轻度染色
const deriveSiderBg = (primary: string, base: string, dark: boolean) => {
  const mixRatio = dark ? 0.22 : 0.18
  const mixed = blendColors(base, primary, mixRatio)
  return dark ? hslDarken(mixed, 8) : hslLighten(mixed, 6)
}

const deriveSiderBorder = (siderBg: string, primary: string, dark: boolean) => {
  return dark ? blendColors(siderBg, primary, 0.3) : blendColors('#d9d9d9', primary, 0.25)
}

// 监听系统主题变化
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const handleSystemThemeChange = () => {
  if (themeMode.value === 'system' && !activeAppearance.value) updateTheme()
}
mediaQuery.addEventListener('change', handleSystemThemeChange)

// 监听主题模式和颜色变化
watch(themeMode, updateTheme, { immediate: true })
watch(themeColor, updateTheme)

// Ant Design 主题配置
function getThemeConfig() {
  const baseSurface = isDark.value ? RHINE_SURFACE_TOKENS.dark : RHINE_SURFACE_TOKENS.light
  const custom = activeAppearance.value?.tokens
  const radius = custom?.borderRadius ?? 2

  return {
    algorithm: isDark.value ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: custom?.colorPrimary ?? resolveThemeColor(themeColor.value, isDark.value),
      colorBgLayout: custom?.colorBgLayout ?? baseSurface.colorBgLayout,
      colorBgContainer: custom?.colorBgContainer ?? baseSurface.colorBgContainer,
      colorBgElevated: custom?.colorBgElevated ?? baseSurface.colorBgElevated,
      colorText: custom?.colorText ?? baseSurface.colorText,
      colorTextSecondary: custom?.colorTextSecondary ?? baseSurface.colorTextSecondary,
      colorTextTertiary: baseSurface.colorTextTertiary,
      colorBorder: custom?.colorBorder ?? baseSurface.colorBorder,
      colorBorderSecondary: custom?.colorBorderSecondary ?? baseSurface.colorBorderSecondary,
      colorSuccess: baseSurface.colorSuccess,
      colorWarning: baseSurface.colorWarning,
      colorError: baseSurface.colorError,
      colorInfo: baseSurface.colorInfo,
      borderRadius: radius,
      borderRadiusLG: radius,
      borderRadiusSM: Math.min(radius, 2),
      fontFamily: RHINE_FONT_FAMILY,
      fontFamilyCode: RHINE_FONT_MONO,
    },
    components: {
      InputNumber: {
        // 步进按钮（▲▼）常驻显示：antd 默认悬停才出现，快速连续调整不直观
        handleVisible: true as const,
      },
      Card: {
        borderRadiusLG: radius,
        headerBg: 'transparent',
      },
      Button: {
        borderRadius: radius,
        borderRadiusLG: radius,
        borderRadiusSM: Math.min(radius, 2),
        primaryShadow: 'none',
        defaultShadow: 'none',
        dangerShadow: 'none',
      },
      Modal: {
        borderRadiusLG: radius,
        headerBg: custom?.colorBgElevated ?? baseSurface.colorBgElevated,
        contentBg: custom?.colorBgElevated ?? baseSurface.colorBgElevated,
      },
      Table: {
        borderRadius: radius,
        headerBorderRadius: 0,
        headerBg: isDark.value ? '#141a1e' : '#e6e3dc',
      },
      Tabs: {
        cardBg: isDark.value ? '#13191d' : '#e8e5dd',
        borderRadiusLG: 0,
      },
      Tag: {
        borderRadiusSM: Math.min(radius, 2),
      },
      Segmented: {
        borderRadius: radius,
        borderRadiusSM: Math.min(radius, 2),
      },
      Select: {
        borderRadius: radius,
        borderRadiusLG: radius,
      },
      Input: {
        borderRadius: radius,
        borderRadiusLG: radius,
      },
      DatePicker: {
        borderRadius: radius,
      },
    },
  }
}

const antdTheme = computed(getThemeConfig)

export function useTheme() {
  const resetTheme = (): Promise<void> =>
    queueThemeChange(async () => {
      const revision = ++themeRevision
      const savedConfigRevision = configRevision
      const defaults: ThemeSnapshot = {
        themeMode: 'system',
        themeColor: 'gold',
        appearanceId: null,
      }
      themeHydrated = true
      themeMode.value = defaults.themeMode
      themeColor.value = defaults.themeColor
      appearanceId.value = null
      activeAppearance.value = null
      updateTheme()
      try {
        await saveConfig(defaults)
        if (configRevision === savedConfigRevision) setPersistedThemeSnapshot(defaults)
      } catch (error) {
        if (revision === themeRevision) restorePersistedThemeSnapshot()
        logger.error(`重置主题失败: ${error instanceof Error ? error.message : String(error)}`)
        throw error
      }
    })

  const setThemeMode = (mode: ThemeMode): Promise<void> =>
    queueThemeChange(async () => {
      const revision = ++themeRevision
      const savedConfigRevision = configRevision
      themeHydrated = true
      themeMode.value = mode
      activeAppearance.value = null
      appearanceId.value = null
      updateTheme()
      try {
        await saveConfig({ themeMode: mode, appearanceId: null })
        if (configRevision === savedConfigRevision) {
          setPersistedThemeSnapshot({
            ...persistedThemeSnapshot,
            themeMode: mode,
            appearanceId: null,
          })
        }
      } catch (error) {
        if (revision === themeRevision) restorePersistedThemeSnapshot()
        logger.error(`保存主题模式失败: ${error instanceof Error ? error.message : String(error)}`)
        throw error
      }
    })

  const setThemeColor = (color: ThemeColor): Promise<void> =>
    queueThemeChange(async () => {
      const revision = ++themeRevision
      const savedConfigRevision = configRevision
      themeColor.value = color
      updateTheme()
      try {
        await saveConfig({ themeColor: color })
        if (configRevision === savedConfigRevision) {
          setPersistedThemeSnapshot({ ...persistedThemeSnapshot, themeColor: color })
        }
      } catch (error) {
        if (revision === themeRevision) restorePersistedThemeSnapshot()
        logger.error(`保存主题色失败: ${error instanceof Error ? error.message : String(error)}`)
        throw error
      }
    })

  const loadAppearances = async (): Promise<void> => {
    const loadRevision = ++appearanceLoadRevision
    let list: InstalledAppearance[] = []
    let listFailed = false
    try {
      list = (await window.hostAPI.listAppearances?.()) ?? []
    } catch (error) {
      listFailed = true
      logger.warn(
        `读取外观包失败，回落默认外观: ${error instanceof Error ? error.message : String(error)}`
      )
    }
    if (loadRevision !== appearanceLoadRevision) return
    appearances.value = list
    if (listFailed) {
      activeAppearance.value = null
      updateTheme()
      return
    }
    if (appearanceId.value) {
      const loaded = appearances.value.find(item => item.id === appearanceId.value)
      if (!loaded) {
        const expectedId = appearanceId.value
        const savedThemeRevision = themeRevision
        activeAppearance.value = null
        updateTheme()
        const savedConfigRevision = configRevision
        try {
          const result = await window.hostAPI.clearInvalidAppearance?.(expectedId)
          if (result?.success && result.appearanceId !== undefined) {
            const currentAppearance = result.appearanceId
              ? (appearances.value.find(item => item.id === result.appearanceId) ??
                (await window.hostAPI.getAppearance?.(result.appearanceId)))
              : null
            if (
              loadRevision !== appearanceLoadRevision ||
              themeRevision !== savedThemeRevision ||
              appearanceId.value !== expectedId
            ) {
              return
            }
            appearanceId.value = result.appearanceId
            activeAppearance.value = currentAppearance ?? null
            if (configRevision === savedConfigRevision) {
              setPersistedThemeSnapshot({
                ...persistedThemeSnapshot,
                appearanceId: result.appearanceId,
              })
            }
          }
        } catch (error) {
          logger.warn(
            `清理失效外观配置失败: ${error instanceof Error ? error.message : String(error)}`
          )
        }
      } else {
        activeAppearance.value = loaded
      }
    } else {
      // 跨窗口切回内置模式时必须清掉此前缓存的外观，否则 isDark 和 CSS 仍沿用旧包。
      activeAppearance.value = null
    }
    updateTheme()
  }

  const setAppearance = (id: string | null): Promise<void> =>
    queueThemeChange(async () => {
      const revision = ++themeRevision
      const savedConfigRevision = configRevision
      themeHydrated = true
      if (!id) {
        activeAppearance.value = null
        appearanceId.value = null
        updateTheme()
        try {
          await saveConfig({ appearanceId: null })
          if (configRevision === savedConfigRevision) {
            setPersistedThemeSnapshot({ ...persistedThemeSnapshot, appearanceId: null })
          }
        } catch (error) {
          if (revision === themeRevision) restorePersistedThemeSnapshot()
          logger.error(
            `保存默认外观失败: ${error instanceof Error ? error.message : String(error)}`
          )
          throw error
        }
        return
      }
      const appearance =
        appearances.value.find(item => item.id === id) ?? (await window.hostAPI.getAppearance?.(id))
      if (!appearance) throw new Error('外观不存在或已损坏')
      if (revision !== themeRevision) return
      activeAppearance.value = appearance
      appearanceId.value = appearance.id
      updateTheme()
      try {
        await saveConfig({ appearanceId: appearance.id })
        if (configRevision === savedConfigRevision) {
          setPersistedThemeSnapshot({ ...persistedThemeSnapshot, appearanceId: appearance.id })
        }
      } catch (error) {
        if (revision === themeRevision) restorePersistedThemeSnapshot()
        logger.error(
          `保存自定义外观失败: ${error instanceof Error ? error.message : String(error)}`
        )
        throw error
      }
    })

  const upsertAppearance = (appearance: InstalledAppearance): void => {
    const existingIndex = appearances.value.findIndex(item => item.id === appearance.id)
    if (existingIndex === -1) appearances.value.push(appearance)
    else appearances.value[existingIndex] = appearance
  }

  const importAppearance = async (
    zipPath: string,
    replace = false
  ): Promise<import('@/types/appearance').AppearanceImportResult> => {
    const result = await window.hostAPI.importAppearance?.(zipPath, replace)
    if (!result) {
      return {
        success: false,
        code: 'UNSUPPORTED',
        error: '当前环境不支持导入外观包',
      }
    }
    if (result.success && result.appearance) upsertAppearance(result.appearance)
    return result
  }

  // 只交主进程里已校验的临时包句柄，路径和下载地址都不经过渲染进程。
  const installOnlineAppearance = async (
    token: string,
    replace = false
  ): Promise<OnlineAppearanceInstallResult> => {
    const result = await window.hostAPI.installOnlineAppearance?.(token, replace)
    if (!result) {
      return {
        success: false,
        code: 'UNSUPPORTED',
        error: '当前环境不支持在线外观',
      }
    }
    if (result.success && result.appearance) upsertAppearance(result.appearance)
    return result
  }

  const removeAppearance = async (id: string): Promise<{ success: boolean; error?: string }> => {
    const result = await window.hostAPI.removeAppearance?.(id)
    if (!result) return { success: false, error: '当前环境不支持移除外观包' }
    if (result.success) {
      appearances.value = appearances.value.filter(item => item.id !== id)
      // 主进程删除时同步清理当前选择；这里只刷新，不排入会覆盖新选择的 null 写入。
      await loadAppearances()
    }
    return result
  }

  const initAppearanceChangedListener = () => {
    if (appearanceListenerInitialized) return
    appearanceListenerInitialized = true
    const dispose = window.hostAPI.onAppearanceChanged?.(() => {
      void loadAppearances()
    })
    return dispose
  }

  const initThemeConfigListener = () => {
    if (themeConfigListenerInitialized) return
    themeConfigListenerInitialized = true
    window.hostAPI.onThemeConfigChanged?.(rawConfig => {
      if (rawConfig === null || typeof rawConfig !== 'object') return
      themeHydrated = true
      themeRevision += 1
      configRevision += 1
      const config = rawConfig as Partial<FrontendConfig>
      if (
        config.themeMode === 'system' ||
        config.themeMode === 'light' ||
        config.themeMode === 'dark'
      ) {
        themeMode.value = config.themeMode
      }
      if (
        config.themeColor &&
        Object.prototype.hasOwnProperty.call(themeColors, config.themeColor)
      ) {
        themeColor.value = config.themeColor
      }
      appearanceId.value = typeof config.appearanceId === 'string' ? config.appearanceId : null
      commitPersistedThemeSnapshot()
      // 回声只换选择：缓存里有就直接用，全量重读留给 appearance-changed，
      // 否则每切一次主题色，每个窗口都要把所有包的素材经 IPC 重传一遍。
      const cached = appearanceId.value
        ? appearances.value.find(item => item.id === appearanceId.value)
        : null
      if (cached === undefined) {
        activeAppearance.value = null
        void loadAppearances()
        return
      }
      activeAppearance.value = cached
      updateTheme()
    })
  }

  // 旧浏览器偏好由 getConfig 迁移；主题只从持久化配置恢复。
  const initTheme = async (preloadedConfig?: Partial<FrontendConfig>) => {
    initAppearanceChangedListener()
    initThemeConfigListener()
    const config = preloadedConfig ?? (await getConfig())
    themeHydrated = true
    if (
      config.themeMode === 'system' ||
      config.themeMode === 'light' ||
      config.themeMode === 'dark'
    ) {
      themeMode.value = config.themeMode
    }
    if (config.themeColor && Object.prototype.hasOwnProperty.call(themeColors, config.themeColor)) {
      themeColor.value = config.themeColor
    }
    appearanceId.value = typeof config.appearanceId === 'string' ? config.appearanceId : null
    commitPersistedThemeSnapshot()
    if (!appearanceId.value) {
      activeAppearance.value = null
      updateTheme()
    }
    await loadAppearances()
  }

  return {
    themeMode: computed(() => themeMode.value),
    themeColor: computed(() => themeColor.value),
    isDark: computed(() => isDark.value),
    antdTheme,
    antTokens: computed(() => resolvedAntTokens.value),
    themeColors,
    appearances: computed(() => appearances.value),
    appearanceId: computed(() => appearanceId.value),
    activeAppearance: computed(() => activeAppearance.value),
    syncAntTokens: (tokens: AntTokens) => {
      resolvedAntTokens.value = tokens
      updateCSSVariables()
    },
    setThemeMode,
    setThemeColor,
    resetTheme,
    setAppearance,
    loadAppearances,
    importAppearance,
    installOnlineAppearance,
    removeAppearance,
    initAppearanceChangedListener,
    initTheme,
  }
}
