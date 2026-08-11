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
import mathjax3 from 'markdown-it-mathjax3'
import alerts from 'markdown-it-github-alerts'
import toc from 'markdown-it-toc-done-right'
import { useFileListStore } from '@/stores/fileList.js'
import { storeToRefs } from 'pinia'
import { ArrowDown, Menu as IconMenu, Operation, MoreFilled } from '@element-plus/icons-vue'
import ThemeDropdown from '@/components/ThemeDropdown.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import DoodleBall from '@/components/DoodleBall.vue'
import { setupAnnotation, bindAnnotations, bindAnnGlobal } from '@/utils/annotation.js'

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
// >= 1400: 显示右侧边栏 (原为 1100，现在更严格以避免遮挡)
// < 1280: 使用 "..." 菜单切换主题
const showLeftSidebar = computed(() => windowWidth.value >= 960)
const showRightSidebar = computed(() => windowWidth.value >= 1400)
const isMobile = computed(() => windowWidth.value < 960)
// 当右侧边栏隐藏 (但非移动端) 时，需要显示大纲按钮
const showOutlineButton = computed(() => !showRightSidebar.value && !isMobile.value)

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
const rightSidebarCollapsed = ref(localStorage.getItem('kb_right_collapsed') === '1')   // 手动收起右侧大纲栏（带记忆）
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
  if (currentDoc.value) store.fetchDocBySlug(route.params.slug)
}

// 全局 AI 助手「去编辑页查看修改」→ 用当前文档 id 跳编辑页（编辑页会自动加载 AI 草稿并弹红绿 diff）
const onAiGotoCurrentEdit = () => {
  if (currentDoc.value) router.push('/edit/' + currentDoc.value.id)
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
  router.push('/edit/' + doc.id)
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
  router.push('/edit/' + doc.id)
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
  router.push('/edit/' + doc.id)
}
const cancelAiPreview = () => { aiPreview.value = null }

