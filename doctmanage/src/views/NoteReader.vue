<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { full as emoji } from 'markdown-it-emoji'
import mathjax3 from 'markdown-it-mathjax3'
import mdImgSize from '@/utils/mdImgSize.js'
import anchor from 'markdown-it-anchor'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'
import ImageViewer from '@/components/ImageViewer.vue'
import DoodleBall from '@/components/DoodleBall.vue'
import { setupAnnotation, bindAnnotations, bindAnnGlobal } from '@/utils/annotation.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const doc = ref(null)
const loading = ref(true)
const notFound = ref(false)
const interact = ref({ liked: false, favorited: false, shared: false })
const comments = ref([])
const commentText = ref('')
const commentAnchor = ref('')
const busy = ref(false)
// ── 主题评分 ──
const dimLabels = { professional: '专业', practical: '实用', readable: '易读', insight: '感悟' }
const allTags = ['简洁明了', '内容充实', '值得一读', '干货满满', '有所收获']
const rating = ref({ count: 0, total: 0, dims: {}, tags: {}, mine: null, my_tags: [], remaining_today: 3 })
const rateOpen = ref(false)
const rateForm = ref({ professional: 0, practical: 0, readable: 0, insight: 0, tags: [] })
const loadRating = async () => {
  try {
    const res = await api.get(`/notes/${docId.value}/rating`)
    rating.value = res.data
  } catch (e) { /* 忽略 */ }
}
const openRate = () => {
  if (!requireLogin()) return
  const m = rating.value.mine || {}
  rateForm.value = { professional: m.professional || 0, practical: m.practical || 0, readable: m.readable || 0, insight: m.insight || 0, tags: [...(rating.value.my_tags || [])] }
  rateOpen.value = true
}
const toggleTag = (t) => {
  const i = rateForm.value.tags.indexOf(t)
  if (i >= 0) rateForm.value.tags.splice(i, 1)
  else rateForm.value.tags.push(t)
}
const submitRating = async () => {
  const vals = [rateForm.value.professional, rateForm.value.practical, rateForm.value.readable, rateForm.value.insight]
  if (vals.some(v => v < 1 || v > 5)) { ElMessage.warning('请为专业、实用、易读、感悟各打 1-5 星'); return }
  busy.value = true
  try {
    const res = await api.post(`/notes/${docId.value}/rating`, { ...rateForm.value })
    ElMessage.success(res.data.earned ? '评分成功，获得 2 知屿币' : '评分已更新')
    rateOpen.value = false
    await loadRating()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '评分失败')
  }
  busy.value = false
}
const stars = (v) => {
  const n = Math.max(0, Math.min(5, Math.round(Number(v) || 0)))
  return '★'.repeat(n) + '☆'.repeat(5 - n)
}
const pct = (n) => (rating.value.count > 0 ? Math.round(n / rating.value.count * 100) : 0)
// 雷达图（5 轴 = 5 个评价标签，数值 = 占比）
const radarCx = 110, radarCy = 96, radarR = 60
const radarAngle = (i) => -Math.PI / 2 + (i - 1) * 2 * Math.PI / 5
const radarTag = (i) => Object.keys(rating.value.tags)[i - 1] || ''
const radarTip = (i, ratio) => [radarCx + radarR * ratio * Math.cos(radarAngle(i)), radarCy + radarR * ratio * Math.sin(radarAngle(i))]
const radarRatio = (i) => {
  const n = rating.value.tags[radarTag(i)] || 0
  return rating.value.count > 0 ? n / rating.value.count : 0
}
const radarPoly = (gridRatio) => {
  const pts = []
  for (let i = 1; i <= 5; i++) {
    const ratio = gridRatio != null ? gridRatio : radarRatio(i)
    const [x, y] = radarTip(i, ratio)
    pts.push(x.toFixed(1) + ',' + y.toFixed(1))
  }
  return pts.join(' ')
}
// 占比提示：跟随鼠标，显示在鼠标右上方
const tipShow = ref(false)
const tipX = ref(0)
const tipY = ref(0)
const onRateMove = (e) => {
  tipShow.value = true
  tipX.value = e.offsetX + 14
  tipY.value = e.offsetY - 148
}
// 定位当前阅读位置的段落作为评论锚点
const pickAnchor = () => {
  // 1) 优先定位当前视口中的小标题（h2/h3/h4）
  const headings = document.querySelectorAll('.markdown-body h2, .markdown-body h3, .markdown-body h4')
  const mid = window.scrollY + window.innerHeight * 0.4
  let best = null
  for (const h of headings) {
    if (h.getBoundingClientRect().top + window.scrollY <= mid) best = h
    else break
  }
  if (best) {
    commentAnchor.value = best.innerText.trim().slice(0, 60)
    ElMessage.success('已定位段落：' + commentAnchor.value)
    return
  }
  // 2) 兜底：取当前视口内第一个段落文本前 40 字作为锚点
  const midY = window.scrollY + window.innerHeight * 0.4
  const paras = document.querySelectorAll('.markdown-body p, .markdown-body li')
  for (const p of paras) {
    const rect = p.getBoundingClientRect()
    if (rect.top + window.scrollY > midY - 200 && rect.top + window.scrollY < midY + 300) {
      const txt = p.innerText.trim().slice(0, 40)
      if (txt) { commentAnchor.value = txt; ElMessage.success('已定位到该段落'); return }
    }
  }
  commentAnchor.value = ''
  ElMessage.info('未找到可定位的段落，将作为整篇评论')
}
const readStart = ref(Date.now())
const reported = ref(0)

const slugify = (s) => {
  const text = String(s || '').replace(/<[^>]+>/g, '')
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'section'
}
const md = new MarkdownIt({ html: false, linkify: true, breaks: true, highlight: (code, lang) => {
  if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value
  return hljs.highlightAuto(code).value
}}).use(anchor, {
  level: [1, 2, 3],
  slugify,
  permalink: anchor.permalink.linkInsideHeader({ symbol: '§', class: 'header-anchor', placement: 'before' }),
}).use(emoji).use(mathjax3).use(mdImgSize)
setupAnnotation(md)
const rendered = computed(() => doc.value ? md.render(doc.value.content) : '')

