// 个人知识库 · 主题管理
// 三套全局主题：starlight（深空星际）/ sky（蓝天大气）/ minimal（纯色简约）
// 切换时同时维护 <html data-theme> 与 html.dark，保证 Docs 等页面全局配色一致
// themeState 为全局响应式状态：任何组件 applyTheme 后全站（背景、下拉框）联动

import { reactive } from 'vue'

const THEME_KEY = 'kb-theme'
const LEGACY_KEY = 'vp-theme'

export const THEMES = [
  { id: 'starlight', label: '深空星际', short: '星空', icon: '🌌', dark: true, desc: '星云漫游 · 沉浸深空' },
  { id: 'sky', label: '蓝天大气', short: '蓝天', icon: '☀️', dark: false, desc: '晴空万里 · 明亮通透' },
  { id: 'minimal', label: '纯色简约', short: '简约', icon: '▫️', dark: false, desc: '素净专注 · 极简高效' },
]

export function getTheme() {
  const saved = localStorage.getItem(THEME_KEY)
  if (saved && THEMES.some((t) => t.id === saved)) return saved
  // 兼容旧版 vp-theme 开关
  const legacy = localStorage.getItem(LEGACY_KEY)
  return legacy === 'dark' ? 'starlight' : 'starlight'
}

// 全局响应式主题状态（组件内直接引用 themeState.id 实现联动）
export const themeState = reactive({ id: getTheme() })

export function applyTheme(id) {
  const theme = THEMES.find((t) => t.id === id) || THEMES[0]
  document.documentElement.setAttribute('data-theme', theme.id)
  document.documentElement.classList.toggle('dark', theme.dark)
  localStorage.setItem(THEME_KEY, theme.id)
  localStorage.setItem(LEGACY_KEY, theme.dark ? 'dark' : 'light')
  themeState.id = theme.id
  return theme
}

export function initTheme() {
  return applyTheme(getTheme())
}