// 全局 AI 助手「打开笔记」→ 阅览室就地打开（不跳笔记广场）；不在本阅览室列表才降级跳广场
const onAiOpenNote = (e) => {
  const id = e.detail?.id
  if (!id) return
  if (currentDoc.value && currentDoc.value.id === id) {
    ElMessage.info('已在这篇笔记中')
    return
  }
  const doc = flatDocs.value.find(d => d.id === id)
  if (doc) {
    selectDoc(doc)
    ElMessage.success('已在阅览室打开《' + (doc.title || '') + '》')
  } else {
    router.push('/notes/' + id)
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
  router.push('/edit/' + doc.id)
}

// 侧栏收起
const toggleSidebar = () => { sidebarCollapsed.value = !sidebarCollapsed.value; localStorage.setItem('kb_sidebar_collapsed', sidebarCollapsed.value ? '1' : '0') }
const toggleRightSidebar = () => { rightSidebarCollapsed.value = !rightSidebarCollapsed.value; localStorage.setItem('kb_right_collapsed', rightSidebarCollapsed.value ? '1' : '0') }

// 右键菜单随全局点击关闭（原有 handleGlobalClick 已有类似逻辑）
onMounted(() => {
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

  
  store.fetchDocs()
  loadRoom()
  const slug = route.params.slug
  if (slug) store.fetchDocBySlug(slug)
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

watch(() => route.params.slug, (slug) => {
  if (slug) store.fetchDocBySlug(slug)
  showMenuDrawer.value = false // 导航时关闭抽屉
  // 滚动到顶部
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
  router.push(`/docs/${doc.slug}`)
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
    return ''; // 使用外部默认转义
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
md.use(mathjax3)
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
  if (!route.params.slug) return -1
  return flatDocs.value.findIndex(d => d.slug === route.params.slug)
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
  <div class="docs-layout">
    
    <!-- 移动端头部 (第一行: 标题 + 首页 + 菜单) -->
    <!-- 仅在左侧边栏隐藏时显示 (移动端) -->
    <header v-if="!showLeftSidebar" class="mobile-header-top">
      <div class="mobile-header-inner">
         <span class="site-title" @click="goHome">知屿</span>
         <div class="mobile-actions">
            <router-link to="/" class="nav-link-text">Home</router-link>
         </div>
      </div>
    </header>

    <!-- 移动端子头部 (第二行: 菜单 + 大纲) -->
    <div v-if="!showLeftSidebar" class="mobile-header-sub">
       <div class="sub-inner">
          <button class="icon-btn" @click="showMenuDrawer = true">
            <el-icon><IconMenu /></el-icon>
            <span class="btn-text">Menu</span>
          </button>
          
          <el-popover
            trigger="click"
            placement="bottom-end"
            :width="isMobile ? '92vw' : '400px'"
            popper-class="outline-popover"
            :teleported="true"
            :append-to-body="true"
          >
            <template #reference>
              <button class="icon-btn">
                <span class="btn-text">大纲</span>
                <el-icon><ArrowDown /></el-icon>
              </button>
            </template>
            <div class="popover-outline">
              <div class="outline-item return-top" @click="scrollToTop">Return to top</div>
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
      
      <!-- 左侧边栏 (桌面/平板)：收起时保留窄条（VSCode 式） -->
      <aside v-if="showLeftSidebar" class="left-sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div v-if="!sidebarCollapsed" class="left-sidebar-inner">
          <div class="sidebar-header">
             <span class="site-title" @click="goHome">知屿 <em class="room-tag">阅览室</em></span>
             <span class="group-ctrl">
               <button class="gc-btn" data-tip="添加笔记" @click="addOpen = true">＋</button>
               <button class="gc-btn" data-tip="收起侧栏" @click="toggleSidebar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg></button>
             </span>
          </div>
          <div class="sidebar-scroll">
            <div v-if="!auth.isLogin" class="side-empty">登录后使用你的阅览室</div>
            <div v-else-if="roomLoading" class="side-empty">加载中…</div>
            <div v-else-if="!grouped.length" class="side-empty">阅览室还没有笔记<br /><span class="side-empty-sub">去笔记广场或书房把笔记加入阅览室</span></div>
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
                  :class="{ active: route.params.slug === item.slug }"
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
        <button v-else class="sb-rail" data-tip="展开侧栏" data-tip-align="left" @click="toggleSidebar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg>
          <span class="sb-rail-text">目录</span>
        </button>
      </aside>

      <!-- 中间列包装器 (导航栏 + 内容) -->
      <div class="content-wrapper">
        <!-- 文档主要内容 -->
        <main class="doc-main">
          <div class="doc-container">
            <article class="doc-card">
              <!-- 右上角大纲浮钮（当右侧大纲栏隐藏时） -->
              <el-popover
                v-if="showOutlineButton"
                trigger="click"
                placement="bottom-end"
                :width="300"
                popper-class="outline-popover"
                :teleported="true"
              >
                <template #reference>
                  <button class="outline-fab" aria-label="Table of Contents">
                    <el-icon><Operation /></el-icon>
                    <span>大纲</span>
                  </button>
                </template>
                <div class="popover-outline">
                  <div class="outline-item return-top" @click="scrollToTop">Return to top</div>
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
              <div class="doc-tools" v-if="currentDoc && (isMyDoc(currentDoc) || auth.user?.role === 'admin')">
                <button class="tool-btn" @click="editCurrent">✏️ 编辑此页</button>
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
              <div class="markdown-body" v-html="rendered" @click="onContentClick"></div>
              <ImageViewer :visible="viewerOpen" :url="viewerUrl" @close="viewerOpen = false" />
              <DoodleBall v-if="currentDoc" target=".doc-card" :doc-id="currentDoc.id" :is-mine="isMyDoc(currentDoc)" />
              <div class="doc-footer">
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
        <div v-if="!rightSidebarCollapsed" class="right-sidebar-inner">
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
        <button v-else class="sb-rail" data-tip="展开大纲" data-tip-align="right" @click="toggleRightSidebar">
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
                :class="{ active: route.params.slug === item.slug }"
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

/* --- Mobile Headers --- */
.mobile-header-top {
  height: 56px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg);
  position: sticky;
  top: 0;
  z-index: 20;
}
.mobile-header-inner {
  max-width: var(--layout-max);
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}
.mobile-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mobile-header-sub {
  height: 48px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg);
  position: sticky;
  top: 56px;
  z-index: 19;
}
.sub-inner {
  max-width: var(--layout-max);
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

/* --- Desktop Layout --- */
.main-wrapper {
  display: grid;
  width: 100%;
  /* VSCode 式三栏：左/右侧栏宽度由内容决定（可动画收缩），中间内容区自适应 */
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas: 'left main right';
  position: relative;
  /* Removed overflow-x: hidden to prevent breaking sticky positioning if container height is constrained */
}

/* Left Sidebar */
.left-sidebar {
  grid-area: left;
  /* Default: Dynamic Spacer Mode (Wide Screen) */
  flex: 1; 
  min-width: 0;
  background: var(--c-sidebar-bg);
  display: flex;
  flex-direction: column;
  align-items: flex-end; /* Stick content to the right (next to doc) */
  border-right: 1px solid transparent; 
  /* Ensure it stretches to full height of parent so sticky child can move within it */
  align-self: stretch; 
}

.left-sidebar-inner {
  width: 262px;
  min-width: 262px;
  height: calc(100vh - 60px); /* 避开全局导航 */
  position: sticky;
  top: 60px; /* 全局导航下方，让侧栏往左上靠 */
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

/* 品牌区：与顶部有明显留白，去掉硬分隔线，靠留白分区 */
.group-ctrl { display: inline-flex; gap: 2px; }
.gc-btn {
  width: 26px; height: 26px; border-radius: 8px; cursor: pointer;
  border: none; background: transparent;
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

/* 侧栏收起：宽度 280 → 48 动画（grid 列为 auto，跟随宽度平滑伸缩），另一侧栏不动 */
.main-wrapper.sidebar-collapsed .left-sidebar { width: 48px; }
.main-wrapper.right-collapsed .right-sidebar { width: 48px; }
.left-sidebar { width: 280px; transition: width .3s ease; }
.right-sidebar { width: 280px; transition: width .3s ease; }
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
  width: 100%; height: 100%;
  border: none; background: transparent; cursor: pointer;
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
  flex: 1; /* Dynamic Spacer */
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start; /* Align content to left (next to doc) */
  align-self: stretch; 
}

.right-sidebar-inner {
  width: 100%; /* Fill available space */
  min-width: 260px;
  height: calc(100vh - 60px); 
  position: sticky;
  top: 60px; /* 与左侧导航栏同高对齐 */
  padding: 20px 0 24px; 
  overflow-y: auto;
  overflow-x: hidden;
}

/* 大纲标题行：收缩按钮在"大纲"文字左边，垂直居中 */
.outline-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.rs-collapse-btn {
  width: 26px; height: 26px; flex-shrink: 0; border-radius: 8px; cursor: pointer;
  border: none; background: transparent; color: var(--text2);
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
    grid-template-columns: 270px minmax(0, 1fr);
    grid-template-areas: 'left main';
  }
  .main-wrapper.sidebar-collapsed {
    grid-template-columns: 48px minmax(0, 1fr);
    grid-template-areas: 'left main';
  }
  
  .left-sidebar {
    /* 切换到固定宽度 */
    grid-area: left;
    flex: 0 0 270px;
    width: 270px;
    align-items: stretch; /* 填充宽度 */
  }
  
  .left-sidebar-inner {
    width: 100%;
    min-width: 0;
  }
  
  .content-wrapper {
    /* 切换到流式宽度 */
    grid-area: main;
    flex: 1;
    width: auto;
    max-width: 1000px; /* 可选的最大宽度以提高可读性 */
  }
  
  /* 右侧边栏在这里可能被 JS 隐藏，但如果没有，它会挤压内容。 
     JS 应确保在 ~1400px 以下 showRightSidebar 为 false。 */
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
.outline-item.return-top {
  border-bottom: 1px solid var(--c-border);
  margin-bottom: 4px;
  font-weight: 500;
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
  .doc-container {
    padding: 24px 24px;
  }
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

/* 移动端头部：避开全局导航，毛玻璃化 */
.mobile-header-top {
  top: 60px;
  background: color-mix(in srgb, var(--c-bg) 78%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
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
.doc-card {
  position: relative;
  border-radius: 20px;
  border: 1px solid var(--c-border);
  box-shadow: var(--shadow-1);
  background: color-mix(in srgb, var(--c-bg) 82%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
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

/* 右上角大纲浮钮：毛玻璃小胶囊，悬浮在卡片右上角 */
.outline-fab {
  position: absolute;
  top: 16px;
  right: 20px;
  z-index: 5;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 13px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: color-mix(in srgb, var(--c-bg) 55%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: var(--c-text-2);
  font-size: 12.5px;
  cursor: pointer;
  transition: all .25s;
}
.outline-fab:hover {
  color: var(--brand-1);
  border-color: color-mix(in srgb, var(--brand-1) 45%, transparent);
  box-shadow: 0 4px 14px color-mix(in srgb, var(--brand-1) 20%, transparent);
}
/* 锚点 # 相对标题定位，让锚点落在卡片内侧 */
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  position: relative;
}
/* 文档大标题（h1）右侧留出大纲按钮空间，避免遮挡 */
:deep(.markdown-body h1) {
  padding-right: 96px;
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
.doc-tools { display: flex; justify-content: flex-end; margin-bottom: 14px; }
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
