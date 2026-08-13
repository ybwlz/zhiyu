<script setup>
import { onMounted, onUnmounted, computed, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import anchor from 'markdown-it-anchor'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { full as emoji } from 'markdown-it-emoji'
import container from 'markdown-it-container'
// import mathjax3 from 'markdown-it-mathjax3'
import mdImgSize from '@/utils/mdImgSize.js'
import { mathInlinePlugin } from '@/utils/mathjax-render.js'
import alerts from 'markdown-it-github-alerts'
import toc from 'markdown-it-toc-done-right'
import { useFileListStore } from '@/stores/fileList.js'
import { storeToRefs } from 'pinia'
import { ArrowDown, Menu as IconMenu, Operation, MoreFilled } from '@element-plus/icons-vue'
import ThemeDropdown from '@/components/ThemeDropdown.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import DoodleBall from '@/components/DoodleBall.vue'
import { setupAnnotation, bindAnnotations, bindAnnGlobal } from '@/utils/annotation.js'

// ── 沉浸式阅读：隐藏导航/侧栏，只留正文 ──
const immersive = ref(false)
const toggleImmersive = () => {
  immersive.value = !immersive.value
  document.body.classList.toggle('immersive', immersive.value)
}
onUnmounted(() => { document.body.classList.remove('immersive') })

// ── 正文图片点击放大 ──
const viewerOpen = ref(false)
const viewerUrl = ref('')
const onContentClick = (e) => {
  const t = e.target
  // 批注由全局委托处理（capture 阶段已拦截），这里只处理图片放大
  if (t && t.tagName === 'IMG') {
    viewerUrl.value = t.currentSrc || t.src
    viewerOpen.value = true
  }
}
// 删除批注（作者）：从 content 移除对应容器并保存
const onDelAnn = async (block, index) => {
  if (!auth.isLogin || currentDoc.value?.user_id !== auth.user?.id) { ElMessage.warning('只能删除自己笔记的批注'); return }
  const id = block.getAttribute('data-ann-id') || ''
  try {
    let newContent = currentDoc.value.content || ''
    if (id) {
      // 新格式：删记录 + 移除正文锚点
      newContent = newContent.replace(new RegExp(':::annotation\\s+' + id + '\\s*:::'), '').replace(/\n{3,}/g, '\n\n')
      delete annMap.value[id]
      try { await api.delete('/annotations/' + id) } catch (e) { /* 忽略 */ }
    } else {
      const re = /:::annotation\n[\s\S]*?\n:::/g
      let i = 0
      newContent = newContent.replace(re, (m) => {
        i += 1
        return i === index + 1 ? '' : m
      })
    }
    if (newContent === (currentDoc.value.content || '')) { block.remove(); return }
    await api.put('/docs/' + currentDoc.value.id, { content: newContent, type: currentDoc.value.type, title: currentDoc.value.title })
    currentDoc.value.content = newContent
    ElMessage.success('批注已删除')
  } catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

// 批注记录加载（新格式批注：文字/笔迹存 note_annotations，按 id 拉取渲染）
const annMap = ref({})
const loadAnnData = async () => {
  const doc = currentDoc.value
  if (!doc || !auth.isLogin) return
  try {
    const res = await api.get('/notes/' + doc.id + '/annotations')
    const m = {}
    for (const r of res.data || []) {
      if (r.kind === 'note') m[r.id] = { note_text: r.note_text || '', strokes: Array.isArray(r.strokes) ? r.strokes : [], canvas_w: r.canvas_w || 0, canvas_h: r.canvas_h || 0 }
    }
    annMap.value = m
    const root = document.querySelector('.doc-card .markdown-body')
    if (root) bindAnnotations(root, annMap.value, { editable: false })
  } catch (e) { /* 忽略 */ }
}

const route = useRoute()
const router = useRouter()
const store = useFileListStore()
const { fileListData, typesData, currentDoc } = storeToRefs(store)

// --- 响应式逻辑 ---
const windowWidth = ref(window.innerWidth)

const updateWidth = () => {
  windowWidth.value = window.innerWidth
}

// 逻辑:
// < 960: 移动端 (抽屉 + 弹出框，无侧边栏)
// >= 960: 桌面端布局 (左侧边栏可见)
// 960~1399: 显示右侧边栏但默认收起为窄条（平板端初始先缩小）；>= 1400 默认展开（与 PC 一致）
// < 1280: 使用 "..." 菜单切换主题
const showLeftSidebar = computed(() => windowWidth.value >= 960)
const showRightSidebar = computed(() => windowWidth.value >= 960)
const isMobile = computed(() => windowWidth.value < 960)

// --- 抽屉与弹出框状态 ---
const showMenuDrawer = ref(false)



// --- 数据获取 ---
// ═══════════ 阅览室（工作台）改造 ═══════════
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'
const auth = useAuthStore()
const roomIds = ref(new Set())
const roomLoading = ref(false)
const sidebarCollapsed = ref(localStorage.getItem('kb_sidebar_collapsed') === '1')    // 手动收起左侧栏（Reasonix 式，带记忆）
// 右侧大纲栏：默认恒展开；不记忆收起状态（避免刷新后残留 48px 窄条"留缝"）
const rightSidebarCollapsed = ref(false)
const isMyDoc = (doc) => auth.isLogin && doc.user_id === auth.user?.id

const loadRoom = async () => {
  if (!auth.isLogin) { roomIds.value = new Set(); return }
  roomLoading.value = true
  try {
    const res = await api.get('/reading-list', { params: { t: Date.now() } })
    roomIds.value = new Set((res.data || []).map(d => d.id))
  } catch (e) { /* 忽略 */ }
  roomLoading.value = false
}
watch(() => auth.isLogin, (v) => { if (v) loadRoom() }, { immediate: true })

// 侧栏数据：阅览室 = 只显示已加入阅览室的笔记（未登录无阅览室）
const sidebarDocs = computed(() => {
  const all = Array.isArray(fileListData.value) ? fileListData.value : []
  if (!auth.isLogin) return []
  return all.filter(d => roomIds.value.has(d.id))
})

// 右键菜单
const ctxMenu = ref({ show: false, x: 0, y: 0, doc: null })
const openCtxMenu = (e, doc) => {
  ctxMenu.value = { show: true, x: e.clientX, y: e.clientY, doc }
}
const closeCtxMenu = () => { ctxMenu.value.show = false }
// 右键其他位置（非菜单/非笔记条目）时收起已打开的菜单
const closeCtxMenuGlobal = (e) => {
  if (e.target.closest('.ctx-menu') || e.target.closest('.doc-link')) return
  ctxMenu.value.show = false
}
const moveOutRoom = async (doc) => {
  try { await api.delete('/reading-list/' + doc.id) } catch (e) { /* 忽略 */ }
  const s = new Set(roomIds.value); s.delete(doc.id); roomIds.value = s
  closeCtxMenu()
}
const addToRoom = async (doc) => {
  // 加入阅览室：临时引用（不复制），可放广场笔记或书房笔记
  try {
    await api.post('/reading-list', { doc_id: doc.id, source: 'square' })
    const s = new Set(roomIds.value); s.add(doc.id); roomIds.value = s
  } catch (e) { /* 忽略 */ }
  closeCtxMenu()
}
// 收纳至书房（复制为自己的笔记）
const collectToStudy = async (doc) => {
  // 加入书房：复制一份归我所有（幂等，原版不动，副本可编辑，自动进阅览室）
  try {
    const res = await api.post('/docs/' + doc.id + '/collect')
    if (res.data && res.data.id) {
      const s = new Set(roomIds.value); s.add(res.data.id); roomIds.value = s
    }
    if (typeof store.fetchDocs === 'function') store.fetchDocs()
  } catch (e) { /* 忽略 */ }
  closeCtxMenu()
}
const ctxActions = computed(() => {
  const doc = ctxMenu.value.doc
  if (!doc) return []
  const acts = []
  // 阅览室只放书房里选进来的笔记：这里只有移出 + 打开
  if (roomIds.value.has(doc.id)) {
    acts.push({ label: '📤 移出阅览室', fn: moveOutRoom })
  }
  acts.push({ label: '🔗 打开笔记', fn: () => { selectDoc(doc); closeCtxMenu() } })
  return acts
})

// 添加笔记弹窗：只列出自己的书房笔记（不掺入广场/别人的笔记）
const addOpen = ref(false)
const addQuery = ref('')
const addList = computed(() => {
  const all = Array.isArray(fileListData.value) ? fileListData.value : []
  const mine = auth.isLogin && auth.user ? all.filter(d => d.user_id === auth.user.id) : []
  const q = addQuery.value.trim()
  return mine.filter(d => !q || (d.title || '').includes(q))
})

// 编辑当前文档
const editCurrent = () => { if (currentDoc.value) router.push('/edit/' + currentDoc.value.id) }

// AI 工具改完笔记后刷新当前阅览室内容
const onAiChanged = () => {
  if (currentDoc.value) store.fetchDocByKey(route.params.key)
}

// 全局 AI 助手「去编辑页查看修改」→ 用当前文档 id 跳编辑页（编辑页会自动加载 AI 草稿并弹红绿 diff）
const onAiGotoCurrentEdit = () => {
  if (currentDoc.value) router.push('/edit/' + currentDoc.value.id + '?from=docs')
}

// 全局 AI 助手「局部替换」→ 在原文中定位被替换的块，替换为新块后预填编辑页
const onAiLocalEdit = (e) => {
  const original = (e.detail?.original || '').trim()
  const replacement = (e.detail?.replacement || '').trim()
  const doc = currentDoc.value
  if (!original || !replacement || !doc) return
  const content = doc.content || ''
  const idx = content.indexOf(original)
  if (idx === -1) {
    ElMessage.error('没能在笔记原文里找到 AI 要替换的位置（内容可能对不上），已取消。请换种说法再试')
    return
  }
  const newContent = content.slice(0, idx) + replacement + content.slice(idx + original.length)
  try {
    localStorage.setItem('zhiyu_draft_' + doc.id, JSON.stringify({
      title: doc.title, type: doc.type || '笔记', visibility: doc.visibility,
      content: newContent, ts: Date.now(), ai: true,
    }))
  } catch (err) {}
  router.push('/edit/' + doc.id + '?from=docs')
}

// 全局 AI 助手「说改就改」→ 把 AI 修改内容写入编辑页草稿并跳转编辑页（编辑页左侧源码+右侧预览，可微调再保存）
const onAiGotoEdit = (e) => {
  const text = (e.detail?.text || '').trim()
  const doc = currentDoc.value
  if (!text || !doc) return
  try {
    localStorage.setItem('zhiyu_draft_' + doc.id, JSON.stringify({
      title: doc.title, type: doc.type || '笔记', visibility: doc.visibility,
      content: text, ts: Date.now(), ai: true,
    }))
  } catch (err) {}
  router.push('/edit/' + doc.id + '?from=docs')
}

// 全局 AI 助手「应用修改」→ 载入 AI 修改预览（在阅览室预览区先看效果，确认后再保存）
const aiPreview = ref(null) // { text }
const onAiPreviewDoc = (e) => {
  const text = (e.detail?.text || '').trim()
  if (!text) return
  aiPreview.value = { text }
  window.scrollTo({ top: 0, behavior: 'smooth' })
  ElMessage.info('已载入 AI 修改预览，确认无误后点「应用修改」')
}
const applyAiPreview = async () => {
  if (!aiPreview.value) return
  const doc = currentDoc.value
  if (!doc) return
  const text = aiPreview.value.text
  // 安全校验：AI 内容不足原文三成 → 大概率是片段不是完整笔记，拒绝替换避免毁掉笔记
  const docLen = (doc.content || '').length
  if (docLen > 0 && text.length < docLen * 0.3) {
    ElMessage.error('AI 输出的内容像是片段而不是完整笔记，已取消应用。请让 AI 重新生成完整笔记后再试')
    return
  }
  // 统一走 diff 预览：写入草稿并跳编辑页，编辑页自动弹红绿 diff，用户确认后才保存（不再直接写库）
  try {
    localStorage.setItem('zhiyu_draft_' + doc.id, JSON.stringify({
      title: doc.title, type: doc.type || '笔记', visibility: doc.visibility,
      content: text, ts: Date.now(), ai: true,
    }))
  } catch (err) {}
  aiPreview.value = null
  router.push('/edit/' + doc.id + '?from=docs')
}
const cancelAiPreview = () => { aiPreview.value = null }

// 全局 AI 助手「打开笔记」→ 阅览室就地打开（不跳笔记广场）；不在本阅览室列表才降级跳广场
const onAiOpenNote = (e) => {
  const id = e.detail?.id
  const pubId = e.detail?.public_id
  if (!id && !pubId) return
  if (currentDoc.value && currentDoc.value.id === id) {
    ElMessage.info('已在这篇笔记中')
    return
  }
  const doc = flatDocs.value.find(d => d.id === id) || (pubId ? flatDocs.value.find(d => d.public_id === pubId) : null)
  if (doc) {
    selectDoc(doc)
    ElMessage.success('已在阅览室打开《' + (doc.title || '') + '》')
  } else {
    router.push('/notes/' + (pubId || id))
  }
}

// 全局 AI 助手「插入笔记」→ 追加到当前阅览室笔记（阅览室只有自己的笔记：书房原笔记或 collect 副本，直接更新）
const onAiInsert = async (e) => {
  const text = (e.detail?.text || '').trim()
  const doc = currentDoc.value
  if (!text || !doc) return
  try {
    // 统一走 diff 预览：写入本地草稿并跳编辑页，编辑页自动弹红绿 diff，用户确认后才保存（不再直接写库）
    localStorage.setItem('zhiyu_draft_' + doc.id, JSON.stringify({
      title: doc.title, type: doc.type || '笔记', visibility: doc.visibility,
      content: (doc.content || '') + '\n\n' + text, ts: Date.now(), ai: true,
    }))
  } catch (err) {}
  router.push('/edit/' + doc.id + '?from=docs')
}

// 侧栏收起
const toggleSidebar = () => { sidebarCollapsed.value = !sidebarCollapsed.value; localStorage.setItem('kb_sidebar_collapsed', sidebarCollapsed.value ? '1' : '0') }
const toggleRightSidebar = () => { rightSidebarCollapsed.value = !rightSidebarCollapsed.value; localStorage.setItem('kb_right_collapsed', rightSidebarCollapsed.value ? '1' : '0') }

// 右键菜单随全局点击关闭（原有 handleGlobalClick 已有类似逻辑）
onMounted(() => {
  // 列表模式（无 key）清掉阅读页残留的 currentDoc，避免广场/阅读页的笔记串进阅览室
  if (!route.params.key) currentDoc.value = null
  window.addEventListener('resize', updateWidth)
  window.addEventListener('scroll', onScroll) // 监听窗口滚动
  window.addEventListener('click', handleGlobalClick) // 全局点击：关闭右键菜单/复制/锚点
  window.addEventListener('contextmenu', closeCtxMenuGlobal) // 右键其他位置也收起菜单
  window.addEventListener('zhiyu:ai-insert', onAiInsert)
  window.addEventListener('zhiyu:ai-open-note', onAiOpenNote)
  window.addEventListener('zhiyu:ai-preview-doc', onAiPreviewDoc)
  window.addEventListener('zhiyu:ai-goto-edit', onAiGotoEdit)
  window.addEventListener('zhiyu:ai-local-edit', onAiLocalEdit)
  window.addEventListener('zhiyu:ai-changed', onAiChanged)
  window.addEventListener('zhiyu:ai-goto-current-edit', onAiGotoCurrentEdit)
  bindAnnGlobal({ onDel: onDelAnn })

  
  const docsP = store.fetchDocs()
  loadRoom()
  const key = route.params.key
  if (auth.isLogin && key) {
    store.fetchDocByKey(key)
  } else if (!auth.isLogin) {
    // 未登录：阅览室不加载任何文档（左侧与正文均提示登录）
  }
  // 无 key（顶部导航进 /docs）：纯列表模式，不自动打开任何笔记（右侧显示占位提示）
})

onUnmounted(() => {
  window.removeEventListener('resize', updateWidth)
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('click', handleGlobalClick)
  window.removeEventListener('zhiyu:ai-insert', onAiInsert)
  window.removeEventListener('zhiyu:ai-open-note', onAiOpenNote)
  window.removeEventListener('zhiyu:ai-preview-doc', onAiPreviewDoc)
  window.removeEventListener('zhiyu:ai-goto-edit', onAiGotoEdit)
  window.removeEventListener('zhiyu:ai-local-edit', onAiLocalEdit)
  window.removeEventListener('zhiyu:ai-changed', onAiChanged)
  window.removeEventListener('zhiyu:ai-goto-current-edit', onAiGotoCurrentEdit)
  window.removeEventListener('contextmenu', closeCtxMenuGlobal)
})

// 切换笔记：先显示加载态（不显示旧内容），新内容就绪后再滚到顶部，避免“先跳顶+旧文字”的闪烁
const docLoading = ref(false)
watch(() => route.params.key, async (key) => {
  if (!key) return
  showMenuDrawer.value = false // 导航时关闭抽屉
  docLoading.value = true
  try {
    await store.fetchDocByKey(key)
  } catch (e) { /* 忽略 */ }
  docLoading.value = false
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'instant' })
})