const docId = computed(() => Number(route.params.id))

// ── 阅读大纲 ──
const outline = ref([])
const outlineOpen = ref(false)
const activeId = ref('')
const collectOutline = () => {
  const mb = document.querySelector('.markdown-body')
  const hs = mb ? [...mb.querySelectorAll('h1, h2, h3')] : []
  outline.value = hs.map(h => ({ id: h.id, title: h.innerText.trim().slice(0, 40), level: Number(h.tagName[1]) }))
}
const scrollToHeading = (id) => {
  const el = document.getElementById(id)
  if (el) {
    const top = el.getBoundingClientRect().top + window.scrollY - 90
    window.scrollTo({ top, behavior: 'auto' })
    outlineOpen.value = false
  }
}
const readProgress = ref(0)
const onScrollProgress = () => {
  const h = document.documentElement.scrollHeight - window.innerHeight
  readProgress.value = h > 0 ? Math.min(100, Math.round((window.scrollY / h) * 100)) : 0
}
const onScrollOutline = () => {
  if (!outline.value.length) return
  const mid = window.scrollY + window.innerHeight * 0.3
  let cur = ''
  for (const h of outline.value) {
    const el = document.getElementById(h.id)
    if (el && el.getBoundingClientRect().top + window.scrollY <= mid) cur = h.id
  }
  activeId.value = cur
}
const outlineWatch = watch(rendered, () => {
  collectOutline()
  bindAnnotations(document.querySelector('.reader-card .markdown-body'), annMap.value, { editable: false })
  window.dispatchEvent(new Event('zhiyu:doodle-reflow'))
  loadAnnData()
}, { flush: 'post' })

// 路由切换（上一篇/下一篇）时重新加载
watch(() => route.params.id, () => {
  doc.value = null
  comments.value = []
  outline.value = []
  interact.value = {}
  prevNote.value = null
  nextNote.value = null
  summaryOpen.value = false
  load()
})
const immersive = ref(false)

// 全局 AI 助手「写评论」动作 → 填评论框
const onAiComment = (e) => {
  const text = e.detail?.text
  if (!text) return
  commentText.value = text
  nextTick(() => inputRef.value?.focus())
  ElMessage.success('AI 评论草稿已填入，可修改后发表')
}

// 全局 AI 助手「插入笔记」动作 → 把 AI 内容追加到当前笔记（仅限自己的笔记）
const onAiInsert = async (e) => {
  const text = (e.detail?.text || '').trim()
  if (!text || !doc.value) return
  if (doc.value.user_id !== auth.user?.id) {
    ElMessage.warning('这是别人的笔记，不能直接插入；可用「存为笔记」保存到你的书房')
    return
  }
  // 统一走 diff 预览：写入草稿并跳编辑页，编辑页自动弹红绿 diff，用户确认后才保存（不再直接写库）
  try {
    localStorage.setItem('zhiyu_draft_' + docId.value, JSON.stringify({
      title: doc.value.title, type: doc.value.type || '笔记', visibility: doc.value.visibility,
      content: (doc.value.content || '') + '\n\n' + text, ts: Date.now(), ai: true,
    }))
  } catch (err) {}
  router.push('/edit/' + docId.value)
}
const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/docs/' + docId.value)
    doc.value = res.data
    const st = await api.get(`/notes/${docId.value}/interact`)
    interact.value = st.data
    const cm = await api.get(`/notes/${docId.value}/comments`)
    comments.value = cm.data
    window.__cmt = { api: cm.data.length, dom: comments.value.length }
    readStart.value = Date.now()
  } catch (e) {
    if (e.response?.status === 403 || e.response?.status === 404) notFound.value = true
  }
  loading.value = false
  await nextTick()
  collectOutline()
  loadAuthor()
  loadRating()
  loadNeighbors()
  // 通知跳转：?focus=comment 时定位到评论区
  if (route.query.focus === 'comment') {
    await nextTick()
    setTimeout(() => {
      const el = document.querySelector('.comment-box')
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 350)
  }
}

// 阅读时长上报（离开页面或每 60s）
const reportRead = async () => {
  const secs = Math.floor((Date.now() - readStart.value) / 1000) - reported.value
  if (secs < 5) return
  reported.value += secs
  try { await api.post(`/notes/${docId.value}/read`, { seconds: secs }) } catch (e) { /* 忽略 */ }
}
let readTimer = null
onMounted(() => {
  bindAnnGlobal({ onDel: onDelAnn })
  load()
  readTimer = setInterval(reportRead, 60000)
  window.addEventListener('scroll', onScrollOutline, { passive: true })
  window.addEventListener('scroll', onScrollProgress, { passive: true })
  window.addEventListener('zhiyu:ai-comment', onAiComment)
  window.addEventListener('zhiyu:ai-insert', onAiInsert)
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScrollOutline)
  window.removeEventListener('scroll', onScrollProgress)
  window.removeEventListener('zhiyu:ai-comment', onAiComment)
  window.removeEventListener('zhiyu:ai-insert', onAiInsert)
})
onBeforeUnmount(() => {
  clearInterval(readTimer)
  reportRead()
})