// --- 分组逻辑 (侧边栏)：只按实际笔记的科目分组，没有笔记的分组不显示 ---
const grouped = computed(() => {
  const map = new Map()
  for (const d of sidebarDocs.value) {
    if (searchText.value && !(d.title || '').includes(searchText.value)) continue
    const k = d.type || '未分类'
    if (!map.has(k)) map.set(k, [])
    map.get(k).push(d)
  }
  const entries = Array.from(map.entries()).map(([k, v]) => ({ type: k, items: v }))
  const filtered = filterType.value ? entries.filter((e) => e.type === filterType.value) : entries
  return filtered.filter(e => e.items.length > 0)
})

const escHtml = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const highlightTitle = (title) => {
  const t = escHtml(title || '')
  const kw = (searchText.value || '').trim()
  if (!kw) return t
  try {
    return t.split(kw).join(`<mark class="kw-hl">${escHtml(kw)}</mark>`)
  } catch (e) { return t }
}
const actionButtons = computed(() => {
  const fromApi = Array.isArray(typesData.value) ? typesData.value.map(x => x.value).filter(Boolean) : []
  
  if (fromApi.length > 0) {
    return fromApi.map((t, i) => ({
      theme: i === 0 ? 'brand' : 'alt',
      text: t,
      type: t
    }))
  }

  return [
    { theme: 'brand', text: '数学公式', type: '数学公式' },
    { theme: 'alt', text: '系统更新日志', type: '系统更新日志' }
  ]
})

// 独立展开状态 (Set)
const openTypes = ref(new Set())
const activeType = ref('')

// 首页/科目卡片跳转带入的 type 过滤（/docs?type=xxx）
const filterType = ref(route.query.type || '')
// 首页搜索框带入的关键词过滤（/docs?search=xxx，按标题匹配）
const searchText = ref(route.query.search || '')
watch(() => route.query.search, (s) => { searchText.value = s || '' }, { immediate: true })
// 搜索时（或类型加载完成时）自动展开所有分组
const expandAll = () => {
  if (!searchText.value) return
  openTypes.value = new Set(grouped.value.map(g => g.type))
}
watch(typesData, expandAll, { immediate: true })
watch(searchText, (s) => { if (s) setTimeout(expandAll, 100) })