const requireLogin = () => {
  if (!auth.isLogin) { ElMessage.warning('请先登录'); router.push('/login'); return false }
  return true
}
const toggleLike = async () => {
  if (!requireLogin()) return
  try {
    if (interact.value.liked) await api.delete(`/notes/${docId.value}/like`)
    else await api.post(`/notes/${docId.value}/like`)
    interact.value.liked = !interact.value.liked
    doc.value.likes_count += interact.value.liked ? 1 : -1
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
const toggleFav = async () => {
  if (!requireLogin()) return
  try {
    if (interact.value.favorited) await api.delete(`/notes/${docId.value}/favorite`)
    else await api.post(`/notes/${docId.value}/favorite`)
    interact.value.favorited = !interact.value.favorited
    doc.value.favorites_count += interact.value.favorited ? 1 : -1
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
const share = async () => {
  if (!requireLogin()) return
  try {
    if (!interact.value.shared) {
      await api.post(`/notes/${docId.value}/share`)
      interact.value.shared = true
      ElMessage.success('已转发到你的主页')
    } else ElMessage.info('已转发过')
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
const download = async () => {
  try {
    const res = await api.post(`/notes/${docId.value}/download`)
    const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = (res.data.title || 'note') + '.md'
    a.click()
    URL.revokeObjectURL(a.href)
    doc.value.downloads_count += 1
    ElMessage.success('下载成功')
  } catch (e) { ElMessage.error('下载失败') }
}
const replyTarget = ref(null)
const inputRef = ref(null)
const startReply = (c) => {
  if (!requireLogin()) return
  replyTarget.value = c
  commentText.value = ''
  inputRef.value?.focus()
}
const cancelReply = () => { replyTarget.value = null }
const sendComment = async () => {
  if (!requireLogin()) return
  const content = commentText.value.trim()
  if (!content) return
  busy.value = true
  try {
    await api.post(`/notes/${docId.value}/comments`, { content, anchor: commentAnchor.value, parent_id: replyTarget.value?.id || null })
    commentText.value = ''
    commentAnchor.value = ''
    replyTarget.value = null
    doc.value.comments_count += 1
    const cm = await api.get(`/notes/${docId.value}/comments`)
    comments.value = cm.data
    window.__cmt = { api: cm.data.length, dom: comments.value.length }
    ElMessage.success('评论成功')
  } catch (e) { ElMessage.error(e.response?.data?.error || '评论失败') }
  busy.value = false
}
const goUser = (uid) => { if (uid) router.push('/user/' + uid) }
const openNote = (id) => { if (id) router.push('/notes/' + id) }

// ── 评论 emoji 快捷 ──
const emojis = ['👍', '🔥', '😂', '💯', '🙏', '📚', '💡', '✨', '❤️', '👏']
const emojiOpen = ref(false)
const insertEmoji = (e) => { commentText.value += e }
// ── 上一篇 / 下一篇 ──
const prevNote = ref(null)
const nextNote = ref(null)
const loadNeighbors = async () => {
  try {
    const res = await api.get('/docs?scope=public')
    const all = res.data || []
    const idx = all.findIndex(n => n.id === docId.value)
    if (idx > 0) prevNote.value = all[idx - 1] || null
    if (idx >= 0 && idx < all.length - 1) nextNote.value = all[idx + 1] || null
  } catch (e) { /* 忽略 */ }
}

// ── AI 总结 ──
const summary = ref('')
const summaryLoading = ref(false)
const summaryOpen = ref(false)
const summaryMd = (t) => md.render(t)
const renderCmt = (t) => md.render(t || '')

// ── 正文图片点击放大 / 批注交互 ──
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
  if (!auth.isLogin || doc.value?.user_id !== auth.user?.id) { ElMessage.warning('只能删除自己笔记的批注'); return }
  const id = block.getAttribute('data-ann-id') || ''
  try {
    let newContent = doc.value.content || ''
    if (id) {
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
    if (newContent === (doc.value.content || '')) { block.remove(); return }
    await api.put('/docs/' + docId.value, { content: newContent, type: doc.value.type, title: doc.value.title })
    doc.value.content = newContent
    ElMessage.success('批注已删除')
  } catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
}

// 批注记录加载（新格式批注：文字/笔迹存 note_annotations，按 id 拉取渲染）
const annMap = ref({})
const loadAnnData = async () => {
  if (!docId.value) return
  try {
    const res = await api.get('/notes/' + docId.value + '/annotations')
    const m = {}
    for (const r of res.data || []) {
      if (r.kind === 'note') m[r.id] = { note_text: r.note_text || '', strokes: Array.isArray(r.strokes) ? r.strokes : [], canvas_w: r.canvas_w || 0, canvas_h: r.canvas_h || 0 }
    }
    annMap.value = m
    bindAnnotations(document.querySelector('.reader-card .markdown-body'), annMap.value, { editable: false })
  } catch (e) { /* 忽略 */ }
}
const aiSummary = async () => {
  if (!requireLogin()) return
  summaryOpen.value = true
  summaryLoading.value = true
  summary.value = ''
  try {
    const token = localStorage.getItem('kb_token') || ''
    const resp = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({ question: '请总结这篇笔记的核心要点（分点列出），并说明哪些地方需要特别注意', note_id: docId.value, stream: true }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      summary.value = err.error === 'AI 额度已用完，可去积分商城兑换' ? '⚠️ AI 额度已用完，可去积分商城兑换' : '😅 总结失败：' + (err.error || '网络异常')
    } else {
      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop()
        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data:'))
          if (!line) continue
          try {
            const obj = JSON.parse(line.slice(5).trim())
            if (obj.delta) summary.value += obj.delta
            else if (obj.error) summary.value += '\n😅 ' + obj.error
          } catch (e) { /* 忽略 */ }
        }
      }
    }
  } catch (e) {
    summary.value = '😅 网络异常：' + e.message
  }
  summaryLoading.value = false
}

// ── 作者卡片 ──
const author = ref(null)
const authorNotes = ref([])
const friendState = ref('')
const loadAuthor = async () => {
  if (!doc.value?.user_id) return
  try {
    const [ap, an] = await Promise.all([
      api.get('/users/' + doc.value.user_id),
      api.get(`/users/${doc.value.user_id}/notes?scope=public`),
    ])
    author.value = ap.data
    authorNotes.value = (an.data || []).filter(n => n.id !== docId.value).slice(0, 15)
    if (auth.isLogin && auth.user?.id !== doc.value.user_id) {
      const fr = await api.get('/friends')
      if (fr.data?.list) {
        const f = fr.data.list.find(x => x.other_id === doc.value.user_id)
        friendState.value = f ? (f.status === 'accepted' ? '好友' : '申请中') : ''
      }
    }
  } catch (e) { /* 忽略 */ }
}
const sendFriendReq = async () => {
  if (!requireLogin()) return
  try {
    await api.post('/friends/request', { user_id: doc.value.user_id })
    friendState.value = '申请中'
    ElMessage.success('好友申请已发送')
  } catch (e) { ElMessage.error(e.response?.data?.error || '发送失败') }
}
</script>

<template>
  <div class="reader-page">
    <div class="reading-bar" :style="{ width: readProgress + '%' }"></div>
    <div v-if="loading" class="center-hint">加载中…</div>
    <div v-else-if="notFound" class="center-hint">
      笔记不存在或没有权限查看
      <div><button class="back-btn" @click="router.push('/notes')">返回广场</button></div>
    </div>

    <div v-else class="reader-layout">
      <!-- 左栏：该作者的笔记 -->
      <aside class="nr-side nr-left">
        <div class="nr-side-head">
          <span class="nr-author" @click="goUser(doc.user_id)">
            <span class="avatar-mini">{{ (doc.author_nickname || doc.author_username || '?').slice(0, 1) }}</span>
            <span class="nr-author-name">{{ doc.author_nickname || doc.author_username || '系统' }}</span>
          </span>
        </div>
        <div class="nr-side-sub">TA 的笔记</div>
        <div class="nr-list">
          <div v-for="n in authorNotes" :key="n.id" class="nr-item" :class="{ on: n.id === docId }" @click="router.push('/notes/' + n.id)">
            <span class="nr-item-title">{{ n.title }}</span>
          </div>
          <div v-if="!authorNotes.length" class="nr-empty">暂无其他公开笔记</div>
        </div>
      </aside>

      <article class="reader-card">
        <div class="reader-head">
          <h1 class="reader-title">{{ doc.title }}</h1>
          <div class="reader-meta">
            <span class="author" @click="goUser(doc.user_id)">
              <span class="avatar-mini">{{ (doc.author_nickname || doc.author_username || '?').slice(0, 1) }}</span>
              {{ doc.author_nickname || doc.author_username || '系统' }}
            </span>
            <span class="type-badge">{{ doc.type }}</span>
            <span class="time">{{ doc.updated_at }}</span>
          </div>
        </div>

        <div class="markdown-body" v-html="rendered" @click="onContentClick"></div>
        <ImageViewer :visible="viewerOpen" :url="viewerUrl" @close="viewerOpen = false" />
        <DoodleBall v-if="doc" target=".reader-card" :doc-id="docId" :is-mine="doc.user_id === auth.user?.id" />

        <!-- 互动条 -->
        <div class="action-bar">
          <button class="act-btn" :class="{ on: interact.liked }" @click="toggleLike">
            👍 {{ doc.likes_count }}
          </button>
          <button class="act-btn" :class="{ on: interact.favorited }" @click="toggleFav">
            ⭐ {{ doc.favorites_count }}
          </button>
          <button class="act-btn" :class="{ on: interact.shared }" @click="share">↗ 转发</button>
          <button class="act-btn" @click="download">⬇ 下载 {{ doc.downloads_count }}</button>
          <button class="act-btn" :class="{ on: summaryOpen }" @click="aiSummary">🤖 AI 总结</button>
        </div>

        <!-- AI 总结面板 -->
        <div v-if="summaryOpen" class="summary-panel">
          <div class="summary-head">
            <span>🤖 AI 总结</span>
            <span v-if="summaryLoading" class="summary-loading">生成中…</span>
            <span class="anchor-x" @click="summaryOpen = false">✕</span>
          </div>
          <div class="summary-body" v-html="summaryMd(summary)"></div>
        </div>

        <!-- 作者卡片 -->
        <div v-if="author" class="author-card">
          <div class="author-left">
            <span class="author-avatar" @click="goUser(author.id)">
              {{ (author.nickname || author.username || '?').slice(0, 1) }}
            </span>
            <div class="author-info">
              <div class="author-name" @click="goUser(author.id)">
                {{ author.nickname || author.username }}
                <span v-if="author.badge === 'scholar'" class="badge-gold">🏅 学霸</span>
                <span class="author-uid">@{{ author.username }}</span>
              </div>
              <div class="author-bio">{{ author.bio || '这个人很懒，什么也没写' }}</div>
            </div>
          </div>
          <div class="author-right">
            <button v-if="auth.isLogin && auth.user?.id !== author.id && !friendState" class="fr-btn" @click="sendFriendReq">＋ 加好友</button>
            <span v-else-if="friendState === '好友'" class="fr-state">✓ 已是好友</span>
            <span v-else-if="friendState === '申请中'" class="fr-state">⏳ 申请中</span>
          </div>
          <div v-if="authorNotes.length" class="author-notes">
            <span class="an-label">TA 的其他笔记：</span>
            <span v-for="n in authorNotes" :key="n.id" class="an-item" @click="openNote(n.id)">{{ n.title }}</span>
          </div>
        </div>

        <!-- 主题评分 -->
        <div class="rate-section">
          <div class="rate-bar">
            <button class="rate-btn" @click="openRate">⭐ 主题评分</button>
            <span class="rate-count">{{ rating.count }} 人已评分</span>
          </div>
          <div v-if="rating.count > 0" class="rate-stats">
            <div class="rate-left">
              <div class="rate-score">{{ rating.total }}<span class="rate-score-max"> / 10</span></div>
              <div class="rate-score-label">综合得分<span class="rate-q" :data-tip="'综合得分 = 专业、实用、易读、感悟四维平均 ×2，满分 10 分'">ⓘ</span></div>
              <div class="rate-people">共 {{ rating.count }} 人参与评分</div>
            </div>
            <div class="rate-mid">
              <div v-for="(label, key) in dimLabels" :key="key" class="rate-dim">
                <span class="rd-name">{{ label }}</span>
                <span class="rd-stars">{{ stars(rating.dims[key] || 0) }}</span>
              </div>
            </div>
            <div class="rate-right" @mousemove="onRateMove" @mouseleave="tipShow = false">
              <div class="rt-tooltip" :class="{ show: tipShow }" :style="{ left: tipX + 'px', top: tipY + 'px' }">
                <div class="rtt-title">用户评价占比(%)</div>
                <div v-for="(n, tag) in rating.tags" :key="tag" class="rtt-row">
                  <span class="rtt-dot">·</span>{{ tag }}<b>{{ pct(n) }}</b>
                </div>
              </div>
              <svg class="radar" viewBox="0 0 220 200">
                <polygon v-for="l in [0.33, 0.66, 1]" :key="'g' + l" :points="radarPoly(l)" class="radar-grid" />
                <line v-for="i in 5" :key="'a' + i" :x1="radarTip(i, 1)[0]" :y1="radarTip(i, 1)[1]" :x2="radarCx" :y2="radarCy" class="radar-axis" />
                <polygon :points="radarPoly(null)" class="radar-data" />
                <circle v-for="i in 5" :key="'d' + i" :cx="radarTip(i, radarRatio(i))[0]" :cy="radarTip(i, radarRatio(i))[1]" r="3" class="radar-dot" />
                <text v-for="i in 5" :key="'t' + i" :x="radarTip(i, 1.32)[0]" :y="radarTip(i, 1.32)[1]" text-anchor="middle" class="radar-label">{{ radarTag(i) }}</text>
              </svg>
            </div>
          </div>
        </div>

        <!-- 评论区 -->
        <div class="comment-box">
          <h3 class="comment-title">评论（{{ doc.comments_count }}）</h3>
          <div v-if="commentAnchor" class="comment-anchor">📍 评论段落：{{ commentAnchor }} <span class="anchor-x" @click="commentAnchor = ''">✕</span></div>
          <div v-if="replyTarget" class="reply-banner">
            ↪ 回复 <b>@{{ replyTarget.nickname || replyTarget.username }}</b> <span class="anchor-x" @click="cancelReply">✕</span>
          </div>
          <div class="comment-input-row">
            <div class="emoji-wrap">
              <button class="anchor-btn" data-tip="插入表情" @click="emojiOpen = !emojiOpen">😊</button>
              <Transition name="bell-panel">
                <div v-if="emojiOpen" class="emoji-panel">
                  <button v-for="e in emojis" :key="e" class="emoji-item" @click="insertEmoji(e)">{{ e }}</button>
                </div>
              </Transition>
            </div>
            <input ref="inputRef" v-model="commentText" class="comment-input" :placeholder="replyTarget ? '回复 @' + (replyTarget.nickname || replyTarget.username) + '…' : '写下你的评论…'" @keyup.enter="sendComment" />
            <button class="anchor-btn" data-tip="定位到当前阅读段落" @click="pickAnchor">📍</button>
            <button class="comment-send" :disabled="busy" @click="sendComment">发表</button>
          </div>
          <div v-if="comments.length === 0" class="no-comment">还没有评论，抢个沙发</div>
          <div v-for="c in comments" :key="c.id" class="comment-item" :class="{ &quot;has-parent&quot;: c.parent_id }">
            <span class="c-avatar">
              <img v-if="c.avatar" :src="c.avatar" alt="avatar" />
              <span v-else>{{ (c.nickname || c.username || '?').slice(0, 1) }}</span>
            </span>
            <div class="c-body">
              <div v-if="c.anchor" class="c-anchor">📍 {{ c.anchor }}</div>
              <div class="c-meta">
                <span class="c-name" @click="goUser(c.user_id)">{{ c.nickname || c.username }}</span>
                <span v-if="c.parent_id" class="c-reply-to">回复 @{{ c.parent_nickname || c.parent_username }}</span>
                <span class="c-time">{{ c.created_at }}</span>
              </div>
              <div class="c-content" v-html="renderCmt(c.content)"></div>
              <button class="c-reply-btn" @click="startReply(c)">回复</button>
            </div>
          </div>
        </div>

        <!-- 上一篇 / 下一篇 -->
        <div class="prev-next">
          <div v-if="prevNote" class="pn-item" @click="openNote(prevNote.id)">
            <span class="pn-dir">← 上一篇</span>
            <span class="pn-title">{{ prevNote.title }}</span>
          </div>
          <div v-else class="pn-item disabled">← 已是第一篇</div>
          <div v-if="nextNote" class="pn-item right" @click="openNote(nextNote.id)">
            <span class="pn-dir">下一篇 →</span>
            <span class="pn-title">{{ nextNote.title }}</span>
          </div>
          <div v-else class="pn-item disabled right">已是最后一篇 →</div>
        </div>
      </article>

      <!-- 右栏：阅读大纲 -->
      <aside class="nr-side nr-right">
        <div class="nr-side-head"><span class="nr-side-title">📑 大纲</span></div>
        <div class="nr-outline">
          <div
            v-for="h in outline" :key="h.id"
            class="nr-ol-item"
            :class="{ 'indent-2': h.level === 2, 'indent-3': h.level === 3, active: activeId === h.id }"
            @click="scrollToHeading(h.id)"
          >{{ h.title }}</div>
          <div v-if="outline.length === 0" class="nr-empty">本篇暂无小节标题</div>
        </div>
      </aside>
    </div>

    <!-- 主题评分弹窗 -->
    <div v-if="rateOpen" class="rate-modal" @click.self="rateOpen = false">
      <div class="rate-dialog">
        <div class="rate-dialog-head">
          <span>主题评分</span>
          <span class="anchor-x" @click="rateOpen = false">✕</span>
        </div>
        <div class="rate-dialog-sub">
          <span class="rds-mine">我的评分</span>
          <span class="rds-record">评分记录({{ rating.count }})</span>
        </div>
        <div class="rate-dialog-note">注：请根据实际情况进行评分，恶意评分将受到处罚。参与评分后可获得 <b>2 知屿币</b> 奖励。今日剩余 <b>{{ rating.remaining_today }}</b> 次。</div>
        <div class="rate-dialog-dims">
          <div v-for="(label, key) in dimLabels" :key="key" class="rdd-row">
            <span class="rdd-name">{{ label }}</span>
            <span class="rdd-stars">
              <span v-for="i in 5" :key="i" class="rdd-star" :class="{ on: rateForm[key] >= i }" @click="rateForm[key] = i">{{ i <= rateForm[key] ? '★' : '☆' }}</span>
            </span>
          </div>
        </div>
        <div class="rate-dialog-tags">
          <span class="rdt-label">主题评价：</span>
          <span v-for="t in allTags" :key="t" class="rdt-pill" :class="{ on: rateForm.tags.includes(t) }" @click="toggleTag(t)">{{ t }}</span>
        </div>
        <div class="rate-dialog-foot">
          <button class="rdf-cancel" @click="rateOpen = false">取消</button>
          <button class="rdf-save" :disabled="busy" @click="submitRating">提交评分</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reader-page { min-height: 100vh; padding: 92px 24px 60px; box-sizing: border-box; transition: padding .3s; }
.reading-bar {
  position: fixed; top: 0; left: 0; height: 3px; z-index: 120;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
  border-radius: 0 3px 3px 0;
  transition: width .15s ease-out;
  box-shadow: 0 0 8px color-mix(in srgb, var(--brand-1) 55%, transparent);
}
.reader-page.immersive { padding: 24px; }

.center-hint { text-align: center; color: var(--text2); padding: 80px 0; }
.back-btn {
  margin-top: 14px; padding: 9px 22px; border: none; border-radius: 999px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; cursor: pointer;
}
.reader-layout {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr) 230px;
  gap: 22px;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 20px;
  align-items: start;
}
/* 单篇阅读页左右侧栏（与阅览室同风格：玻璃卡片、吸顶） */
.nr-side {
  position: sticky;
  top: 80px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  padding: 16px 14px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--bg-soft) 80%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
}
.nr-side-head { margin-bottom: 4px; }
.nr-side-title { font-size: 13.5px; font-weight: 700; color: var(--text1); }
.nr-side-sub { font-size: 11.5px; color: var(--text2); margin: 10px 0 6px; font-weight: 600; }
.nr-author {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 4px 2px; border-radius: 10px;
}
.nr-author:hover .nr-author-name { color: var(--brand-1); }
.nr-author-name { font-size: 14px; font-weight: 700; color: var(--text1); }
.nr-list { display: flex; flex-direction: column; gap: 2px; }
.nr-item {
  padding: 7px 10px; border-radius: 9px; cursor: pointer;
  font-size: 12.5px; color: var(--text2); line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  transition: all .15s;
}
.nr-item:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.nr-item.on { color: var(--brand-1); font-weight: 600; background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.nr-outline { display: flex; flex-direction: column; gap: 2px; }
.nr-ol-item {
  padding: 6px 10px; border-radius: 8px; cursor: pointer;
  font-size: 12.5px; color: var(--text2); line-height: 1.45;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  transition: all .15s;
}
.nr-ol-item.indent-2 { padding-left: 22px; }
.nr-ol-item.indent-3 { padding-left: 32px; }
.nr-ol-item:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.nr-ol-item.active { color: var(--brand-1); font-weight: 600; background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.nr-empty { padding: 14px 8px; text-align: center; color: var(--text2); font-size: 12px; }
@media (max-width: 1180px) {
  .reader-layout { grid-template-columns: 1fr; max-width: 920px; }
  .nr-side { display: none; } /* 窄屏隐藏侧栏 */
}
.reader-card {
  position: relative;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 22px;
  box-shadow: var(--shadow-1);
  padding: 40px 48px;
  backdrop-filter: blur(12px);
}
.reader-head { margin-bottom: 26px; }
.reader-title { font-size: 27px; font-weight: 800; margin: 0 0 12px; color: var(--text1); }
.reader-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.author { display: inline-flex; align-items: center; gap: 7px; font-size: 13.5px; color: var(--text2); cursor: pointer; }
.author:hover { color: var(--brand-1); }
.avatar-mini {
  width: 24px; height: 24px; border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 12px;
  display: inline-flex; align-items: center; justify-content: center;
}
.type-badge {
  font-size: 11.5px; padding: 3px 10px; border-radius: 999px;
  color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 25%, transparent);
}
.time { font-size: 12.5px; color: var(--text2); }

.markdown-body { line-height: 1.85; font-size: 15px; color: var(--text1); }
.markdown-body :deep(h1) { font-size: 1.9rem; margin: 24px 0 16px; }
.markdown-body :deep(h2) { font-size: 1.45rem; margin: 28px 0 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.markdown-body :deep(h3) { font-size: 1.2rem; margin: 22px 0 10px; }
.markdown-body :deep(pre) { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 16px; overflow-x: auto; }
.markdown-body :deep(code) { background: color-mix(in srgb, var(--text1) 8%, transparent); border-radius: 5px; padding: 2px 6px; font-size: 13.5px; }
.markdown-body :deep(pre code) { background: transparent; padding: 0; }
.markdown-body :deep(table) { border-collapse: collapse; margin: 14px 0; width: 100%; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid var(--border); padding: 8px 12px; }
.markdown-body :deep(img) { max-width: 100%; border-radius: 10px; }
.markdown-body :deep(blockquote) { border-left: 3px solid var(--brand-1); margin: 14px 0; padding: 6px 16px; color: var(--text2); background: color-mix(in srgb, var(--brand-1) 6%, transparent); border-radius: 0 10px 10px 0; }

.summary-panel {
  margin: 0 0 24px; padding: 18px 22px;
  border-radius: 16px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--brand-1) 7%, var(--bg-soft)), var(--bg-soft));
  border: 1px solid color-mix(in srgb, var(--brand-1) 25%, transparent);
}
.summary-head {
  display: flex; align-items: center; gap: 10px;
  font-size: 14px; font-weight: 700; color: var(--text1);
  margin-bottom: 12px;
}
.summary-loading { font-size: 12px; color: var(--brand-1); font-weight: 400; }
.summary-body { font-size: 13.5px; line-height: 1.8; color: var(--text1); }
.summary-body :deep(p) { margin: 0 0 8px; }
.summary-body :deep(li) { margin-bottom: 4px; }
.action-bar {
  display: flex; gap: 10px; flex-wrap: wrap;
  margin-top: 32px; padding-top: 22px; border-top: 1px solid var(--border);
}
.act-btn {
  padding: 9px 18px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 13.5px; cursor: pointer;
  transition: all .2s;
}
.act-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.act-btn.on {
  color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 12%, transparent);
  border-color: color-mix(in srgb, var(--brand-1) 35%, transparent);
}