// ── 正文关键词高亮（DOM 安全实现） ──
const highlightBody = () => {
  const body = document.querySelector('.markdown-body')
  if (!body) return
  body.querySelectorAll('mark.kw-hl').forEach((m) => {
    const p = m.parentNode
    p.replaceChild(document.createTextNode(m.textContent), m)
    p.normalize()
  })
  const kw = (searchText.value || '').trim()
  if (!kw) return
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT)
  const nodes = []
  while (walker.nextNode()) nodes.push(walker.currentNode)
  for (const node of nodes) {
    if (!node.nodeValue || !node.nodeValue.includes(kw)) continue
    if (node.parentElement && node.parentElement.closest('mark, a, code, pre, mjx-container, .header-anchor')) continue
    const frag = document.createDocumentFragment()
    const parts = node.nodeValue.split(kw)
    parts.forEach((p, i) => {
      if (p) frag.appendChild(document.createTextNode(p))
      if (i < parts.length - 1) {
        const m = document.createElement('mark')
        m.className = 'kw-hl'
        m.textContent = kw
        frag.appendChild(m)
      }
    })
    node.parentNode.replaceChild(frag, node)
  }
}

watch(() => route.query.type, (t) => {
  filterType.value = t || ''
  if (t) openTypes.value = new Set([t])
}, { immediate: true }) 

// 自动展开所有有笔记的分组（没有笔记的分组不出现，也不展开）
watch(grouped, (gs) => {
  if (gs.length > 0 && openTypes.value.size === 0) {
    openTypes.value = new Set(gs.map(g => g.type))
  }
}, { immediate: true })

const allTypes = computed(() => grouped.value.map(g => g.type))
const expandAllGroups = () => { openTypes.value = new Set(allTypes.value) }
const collapseAllGroups = () => { openTypes.value = new Set() }
const toggleGroup = (t) => {
  if (openTypes.value.has(t)) {
    openTypes.value.delete(t)
  } else {
    openTypes.value.add(t)
  }
}

const selectDoc = (doc) => {
  router.push(`/docs/${doc.public_id}`)
}

const goHome = () => router.push('/')

// --- Markdown & 大纲逻辑 ---
const slugify = (s) => {
  // 去除 HTML 标签以获取纯净 ID
  const text = String(s || '').replace(/<[^>]+>/g, '')
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'section'
}

const md = new MarkdownIt({ 
  html: false, 
  linkify: true, 
  typographer: true, 
  breaks: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
      } catch (__) {}
    }
    // 无语言（或语言未知）：自动检测高亮，与笔记阅读页一致，避免星空背景下白字不清
    try {
      return hljs.highlightAuto(str).value;
    } catch (__) {
      return '';
    }
  }
})

// 1. 锚点插件
md.use(anchor, {
  slugify,
  permalink: anchor.permalink.linkInsideHeader({
    symbol: '#',
    placement: 'before',
    class: 'header-anchor',
    ariaHidden: true
  })
})

// --- 扩展 ---
md.use(emoji)
md.use(mathInlinePlugin)
md.use(mdImgSize)
md.use(alerts)
setupAnnotation(md)
// 目录: [[toc]]
md.use(toc, {
  listType: 'ul',
  slugify,
  level: [2, 3],
  format: function(x, htmlencode) {
    // 1. 移除 Markdown 链接: [text](url) -> text
    let text = x.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    // 2. 移除 HTML 标签（如果有）（基本安全性，虽然 htmlencode 会处理，但我们希望去除以获得纯文本）
    // 等等，htmlencode 已经传入。
    // 我们先去除链接语法。
    return `<span>${htmlencode(text)}</span>`;
  }
})

const createContainer = (klass, defaultTitle) => {
  return [container, klass, {
    render: function (tokens, idx) {
      const token = tokens[idx]
      const info = token.info.trim().slice(klass.length).trim()
      if (token.nesting === 1) {
        let title = info || defaultTitle
        // 如果未提供自定义标题，则本地化默认标题
        if (!info) {
          if (klass === 'tip') title = '提示'
          else if (klass === 'info') title = '信息'
          else if (klass === 'warning') title = '警告'
          else if (klass === 'danger') title = '危险'
          else if (klass === 'details') title = '详细信息'
        }
        
        if (klass === 'details') {
          return `<details class="custom-block details"><summary>${title}</summary>\n`
        }
        return `<div class="${klass} custom-block"><p class="custom-block-title">${title}</p>\n`
      } else {
        if (klass === 'details') {
          return `</details>\n`
        }
        return `</div>\n`
      }
    }
  }]
}

md.use(...createContainer('tip', 'TIP'))
md.use(...createContainer('info', 'INFO'))
md.use(...createContainer('warning', 'WARNING'))
md.use(...createContainer('danger', 'DANGER'))
md.use(...createContainer('details', 'Details'))

// 代码组 (视觉 + 交互)
md.use(container, 'code-group', {
  render: function (tokens, idx) {
    if (tokens[idx].nesting === 1) {
      // 查找后续的 fence tokens 以构建标签页
      let tabs = '';
      let i = idx + 1;
      let first = true;
      
      while (i < tokens.length && tokens[i].type !== 'container_code-group_close') {
        if (tokens[i].type === 'fence') {
          const info = tokens[i].info ? md.utils.unescapeAll(tokens[i].info).trim() : '';
          // 从 [title] 或文件名中提取标题
          let title = '';
          const match = info.match(/\[(.*?)\]/);
          if (match) {
            title = match[1];
          } else {
             // 回退到语言
             title = info.split(/\s+/)[0] || 'Code';
          }
          
          tabs += `<div class="code-group-tab ${first ? 'active' : ''}">${title}</div>`;
          
          // 标记 token 以便在 fence 渲染器中添加 active 类（如果需要），
          // 但 fence 渲染器是分开的。我们将把 fence 输出包装在一个 wrapper 中。
          // 实际上，我们只需要依赖结构：
          // .code-group > .tabs + .blocks > .block
        }
        i++;
      }
      
      return `<div class="code-group">
                <div class="code-group-tabs">${tabs}</div>
                <div class="code-group-blocks">\n`;
    } else {
      return `  </div>
              </div>\n`;
    }
  }
})

// 增强的代码组 Fence 渲染器
const defaultFence = md.renderer.rules.fence;
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  // 检查是否在代码组内
  let inGroup = false;
  let isFirstInGroup = false;
  
  // 向后检查虽然开销大但目前是安全的，或者我们可以使用 env 状态
  // 简单启发式：检查父 token 是否为 code-group 容器
  // Markdown-it 不容易获取父引用。
  // 我们可以假设前一个 token 是 container_code-group_open 或其中的另一个 fence。
  
  // 让我们实现一个更简单的方法：
  // 我们只渲染 fence。上面的 'code-group' 容器逻辑处理包装 div .code-group-blocks。
  // 但我们需要将每个 fence 包装在一个可切换的 div 中。
  // 并且我们需要知道它是否应默认处于活动状态（第一个）。
  
  // 实际上，我们可以 hack 容器渲染器不在这里渲染标签页，但这很难，因为我们需要向前看。
  // 上面的实现（向前看）对于标签页是正确的。
  // 现在我们需要包装 fence 结果。
  
  const token = tokens[idx];
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : '';
  
  // 为了高亮显示，从 info 中去除 [title]
  token.info = info.replace(/\[.*?\]/, '').trim();
  
  const rawCode = defaultFence(tokens, idx, options, env, self);
  
  // 如果我们在代码组内，我们需要包装它。
  // 我们怎么知道？我们可以检查周围的容器是否是 code-group。
  // 在这个“结对编程”上下文中，让我们只是将每个 fence 包装在一个通用 wrapper 中
  // 它表现良好，或者如果我们检测到我们在组中，则使用特定的类。
  // 因为 'defaultFence' 返回之前代码中的自定义 .code-block-wrapper...
  
  // 让我们直接修改以前的自定义 fence 渲染器，而不是包装 defaultFence
  // 以避免双重包装或混淆。
  
  // ... (参见下面的集成实现)
  return rawCode; 
};

// 重定义 fence 规则以支持代码组可见性 + 行号 + 高亮
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  // 转义辅助函数
  const unescape = (str) => md.utils.unescapeAll(str).trim();
  
  const info = token.info ? unescape(token.info) : '';
  
  // 解析 Info 字符串
  // 格式: lang [title] {ranges} :line-numbers=start
  
  let rawInfo = info;
  let langName = '';
  let lineNumbersMode = false;
  let lineNumbersStart = 1;
  let highlights = [];

  // 1. 提取标题 [foo] (去除它，由代码组容器处理，但我们需要纯净的 info)
  const titleMatch = rawInfo.match(/\[(.*?)\]/);
  if (titleMatch) {
    rawInfo = rawInfo.replace(/\[.*?\]/, '');
  }

  // 2. 提取高亮 {4,6-10}
  const rangeMatch = rawInfo.match(/\{([0-9,\s-]+)\}/);
  if (rangeMatch) {
    const rangeStr = rangeMatch[1];
    rawInfo = rawInfo.replace(/\{.*?\}/, '');
    
    rangeStr.split(',').forEach(part => {
      part = part.trim();
      if (part.includes('-')) {
        const [start, end] = part.split('-');
        const s = parseInt(start, 10);
        const e = parseInt(end, 10);
        for (let i = s; i <= e; i++) {
          highlights.push(i);
        }
      } else {
        highlights.push(parseInt(part, 10));
      }
    });
  }

  // 3. 提取行号 :line-numbers(=start)?
  // 正则表达式匹配 :line-numbers 或 :line-numbers=2
  const lnMatch = rawInfo.match(/:line-numbers(?:=(\d+))?/);
  if (lnMatch) {
    lineNumbersMode = true;
    if (lnMatch[1]) {
      lineNumbersStart = parseInt(lnMatch[1], 10);
    }
    rawInfo = rawInfo.replace(/:line-numbers(?:=\d+)?/, '');
  }

  // 4. 提取语言名称
  langName = rawInfo.trim().split(/\s+/)[0] || '';

  // 代码高亮
  let code = options.highlight 
    ? options.highlight(token.content, langName) 
    : md.utils.escapeHtml(token.content);
    
  if (!code && options.highlight) {
    code = md.utils.escapeHtml(token.content);
  }

  // 分割行以计数 (使用原始内容以避免 HTML 标签问题)
  const lines = token.content.split(/\r?\n/);
  if (lines[lines.length - 1] === '') lines.pop(); // 移除末尾换行结果

  // 构建包装类
  const wrapperClasses = ['code-block-wrapper'];
  if (lineNumbersMode) wrapperClasses.push('line-numbers-mode');

  // 检查代码组激活状态
  let inGroup = false;
  if (idx > 0 && tokens[idx-1].type === 'container_code-group_open') {
    wrapperClasses.push('active'); // 组内第一个
    inGroup = true;
  } else {
      // 检查是否在组内但不是第一个
      // 我们向后扫描 open/close
      for (let k = idx - 1; k >= 0; k--) {
        if (tokens[k].type === 'container_code-group_close') { inGroup = false; break; }
        if (tokens[k].type === 'container_code-group_open') { inGroup = true; break; }
      }
  }

  // 生成高亮覆盖层
  let highlightOverlay = '';
  if (highlights.length > 0) {
    highlightOverlay = '<div class="highlight-lines">';
    for (let i = 0; i < lines.length; i++) {
      const lineNum = i + 1;
      const isHl = highlights.includes(lineNum);
      highlightOverlay += `<div class="highlight-line ${isHl ? 'highlighted' : ''}">&nbsp;</div>`;
    }
    highlightOverlay += '</div>';
  }

  // 生成行号
  let lineNumbersHtml = '';
  if (lineNumbersMode) {
    lineNumbersHtml = '<div class="line-numbers-wrapper">';
    for (let i = 0; i < lines.length; i++) {
      lineNumbersHtml += `<span class="line-number">${lineNumbersStart + i}</span><br>`;
    }
    lineNumbersHtml += '</div>';
  }

  const label = langName ? `<span class="code-lang">${langName}</span>` : '';
  const copyBtn = `<button class="copy-code-btn" data-code="${encodeURIComponent(token.content)}"></button>`;

  return `<div class="${wrapperClasses.join(' ')}">` +
           `<div class="code-header">${label}${copyBtn}</div>` +
           lineNumbersHtml +
           highlightOverlay +
           `<pre class="language-${langName}"><code class="language-${langName}">${code}</code></pre>` +
         `</div>`;
};

// 代码组逻辑
const handleCodeGroupClick = (e) => {
  if (e.target.classList.contains('code-group-tab')) {
    const tabs = e.target.parentElement;
    const blocks = tabs.nextElementSibling;
    if (!blocks || !blocks.classList.contains('code-group-blocks')) return;

    const index = Array.from(tabs.children).indexOf(e.target);
    if (index === -1) return;

    // 更新标签页
    Array.from(tabs.children).forEach((tab, i) => {
      if (i === index) tab.classList.add('active');
      else tab.classList.remove('active');
    });

    // 更新块
    Array.from(blocks.children).forEach((block, i) => {
      if (i === index) block.classList.add('active');
      else block.classList.remove('active');
    });
  }
}

// --- 全局点击处理 (复制 + 链接 + 代码组) ---
const handleGlobalClick = (e) => {
  // 0. 关闭右键菜单
  if (!e.target.closest('.ctx-menu')) ctxMenu.value.show = false
  // 1. 代码组逻辑
  if (e.target.classList.contains('code-group-tab')) {
    handleCodeGroupClick(e);
    return;
  }
  // 1. 复制逻辑
  if (e.target.classList.contains('copy-code-btn')) {
    const code = decodeURIComponent(e.target.getAttribute('data-code') || '')
    navigator.clipboard.writeText(code).then(() => {
      e.target.classList.add('copied')
      setTimeout(() => {
        e.target.classList.remove('copied')
      }, 2000)
    }).catch(err => {
      console.error('Copy failed', err)
    })
    return
  }

  // 2. 锚点/链接拦截
  const link = e.target.closest('a')
  if (link) {
    const href = link.getAttribute('href')
    // 哈希链接（锚点）
    if (href && href.startsWith('#')) {
      e.preventDefault()
      const id = decodeURIComponent(href.slice(1))
      scrollToHeading(id)
      // 可选：如果需要，手动更新 URL 哈希，但小心不要触发默认跳转
      history.pushState(null, null, href)
      return
    }
  }
}

const placeholderMd = computed(() => {
  return `# 阅览室\n\n请从左侧选择文档阅读。`
})

// --- 收集目录标题 ---
// 通过检查 token 重新实现目录收集
const renderResult = computed(() => {
  // AI 修改预览模式：优先渲染 AI 输出，方便先看效果再应用
  const source = aiPreview.value ? String(aiPreview.value.text) : (currentDoc.value?.content ? String(currentDoc.value.content) : placeholderMd.value)
  const env = {}
  
  // 用于目录提取的自定义渲染
  const tokens = md.parse(source, env)
  
  const headings = []
  const slugCounts = new Map()
  
  tokens.forEach((t, i) => {
    if (t.type === 'heading_open') {
      const tag = t.tag
      const level = Number(tag.replace('h', ''))
      if (level >= 2 && level <= 3) {
        // 查找内联 token
        const inline = tokens[i + 1]
        const title = inline && inline.type === 'inline' ? inline.content : ''
        
        let id = t.attrGet('id')
        if (!id) {
           // 如果锚点尚未运行或设置，则回退（如果正确使用则不太可能）
           const base = slugify(title)
           const n = (slugCounts.get(base) || 0) + 1
           slugCounts.set(base, n)
           id = n === 1 ? base : `${base}-${n}`
        }
        
        headings.push({ level, title, id })
      }
    }
  })
  
  const html = md.renderer.render(tokens, md.options, env)
  return { html, headings }
})

const rendered = computed(() => renderResult.value.html)
// 正文关键词高亮触发（rendered 定义后）
watch(rendered, () => { setTimeout(highlightBody, 120) })
watch(rendered, () => {
  bindAnnotations(document.querySelector('.doc-card .markdown-body'), annMap.value, { editable: false })
  window.dispatchEvent(new Event('zhiyu:doodle-reflow'))
  loadAnnData()
}, { flush: 'post' })
watch(searchText, (s) => { setTimeout(highlightBody, 80) })
const outline = computed(() => renderResult.value.headings.filter(h => h.level >= 2 && h.level <= 3))

// --- 滚动监听与目录交互 ---
const activeId = ref('')

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
// 一键回到顶部 / 到底部（与笔记阅读页同款）
const jumpTo = (pos) => {
  window.scrollTo({ top: pos === 'top' ? 0 : document.documentElement.scrollHeight, behavior: 'smooth' })
}

const scrollToHeading = (id) => {
  const el = document.getElementById(id)
  if (el) {
    const headerOffset = 60
    const elementPosition = el.getBoundingClientRect().top
    const offsetPosition = elementPosition + window.pageYOffset - headerOffset
    window.scrollTo({
      top: offsetPosition,
      behavior: "smooth"
    })
  }
}

// 滚动监听实现（窗口滚动）
const onScroll = () => {
  if (ctxMenu.value.show) ctxMenu.value.show = false // 滚动时收起右键菜单
  const headings = outline.value.map(h => h.id)
  if (headings.length === 0) return

  const scrollY = window.scrollY
  const headerOffset = 100
  
  let current = ''
  for (const id of headings) {
    const el = document.getElementById(id)
    if (!el) continue
    
    // 检查元素是否在“视线”上方
    if (el.offsetTop - headerOffset <= scrollY) {
      current = id
    } else {
      break
    }
  }
  activeId.value = current
}

// --- 上一篇 / 下一篇 逻辑 ---
const flatDocs = computed(() => grouped.value.flatMap(g => g.items))
const currentIndex = computed(() => {
  if (!route.params.key) return -1
  return flatDocs.value.findIndex(d => d.public_id === route.params.key)
})
const prevDoc = computed(() => {
  const idx = currentIndex.value
  if (idx > 0) return flatDocs.value[idx - 1]
  return null
})
const nextDoc = computed(() => {
  const idx = currentIndex.value
  if (idx > -1 && idx < flatDocs.value.length - 1) return flatDocs.value[idx + 1]
  return null
})

</script>