.reply-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; margin-bottom: 8px;
  border-radius: 10px;
  font-size: 12.5px; color: var(--text2);
  background: color-mix(in srgb, var(--brand-1) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 25%, transparent);
}
.reply-banner b { color: var(--brand-1); }
.comment-item.has-parent { margin-left: 34px; position: relative; }
.comment-item.has-parent::before {
  content: ''; position: absolute; left: -16px; top: 0; bottom: 0;
  width: 2px; border-radius: 2px;
  background: color-mix(in srgb, var(--brand-1) 22%, transparent);
}
.c-reply-to {
  font-size: 12px; color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  padding: 1px 8px; border-radius: 999px;
}
.c-reply-btn {
  border: none; background: none; cursor: pointer;
  font-size: 12px; color: var(--text2);
  padding: 2px 4px; margin-top: 4px;
}
.c-reply-btn:hover { color: var(--brand-1); }
.author-card {
  display: flex; flex-wrap: wrap; align-items: center; gap: 14px;
  padding: 18px 20px; margin-bottom: 24px;
  border-radius: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
}
.author-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 200px; }
.author-avatar {
  width: 44px; height: 44px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700; color: #fff;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  cursor: pointer; flex-shrink: 0;
}
.author-name { font-size: 15px; font-weight: 700; color: var(--text1); cursor: pointer; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.badge-gold { font-size: 11.5px; background: linear-gradient(120deg, #f59e0b, #fbbf24); color: #fff; padding: 1px 8px; border-radius: 999px; }
.author-uid { font-size: 12px; color: var(--text2); font-weight: 400; }
.author-bio { font-size: 12.5px; color: var(--text2); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 420px; }
.author-right { flex-shrink: 0; }
.fr-btn {
  padding: 7px 16px; border-radius: 999px; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--brand-1) 45%, transparent);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  color: var(--brand-1); font-size: 13px;
  transition: all .2s;
}
.fr-btn:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; border-color: transparent; }
.fr-state { font-size: 12.5px; color: var(--text2); padding: 6px 12px; border: 1px dashed var(--border); border-radius: 999px; }
.author-notes { width: 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 12px; border-top: 1px dashed var(--border); }
.an-label { font-size: 12px; color: var(--text2); }
.an-item {
  font-size: 12.5px; color: var(--brand-1); cursor: pointer;
  padding: 3px 10px; border-radius: 999px;
  background: color-mix(in srgb, var(--brand-1) 8%, transparent);
  max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.an-item:hover { background: color-mix(in srgb, var(--brand-1) 18%, transparent); }
.prev-next {
  display: flex; gap: 14px; margin-top: 30px;
}
.pn-item {
  flex: 1; display: flex; flex-direction: column; gap: 4px;
  padding: 14px 18px; border-radius: 14px;
  background: var(--bg-soft); border: 1px solid var(--border);
  cursor: pointer; transition: all .2s;
}
.pn-item:hover { border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); transform: translateY(-2px); }
.pn-item.right { text-align: right; }
.pn-item.disabled { opacity: .45; cursor: default; transform: none !important; }
.pn-dir { font-size: 12px; color: var(--brand-1); }
.pn-title { font-size: 13.5px; font-weight: 600; color: var(--text1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* ── 主题评分 ── */
.rate-section { margin-top: 40px; }
.rate-bar { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 16px; }
.rate-btn { border: none; background: none; color: var(--text1); font-size: 14.5px; font-weight: 600; padding: 6px 4px; cursor: pointer; }
.rate-btn:hover { color: var(--brand-1); }
.rate-count { color: var(--text2); font-size: 13px; }
.rate-stats { display: flex; gap: 26px; align-items: stretch; border-top: 1px solid var(--border); padding-top: 18px; flex-wrap: wrap; }
.rate-left { min-width: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.rate-score { font-size: 30px; font-weight: 800; color: var(--text1); line-height: 1.1; }
.rate-score-max { font-size: 14px; color: var(--text2); font-weight: 400; }
.rate-score-label { font-size: 12.5px; color: var(--text2); margin-top: 3px; }
.rate-q { cursor: help; margin-left: 2px; }
.rate-people { font-size: 12px; color: var(--text2); margin-top: 3px; }
.rate-mid { flex: 1; min-width: 190px; display: flex; flex-direction: column; justify-content: center; gap: 7px; }
.rate-dim { display: flex; align-items: center; gap: 10px; }
.rd-name { font-size: 12.5px; color: var(--text2); width: 34px; }
.rd-stars { font-size: 13.5px; letter-spacing: 1px; color: #f59e0b; }
.rate-right { flex: 1.2; min-width: 220px; display: flex; flex-direction: column; justify-content: center; gap: 7px; position: relative; }
.radar { width: 210px; height: 190px; display: block; margin: 0 auto; }
.radar-grid { fill: none; stroke: var(--text2); stroke-opacity: .3; stroke-width: 1; }
.radar-axis { stroke: var(--text2); stroke-opacity: .22; stroke-width: 1; }
.radar-data { fill: rgba(249, 115, 22, .32); stroke: #f97316; stroke-width: 2; stroke-linejoin: round; }
.radar-dot { fill: #f97316; }
.radar-label { font-size: 10.5px; fill: var(--text2); }
.rt-tooltip { position: absolute; background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; font-size: 11.5px; color: var(--text1); box-shadow: var(--shadow-1); opacity: 0; visibility: hidden; transition: opacity .12s; z-index: 50; min-width: 128px; pointer-events: none; }
.rt-tooltip.show { opacity: 1; visibility: visible; }
.rtt-title { font-weight: 700; margin-bottom: 5px; font-size: 11.5px; color: var(--text1); }
.rtt-row { display: flex; gap: 6px; align-items: center; padding: 2px 0; color: var(--text2); }
.rtt-row b { margin-left: auto; color: var(--text1); font-weight: 700; }
/* 评分弹窗 */
.rate-modal { position: fixed; inset: 0; background: var(--overlay-bg); z-index: 1200; display: flex; align-items: center; justify-content: center; padding: 20px; }
.rate-dialog { width: 470px; max-width: 100%; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 16px; padding: 22px 24px; box-shadow: var(--shadow-1); box-sizing: border-box; }
.rate-dialog-head { display: flex; align-items: center; justify-content: space-between; font-size: 16px; font-weight: 700; margin-bottom: 12px; }
.rate-dialog-sub { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.rds-mine { font-size: 13.5px; font-weight: 700; }
.rds-record { font-size: 12px; color: var(--text2); }
.rate-dialog-note { font-size: 12px; color: var(--text2); background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; margin-bottom: 16px; line-height: 1.65; }
.rate-dialog-note b { color: var(--brand-1); }
.rate-dialog-dims { display: flex; flex-direction: column; gap: 11px; margin-bottom: 16px; }
.rdd-row { display: flex; align-items: center; gap: 12px; }
.rdd-name { font-size: 13.5px; width: 44px; }
.rdd-stars { display: flex; gap: 3px; }
.rdd-star { font-size: 25px; color: #d1d5db; cursor: pointer; transition: transform .1s; line-height: 1; }
.rdd-star.on { color: #f59e0b; }
.rdd-star:hover { transform: scale(1.15); }
.rate-dialog-tags { margin-bottom: 18px; }
.rdt-label { font-size: 13px; margin-right: 4px; }
.rdt-pill { display: inline-block; font-size: 12px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--border); background: var(--card-bg); color: var(--text2); margin: 5px 6px 0 0; cursor: pointer; }
.rdt-pill.on { color: #fff; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); border-color: transparent; }
.rate-dialog-foot { display: flex; justify-content: flex-end; gap: 10px; }
.rdf-cancel { padding: 8px 18px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text2); cursor: pointer; }
.rdf-save { padding: 8px 20px; border: none; border-radius: 999px; background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; cursor: pointer; font-weight: 600; }
.rdf-save:disabled { opacity: .5; cursor: not-allowed; }
.comment-box { margin-top: 36px; }
.comment-title { font-size: 16px; font-weight: 700; margin: 0 0 16px; color: var(--text1); }
.emoji-wrap { position: relative; }
.emoji-panel {
  position: absolute; bottom: 40px; left: 0; z-index: 50;
  display: flex; flex-wrap: wrap; gap: 2px;
  width: 210px; padding: 8px;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 12px; box-shadow: var(--shadow-1);
}
.emoji-item {
  border: none; background: none; cursor: pointer;
  font-size: 16px; padding: 4px; border-radius: 6px;
  transition: transform .12s;
}
.emoji-item:hover { transform: scale(1.25); background: color-mix(in srgb, var(--brand-1) 10%, transparent); }
.comment-input-row { display: flex; gap: 10px; margin-bottom: 18px; }
.comment-input {
  flex: 1; padding: 10px 16px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1);
  font-size: 14px; outline: none;
}
.comment-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.comment-send {
  padding: 10px 22px; border: none; border-radius: 999px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.no-comment { color: var(--text2); font-size: 13px; padding: 14px 0; }
.comment-anchor {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 25%, transparent);
  border-radius: 999px; padding: 5px 14px; margin-bottom: 10px;
}
.anchor-x { cursor: pointer; color: var(--text2); }
.anchor-x:hover { color: #ef4444; }
.anchor-btn {
  width: 40px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--btn-bg);
  font-size: 16px; cursor: pointer; transition: all .2s;
}
.anchor-btn:hover { border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); transform: scale(1.05); }
.c-anchor {
  font-size: 12px; color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 8%, transparent);
  border-radius: 8px; padding: 3px 10px;
  margin-bottom: 6px; width: fit-content;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 100%;
}
.comment-item { display: flex; gap: 12px; padding: 14px 0; border-top: 1px solid var(--border); }
.c-avatar {
  width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 14px;
  display: inline-flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.c-avatar img { width: 100%; height: 100%; object-fit: cover; }
.c-body { flex: 1; min-width: 0; }
.c-meta { display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }
.c-name { font-size: 13.5px; font-weight: 600; color: var(--brand-1); cursor: pointer; }
.c-time { font-size: 12px; color: var(--text2); }
.c-content { font-size: 14px; color: var(--text1); line-height: 1.6; word-break: break-word; }

</style>