<template>
  <div class="docs-layout" :class="{ immersive }">
    <!-- 一键回到顶部 / 到底部（与笔记阅读页同款，仅沉浸式阅读显示） -->
    <div class="scroll-jump" v-if="immersive">
      <button class="sj-btn" data-tip="回到顶部" data-tip-align="left" @click="jumpTo('top')">↑</button>
      <button class="sj-btn" data-tip="到底部" data-tip-align="left" @click="jumpTo('bottom')">↓</button>
    </div>
    
    <!-- 移动端顶部刘海条（Menu + 大纲）：fixed 固定在全局导航栏下方（= 卡片顶部），不随内容滚动、不盖导航栏 -->
    <div v-if="!showLeftSidebar" class="mobile-header-sub">
      <div class="sub-inner">
        <button class="icon-btn" @click="showMenuDrawer = true">
          <el-icon><IconMenu /></el-icon>
          <span class="btn-text">Menu</span>
        </button>
        <el-popover
          ref="outlinePopperRefMobile"
          trigger="click"
          placement="bottom-end"
          :width="isMobile ? '92vw' : '400px'"
          popper-class="outline-popover"
          :teleported="true"
          :append-to-body="true"
          @show="fixOutlinePopper"
        >
          <template #reference>
            <button class="icon-btn">
              <span class="btn-text">大纲</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
          </template>
          <div class="popover-outline">
            <div
              v-for="h in outline" :key="h.id"
              class="outline-item"
              :class="{ 'indent-2': h.level === 2, 'indent-3': h.level === 3, 'active': activeId === h.id }"
              @click="scrollToHeading(h.id)"
            >
              {{ h.title }}
            </div>
          </div>
        </el-popover>
      </div>
    </div>

    <!-- 主布局容器 -->
    <div class="main-wrapper" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'right-collapsed': rightSidebarCollapsed }">
      
      <!-- 左侧边栏 (桌面/平板)：收起时保留窄条（与右侧栏同构） -->
      <aside v-if="showLeftSidebar" class="left-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="left-sidebar-inner" :class="{ 'is-collapsed': sidebarCollapsed }">
          <div class="sidebar-header">
             <span class="site-title" @click="goHome">知屿 <em class="room-tag">阅览室</em></span>
             <span class="group-ctrl">
               <button class="gc-btn" data-tip="添加笔记" @click="addOpen = true">＋</button>
               <button class="gc-btn" data-tip="收起侧栏" @click="toggleSidebar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg></button>
             </span>
          </div>
          <div class="sidebar-scroll">
            <div v-if="auth.isLogin && roomLoading" class="side-empty">加载中…</div>
            <div v-else-if="auth.isLogin && !grouped.length" class="side-empty">阅览室还没有笔记<br /><span class="side-empty-sub">去笔记广场或书房把笔记加入阅览室</span></div>
            <div class="group" v-for="g in grouped" :key="g.type">
              <div class="group-title" @click="toggleGroup(g.type)" :class="{ active: openTypes.has(g.type) }">
                {{ g.type }}
                <span class="caret" :class="{ open: openTypes.has(g.type) }"></span>
              </div>
              <div class="group-items" v-if="openTypes.has(g.type)">
                <div 
                  v-for="item in g.items" 
                  :key="item.id"
                  class="doc-link"
                  :class="{ active: route.params.key === item.public_id }"
                  @click="selectDoc(item)"
                  @contextmenu.prevent="openCtxMenu($event, item)"
                >
                  <span v-html="highlightTitle(item.title)"></span>
                  <span v-if="item.origin_id" class="from-square">来自广场</span>
                  <span v-if="item.format && item.format !== 'md'" class="dl-fmt">{{ item.format.toUpperCase() }}</span>
                  <span v-if="roomIds.has(item.id)" class="dl-room">📖</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <button v-if="sidebarCollapsed" class="sb-rail" data-tip="展开侧栏" data-tip-align="left" @click="toggleSidebar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg>
          <span class="sb-rail-text">导航</span>
        </button>
      </aside>

      <!-- 中间列包装器 (导航栏 + 内容) -->
      <div class="content-wrapper">
        <!-- 文档主要内容 -->
        <main class="doc-main">
          <div class="doc-container">
            <article class="doc-card">
              <div class="doc-tools" v-if="currentDoc">
                <a v-if="currentDoc.attachment" class="att-link" :href="'/uploads/' + currentDoc.attachment" target="_blank" rel="noopener">📎 附件</a>
                <button v-if="isMyDoc(currentDoc) || auth.user?.role === 'admin'" class="tool-btn" @click="editCurrent">✏️ 编辑此页</button>
                <button class="immersive-btn" :class="{ on: immersive }" @click="toggleImmersive" data-tip="沉浸">⛶</button>
              </div>
              <div v-if="aiPreview" class="ai-preview-bar">
                <div class="ai-preview-info">
                  <b>🤖 AI 修改预览</b>
                  <span>下面是 AI 修改后的内容（尚未保存），确认无误后点「应用修改」</span>
                </div>
                <div class="ai-preview-actions">
                  <button class="ai-pv-cancel" type="button" @click="cancelAiPreview">✕ 放弃</button>
                  <button class="ai-pv-apply" type="button" @click="applyAiPreview">✓ 应用修改</button>
                </div>
              </div>
              <div v-if="docLoading" class="doc-loading">加载中…</div>              <div v-else-if="!currentDoc" class="doc-empty">📖 从左侧列表选择一篇笔记开始阅读</div>
              <div v-else class="markdown-body" v-html="rendered" @click="onContentClick"></div>
              <!-- 附件：上传的文件（PDF/Office 等）可下载 -->
              <div v-if="currentDoc && currentDoc.attachment" class="doc-attachment">
                <a :href="'/uploads/' + currentDoc.attachment" download class="att-link">📎 下载附件</a>
              </div>
              <!-- 附件下载（创建时上传的 PDF/Excel 等） -->
              <div v-if="currentDoc && currentDoc.attachment" class="doc-attachment">
                <a :href="'/uploads/' + currentDoc.attachment" download class="att-link">📎 下载附件</a>
              </div>
              <ImageViewer :visible="viewerOpen" :url="viewerUrl" @close="viewerOpen = false" />
              <DoodleBall v-if="currentDoc" target=".doc-card" :doc-id="currentDoc.id" :is-mine="isMyDoc(currentDoc)" />
              <!-- 上一篇/下一篇：等正文加载完成（docLoading=false 且 currentDoc 就绪）才显示，加载中只显示「加载中…」与 notes 页一致 -->
              <div v-if="currentDoc && !docLoading" class="doc-footer">
                <div class="prev-next-nav">
                    <a v-if="prevDoc" class="pager-link prev" href="#" @click.prevent="selectDoc(prevDoc)">
                      <span class="desc">Previous page</span>
                      <span class="title">{{ prevDoc.title }}</span>
                    </a>
                    <a v-if="nextDoc" class="pager-link next" href="#" @click.prevent="selectDoc(nextDoc)">
                      <span class="desc">Next page</span>
                      <span class="title">{{ nextDoc.title }}</span>
                    </a>
                </div>
              </div>
            </article>
          </div>
        </main>
      </div>

      <!-- 右侧边栏 (如果 >= 1400 则可见)：收起时保留窄条 -->
      <aside v-if="showRightSidebar" class="right-sidebar" :class="{ collapsed: rightSidebarCollapsed }">
        <div class="right-sidebar-inner" :class="{ 'is-collapsed': rightSidebarCollapsed }">
          <div class="outline-content">
            <div class="outline-head">
              <button class="rs-collapse-btn" data-tip="收起大纲" data-tip-align="left" @click="toggleRightSidebar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="13.8" y1="4" x2="13.8" y2="20"/></svg></button>
              <div class="outline-title">大纲</div>
            </div>
            <div class="outline-list">
              <div 
                  v-for="h in outline" :key="h.id"
                  class="outline-link"
                  :class="{ 'indent-2': h.level === 2, 'indent-3': h.level === 3, 'active': activeId === h.id }"
                  @click="scrollToHeading(h.id)"
                >
                  {{ h.title }}
              </div>
            </div>
          </div>
        </div>
        <button v-if="rightSidebarCollapsed" class="sb-rail" data-tip="展开大纲" data-tip-align="right" @click="toggleRightSidebar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="13.8" y1="4" x2="13.8" y2="20"/></svg>
          <span class="sb-rail-text">大纲</span>
        </button>
      </aside>

    </div>

    <!-- 移动端抽屉 -->
    <el-drawer
      v-model="showMenuDrawer"
      direction="ltr"
      size="min(78vw, 300px)"
      :with-header="false"
      :modal="true"
      :append-to-body="true"
      class="mobile-menu-drawer"
    >
      <div class="drawer-content">
        <div class="group" v-for="g in grouped" :key="g.type">
            <div class="group-title" @click="toggleGroup(g.type)" :class="{ active: openTypes.has(g.type) }">
              {{ g.type }}
              <span class="caret" :class="{ open: openTypes.has(g.type) }"></span>
            </div>
            <div class="group-items" v-if="openTypes.has(g.type)">
              <div 
                v-for="item in g.items" 
                :key="item.id"
                class="doc-link"
                :class="{ active: route.params.key === item.public_id }"
                @click="selectDoc(item)"
              >
                <span v-html="highlightTitle(item.title)"></span>
                  <span v-if="item.origin_id" class="from-square">来自广场</span>
              </div>
            </div>
          </div>
      </div>
    </el-drawer>

    <!-- 右键菜单 -->
    <div v-if="ctxMenu.show" class="ctx-menu" :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }">
      <div
        v-for="a in ctxActions" :key="a.label"
        class="ctx-item" :class="{ disabled: a.disabled }"
        @click="a.fn && a.fn(ctxMenu.doc)"
      >{{ a.label }}</div>
    </div>

    <!-- 添加笔记弹窗 -->
    <div v-if="addOpen" class="add-mask" @click.self="addOpen = false">
      <div class="add-panel">
        <h3>＋ 添加到阅览室</h3>
        <p class="add-tip">从我的书房中挑选笔记，加入本次学习的工作台。想用广场笔记？先在广场点「加入书房」。</p>
        <input v-model="addQuery" class="add-search" placeholder="搜索标题…" />
        <div class="add-list">
          <div v-for="d in addList" :key="d.id" class="add-item">
            <span class="add-title">{{ d.title }}</span>
            <span class="add-meta">{{ d.type }}</span>
            <button
              class="add-btn"
              :class="{ in: roomIds.has(d.id) }"
              @click="roomIds.has(d.id) ? moveOutRoom(d) : addToRoom(d)"
            >{{ roomIds.has(d.id) ? '✓ 已加入' : '加入' }}</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.docs-layout {
  min-height: 100vh;
  /* 背景透明：透出 App 全局主题背景 */
  background-color: transparent;
  color: var(--c-text-1);
}

/* 移动端顶部：Menu/大纲 两个小浮空按钮（无背景，不占横幅），fixed 在全局导航栏下方 */
.mobile-header-sub {
  position: fixed; top: 60px; left: 0; right: 0;
  z-index: 90;
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 14px;
  background: transparent;
  border: none;
  box-shadow: none;
}
.sub-inner {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 一键回到顶部 / 到底部（与笔记阅读页同款） */
.scroll-jump {
  position: fixed; right: 18px; bottom: 96px; z-index: 300;
  display: flex; flex-direction: column; gap: 8px;
}
.sj-btn {
  width: 40px; height: 40px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--bg-soft);
  color: var(--text2); font-size: 16px; cursor: pointer;
  box-shadow: var(--shadow-1); transition: all .2s;
  display: inline-flex; align-items: center; justify-content: center;
}
.sj-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); transform: scale(1.06); }

/* 沉浸式阅读：隐藏左侧列表/右侧大纲/编辑按钮，正文单列居中放大 */
.docs-layout.immersive .left-sidebar,
.docs-layout.immersive .right-sidebar { display: none; }
.docs-layout.immersive .doc-tools .tool-btn { display: none; }
/* 沉浸：强制单列全宽（覆盖收起态的三列，否则正文会被塞进 48px 第一列变竖条） */
.docs-layout.immersive .main-wrapper,
.docs-layout.immersive .main-wrapper.sidebar-collapsed,
.docs-layout.immersive .main-wrapper.right-collapsed,
.docs-layout.immersive .main-wrapper.sidebar-collapsed.right-collapsed {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: 'main';
}
.docs-layout.immersive .doc-container { max-width: 1280px; }

/* --- Desktop Layout --- */
.main-wrapper {
  display: grid;
  width: 100%;
  /* 固定三栏宽度（可动画）：收起时列宽由 grid-template-columns 过渡平滑伸缩。
     不要用 auto 轨道——auto 轨道跟随内容尺寸，内容 v-if 切换时宽度会瞬时跳变，
     且对侧栏自身的 width transition 无效（实测不产生动画）。 */
  grid-template-columns: 280px minmax(0, 1fr) 280px;
  grid-template-areas: 'left main right';
  transition: grid-template-columns .3s ease;
  position: relative;
  /* Removed overflow-x: hidden to prevent breaking sticky positioning if container height is constrained */
}

/* Left Sidebar */
.left-sidebar {
  grid-area: left;
  width: 100%; /* 填满轨道；轨道负责收起/展开的宽度动画 */
  min-width: 0;
  background: var(--c-sidebar-bg);
  display: flex;
  flex-direction: column;
  align-items: flex-end; /* Stick content to the right (next to doc) */
  border-right: 1px solid transparent; 
  /* Ensure it stretches to full height of parent so sticky child can move within it */
  align-self: stretch;
  position: relative; /* 供收起后的窄条按钮绝对定位覆盖 */
}

.left-sidebar-inner {
  width: 100%;
  min-width: 0; /* 不强制撑宽：展开/收起宽度过渡由 grid 轨道驱动，内容被自身裁切 */
  height: calc(100vh - 60px);
  position: sticky;
  top: 60px; /* 全局导航下方 */
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden; /* 收起过渡期间裁切横向溢出的内容，避免文字跑出窄条 */
}
/* 收起态：内容隐藏，保留 DOM（避免 v-if 重建导致 sticky 重排/闪烁）。
   不用 opacity/transform 过渡——实测会让 grid 宽度动画的启动晚 1~2 帧（点击停顿感），
   与书房一致：内容显隐交给宽度裁切，点击立即响应。 */
.left-sidebar-inner.is-collapsed {
  opacity: 0;
  pointer-events: none;
}

/* 品牌区：与顶部有明显留白，去掉硬分隔线，靠留白分区 */
.group-ctrl { display: inline-flex; gap: 2px; }
.gc-btn {
  width: 26px; height: 26px; border-radius: 8px; cursor: pointer;
  border: none; background: transparent;
  outline: none; /* 点击获焦时不显默认蓝框 */
  -webkit-tap-highlight-color: transparent; /* 平板触屏点击不闪浏览器默认高亮 */
  color: var(--text2); font-size: 12px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.gc-btn:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent); transform: translateY(-1px); }
.gc-btn svg { width: 14px; height: 14px; }
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 22px;
  margin-bottom: 6px;
  overflow: hidden; /* 窄轨道动画期间裁切换行/溢出内容，固定头部高度，避免卡片上下跳变 */
}
.site-title {
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--c-text-1);
  white-space: nowrap; /* 标题不换行：窄轨道下保持单行，高度恒定 */
}
.site-title::before {
  content: '✦';
  font-size: 15px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.sidebar-scroll {
  flex: 1;
  padding-bottom: 28px;
  padding-right: 6px;
}

/* Content Wrapper */
.content-wrapper {
  grid-area: main;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-bg);
  z-index: 1;
  position: relative; /* 供收起恢复按钮贴边缘定位 */
}

/* 侧栏收起：左/右栏保留 48px 窄条；列宽由 grid-template-columns 过渡平滑伸缩。
   不用 width 动画驱动轨道——grid auto 轨道跟随内容尺寸，内容 v-if 切换时宽度瞬时跳变，
   对侧栏自身 width 的 transition 无效（实测不产生动画）。 */
.main-wrapper.sidebar-collapsed { grid-template-columns: 48px minmax(0, 1fr) 280px; }
.main-wrapper.right-collapsed { grid-template-columns: 280px minmax(0, 1fr) 48px; }
.main-wrapper.sidebar-collapsed.right-collapsed { grid-template-columns: 48px minmax(0, 1fr) 48px; }
/* 窄条样式：VSCode 活动栏式——透明底、无边框，融入页面背景 */
.left-sidebar.collapsed,
.right-sidebar.collapsed {
  align-items: stretch;
  justify-content: flex-start;
  background: transparent;
}
/* 窄条不加边框：收起后是干净的竖条，不显突兀 */
.left-sidebar.collapsed {
  border-right: none;
  border-left: none;
}
.right-sidebar.collapsed {
  border-left: none;
  border-right: none;
}
.sb-rail {
  position: absolute; /* 覆盖在常驻的 inner 之上：不参与 flex 排列（否则会被挤到内容下方视口外） */
  inset: 0;
  width: 100%; height: 100%;
  border: none; background: transparent; cursor: pointer;
  outline: none; /* 点击获焦时不显默认蓝框 */
  -webkit-tap-highlight-color: transparent; /* 平板触屏点击不闪浏览器默认高亮 */
  display: flex; flex-direction: column; align-items: center;
  justify-content: flex-start; /* 靠上 */
  padding-top: 18px;
  gap: 14px;
  color: var(--text2);
  transition: background .2s, color .2s;
}
.sb-rail:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 7%, transparent); }
.sb-rail svg { width: 20px; height: 20px; color: var(--brand-1); }
.sb-rail-text {
  writing-mode: vertical-rl;
  font-size: 11.5px; letter-spacing: 3px;
  color: inherit;
  user-select: none;
}
/* 侧栏内容切换淡入淡出 */
.sb-fade-enter-active, .sb-fade-leave-active { transition: opacity .18s ease; }
.sb-fade-enter-from, .sb-fade-leave-to { opacity: 0; }


/* Doc Main */
.doc-main {
  flex: 1;
  min-width: 0;
}
.doc-container {
  max-width: 880px; 
  margin: 0 auto;
  padding: 26px 24px 50px; /* 水平内边距收窄：让正文卡片尽量铺开 */
  transition: max-width .3s ease; /* 只过渡宽度，margin 恒为 auto 居中，避免 auto↔px 跳变 */
}
/* 收起左栏：正文放大并保持居中 */
.main-wrapper.sidebar-collapsed .doc-container {
  max-width: 1000px;
}
/* 收起右栏：正文放大并保持居中（内容区随侧栏收缩平滑变宽，正文随之右扩居中） */
.main-wrapper.right-collapsed .doc-container {
  max-width: 1100px;
}
/* 两边都收起：正文保持居中 */
.main-wrapper.sidebar-collapsed.right-collapsed .doc-container {
  max-width: 1100px;
}
@media (max-width: 959px) {
  .doc-container {
    padding: 24px 24px; /* Mobile padding */
  }
}

/* Right Sidebar */
.right-sidebar {
  grid-area: right;
  width: 100%; /* 填满轨道；轨道负责收起/展开的宽度动画 */
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start; /* Align content to left (next to doc) */
  align-self: stretch; 
  position: relative; /* 供收起后的窄条按钮绝对定位覆盖 */
}

.right-sidebar-inner {
  width: 100%; /* Fill available space */
  min-width: 0; /* 不强制撑宽：展开/收起宽度过渡由 grid 轨道驱动，内容被自身裁切 */
  height: calc(100vh - 60px); 
  position: sticky;
  top: 60px; /* 与左侧导航栏同高对齐 */
  padding: 20px 0 24px; 
  overflow-y: auto;
  overflow-x: hidden;
}
/* 收起态：内容隐藏，保留 DOM。同左栏——不用 opacity/transform 过渡，避免 grid 动画启动延迟 */
.right-sidebar-inner.is-collapsed {
  opacity: 0;
  pointer-events: none;
}

/* 大纲标题行：收缩按钮在"大纲"文字左边，垂直居中 */
.outline-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  overflow: hidden; /* 窄轨道动画期间裁切溢出内容，固定头部高度，避免卡片上下跳变 */
}
.rs-collapse-btn {
  width: 26px; height: 26px; flex-shrink: 0; border-radius: 8px; cursor: pointer;
  border: none; background: transparent; color: var(--text2);
  outline: none; /* 点击获焦时不显默认蓝框 */
  -webkit-tap-highlight-color: transparent; /* 平板触屏点击不闪浏览器默认高亮 */
  display: inline-flex; align-items: center; justify-content: center;
  transition: background .15s, color .15s;
}
.rs-collapse-btn:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.rs-collapse-btn svg { width: 17px; height: 17px; }

/* 右侧大纲栏收起后：由窄条取代（旧浮动按钮废弃） */
.rs-restore { display: none; }
.rs-restore:hover { display: none; }
.rs-restore svg { display: none; }

/* Hide scrollbar for outline */
.right-sidebar-inner::-webkit-scrollbar,
.outline-list::-webkit-scrollbar {
  display: none;
}

.outline-content {
  padding: 0 16px;
  width: 100%;
  box-sizing: border-box;
}

/* --- 响应式逻辑 --- */

/* 
   断点 1: 当空间紧缺时隐藏右侧边栏。
   阈值: 270 (左) + 880 (文档) + 260 (右) + 边距 ~= 1450px。
   如果 < 1450px，我们隐藏右侧边栏 (由 JS 中的 v-if="showRightSidebar" 处理)。
   但我们也需要调整布局以防止裁剪左侧边栏。
*/

/* 
   断点 2: 从 "动态间距" 切换到 "左侧固定 + 中间流式"。
   这避免了当 "间距" 缩小到 270px 以下时裁剪左侧边栏。
   计算: (Window - 880) / 2 < 270 => Window < 1420。
   所以在 1420px 以下，我们必须切换布局模式。
*/
@media (max-width: 1400px) {
  .main-wrapper {
    grid-template-columns: 270px minmax(0, 1fr) 260px;
    grid-template-areas: 'left main right';
  }
  .main-wrapper.sidebar-collapsed {
    grid-template-columns: 48px minmax(0, 1fr) 260px;
    grid-template-areas: 'left main right';
  }
  .main-wrapper.right-collapsed {
    grid-template-columns: 270px minmax(0, 1fr) 48px;
    grid-template-areas: 'left main right';
  }
  .main-wrapper.sidebar-collapsed.right-collapsed {
    grid-template-columns: 48px minmax(0, 1fr) 48px;
    grid-template-areas: 'left main right';
  }
  
  .left-sidebar {
    /* 切换到固定宽度 */
    grid-area: left;
    width: 100%; /* 填满轨道（轨道在收起时平滑收缩到 48px） */
    align-items: stretch; /* 填充宽度 */
  }
  
  .left-sidebar-inner {
    width: 100%;
    min-width: 0;
  }

  .right-sidebar {
    width: 100%;
  }
  
  .content-wrapper {
    /* 切换到流式宽度 */
    grid-area: main;
    flex: 1;
    width: 100%; /* 填满中间轨道：轨道 < 1000px 时正文随轨道宽度，不向两侧栏溢出 */
    max-width: 1000px; /* 可选的最大宽度以提高可读性 */
    margin-inline: auto; /* 中间列在轨道内居中（收起后轨道 > 1000px 时正文保持居中，不再靠左） */
  }
}

/* 移动端调整由 showLeftSidebar 逻辑 (< 960px) 处理 */

/* Common Components */
.site-title {
  font-weight: 600;
  font-size: 1.1rem;
  cursor: pointer;
  display: block;
  text-decoration: none;
  color: var(--c-text-1);
}
.nav-link-text:hover {
  color: var(--c-brand);
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--c-text-1);
  padding: 4px 8px;
  border-radius: 4px;
}
.icon-btn:hover {
  background-color: var(--c-bg-soft);
}


/* Sidebar Groups */
.group {
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 12px;
  padding-bottom: 12px;
}
.group:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.group-title {
  padding: 8px 24px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--c-text-1);
  width: 100%;
  box-sizing: border-box;
}
.group-title {
  /* width:auto 覆盖原 width:100%：配合左右 margin 不再溢出玻璃卡片边框 */
  width: auto;
  border-radius: 10px;
  margin: 4px 10px;
  padding: 8px 12px;
  transition: color .25s, background .25s;
}
.group-title:hover {
  color: var(--c-brand);
  background-color: color-mix(in srgb, var(--brand-1) 6%, transparent);
}
.group-title.active {
  color: var(--brand-1);
}
.group-items {
  padding-bottom: 12px;
  width: 100%;
}
.kw-hl { background: color-mix(in srgb, var(--brand-1) 30%, transparent); color: inherit; border-radius: 3px; padding: 0 2px; }
.doc-link {
  display: block;
  padding: 9px 16px 9px 18px;
  margin: 2px 10px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--c-text-2);
  cursor: pointer;
  width: auto;
  border-radius: 10px;
  border: 1px solid transparent;
  box-sizing: border-box;
  text-decoration: none;
  transition: color .2s, background .2s, border-color .2s;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
/* hover：单纯浅色框 + 轻微凸起 */
.doc-link:hover {
  color: var(--c-text-1);
  background: color-mix(in srgb, var(--brand-1) 8%, transparent);
  border-color: color-mix(in srgb, var(--brand-1) 18%, transparent);
  transform: translateX(3px);
}
/* 选中：浅色高亮 + 凸起，仅此两项，无渐变/无投影/无内嵌条 */
.doc-link.active {
  color: var(--brand-1);
  font-weight: 600;
  background: color-mix(in srgb, var(--brand-1) 12%, transparent);
  border-color: color-mix(in srgb, var(--brand-1) 26%, transparent);
  transform: translateX(4px);
}
.caret {
  width: 0; 
  height: 0; 
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 5px solid var(--c-text-2); /* Point Right */
  transition: transform 0.2s;
}
.caret.open {
  transform: rotate(90deg); /* Point Down */
}

/* Outline Links */
.outline-title {
  font-weight: 600;
  margin-bottom: 0;
  font-size: 14px;
  white-space: nowrap; /* 标题不换行：窄轨道下保持单行，高度恒定 */
}
.outline-list {
  position: relative;
  border-left: 1px solid var(--c-border); /* Vertical Gray Line */
  overflow-x: auto; /* Allow horizontal scroll */
  padding-bottom: 4px;
}
.outline-link {
  display: block;
  padding: 4px 16px 4px 12px;
  font-size: 13px;
  color: var(--c-text-2);
  cursor: pointer;
  text-decoration: none;
  line-height: 1.6;
  border-left: 2px solid transparent; /* Active Indicator */
  margin-left: -1px; /* Overlap the gray line */
  
  /* Allow Wrap */
  white-space: normal;
  word-break: break-word;
  width: auto;
  min-width: 100%;
}
.outline-link:hover, .outline-link.active {
  color: var(--c-brand);
  border-left-color: var(--c-brand);
}
.outline-link.indent-3 {
  padding-left: 24px;
}

/* --- Home Page Styles --- */
.home-content {
  width: 100%;
  max-width: 100%;
  padding-bottom: 64px;
}
.VPHero {
  padding: 64px 24px 24px;
  text-align: center;
}
.container {
  max-width: 1152px;
  margin: 0 auto;
}
.name {
  font-size: 56px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, #409eff 0%, #a855f7 30%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 0 auto;
  text-align: center;
}
.text {
  margin-top: 14px;
  font-size: 24px;
  line-height: 1.2;
  color: var(--c-text-2);
  font-weight: 600;
  text-align: center;
}
.actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  justify-content: center;
}
.btn {
  border-radius: 20px;
  padding: 10px 24px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid var(--c-brand);
  background: var(--c-bg);
  color: var(--c-brand);
  font-weight: 600;
  transition: all 0.2s;
}
.btn:hover {
  background: var(--c-brand-light);
  color: #fff;
  border-color: var(--c-brand-light);
}
.btn.brand {
  background: var(--c-brand);
  color: #fff;
}
.btn.brand:hover {
  background: var(--c-brand-light);
}

.VPFeatures {
  padding: 40px 24px 64px;
  background: var(--c-bg);
}
.feature-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
}
.VPFeature {
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: 24px;
  background: var(--c-bg-soft);
  transition: transform .15s ease, border-color .15s ease;
}
.VPFeature:hover {
  transform: translateY(-2px);
  border-color: var(--c-brand);
}
.feature-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--c-text-1);
  font-size: 16px;
}
.feature-desc {
  color: var(--c-text-2);
  font-size: 14px;
  line-height: 1.6;
}
@media (max-width: 640px) {
  .name { font-size: 40px; }
  .text { font-size: 20px; }
}

/* Markdown Override - Handled in docs-theme.css */


/* Prev/Next */
.prev-next-nav {
  margin-top: 64px;
  padding-top: 24px;
  border-top: 1px solid var(--c-border);
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.pager-link {
  display: block;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 11px 16px 13px;
  width: 48%;
  flex-grow: 1;
  max-width: 48%;
  cursor: pointer;
  text-decoration: none;
  transition: border-color 0.25s;
  background-color: var(--c-bg);
}
.pager-link:hover {
  border-color: var(--c-brand);
}
.pager-link.prev {
  margin-right: auto;
}
.pager-link.next {
  margin-left: auto;
  text-align: right;
}
.pager-link .desc {
  display: block;
  font-size: 12px;
  line-height: 20px;
  font-weight: 500;
  color: var(--c-text-2);
}
.pager-link .title {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--c-brand);
  transition: color 0.25s;
  margin-top: 4px;
}

/* Mobile Popover Items */
.popover-outline {
  max-height: 60vh;
  overflow-y: auto;
}
/* 大纲浮层：跟随站内主题（暗色/浅色都统一，不再纯白） */
.outline-popover {
  --el-popover-bg-color: var(--bg-soft) !important;
  --el-popover-border-color: var(--border) !important;
  --el-text-color-primary: var(--text1) !important;
  background: var(--bg-soft) !important;
  border-color: var(--border) !important;
  color: var(--text1) !important;
  box-shadow: var(--shadow-1) !important;
  border-radius: 12px !important;
}
.outline-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: var(--c-text-2);
}
.outline-item:hover, .outline-item.active {
  color: var(--c-brand);
  background: var(--c-bg-soft);
}
.outline-item.indent-3 {
  padding-left: 32px;
}

/* Menu Popover Styles */
.menu-popover-content {
  padding: 4px 0;
}
.menu-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
}
.menu-label {
  font-size: 14px;
  color: var(--c-text-2);
  font-weight: 500;
}

@media (max-width: 959px) {
  /* 移动端：左右侧栏均隐藏，内容区占满整行 */
  .main-wrapper {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: 'main';
  }
  /* 移动端：正文铺满屏幕，去掉卡片围边；卡片顶部圆角与刘海条匹配消除缝隙（!important 防止被后面普通规则覆盖） */
  .doc-container { padding: 0 !important; }
  .doc-card {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 16px 16px 0 0 !important; /* 顶部圆角与刘海条一致，左右两边缘无缝 */
    padding: 20px 18px 44px !important;
  }
  .doc-card::before { display: none !important; }
}

/* ═══════════════════════════════════════════════════════════
   知识库视觉统一（与首页同审美：主题背景、玻璃卡片、弱化分区）
   ═══════════════════════════════════════════════════════════ */

/* 页面整体：背景交给 App 全局主题背景层（本地不再设底色），顶部为全局导航让位 */
.docs-layout {
  padding-top: 60px;
  background: transparent;
  min-height: 100vh;
}
/* 移动端：顶部浮空按钮（约 40px）占位，内容从导航栏 + 按钮下方开始 */
@media (max-width: 959px) {
  .docs-layout { padding-top: 100px; }
}

/* 左侧栏：融入背景，目录玻璃卡片化 */
.left-sidebar {
  background: transparent !important;
}
.left-sidebar-inner {
  padding: 10px 14px 20px 10px;
  box-sizing: border-box;
}
.group-ctrl { display: inline-flex; gap: 2px; }
.gc-btn {
  width: 26px; height: 26px; border-radius: 8px; cursor: pointer;
  border: none; background: transparent;
  outline: none; /* 点击获焦时不显默认蓝框 */
  -webkit-tap-highlight-color: transparent; /* 平板触屏点击不闪浏览器默认高亮 */
  color: var(--text2); font-size: 12px; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.gc-btn:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent); transform: translateY(-1px); }
.gc-btn svg { width: 14px; height: 14px; }
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: none;
  padding-bottom: 10px;
}
.sidebar-scroll {
  background: color-mix(in srgb, var(--c-bg-soft) 55%, transparent);
  border: 1px solid var(--c-border);
  border-radius: 18px;
  padding: 10px 0;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: var(--shadow-1);
}

/* 内容区：透明背景，让阅读卡片浮起 */
.content-wrapper {
  background: transparent !important;
}


/* 文档卡片：更大圆角 + 柔和阴影 + 半透明玻璃（保证正文在全局背景上可读）
   内边距加宽：把标题锚点 # 也包进卡片内 */
.doc-loading {
  padding: 60px 24px;
  text-align: center;
  color: var(--text2);
  font-size: 14px;
}
.doc-empty {
  padding: 120px 24px;
  text-align: center;
  color: var(--text3);
  font-size: 15px;
  letter-spacing: .5px;
}
/* 未登录访问阅览室：不显示登录引导，直接空白（左侧与正文都空，正文显示未选中文档的占位文案） */
.doc-card {
  position: relative;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  box-shadow: var(--shadow-1);
  /* 保持 82% 半透明原观感；去掉 backdrop-filter（快速拖动滚动条时整卡重采样导致白屏/卡片消失）。
     82% 已接近实色，去掉模糊视觉几乎无差异，但滚动流畅 */
  background: color-mix(in srgb, var(--c-bg) 82%, transparent);
  padding: 34px 40px 40px;
  overflow: hidden;
}
/* 右上角渐变光晕（参考 reasonix changelog 的正文氛围） */
.doc-card::before {
  content: '';
  position: absolute;
  top: -120px;
  right: -120px;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--brand-1) 14%, transparent) 0%,
    color-mix(in srgb, var(--brand-2) 8%, transparent) 45%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 0;
}
.doc-card > * {
  position: relative;
  z-index: 1;
}

/* 锚点 # 相对标题定位，让锚点落在卡片内侧 */
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  position: relative;
}

/* ═══ 阅览室 ═══ */
.room-tag { font-style: normal; font-size: 10px; color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 14%, transparent); border-radius: 999px; padding: 1px 8px; margin-left: 4px; vertical-align: 2px; }
.room-switch { display: flex; gap: 4px; padding: 8px 6px 6px; }
.side-empty {
  padding: 28px 18px;
  text-align: center;
  color: var(--text2);
  font-size: 13px;
  line-height: 1.8;
}
.side-empty-sub { font-size: 12px; color: var(--text3, var(--text2)); opacity: .75; }
.rs-btn { flex: 1; padding: 5px 0; border-radius: 8px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2); font-size: 11.5px; cursor: pointer; transition: all .15s; }
.rs-btn.on { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 50%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); font-weight: 600; }
.dl-fmt { font-size: 9.5px; color: var(--text2); border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; margin-left: 6px; }
.dl-room { font-size: 10px; margin-left: 4px; }
.sidebar-restore { display: none; }
.sidebar-restore svg { display: none; }
.doc-tools { display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-bottom: 14px; }
/* 附件下载条 */
.doc-attachment {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}
.att-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 30%, transparent);
  text-decoration: none;
  transition: all .2s;
}
.att-link:hover {
  background: color-mix(in srgb, var(--brand-1) 16%, transparent);
  transform: translateY(-1px);
}
/* 附件下载条 */
.doc-attachment {
  margin: 18px 0 4px;
  padding: 12px 16px;
  border: 1px dashed var(--border);
  border-radius: 12px;
  background: color-mix(in srgb, var(--brand-1) 6%, transparent);
}
.att-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--brand-1);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}
.att-link:hover { text-decoration: underline; }
.tool-btn { padding: 7px 16px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--brand-1) 45%, transparent); background: color-mix(in srgb, var(--brand-1) 8%, transparent); color: var(--brand-1); font-size: 12.5px; cursor: pointer; transition: all .2s; }
.tool-btn:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; border-color: transparent; }

/* AI 修改预览横幅 */
.ai-preview-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;
  padding: 12px 16px; margin-bottom: 16px;
  border-radius: 14px;
  background: linear-gradient(120deg, rgba(0, 198, 255, .09), rgba(227, 5, 247, .09));
  border: 1px solid color-mix(in srgb, var(--brand-1) 35%, transparent);
}
.ai-preview-info { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--text2); }
.ai-preview-info b { color: var(--brand-1); font-size: 14px; white-space: nowrap; }
.ai-preview-actions { display: flex; gap: 8px; }
.ai-pv-cancel, .ai-pv-apply { padding: 7px 18px; border-radius: 999px; border: none; font-size: 13px; cursor: pointer; font-weight: 600; transition: all .2s; }
.ai-pv-cancel { background: var(--btn-bg); border: 1px solid var(--border); color: var(--text2); }
.ai-pv-cancel:hover { color: var(--text1); }
.ai-pv-apply { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; }
.ai-pv-apply:hover { filter: brightness(1.1); }
.ctx-menu { position: fixed; z-index: 300; min-width: 150px; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 6px; box-shadow: var(--shadow-1); }
.ctx-item { padding: 8px 14px; border-radius: 8px; font-size: 13px; color: var(--text2); cursor: pointer; transition: all .12s; }
.ctx-item:hover { background: color-mix(in srgb, var(--brand-1) 10%, transparent); color: var(--brand-1); }
.ctx-item.disabled { opacity: .45; cursor: default; }
.ctx-item.disabled:hover { background: none; color: var(--text2); }
.add-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); backdrop-filter: blur(4px); z-index: 200; display: flex; align-items: center; justify-content: center; }
.add-panel { width: 520px; max-width: 92vw; max-height: 80vh; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 18px; padding: 24px 26px; display: flex; flex-direction: column; }
.add-panel h3 { margin: 0 0 6px; font-size: 16px; color: var(--text1); }
.add-tip { margin: 0 0 14px; font-size: 12.5px; color: var(--text2); line-height: 1.7; }
.add-search { padding: 9px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1); font-size: 13.5px; margin-bottom: 12px; }
.add-list { overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.add-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--btn-bg); }
.add-title { flex: 1; font-size: 13.5px; color: var(--text1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.add-meta { font-size: 11px; color: var(--text2); border: 1px solid var(--border); border-radius: 999px; padding: 0 8px; }
.add-btn { padding: 5px 14px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--brand-1) 45%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); color: var(--brand-1); font-size: 12px; cursor: pointer; transition: all .15s; }
.add-btn:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; }
.add-btn.in { color: var(--text2); border-color: var(--border); background: var(--btn-bg); }
/* ═══ 阅览室 END ═══ */
.from-square { font-size: 10px; color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent); border: 1px solid color-mix(in srgb, var(--brand-1) 30%, transparent); padding: 1px 6px; border-radius: 999px; margin-left: 6px; vertical-align: middle; white-space: nowrap; }
</style>

<style>
/* 代码块：主题感知的半透明背景（浅色=浅灰，深色/星空=半透明深色），文字跟随主题色 */
.doc-card .markdown-body pre {
  background: color-mix(in srgb, var(--bg-soft) 80%, transparent) !important;
  color: var(--text1) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  padding: 16px !important;
  overflow-x: auto !important;
}
.doc-card .markdown-body pre code {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
}
/* 代码高亮配色：跟随主题变量（星空/深色=亮色系，浅色=鲜艳深色系），覆盖 hljs 默认暗淡配色 */
.doc-card .markdown-body .hljs-keyword, .doc-card .markdown-body .hljs-literal, .doc-card .markdown-body .hljs-selector-tag { color: var(--code-kw) !important; }
.doc-card .markdown-body .hljs-string, .doc-card .markdown-body .hljs-regexp, .doc-card .markdown-body .hljs-addition { color: var(--code-str) !important; }
.doc-card .markdown-body .hljs-number, .doc-card .markdown-body .hljs-symbol { color: var(--code-num) !important; }
.doc-card .markdown-body .hljs-comment, .doc-card .markdown-body .hljs-quote { color: var(--code-com) !important; font-style: italic; }
.doc-card .markdown-body .hljs-title, .doc-card .markdown-body .hljs-section, .doc-card .markdown-body .hljs-function .hljs-title, .doc-card .markdown-body .hljs-class .hljs-title { color: var(--code-tit) !important; }
.doc-card .markdown-body .hljs-type, .doc-card .markdown-body .hljs-built_in { color: var(--code-typ) !important; }
.doc-card .markdown-body .hljs-attr, .doc-card .markdown-body .hljs-attribute, .doc-card .markdown-body .hljs-selector-attr { color: var(--code-attr) !important; }
.doc-card .markdown-body .hljs-meta { color: var(--code-meta) !important; }
.doc-card .markdown-body .hljs-variable, .doc-card .markdown-body .hljs-template-variable { color: var(--code-typ) !important; }
.doc-card .markdown-body .hljs-deletion { color: var(--code-kw) !important; }
</style>
