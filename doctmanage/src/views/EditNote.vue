<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import Container from 'markdown-it-container'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { full as emoji } from 'markdown-it-emoji'
import mathjax3 from 'markdown-it-mathjax3'
import alerts from 'markdown-it-github-alerts'
import mdImgSize from '@/utils/mdImgSize.js'
import { ElMessage } from 'element-plus'
import TurndownService from 'turndown'
import { diffLines } from 'diff'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import api from '@/utils/api.js'
import DoodleBall from '@/components/DoodleBall.vue'
import { setupAnnotation, bindAnnotations, ensureDoodleCanvas, drawStrokes, bindAnnGlobal } from '@/utils/annotation.js'

const route = useRoute()
const router = useRouter()
// 返回：按来源页跳转（阅览室→回阅览室，笔记阅读→回该笔记，默认回书房）
const goBack = () => {
  const from = route.query.from
  if (from === 'docs') router.push('/docs')
  else if (from === 'note' && route.params.id) router.push('/notes/' + (loadedPubId.value || route.params.id))
  else router.push('/admin')
}

const isEdit = computed(() => !!route.params.id)
const docId = computed(() => Number(route.params.id))

const title = ref('')
const type = ref('')
const visibility = ref('private')
const content = ref('')
const busy = ref(false)
const loading = ref(false)
const notFound = ref(false)

const md = new MarkdownIt({ html: false, linkify: true, breaks: true, highlight: (code, lang) => {
  if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value
  return hljs.highlightAuto(code).value
}}).use(emoji).use(mathjax3).use(mdImgSize)
setupAnnotation(md)
// ── 代码块：容器包裹 + 行高亮 {n} + 行号 :line-numbers（与 Docs 阅读一致）；[title] 存 data-title 供保存还原 ──
md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx]
  const unescape = (str) => md.utils.unescapeAll(str).trim()
  const info = token.info ? unescape(token.info) : ''
  let rawInfo = info
  let langName = ''
  let lineNumbersMode = false
  let lineNumbersStart = 1
  const highlights = []
  let title = ''
  // 1. 标题 [foo]
  const titleMatch = rawInfo.match(/\[(.*?)\]/)
  if (titleMatch) {
    title = titleMatch[1]
    rawInfo = rawInfo.replace(/\[.*?\]/, '')
  }
  // 2. 高亮 {4,6-10}
  const rangeMatch = rawInfo.match(/\{([0-9,\s-]+)\}/)
  if (rangeMatch) {
    const rangeStr = rangeMatch[1]
    rawInfo = rawInfo.replace(/\{.*?\}/, '')
    rangeStr.split(',').forEach(part => {
      part = part.trim()
      if (part.includes('-')) {
        const [s, e] = part.split('-')
        for (let i = parseInt(s, 10); i <= parseInt(e, 10); i++) highlights.push(i)
      } else if (part) highlights.push(parseInt(part, 10))
    })
  }
  // 3. 行号 :line-numbers(=start)?
  const lnMatch = rawInfo.match(/:line-numbers(?:=(\d+))?/)
  if (lnMatch) {
    lineNumbersMode = true
    if (lnMatch[1]) lineNumbersStart = parseInt(lnMatch[1], 10)
    rawInfo = rawInfo.replace(/:line-numbers(?:=\d+)?/, '')
  }
  // 4. 语言
  langName = rawInfo.trim().split(/\s+/)[0] || ''
  // 5. 高亮代码
  let code = options.highlight ? options.highlight(token.content, langName) : ''
  if (!code) code = md.utils.escapeHtml(token.content)
  // 6. 行数
  const lines = token.content.split(/\r?\n/)
  if (lines[lines.length - 1] === '') lines.pop()
  // 7. wrapper 类
  const wrapperClasses = ['code-block-wrapper']
  if (lineNumbersMode) wrapperClasses.push('line-numbers-mode')
  // 8. code-group 内第一个加 active
  if (idx > 0 && tokens[idx - 1].type === 'container_code-group_open') {
    wrapperClasses.push('active')
  } else {
    for (let k = idx - 1; k >= 0; k--) {
      if (tokens[k].type === 'container_code-group_close') break
      if (tokens[k].type === 'container_code-group_open') { wrapperClasses.push('active'); break }
    }
  }
  // 9. 高亮 overlay
  let highlightOverlay = ''
  if (highlights.length > 0) {
    highlightOverlay = '<div class="highlight-lines">'
    for (let i = 0; i < lines.length; i++) {
      const lineNum = i + 1
      highlightOverlay += `<div class="highlight-line ${highlights.includes(lineNum) ? 'highlighted' : ''}">&nbsp;</div>`
    }
    highlightOverlay += '</div>'
  }
  // 10. 行号
  let lineNumbersHtml = ''
  if (lineNumbersMode) {
    lineNumbersHtml = '<div class="line-numbers-wrapper">'
    for (let i = 0; i < lines.length; i++) lineNumbersHtml += `<span class="line-number">${lineNumbersStart + i}</span><br>`
    lineNumbersHtml += '</div>'
  }
  const label = langName ? `<span class="code-lang">${langName}</span>` : ''
  const copyBtn = `<button class="copy-code-btn" contenteditable="false" data-code="${encodeURIComponent(token.content)}"></button>`
  const titleAttr = title ? ` data-title="${md.utils.escapeHtml(title)}"` : ''
  const hlAttr = highlights.length ? ` data-highlights="${highlights.join(',')}"` : ''
  return `<div class="${wrapperClasses.join(' ')}"${titleAttr}${hlAttr}>` +
    `<div class="code-header">${label}${copyBtn}</div>` +
    lineNumbersHtml + highlightOverlay +
    `<pre class="language-${langName}"><code class="language-${langName}">${code}</code></pre>` +
    `</div>`
}
// ── 代码组 ::: code-group（tabs 切换） ──
md.use(Container, 'code-group', {
  render: function (tokens, idx) {
    if (tokens[idx].nesting === 1) {
      let tabs = ''
      let i = idx + 1
      let first = true
      while (i < tokens.length && tokens[i].type !== 'container_code-group_close') {
        if (tokens[i].type === 'fence') {
          const info = tokens[i].info ? md.utils.unescapeAll(tokens[i].info).trim() : ''
          const m = info.match(/\[(.*?)\]/)
          const title = m ? m[1] : (info.split(/\s+/)[0] || 'Code')
          tabs += `<div class="code-group-tab ${first ? 'active' : ''}">${title}</div>`
          first = false
        }
        i++
      }
      return `<div class="code-group"><div class="code-group-tabs">${tabs}</div><div class="code-group-blocks">\n`
    }
    return `</div></div>\n`
  }
})
// 自定义块容器：例题 / 公式 / 提示 / 信息 / 警告 / 注意 / 详细信息（:::example / :::formula / :::tip … / :::details）
const createBlock = (klass, defaultTitle) => [Container, klass, {
  render(tokens, idx) {
    const token = tokens[idx]
    const info = token.info.trim().slice(klass.length).trim()
    if (token.nesting === 1) {
      if (klass === 'details') return `<details class="custom-block details"><summary>${info || defaultTitle}</summary>\n`
      return `<div class="${klass} custom-block"><p class="custom-block-title">${info || defaultTitle}</p>\n`
    }
    if (klass === 'details') return `</details>\n`
    return `</div>\n`
  }
}]
md.use(...createBlock('example', '例题'))
md.use(...createBlock('formula', '公式'))
md.use(...createBlock('tip', '提示'))
md.use(...createBlock('info', '信息'))
md.use(...createBlock('warning', '警告'))
md.use(...createBlock('danger', '注意'))
md.use(...createBlock('details', '详细信息'))
md.use(alerts) // GitHub 风格警报：> [!NOTE] / [!TIP] / [!IMPORTANT] / [!WARNING] / [!CAUTION]
const rightEl = ref(null)
const loadedPubId = ref('') // 文档 public_id（返回笔记页时用，避免 URL 暴露数字 id）
const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

// ── 公式占位 + KaTeX 渲染成图 ──
const fixLatex = (eq) => String(eq || '').trim().replace(/\\+([a-zA-Z])/g, '\\$1') // AI 常把 LaTeX 写成双反斜杠 \\frac，归一为单反斜杠
const renderMd = (src) => {
  const eqs = []
  let s = String(src || '')
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (m, eq) => { eqs.push({ eq: fixLatex(eq), display: true }); return '%%EQ%%' + (eqs.length - 1) + '%%' })
  s = s.replace(/\$([^\$\n]+?)\$/g, (m, eq) => { eqs.push({ eq: fixLatex(eq), display: false }); return '%%EQ%%' + (eqs.length - 1) + '%%' })
  let html = md.render(s)
  html = html.replace(/%%EQ%%(\d+)%%/g, (m, i) => {
    const it = eqs[+i]
    if (!it) return m
    let k = ''
    try { k = katex.renderToString(it.eq, { displayMode: it.display, throwOnError: false }) } catch (e) { k = '<span class="eq-err">' + escapeHtml(it.eq) + '</span>' }
    return '<eq-wrap data-eq="' + escapeHtml(it.eq) + '" data-display="' + (it.display ? '1' : '0') + '" contenteditable="false">' + k + '</eq-wrap>'
  })
  return html
}
const renderRight = () => {
  if (rightEl.value) {
    rightEl.value.innerHTML = renderMd(content.value)
    upgradeImgs() // 普通图片（粘贴/附件/markdown 引用）也包成可拉伸的 img-zone
    bindAnnotations(rightEl.value, annMap.value, { editable: true, onInput: saveAnnText })
    ensureAnnCanvases(rightEl.value)
  }
  window.dispatchEvent(new Event('zhiyu:doodle-reflow'))
}
// 编辑区所有裸 <img>（非 img-zone）自动升级为可拉伸图片：包 span.img-zone + 8 个拉伸手柄，
// 让粘贴/附件/复制的图片也有与「插入图片」一致的拉伸能力（光标与拖拽自动生效）
const upgradeImgs = () => {
  const root = rightEl.value
  if (!root) return
  const RZ = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
  root.querySelectorAll('.markdown-body img').forEach((img) => {
    if (img.closest('.img-zone')) return
    const zone = document.createElement('span')
    zone.className = 'img-zone'
    zone.setAttribute('contenteditable', 'false')
    img.parentNode.insertBefore(zone, img)
    zone.appendChild(img)
    zone.insertAdjacentHTML('beforeend', RZ.map(d => `<span class="rz rz-${d}"></span>`).join(''))
  })
}
// 给编辑区里 markdown 渲染的批注框补齐手绘画布（插入的批注框自带；渲染重建后缺失则补）
const ensureAnnCanvases = (root) => {
  if (!root) return
  root.querySelectorAll('.ann-block').forEach((b) => {
    if (b.querySelector('canvas.ann-doodle')) return
    const cv = document.createElement('canvas')
    cv.className = 'ann-doodle'
    cv.setAttribute('data-ann-doodle', '')
    b.insertBefore(cv, b.querySelector('.ann-body') || b.lastChild)
    requestAnimationFrame(() => {
      const r = cv.getBoundingClientRect()
      if (!r.width || !r.height) return   // 收起态（display:none）宽为 0：不设尺寸，避免清空笔迹
      const dpr = window.devicePixelRatio || 1
      cv.width = Math.max(1, Math.round(r.width * dpr))
      cv.height = Math.max(1, Math.round(r.height * dpr))
    })
  })
}

// ── 所见即所得反向：HTML -> markdown（公式还原为 $...$ / $$...$$） ──
const td = new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced', bulletListMarker: '-' })
// 代码块头部（语言标签 + 复制按钮）是渲染装饰，保存时不进正文
td.addRule('codeHeader', {
  filter: (node) => node.classList && node.classList.contains('code-header'),
  replacement: () => '',
})
// 自定义容器（::: tip/info/warning/danger/details 等）：标题是装饰，容器本体保留语法
td.addRule('customBlockTitle', {
  filter: (node) => node.classList && (node.classList.contains('custom-block-title') || node.nodeName === 'SUMMARY'),
  replacement: () => '',
})
td.addRule('customBlock', {
  filter: (node) => node.classList && node.classList.contains('custom-block'),
  replacement: (content, node) => {
    const isDetails = node.classList.contains('details')
    const cls = Array.from(node.classList).filter(c => c !== 'custom-block' && c !== 'details')
    const klass = isDetails ? 'details' : (cls[0] || '')
    const titleEl = node.querySelector('.custom-block-title, summary')
    const title = titleEl ? titleEl.textContent.trim() : ''
    return `\n\n::: ${klass}${title ? ' ' + title : ''}\n${content.trim()}\n:::\n\n`
  },
})
// GitHub 警报（> [!NOTE] 等）：标题是装饰，警报本体保留语法
td.addRule('githubAlertTitle', {
  filter: (node) => node.classList && node.classList.contains('markdown-alert-title'),
  replacement: () => '',
})
td.addRule('githubAlert', {
  filter: (node) => node.classList && node.classList.contains('markdown-alert'),
  replacement: (content, node) => {
    const m = String(node.className).match(/markdown-alert-(\w+)/)
    const type = ((m && m[1]) || 'note').toUpperCase()
    const inner = content.trim().split('\n').map(l => '> ' + l).join('\n')
    return `\n\n> [!${type}]\n${inner}\n\n`
  },
})
// 代码块 wrapper：保存时还原 ```lang[ title]（title 来自渲染时存的 data-title）
td.addRule('codeWrapper', {
  filter: (node) => node.classList && node.classList.contains('code-block-wrapper'),
  replacement: (content, node) => {
    const pre = node.querySelector('pre code')
    const lang = pre ? (String(pre.className).match(/language-(\S+)/) || [])[1] || '' : ''
    const code = pre ? pre.textContent : ''
    const title = node.getAttribute('data-title') || ''
    const hl = node.getAttribute('data-highlights') || ''
    const titlePart = title ? ' [' + title + ']' : ''
    const hlPart = hl ? `{${hl}}` : ''
    return `\n\n\`\`\`${lang}${titlePart}${hlPart}\n${code}\n\`\`\`\n\n`
  },
})
// 代码组：tabs 行是渲染装饰，容器还原 ::: code-group
td.addRule('codeGroupTabs', {
  filter: (node) => node.classList && node.classList.contains('code-group-tabs'),
  replacement: () => '',
})
td.addRule('codeGroup', {
  filter: (node) => node.classList && node.classList.contains('code-group'),
  replacement: (content, node) => `\n\n::: code-group\n${content.trim()}\n:::\n\n`,
})
// 图片尺寸：编辑器调整大小后保存为 markdown 的 =WxH 语法（addRule 会插到最前优先匹配）
td.addRule('imgSize', {
  filter: 'img',
  replacement: (content, node) => {
    const src = node.getAttribute('src') || ''
    const alt = node.getAttribute('alt') || ''
    const cs = node.currentStyle || window.getComputedStyle(node)
    const w = parseFloat(node.style.width) || parseFloat(node.getAttribute('width')) || parseFloat(cs.width)
    const h = parseFloat(node.style.height) || parseFloat(node.getAttribute('height')) || parseFloat(cs.height)
    if (!w || !h) return '![' + alt + '](' + src + ')'
    return '![' + alt + '](' + src + ' "=' + Math.round(w) + 'x' + Math.round(h) + '")'
  },
})
td.addRule('eqWrap', {
  filter: (node) => node.nodeName.toLowerCase() === 'eq-wrap',
  replacement: (content, node) => {
    const eq = node.getAttribute('data-eq') || ''
    return node.getAttribute('data-display') === '1' ? '\n$$\n' + eq + '\n$$\n' : '$' + eq + '$'
  },
})
// 表格 → markdown 表格（turndown 默认不支持 <table>，会把表格拆成竖排文本导致内容损坏）
// 这里把 <table> 还原为 | 分隔的 markdown 表格；单元格内公式（eq-wrap）取 data-eq 还原为 $...$，
// KaTeX 双份渲染（mathml + html）与隐藏文本全部剔除，避免内容重复
td.addRule('table', {
  filter: (node) => node.nodeName.toLowerCase() === 'table',
  replacement: (content, node) => {
    const clone = node.cloneNode(true)
    const rows = []
    Array.from(clone.querySelectorAll('tr')).forEach((tr) => {
      const isHead = tr.parentElement && tr.parentElement.tagName === 'THEAD'
      const cells = []
      Array.from(tr.querySelectorAll(isHead ? 'th' : 'td')).forEach((c) => {
        let txt = c.innerHTML.replace(/<eq-wrap[^>]*data-eq="([^"]*)"[^>]*>[\s\S]*?<\/eq-wrap>/g, (m, eq) => '$' + eq + '$')
        txt = txt.replace(/<br\s*\/?>/gi, '\n')
        txt = txt.replace(/<[^>]+>/g, '')
        txt = txt.replace(/[ \t]+/g, ' ').trim()
        cells.push(txt)
      })
      if (!cells.length) return
      rows.push('| ' + cells.join(' | ') + ' |')
      if (isHead) {
        rows.push('| ' + cells.map(() => '---').join(' | ') + ' |')
      }
    })
    if (!rows.length) return ''
    return '\n\n' + rows.join('\n') + '\n\n'
  },
})
let editingRight = false
let editingTimer = null
// 涂鸦画布（常驻编辑区）不参与正文：转 markdown 时忽略
td.addRule('doodleCanvas', {
  filter: 'canvas',
  replacement: () => '',
})
// 批注块 → markdown 容器（:::annotation <id>：文字/笔迹存记录，正文只留锚点；旧格式无 id 时内容直转）
td.addRule('annotation', {
  filter: (node) => node.classList && node.classList.contains('ann-block'),
  replacement: (content, node) => {
    const id = node.getAttribute('data-ann-id') || ''
    if (id) return '\n\n:::annotation ' + id + '\n:::\n\n'
    const body = node.querySelector('.ann-body')
    let txt = body ? (body.tagName === 'TEXTAREA' ? body.value : body.innerHTML) : ''
    try {
      const innerTd = new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced', bulletListMarker: '-' })
      txt = innerTd.turndown(txt)
    } catch (e) { /* 保留原样 */ }
    return '\n\n:::annotation\n' + (txt.trim() || '批注') + '\n:::\n\n'
  },
})
// ── 批注记录（note_annotations）：文字 + 手绘笔迹都存记录，正文 markdown 只留 `:::annotation <id>` 锚点 ──
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
    renderRight()
  } catch (e) { /* 忽略 */ }
}
// 批注框内输入：防抖局部保存单条记录（不触发全篇 turndown，不卡）
const saveAnnText = async (id, text) => {
  try { await api.put('/annotations/' + id, { note_text: text }) } catch (e) { /* 忽略 */ }
}
const saveAnnDoodle = async (id, strokes, w, h) => {
  try { await api.put('/annotations/' + id, { strokes, canvas_w: w, canvas_h: h }) } catch (e) { /* 忽略 */ }
}
// 删除批注：删记录 + 移除块
const delAnn = async (b, idx) => {
  const id = b.getAttribute('data-ann-id')
  if (id) {
    delete annMap.value[id]
    try { await api.delete('/annotations/' + id) } catch (e) { /* 忽略 */ }
  }
  b.remove()
  if (rightEl.value) {
    bindAnnotations(rightEl.value, annMap.value, { editable: true, onInput: saveAnnText })
    onEdit()
  }
}
// 插入批注：光标处插入批注块（可展开收起、可删除，保存为 :::annotation 容器）
const insertAnnotation = async () => {
  // 批注框内不允许再插批注（防套娃）
  const sel0 = window.getSelection()
  let n0 = sel0 && sel0.anchorNode
  if (n0 && n0.nodeType !== 1) n0 = n0.parentElement
  if (n0 && n0.closest && n0.closest('.ann-block')) {
    ElMessage.warning('批注框内不能再插入批注')
    return
  }
  // 保存编辑区光标选区
  let savedRange = null
  const sel = window.getSelection()
  if (sel && sel.rangeCount && rightEl.value && rightEl.value.contains(sel.anchorNode)) {
    savedRange = sel.getRangeAt(0).cloneRange()
  }
  if (!rightEl.value) { ElMessage.error('编辑区还没准备好'); return }
  if (!docId.value) { ElMessage.error('请先保存笔记再插批注'); return }
  // 先创建批注记录（文字/笔迹存这里），正文只留锚点
  let aid = null
  try {
    const res = await api.post('/notes/' + docId.value + '/annotations', { kind: 'note' })
    aid = res.data && res.data.id
  } catch (e) { ElMessage.error('批注创建失败'); return }
  if (!aid) return
  // 直接插入一个可编辑批注块（类似 Jupyter 输出区，在块里直接输入内容）
  const el = document.createElement('div')
  el.className = 'ann-block open'
  el.setAttribute('data-ann-id', String(aid))
  // 注意：整块不能设 contenteditable="false"，否则嵌套编辑区里回车会把新段落创建到框外（跳出批注框）
  const badge = document.createElement('div')
  badge.className = 'ann-badge'
  badge.setAttribute('data-ann-toggle', '')
  badge.title = '点击展开/收起批注'
  // 文字区用 textarea：独立控件，不参与编辑区 contenteditable 嵌套——回车/删除/多行换行全部原生留在框内
  const body = document.createElement('textarea')
  body.className = 'ann-body'
  body.setAttribute('rows', '3')
  body.setAttribute('spellcheck', 'false')
  body.setAttribute('placeholder', '输入批注内容…')
  const foot = document.createElement('div')
  foot.className = 'ann-foot'
  foot.innerHTML = '<button class="ann-del" data-ann-del>🗑 删除批注</button>'
  // 批注框内独立手绘层：永久属于批注框，用外部 ✏️ 手绘激活，「✔ 完成」退出
  const doneBtn = document.createElement('button')
  doneBtn.type = 'button'
  doneBtn.className = 'ann-doodle-done'
  doneBtn.textContent = '✔ 完成'
  const doodle = document.createElement('canvas')
  doodle.className = 'ann-doodle'
  doodle.setAttribute('data-ann-doodle', '')
  el.appendChild(badge); el.appendChild(doneBtn); el.appendChild(doodle); el.appendChild(body); el.appendChild(foot)
  // 插入后设置画布像素尺寸（覆盖整个批注框）
  requestAnimationFrame(() => {
    const w = el.clientWidth, h = el.clientHeight
    const dpr = window.devicePixelRatio || 1
    doodle.width = Math.max(1, Math.round(w * dpr))
    doodle.height = Math.max(1, Math.round(h * dpr))
  })
  rightEl.value.focus()
  // 恢复选区并插入
  let inserted = false
  if (savedRange) {
    const sel2 = window.getSelection()
    sel2.removeAllRanges(); sel2.addRange(savedRange)
  }
  const sel3 = window.getSelection()
  if (sel3 && sel3.rangeCount && sel3.anchorNode && rightEl.value.contains(sel3.anchorNode)) {
    const range = sel3.getRangeAt(0)
    range.deleteContents()
    range.insertNode(el)
    range.setStartAfter(el); range.collapse(true)
    sel3.removeAllRanges(); sel3.addRange(range)
    inserted = true
  }
  if (!inserted) {
    rightEl.value.appendChild(document.createElement('br'))
    rightEl.value.appendChild(el)
  }
  annMap.value[String(aid)] = { note_text: '', strokes: [], canvas_w: 0, canvas_h: 0 }
  bindAnnotations(rightEl.value, annMap.value, { editable: true, onInput: saveAnnText })
  onEdit()
  // 聚焦到批注内容区，直接输入（textarea 用 setSelectionRange）
  body.focus()
  if (typeof body.setSelectionRange === 'function') body.setSelectionRange(0, 0)
  else {
    const r = document.createRange()
    r.selectNodeContents(body); r.collapse(false)
    const s4 = window.getSelection()
    s4.removeAllRanges(); s4.addRange(r)
  }
  ElMessage.success('批注已插入：直接在里面写字，✏️ 手绘可涂画，回车可加宽')
}
const onEdit = (e) => {
  if (!rightEl.value) return
  // 批注框内输入/回车：完全跳过全量转换与编辑区重建（保存时 flushEdit 统一转成 markdown）
  // 否则每次按键都触发 turndown + katex 全量渲染，表现为回车卡顿数秒
  if (e && e.target && e.target.closest && e.target.closest('.ann-block')) {
    return
  }
  editingRight = true
  // 防抖：输入停顿 300ms 才全量转换 markdown（避免每按一键都全量 turndown 导致卡顿）
  if (editingTimer) clearTimeout(editingTimer)
  editingTimer = setTimeout(() => {
    content.value = td.turndown(rightEl.value.innerHTML)
    // content 更新后保持锁定一段时间：不立即重建编辑区（重建会丢光标+全量渲染卡顿）
    // 批注框内打字/回车尤其不能触发重建
    editingTimer = setTimeout(() => { editingRight = false }, 600)
  }, 300)
}
// 保存/导出前强制把编辑区最新内容转成 markdown（含批注框内输入，防抖短路不影响）
const flushEdit = () => {
  if (rightEl.value) {
    if (editingTimer) { clearTimeout(editingTimer); editingTimer = null }
    editingRight = false
    content.value = td.turndown(rightEl.value.innerHTML)
  }
}
// textarea 改源码时重建右栏；右栏编辑时跳过（避免焦点丢失）
watch(content, () => { if (!editingRight && rightEl.value) renderRight() })

// ── 公式点击编辑（渲染成图，点一下弹框改 LaTeX 源码） ──
const eqOpen = ref(false)
const eqForm = ref('')
let eqEditingEl = null
const onEditorKeydown = (e) => {
  // 公式内部：允许选中/复制，禁止输入和删除（防止破坏 KaTeX 结构）
  if (e.target && e.target.closest && e.target.closest('eq-wrap')) {
    if (!e.ctrlKey && !e.metaKey && !e.altKey) e.preventDefault()
  }
}
// 指令定位插入点：识别「在 XX 后面/之后 添加…」，返回 content.value 中 XX 小节内容末尾的索引（-1 = 未定位到，用光标）
const locateInsertInContent = (inst) => {
  const m = String(inst || '').match(/在\s*([^\s，。；、,;]+?)\s*(?:后面|之后|后边|末尾|最后)\s*(?:添加|增加|加|插入|补充|写|放|补)/)
  if (!m) return -1
  const kw = m[1].trim()
  if (!kw) return -1
  const titles = []
  const re = /^##\s*(?:\d+、?)?\s*([^\n]+?)\s*$/gm
  let mm = null
  while ((mm = re.exec(content.value)) !== null) titles.push({ t: mm[1].trim(), idx: mm.index })
  const hit = titles.find(o => o.t === kw) || titles.find(o => o.t.includes(kw)) || titles.find(o => kw.includes(o.t))
  if (!hit) return -1
  const next = titles.find(o => o.idx > hit.idx)
  return next ? next.idx : content.value.length
}

// 编辑区右键（批注已由徽章直接绑定处理）
const onEditorCtx = (e) => { /* 批注右键删除在徽章上直接绑定 */ }
const onEditorClick = (e) => {
  // 代码块复制按钮（与 Docs/NoteReader 阅读页一致）：复制 + copied 反馈，不进入编辑
  if (e.target.classList.contains('copy-code-btn')) {
    e.preventDefault()
    e.stopPropagation()
    const code = decodeURIComponent(e.target.getAttribute('data-code') || '')
    navigator.clipboard.writeText(code).then(() => {
      e.target.classList.add('copied')
      setTimeout(() => e.target.classList.remove('copied'), 2000)
    }).catch(() => {})
    return
  }
  // 代码组 tab 切换（::: code-group）
  if (e.target.classList.contains('code-group-tab')) {
    e.preventDefault()
    e.stopPropagation()
    const tabs = e.target.parentElement
    const blocks = tabs.nextElementSibling
    if (blocks && blocks.classList.contains('code-group-blocks')) {
      const idx = [...tabs.children].indexOf(e.target)
      tabs.querySelectorAll('.code-group-tab').forEach((t) => t.classList.toggle('active', t === e.target))
      blocks.querySelectorAll('.code-block-wrapper').forEach((b, i) => b.classList.toggle('active', i === idx))
    }
    return
  }
  // 批注由全局委托处理（capture 阶段已拦截），这里不再重复
  lastClickPos = { x: e.clientX, y: e.clientY }
  lastClickTime = Date.now()
  // AI 内联 diff：接受/拒绝（优先处理多修改点内嵌块 data-block，其次旧选中内联）
  const accept = e.target.closest('.ai-accept')
  if (accept) {
    const box = accept.closest('.ai-inline-diff')
    if (box && box.dataset.block) {
      // 多修改点内嵌块：找到对应 block 应用修改（content.value 已更新 → watcher 重渲染其余块）
      const b = aiBlocks.value.find(x => String(x.id) === box.dataset.block)
      if (b) acceptBlock(b)
      return
    }
    if (box) {
      let sug = (box.dataset.sug || '').trim()
      // 格式化：编号条目（1）（2）… 前补空行（AI 常把多条公式挤在一行）
      sug = sug.replace(/（(\d+)）/g, '\n\n（$1）').replace(/\n{3,}/g, '\n\n').trim()
      // 标题/公式开头 → 前面补空行，避免与上一行粘连
      if (/^(#|\$|（|\(|\d+[、.])/.test(sug)) sug = '\n\n' + sug
      // 编号处理：只有【新增小节意图】明确时才自动编号+顺延；仅修改某段时一律原样应用，绝不碰编号。
      // 必须【插入前】判断是否新增（插入后新节自己会匹配到，永远误判为已存在）
      const inst = box.dataset.instruction || ''
      const isAddSection = /新增|增加|加入|添加|插入|补(?:充|上)?|扩展|append|add/i.test(inst) && /^\s*##\s/.test(sug)
      let renTitle = ''
      if (isAddSection) {
        const m = sug.match(/^\s*##\s*(?:\d+、?)?(.+)$/m)
        const title = m ? m[1].trim() : ''
        if (title) {
          const esc = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
          // 笔记中已有同名小节 → 修改场景，不编号不顺延
          if (!new RegExp('^##\\s*(?:\\d+、?)?\\s*' + esc + '\\s*$', 'm').test(content.value)) {
            renTitle = title
          }
        }
      }
      // ── 指令智能定位：指令含「在 XX 后面/之后 添加…」→ 源码层插到 XX 小节末尾（不依赖光标）──
      const insAt = locateInsertInContent(inst)
      if (insAt !== -1) {
        let t = content.value
        const pad = sug.startsWith('\n') ? '\n' : '\n\n'
        t = t.slice(0, insAt) + pad + sug + '\n' + t.slice(insAt)
        content.value = t
        if (renTitle) {
          const esc = renTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
          const pos = content.value.search(new RegExp('^##\\s*(?:\\d+、?)?\\s*' + esc + '\\s*$', 'm'))
          if (pos !== -1) {
            let newNum = 1
            const prevNums = content.value.slice(0, pos).match(/##\s*(\d+)、/g)
            if (prevNums && prevNums.length) newNum = parseInt(prevNums[prevNums.length - 1].match(/\d+/)[0]) + 1
            let t2 = content.value
            t2 = t2.replace(new RegExp('^##\\s*(?:\\d+、?)?\\s*' + esc + '\\s*$', 'm'), '## @@NEWNUM@@、' + renTitle)
            t2 = t2.replace(/^##\s+(\d+)、/gm, (mm, num) => { const n = parseInt(num); return n >= newNum ? mm.replace(num, String(n + 1)) : mm })
            t2 = t2.replace('## @@NEWNUM@@、' + renTitle, '## ' + newNum + '、' + renTitle)
            content.value = t2
          }
        }
        content.value = content.value.replace(/\n{3,}/g, '\n\n')
        renderRight()
        save()
        ElMessage.success('已应用 AI 修改')
        return
      }
      // 插入渲染后的 HTML（不是纯文本）：## 标题、$公式、空行段落才会被正确渲染与还原
      const tmpBox = document.createElement('div')
      tmpBox.innerHTML = renderMd(sug)
      const frag = document.createDocumentFragment()
      while (tmpBox.firstChild) frag.appendChild(tmpBox.firstChild)
      box.replaceWith(frag)
      onEdit()
      if (renTitle) {
        const esc = renTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        // 新节编号 = 插入位置前面最近 ## N、 的 N+1（AI 自己写的编号以实际位置为准修正）
        let newNum = 1
        const pos = content.value.search(new RegExp('^##\\s*(?:\\d+、?)?\\s*' + esc + '\\s*$', 'm'))
        if (pos === -1) {
          // 找不到新节标题行（异常情况）→ 不动编号，原样保留
          content.value = content.value.replace(/\n{3,}/g, '\n\n')
          renderRight()
          save()
          ElMessage.success('已应用 AI 修改')
          return
        }
        const prevNums = content.value.slice(0, pos).match(/##\s*(\d+)、/g)
        if (prevNums && prevNums.length) {
          newNum = parseInt(prevNums[prevNums.length - 1].match(/\d+/)[0]) + 1
        }
        let t = content.value
        // 1) 用占位保护新插入的节（避免它自己被 +1）
        t = t.replace(new RegExp('^##\\s*(?:\\d+、?)?\\s*' + esc + '\\s*$', 'm'), '## @@NEWNUM@@、' + renTitle)
        // 2) 其后所有同级编号 >= newNum 的 +1（原 3 → 4、原 4 → 5 …）
        t = t.replace(/^##\s+(\d+)、/gm, (mm, num) => {
          const n = parseInt(num)
          return n >= newNum ? mm.replace(num, String(n + 1)) : mm
        })
        // 3) 还原新插入的节编号
        t = t.replace('## @@NEWNUM@@、' + renTitle, '## ' + newNum + '、' + renTitle)
        content.value = t
      }
      content.value = content.value.replace(/\n{3,}/g, '\n\n')
      renderRight()
      save()
      ElMessage.success('已应用 AI 修改')
    }
    return
  }
  const reject = e.target.closest('.ai-reject')
  if (reject) {
    const box = reject.closest('.ai-inline-diff')
    if (box && box.dataset.block) {
      // 多修改点内嵌块：从列表移除该块（watcher 重渲染，原文从 content.value 恢复）
      const b = aiBlocks.value.find(x => String(x.id) === box.dataset.block)
      if (b) rejectBlock(b)
      return
    }
    if (box) {
      const tmpBox = document.createElement('div')
      tmpBox.innerHTML = renderMd(box.dataset.origin || '')
      const frag = document.createDocumentFragment()
      while (tmpBox.firstChild) frag.appendChild(tmpBox.firstChild)
      box.replaceWith(frag)
      onEdit()
      ElMessage.info('已拒绝修改')
    }
    return
  }
  const wrap = e.target.closest('eq-wrap')
  if (wrap) { e.preventDefault(); eqEditingEl = wrap; eqForm.value = wrap.getAttribute('data-eq') || ''; eqOpen.value = true; return }
}

// ── 图片边缘拖拽缩放（无手柄：鼠标移到图片边缘光标变双箭头，按住拖） ──
let imgDrag = null
const onImgZoneDown = (e) => {
  const rz = e.target.closest('.rz')
  if (!rz || !rightEl.value) return
  e.preventDefault(); e.stopPropagation()
  const zone = rz.closest('.img-zone')
  const img = zone ? zone.querySelector('img') : null
  if (!img) return
  const m = rz.className.match(/rz-(\w+)/)
  const dir = m ? m[1] : 'se'
  imgDrag = { dir, img, startX: e.clientX, startY: e.clientY, w: img.offsetWidth, h: img.offsetHeight }
  // 拉伸期间全局保持对应方向的拉伸光标（鼠标移出图片到正文文本区也不变回 I 形）
  const C = { e: 'ew', w: 'ew', n: 'ns', s: 'ns', nw: 'nwse', se: 'nwse', ne: 'nesw', sw: 'nesw' }[dir] || 'nwse'
  document.body.classList.add('resizing-' + C)
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeEnd)
}
const onResizeMove = (e) => {
  if (!imgDrag) return
  const dx = e.clientX - imgDrag.startX
  const dy = e.clientY - imgDrag.startY
  let w = imgDrag.w, h = imgDrag.h
  if (imgDrag.dir.includes('e')) w = imgDrag.w + dx
  if (imgDrag.dir.includes('w')) w = imgDrag.w - dx
  if (imgDrag.dir.includes('s')) h = imgDrag.h + dy
  if (imgDrag.dir.includes('n')) h = imgDrag.h - dy
  if (w < 20) w = 20
  if (h < 20) h = 20
  imgDrag.img.style.width = w + 'px'
  imgDrag.img.style.height = h + 'px'
}
const onResizeEnd = () => {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeEnd)
  document.body.classList.remove('resizing-ew', 'resizing-ns', 'resizing-nwse', 'resizing-nesw')
  if (imgDrag) { if (imgDrag.img) onEdit(); imgDrag = null }
}
const eqInsertDisplay = ref(false)
const openEqInsert = () => { eqEditingEl = null; eqForm.value = ''; eqInsertDisplay.value = false; eqOpen.value = true }
const openEqInsertBlock = () => { eqEditingEl = null; eqForm.value = '\\text{块公式}'; eqInsertDisplay.value = true; eqOpen.value = true }
const insertEqWrap = (eq, display) => {
  const el = document.createElement('eq-wrap')
  el.setAttribute('data-eq', eq)
  el.setAttribute('data-display', display ? '1' : '0')
  el.setAttribute('contenteditable', 'false')
  try { el.innerHTML = katex.renderToString(eq, { displayMode: display, throwOnError: false }) } catch (err) { el.innerHTML = '<span class="eq-err">' + escapeHtml(eq) + '</span>' }
  rightEl.value?.focus()
  // 走 execCommand 插入，可被 Ctrl+Z 撤销；失败时退回手动插入
  const ok = document.execCommand('insertHTML', false, el.outerHTML)
  if (!ok) {
    const sel = window.getSelection()
    if (sel && sel.rangeCount && rightEl.value && rightEl.value.contains(sel.anchorNode)) {
      const range = sel.getRangeAt(0)
      range.deleteContents()
      range.insertNode(el)
      range.setStartAfter(el); range.collapse(true)
      sel.removeAllRanges(); sel.addRange(range)
    } else if (rightEl.value) {
      rightEl.value.appendChild(document.createElement('br'))
      rightEl.value.appendChild(el)
    }
  }
  onEdit()
}
const saveEq = () => {
  const eq = eqForm.value.trim()
  if (eq) {
    if (eqEditingEl) {
      let k = ''
      try { k = katex.renderToString(eq, { displayMode: eqEditingEl.getAttribute('data-display') === '1', throwOnError: false }) } catch (err) { k = '<span class="eq-err">' + escapeHtml(eq) + '</span>' }
      eqEditingEl.setAttribute('data-eq', eq)
      eqEditingEl.innerHTML = k
      if (rightEl.value) content.value = td.turndown(rightEl.value.innerHTML)
    } else {
      insertEqWrap(eq, eqInsertDisplay.value)
    }
  }
  eqOpen.value = false
  eqEditingEl = null
}

// ── 富文本工具栏（单编辑区，所见即所得） ──
let selBarLock = false // 点击格式按钮后吞掉一次 selectionchange，避免工具条立刻重新弹出
let selecting = false   // 正在拖选（mousedown~mouseup），期间不显示工具条，避免疯狂闪动
let selRaf = null
const selBar = ref({ show: false, x: 0, y: 0 })
const caretAi = ref({ show: false, x: 0, y: 0 })  // 光标后悬浮的小 ✨ 按钮
const showSelBar = () => {
  if (selBarLock) { selBarLock = false; return }
  if (selecting) { selBar.value.show = false; caretAi.value.show = false; return }  // 拖选中：隐藏
  if (!rightEl.value) return
  const sel = window.getSelection()
  if (!sel || sel.rangeCount === 0) { selBar.value.show = false; caretAi.value.show = false; return }
  if (!rightEl.value.contains(sel.anchorNode) && !rightEl.value.contains(sel.focusNode)) { selBar.value.show = false; caretAi.value.show = false; return }
  const rect = sel.getRangeAt(0).getBoundingClientRect()
  if (sel.isCollapsed) {
    // 光标模式：光标后悬浮一个 ✨ 按钮（点它告诉 AI 在光标处新增）
    selBar.value.show = false
    // rect 无效（光标在空白/换行/公式旁时可能为 0,0）→ 用最近点击位置兜底，保证公式旁/标题旁也能用
    if (!rect || (rect.left === 0 && rect.top === 0 && rect.width === 0 && rect.height === 0)) {
      if (lastClickPos && Date.now() - lastClickTime < 800) {
        if (selRaf) cancelAnimationFrame(selRaf)
        const t = { show: true, x: lastClickPos.x + 8, y: lastClickPos.y + 8 }
        selRaf = requestAnimationFrame(() => { caretAi.value = t })
      } else {
        caretAi.value.show = false
      }
      return
    }
    const cx = Math.max(4, Math.min(rect.left + rect.width + 3, window.innerWidth - 40))
    const cy = rect.top + rect.height / 2
    if (selRaf) cancelAnimationFrame(selRaf)
    const target = { show: true, x: cx, y: cy }
    selRaf = requestAnimationFrame(() => { caretAi.value = target })
    return
  }
  caretAi.value.show = false
  let y = rect.top - 46              // 工具条高约 34px + 12px 间距，完全悬浮在选区上方不压字
  if (y < 76) y = rect.bottom + 12   // 上方放不下（靠近顶部）→ 放选区下方，避免压住文字
  if (selRaf) cancelAnimationFrame(selRaf)
  const target = { show: true, x: rect.left + rect.width / 2, y }
  selRaf = requestAnimationFrame(() => { selBar.value = target })  // rAF 节流，减少闪烁
}
const onSelDown = (e) => {
  // 点在工具条/弹窗上不算拖选，否则按钮一按就被隐藏、点击失效
  if (e.target && e.target.closest && (e.target.closest('.sel-bar') || e.target.closest('.modal-mask'))) return
  if (rightEl.value && rightEl.value.contains(e.target)) { selecting = true; selBar.value.show = false }
}
const onSelUp = () => {
  selecting = false
  setTimeout(showSelBar, 0)   // 等选区稳定后再显示
}
const selFmt = (cmd) => { document.execCommand(cmd); selBar.value.show = false; selBarLock = true; onEdit() }
const selFmtBlock = (tag) => { document.execCommand('formatBlock', false, tag); selBar.value.show = false; selBarLock = true; onEdit() }

// ── AI 修改（Copilot 式：内嵌 diff 建议 → 逐个接受/拒绝） ──
const aiSugLoading = ref(false)
const aiInstOpen = ref(false)
const aiInstText = ref('')
let aiSelRange = null
let lastClickPos = null      // 编辑器内最后一次点击坐标（视口）
let lastClickTime = 0
const openAiEdit = () => {
  // 支持两种场景：1) 选中文字修改；2) 光标位置（无选中）在下方新增内容
  const sel = window.getSelection()
  aiSelRange = (sel && sel.rangeCount) ? sel.getRangeAt(0).cloneRange() : null
  if (!aiSelRange) aiSelRange = document.createRange() // 兜底
  if (!rightEl.value) { ElMessage.warning('编辑器未就绪'); return }
  aiInstText.value = ''
  aiInstOpen.value = true
}
const sendAiEdit = async () => {
  if (!aiInstText.value.trim() || !aiSelRange) return
  aiSugLoading.value = true
  aiInstOpen.value = false
  try {
    const targetTxt = aiSelRange.toString()
    const res = await api.post('/ai/edit-suggest', { instruction: aiInstText.value.trim(), target: targetTxt, context: content.value })
    const edits = res.data.edits || []
    // 空笔记场景：后端直接返回完整内容（content 字段）→ 写入编辑器，用户继续编辑后保存
    if (res.data.content) {
      content.value = res.data.content
      ElMessage.success('AI 已生成内容，可继续编辑后保存')
      return
    }
    if (!edits.length) { ElMessage.warning('AI 没有返回有效内容，请换个说法重试'); return }
    // 兜底：空笔记时 AI 可能返回 target 为空的 edit → 同样直接写入
    const emptyEdit = edits.find(e => !(e.target || '').trim())
    if (emptyEdit) {
      content.value = emptyEdit.replacement
      ElMessage.success('AI 已生成内容，可继续编辑后保存')
      return
    }
    if (targetTxt.trim()) {
      // 选中文字 → 定点修改：同样走 aiBlocks 内嵌（统一逻辑：内嵌 diff + acceptBlock/rejectBlock）
      const e0 = edits.find(e => targetTxt.includes(e.target) || e.target.includes(targetTxt)) || edits[0]
      const fresh = mergeAiBlocks([makeBlock(e0.target, e0.replacement)])
      if (!fresh.length || !fresh[0].found) {
        ElMessage.warning('AI 给出的修改位置在正文中找不到，可能上下文已变化，请重新生成或手动修改')
      }
    } else {
      // 第一组功能：未选中 → AI 自定位全文多处修改（Cursor 式：内嵌 diff，累积分批接受）
      const newBlocks = edits.map(e => makeBlock(e.target, e.replacement))
      const fresh = mergeAiBlocks(newBlocks)
      const found = fresh.filter(b => b.found).length
      if (!found && newBlocks.length) {
        ElMessage.warning('AI 给出的修改位置在正文中找不到，可能上下文已变化，请重新生成或手动修改')
      } else {
        ElMessage.info(`AI 找到 ${found} 处新修改建议，可逐个接受/拒绝`)
      }
    }
  } catch (e) { ElMessage.error(e.response?.data?.error || 'AI 请求失败') }
  finally { aiSugLoading.value = false }
}

const hideSelBar = () => { selBar.value.show = false }
const showSource = ref(false)
const sourceClosed = ref(true) // 源码面板动画完全结束后才显示“源码”按钮
const openSource = () => { flushEdit(); sourceClosed.value = false; showSource.value = true }
const onSrcAfterLeave = () => { sourceClosed.value = true }
const fileInput = ref(null)
const fmt = (cmd) => { rightEl.value?.focus(); document.execCommand(cmd); onEdit() }
const fmtBlock = (tag) => { rightEl.value?.focus(); document.execCommand('formatBlock', false, tag); onEdit() }
const pickImage = () => fileInput.value?.click()

// 批注框手绘：复用全局工具球（DoodleBall 同一套画笔），目标为批注框内的画布
const openDoodle = (e) => {
  // 1) 光标在批注块内 → 画光标所在的批注框
  const sel = window.getSelection()
  let node = sel && sel.anchorNode
  if (node && node.nodeType !== 1) node = node.parentElement
  const annBlock = (node && node.closest) ? node.closest('.ann-block') : null
  // 2) 或鼠标悬停在某个批注框上 → 画那个批注框
  let hoverBlock = null
  try {
    const hover = e && e.clientX != null ? document.elementFromPoint(e.clientX, e.clientY) : null
    if (hover && hover.closest) hoverBlock = hover.closest('.ann-block')
  } catch (err) { /* 忽略 */ }
  const target = annBlock || hoverBlock
  if (target) {
    let cv = target.querySelector('canvas.ann-doodle')
    if (!cv) cv = ensureDoodleCanvas(target)
    if (cv) {
      // 手绘激活：画布铺满整个批注框（重设像素尺寸，全框可画；已有笔迹按比例重画）
      const r = target.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      const w = Math.max(1, Math.round(r.width * dpr))
      const h = Math.max(1, Math.round(r.height * dpr))
      if (cv.width !== w || cv.height !== h) {
        cv.width = w
        cv.height = h
        const id = target.getAttribute('data-ann-id')
        const rec = id ? annMap.value[id] : null
        if (rec && rec.strokes && rec.strokes.length) drawStrokes(cv, rec.strokes, rec.canvas_w || 100, rec.canvas_h || 100)
      }
      window.dispatchEvent(new CustomEvent('zhiyu:toggle-doodle', { detail: { target: cv, x: r.left + r.width / 2, y: r.top } }))
    }
    return
  }
  window.dispatchEvent(new CustomEvent('zhiyu:toggle-doodle', { detail: { x: e.clientX, y: e.clientY } }))
}

// 工具球完成批注框手绘：把笔迹存到该批注记录（局部保存，不碰正文），并画到垫底画布持久显示
const onAnnDoodleSave = async (ev) => {
  const d = ev.detail || {}
  const cv = d.canvas
  const strokes = d.strokes || []
  if (!cv || !strokes.length) return
  const block = cv.closest ? cv.closest('.ann-block') : null
  if (!block) return
  const id = block.getAttribute('data-ann-id')
  if (!id) return
  try {
    // 坐标是像素基准（DoodleBall 用 cv.width/rect.width 换算），保存像素尺寸供等比重画
    await api.put('/annotations/' + id, { strokes, canvas_w: cv.width, canvas_h: cv.height })
    if (annMap.value[id]) {
      annMap.value[id].strokes = strokes
      annMap.value[id].canvas_w = cv.width
      annMap.value[id].canvas_h = cv.height
    }
    requestAnimationFrame(() => drawStrokes(cv, strokes, cv.width, cv.height))
    ElMessage.success('手绘已保存到批注')
  } catch (err) { ElMessage.error('手绘保存失败') }
}
const onFilePick = async (e) => {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (file) await insertImage(file)
}

// ── 图片插入（粘贴 / 工具栏选择共用） ──
const insertImage = async (file) => {
  const dataUrl = await new Promise((resolve) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsDataURL(file) })
  try {
    const res = await api.post('/annotations/upload-img', { img: dataUrl })
    const url = '/uploads/' + res.data.path
    rightEl.value?.focus()
    // 走 execCommand 插入，可被 Ctrl+Z 撤销；失败时退回手动插入
    const html = '<span class="img-zone" contenteditable="false"><img src="' + url + '" style="max-width:100%" /><span class="rz rz-nw"></span><span class="rz rz-n"></span><span class="rz rz-ne"></span><span class="rz rz-e"></span><span class="rz rz-se"></span><span class="rz rz-s"></span><span class="rz rz-sw"></span><span class="rz rz-w"></span></span>'
    const ok = document.execCommand('insertHTML', false, html)
    if (!ok) {
      const img = document.createElement('img')
      img.src = url
      img.style.maxWidth = '100%'
      const sel = window.getSelection()
      if (sel && sel.rangeCount && rightEl.value && rightEl.value.contains(sel.anchorNode)) {
        const range = sel.getRangeAt(0)
        range.deleteContents()
        range.insertNode(img)
        range.setStartAfter(img)
        range.collapse(true)
        sel.removeAllRanges(); sel.addRange(range)
      } else if (rightEl.value) {
        rightEl.value.appendChild(document.createElement('br'))
        rightEl.value.appendChild(img)
      }
    }
    onEdit()
    ElMessage.success('图片已插入')
  } catch (err) { ElMessage.error('图片上传失败') }
}
const onPaste = async (e) => {
  const items = e.clipboardData?.items || []
  let file = null
  for (const it of items) { if (it.type && it.type.startsWith('image/')) { file = it.getAsFile(); break } }
  if (!file) return
  e.preventDefault()
  await insertImage(file)
}

const editorRef = ref(null)
const symbolPanel = ref(false)
const symbolBarRef = ref(null)
const closeSymbolPanel = (e) => {
  if (symbolBarRef.value && !symbolBarRef.value.contains(e.target)) symbolPanel.value = false
}
const symbolTab = ref('latex')

const LATEX_GROUPS = [
  { name: '希腊字母', items: [
    { label: 'α alpha', code: '\\alpha' }, { label: 'β beta', code: '\\beta' },
    { label: 'γ gamma', code: '\\gamma' }, { label: 'δ delta', code: '\\delta' },
    { label: 'ε epsilon', code: '\\varepsilon' }, { label: 'θ theta', code: '\\theta' },
    { label: 'λ lambda', code: '\\lambda' }, { label: 'μ mu', code: '\\mu' },
    { label: 'π pi', code: '\\pi' }, { label: 'σ sigma', code: '\\sigma' },
    { label: 'φ phi', code: '\\varphi' }, { label: 'ω omega', code: '\\omega' },
    { label: 'Δ Delta', code: '\\Delta' }, { label: 'Σ Sigma', code: '\\Sigma' }, { label: 'Ω Omega', code: '\\Omega' },
  ]},
  { name: '分数与根式', items: [
    { label: '分数', code: '\\frac{a}{b}' }, { label: '根号', code: '\\sqrt{x}' },
    { label: 'n 次根', code: '\\sqrt[n]{x}' }, { label: '绝对值', code: '|x|' },
  ]},
  { name: '积分与求和', items: [
    { label: '定积分', code: '\\int_{a}^{b} f(x)\\,dx' }, { label: '二重积分', code: '\\iint_{D}' },
    { label: '曲线积分', code: '\\oint_{C}' }, { label: '求和', code: '\\sum_{i=1}^{n}' },
    { label: '连乘', code: '\\prod_{i=1}^{n}' }, { label: '无穷', code: '\\infty' },
  ]},
  { name: '极限与导数', items: [
    { label: '极限', code: '\\lim_{x \\to 0}' }, { label: '趋于', code: '\\to' },
    { label: '偏导数', code: '\\frac{\\partial f}{\\partial x}' }, { label: '微分', code: '\\mathrm{d}x' },
    { label: '梯度', code: '\\nabla f' }, { label: "二阶导", code: "f\u0027\u0027(x)" },
  ]},
  { name: '集合与逻辑', items: [
    { label: '属于', code: '\\in' }, { label: '子集', code: '\\subset' },
    { label: '并集', code: '\\cup' }, { label: '交集', code: '\\cap' },
    { label: '空集', code: '\\emptyset' }, { label: '任意', code: '\\forall' },
    { label: '存在', code: '\\exists' }, { label: '且', code: '\\land' },
    { label: '或', code: '\\lor' }, { label: '非', code: '\\lnot' },
  ]},
  { name: '关系与箭头', items: [
    { label: '≤', code: '\\leq' }, { label: '≥', code: '\\geq' },
    { label: '≠', code: '\\neq' }, { label: '≈', code: '\\approx' },
    { label: '≡', code: '\\equiv' }, { label: '蕴含', code: '\\Rightarrow' },
    { label: '等价', code: '\\Leftrightarrow' }, { label: '↔', code: '\\leftrightarrow' },
  ]},
]

const UNICODE_GROUPS = [
  { name: '希腊字母', items: ['α','β','γ','δ','ε','ζ','η','θ','λ','μ','π','σ','φ','ω','Δ','Σ','Ω'] },
  { name: '运算符', items: ['+','−','×','÷','±','∓','√','∑','∏','∫','∮','∂','∇'] },
  { name: '关系符号', items: ['≤','≥','≠','≈','≡','≪','≫','∞'] },
  { name: '集合', items: ['∈','∉','⊂','⊆','⊇','∪','∩','∅','∀','∃'] },
  { name: '箭头', items: ['→','←','↑','↓','⇒','⇔','↔'] },
  { name: '逻辑', items: ['∧','∨','¬','∴','∵'] },
  { name: '上下标', items: ['x²','x³','xᵢ','x₀','x₁','aᵏ','eˣ','10⁻³'] },
]

const insertAtCursor = (text) => {
  const sel = window.getSelection()
  if (rightEl.value && sel && sel.rangeCount && rightEl.value.contains(sel.anchorNode)) {
    // 右栏（所见即所得）光标处插入
    document.execCommand('insertText', false, text)
    onEdit()
    return
  }
  const ta = editorRef.value
  if (!ta) { content.value += text; renderRight(); return }
  const start = ta.selectionStart ?? content.value.length
  const end = ta.selectionEnd ?? content.value.length
  content.value = content.value.slice(0, start) + text + content.value.slice(end)
  nextTick(() => { ta.focus(); ta.selectionStart = ta.selectionEnd = start + text.length })
}
const insertLatex = (code) => insertAtCursor('$' + code + '$')
const insertUnicode = (ch) => insertAtCursor(ch)
const insertBlockFormula = () => insertAtCursor('\n$$\n' + '公式' + '\n$$\n')

const load = async () => {
  if (!isEdit.value) return
  loading.value = true
  try {
    const res = await api.get('/docs/' + docId.value)
    title.value = res.data.title
    loadedPubId.value = res.data.public_id || ''
    type.value = res.data.type
    content.value = res.data.content
    visibility.value = res.data.visibility
    await nextTick()
    renderRight()
    // 检查本地暂存（未保存的修改）：AI 预填的草稿直接应用；普通草稿提示恢复
    try {
      const raw = localStorage.getItem(draftKey())
      if (raw) {
        const d = JSON.parse(raw)
        if (d && d.ai === true) {
          // AI 修改 → 自动弹红绿 diff 对比（原文 vs AI 内容），接受才应用，不直接覆盖
          title.value = d.title || title.value
          type.value = d.type || type.value
          if (d.visibility !== undefined) visibility.value = d.visibility
          localStorage.removeItem(draftKey())
          await nextTick()
          renderRight()
          if (d.content && d.content !== res.data.content) {
            aiBlocks.value = makeBlocksFromFull(res.data.content || '', d.content)
            if (aiBlocks.value.length) {
              ElMessage.info(`AI 修改已生成对比：共 ${aiBlocks.value.length} 处，可逐个接受/拒绝`)
              nextTick(() => locateAiDiff())
            }
          } else {
            ElMessage.success('AI 内容已载入，可微调后保存')
          }
        } else if (d && (d.content !== res.data.content || d.title !== res.data.title)) {
          draftTs.value = d.ts || 0
          draftTime.value = new Date(d.ts || Date.now()).toTimeString().slice(0, 5)
          showDraftRestore.value = true
        } else {
          localStorage.removeItem(draftKey())
        }
      }
    } catch (e2) {}
    // 后端 AI 草稿（AI 工具 save_draft 写入）：有则弹 diff 对比，接受才应用
    try {
      const dr = await api.get('/docs/' + docId.value + '/draft')
      if (dr.data.draft && dr.data.draft !== res.data.content) {
        aiBlocks.value = makeBlocksFromFull(res.data.content || '', dr.data.draft)
        if (aiBlocks.value.length) {
          ElMessage.info(`AI 修改已生成对比：共 ${aiBlocks.value.length} 处，可逐个接受/拒绝`)
          nextTick(() => locateAiDiff())
        }
      }
    } catch (e3) {}
  } catch (e) {
    if (e.response?.status === 403 || e.response?.status === 404) { notFound.value = true; ElMessage.error('无权限编辑或笔记不存在') }
  }
  loading.value = false
  await nextTick()
  renderRight()
}

const save = async (opts = {}) => {
  if (!title.value.trim()) { ElMessage.warning('请填写标题'); return }
  if (!content.value.trim()) { ElMessage.warning('内容不能为空'); return }
  if (!type.value.trim()) { ElMessage.warning('请填写分类（如：高等数学）'); return }
  // AI 接受/拒绝场景（opts.noFlush）：content.value 已是权威值，跳过 flushEdit，
  // 避免 turndown 把预览区里残留的 diff 块按钮文字（✓ 接受 ✕ 拒绝）转进正文
  if (!opts.noFlush) {
    // 手动保存时：若预览区还有未处理的 AI diff 块，先用 content.value 重建（恢复被 diff 块替换的原文），
    // 避免 diff 块按钮文字被 turndown 转进正文；未接受的修改仍保留在 aiBlocks 中，之后可继续接受
    if (rightEl.value && rightEl.value.querySelector('.ai-inline-diff[data-block]')) {
      renderRight()
    }
    flushEdit()   // 确保编辑区最新内容已转成 markdown
  }
  busy.value = true
  try {
    if (isEdit.value) {
      await api.put(`/docs/${docId.value}`, { type: type.value, title: title.value, content: content.value, visibility: visibility.value })
      ElMessage.success('已保存')
      clearDraft()
    } else {
      const fd = new FormData()
      fd.append('file', new Blob([content.value], { type: 'text/markdown' }), 'note.md')
      fd.append('type', type.value)
      fd.append('title', title.value)
      fd.append('visibility', visibility.value)
      const res = await api.post('/docs', fd)
      ElMessage.success('发布成功')
      clearDraft()
      router.replace('/edit/' + res.data.id)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  }
  busy.value = false
}

// ── 本地自动暂存：编辑内容防抖存 localStorage，防刷新丢失；保存成功后清除 ──
const draftKey = () => 'zhiyu_draft_' + (isEdit.value ? docId.value : 'new')
const draftTs = ref(0)
const draftTime = ref('')
const showDraftRestore = ref(false)
let draftTimer = null
const persistDraft = () => {
  try {
    localStorage.setItem(draftKey(), JSON.stringify({ title: title.value, type: type.value, visibility: visibility.value, content: content.value, ts: Date.now() }))
    draftTs.value = Date.now()
    draftTime.value = new Date().toTimeString().slice(0, 5)
  } catch (e) {}
}
const clearDraft = () => {
  try { localStorage.removeItem(draftKey()) } catch (e) {}
  draftTs.value = 0
  draftTime.value = ''
}
const restoreDraft = () => {
  try {
    const raw = localStorage.getItem(draftKey())
    if (!raw) return
    const d = JSON.parse(raw)
    if (d.title !== undefined) title.value = d.title
    if (d.type !== undefined) type.value = d.type
    if (d.visibility !== undefined) visibility.value = d.visibility
    if (d.content !== undefined) { content.value = d.content; renderRight() }
    draftTs.value = 0
    showDraftRestore.value = false
    ElMessage.success('已恢复暂存内容')
  } catch (e) {}
}
const discardDraft = () => { clearDraft(); showDraftRestore.value = false }
watch([content, title, type, visibility], () => {
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(persistDraft, 800)
})

// 剥离 AI 插入内容里的思考前缀与标记（AI 常输出「用户要求给 XX 加…」「【要插入的新内容片段】」等，不能当正文）
const cleanAiInsertText = (raw) => {
  let t = String(raw || '')
  // 去掉 AI 思考叙述：以"用户要求/需要给/根据/好的"等开头的非正文段落
  t = t.replace(/^(用户要求|需要|根据|好的|以下是|这是要插入|我在|我将在|已为|为你)[^\n]*\n+/g, '')
  // 去掉【要插入的新内容片段】【新内容】【知屿操作：插入】等标记行
  t = t.replace(/【[^】]*】[^\n]*\n*/g, '')
  t = t.replace(/^\s*(新内容|插入内容|代码实现如下|内容如下)[：:]\s*\n*/g, '')
  return t.trim()
}

// 智能定位插入点：AI 内容若含章节号（如 "3.3 代码实现"），插到对应 ## 章节末尾；否则插到全文末尾
const locateAiInsertPos = (aiText) => {
  const c = content.value || ''   // 注意：不能用 const content（会遮蔽外层 ref 触发 TDZ）
  // 提取 AI 内容里的章节号，如 "### 3.3 代码实现" → 3；只匹配行首数字（标题行），避免匹配到正文里的数字
  const secMatch = aiText.match(/^#{1,4}\s*(\d+)(?:\.\d+)?\s*[、.．]?\s*[^\n]*$/m) || aiText.match(/^\s*(\d+)\s*[、.．]\s*[^\n]*$/m)
  if (!secMatch) return c.length
  const secNum = parseInt(secMatch[1], 10)
  if (!secNum) return c.length
  // 找笔记里对应的一级章节 ## N. 标题
  const re = /^##\s*(\d+)[、.．]?\s*[^\n]*$/gm
  let mm = null
  let targetIdx = -1
  let nextIdx = -1
  while ((mm = re.exec(c)) !== null) {
    const n = parseInt(mm[1], 10)
    if (n === secNum) targetIdx = mm.index
    else if (targetIdx !== -1 && n > secNum) { nextIdx = mm.index; break }
  }
  if (targetIdx === -1) return c.length
  return nextIdx !== -1 ? nextIdx : c.length
}

// 取插入点前最后一个「有效内容行」做锚点：跳过空行、`* * *` 分隔线、纯符号行（这些 normLine 后为空，无法定位）
const pickInsertAnchor = (original, pos) => {
  const lines = original.slice(0, pos).split('\n')
  for (let i = lines.length - 1; i >= 0; i--) {
    const s = lines[i].trim()
    if (!s) continue
    if (/^[*\-_=~]{3,}\s*$/.test(s)) continue   // * * * 分隔线
    if (!normLine(s)) continue                   // 去符号后为空（纯 markdown 符号）
    return s
  }
  return ''
}

const onAiInsert = (e) => {
  const text = cleanAiInsertText(e.detail?.text)
  if (!text) return
  const original = content.value || ''
  const pos = locateAiInsertPos(text)
  const anchor = pickInsertAnchor(original, pos)
  if (!anchor) { ElMessage.warning('无法定位插入位置，请手动插入'); return }
  const block = makeBlock(anchor, anchor + '\n' + text)
  if (!block.found) { ElMessage.warning('插入位置在正文中找不到，请手动插入'); return }
  mergeAiBlocks([block])
  ElMessage.info('AI 新增内容已内嵌到对应位置（绿色为新增），可接受/拒绝')
}

// ── AI 修改建议 → 多修改点红绿 diff 卡片（Cursor 式：AI 自定位，可多处，逐个接受/拒绝） ──
let blockId = 0
const aiBlocks = ref([]) // [{ id, target, replacement, parts, ctxBefore, ctxAfter, start, end, found, applied }]
const pendingAiBlocks = () => aiBlocks.value.filter(b => !b.applied)

// 行文本归一化（用于容错匹配）：去掉 markdown 符号与空白差异
const normLine = (s) => s.replace(/^[\s\-*#>]+/, '').replace(/[*#_`~>|]/g, '').replace(/\s+/g, ' ').trim()

// 锚点定位：在 content 中找 target 原文（先精确 → 行级 trim → 行级去符号宽松匹配），返回 {start, end} 或 null
const locateAnchor = (content, target) => {
  if (!target) return null
  const exact = content.indexOf(target)
  if (exact !== -1) return { start: exact, end: exact + target.length }
  const tLines = target.split('\n').map(s => s.trim()).filter(s => s.length > 0)
  const cLines = content.split('\n')
  if (!tLines.length) return null
  const toOffset = (lineIdx) => {
    let off = 0
    for (let k = 0; k < lineIdx; k++) off += cLines[k].length + 1
    return off
  }
  // 1) 行级 trim 精确匹配：target 每一行都能按序匹配
  for (let i = 0; i + tLines.length <= cLines.length; i++) {
    let ok = true
    for (let j = 0; j < tLines.length; j++) {
      if (cLines[i + j].trim() !== tLines[j]) { ok = false; break }
    }
    if (ok) {
      const start = toOffset(i)
      const end = toOffset(i + tLines.length) - 1
      return { start, end }
    }
  }
  // 2) 宽松匹配：允许 target 中存在「新增行」（在原文中匹配不上），
  //    只要求其余行按序出现，替换区间取匹配行的首尾（replacement 自带完整新内容）
  const tNorm = tLines.map(normLine)
  let first = -1, last = -1, cIdx = 0, matched = 0
  for (const tn of tNorm) {
    let found = -1
    for (let k = cIdx; k < cLines.length; k++) {
      if (normLine(cLines[k]) === tn) { found = k; break }
    }
    if (found !== -1) {
      if (first === -1) first = found
      last = found
      cIdx = found + 1
      matched++
    }
    // 找不到：视为 target 里的新增行，跳过
  }
  if (matched === 0) return null
  // 若 target 首行在更靠前的位置有匹配（前面跳过了），回退重找更早的起点，避免定位到后半段
  for (let i = 0; i < first; i++) {
    if (normLine(cLines[i]) === tNorm[0]) { first = i; break }
  }
  const start = toOffset(first)
  const end = toOffset(last + 1) - 1
  return { start, end }
}

// 上下文：定位点前后各取若干行用于展示（从行首/行尾截取，避免大段拷贝）
const blockCtx = (content, start, end, before = 2, after = 2) => {
  let lineStart = content.lastIndexOf('\n', start - 1)
  for (let i = 0; i < before && lineStart > 0; i++) {
    const prev = content.lastIndexOf('\n', lineStart - 1)
    if (prev === -1) break
    lineStart = prev
  }
  const ctxBefore = content.slice(lineStart === -1 ? 0 : (content[lineStart] === '\n' ? lineStart + 1 : lineStart), start)
  let lineEnd = content.indexOf('\n', end)
  for (let i = 0; i < after && lineEnd !== -1; i++) {
    const next = content.indexOf('\n', lineEnd + 1)
    if (next === -1) break
    lineEnd = next
  }
  const ctxAfter = content.slice(end, lineEnd === -1 ? content.length : lineEnd)
  return { ctxBefore: ctxBefore.trim(), ctxAfter: ctxAfter.trim() }
}

// 生成一个修改块：target(锚点原文) + replacement(修改后文本)
// exactPos 可选：diff 分组时已知的精确偏移 {start, end}，优先使用，避免文本重复匹配出错
const makeBlock = (target, replacement, exactPos = null) => {
  const id = ++blockId
  const c = content.value || ''
  let pos = null
  if (exactPos && c.slice(exactPos.start, exactPos.end) === target) pos = exactPos
  else pos = locateAnchor(c, target)
  const found = !!pos
  const { ctxBefore = '', ctxAfter = '' } = pos ? blockCtx(c, pos.start, pos.end) : {}
  return {
    id, target, replacement,
    parts: diffLines(target, replacement),
    ctxBefore, ctxAfter,
    start: pos ? pos.start : -1, end: pos ? pos.end : -1,
    found, applied: false,
  }
}

// 完整内容模式：把「原文 vs AI 新全文」的 diff 自动分组为多个修改块
// 利用 diffLines 的偏移精确定位（不重新文本匹配，避免重复标题/常见行误匹配）。
// 空行 keep 归入当前 hunk（它在原文和新文中都存在）：新文本里要保留它，替换区间则不含它（原文中的保留）。
const makeBlocksFromFull = (original, suggestion) => {
  const parts = diffLines(original, suggestion)
  const blocks = []
  // 逐段累计 original 的偏移：keep 与 removed 的 value 都是 original 的一部分，added 不是
  let origPos = 0
  let cur = null    // { start, end, removed: [], added: [] }
  const flush = () => {
    if (!cur) return
    const target = original.slice(cur.start, cur.end)
    const added = cur.added.join('')
    if (cur.hasRemove) {
      // 修改/删除：target = 原文该段（按精确偏移切出），replacement = 新增文本（含被保留的空行）
      blocks.push(makeBlock(target, added, { start: cur.start, end: cur.end }))
    } else {
      // 纯插入：锚点 = 插入点前最后一个非空行（前端替换后新内容跟在原行后）
      const before = original.slice(0, cur.start)
      const lines = before.split('\n').filter(l => l.trim())
      const anchor = lines.length ? lines[lines.length - 1].trim() : ''
      if (anchor) blocks.push(makeBlock(anchor, anchor + '\n' + added))
      else if (added) blocks.push(makeBlock('', added, { start: 0, end: 0 }))
    }
    cur = null
  }
  for (const p of parts) {
    const isKeep = !p.added && !p.removed
    if (isKeep) {
      if (p.value.trim() === '') {
        // 空行：它在原文和新文中都存在。若当前在 hunk 内，既要进入替换区间（cur.end 推进），
        // 也要留在新文本里（added 保留），这样 target 与 replacement 中的空行相互抵消
        if (cur) {
          cur.added.push(p.value)
          cur.end = origPos + p.value.length
        }
        origPos += p.value.length
        continue
      }
      flush()
      origPos += p.value.length
      continue
    }
    if (!cur) cur = { start: origPos, end: origPos, removed: [], added: [], hasRemove: false }
    if (p.removed) {
      cur.hasRemove = true
      cur.removed.push(p.value)
      cur.end = origPos + p.value.length
      origPos += p.value.length
    }
    if (p.added) cur.added.push(p.value)
  }
  flush()
  return blocks
}

// 重新定位（内容可能因应用其他修改而变化）
const relocateBlocks = () => {
  const c = content.value || ''
  for (const b of aiBlocks.value) {
    if (b.applied) continue
    const pos = locateAnchor(c, b.target)
    b.found = !!pos
    b.start = pos ? pos.start : -1
    b.end = pos ? pos.end : -1
    if (pos) {
      const ctx = blockCtx(c, pos.start, pos.end)
      b.ctxBefore = ctx.ctxBefore; b.ctxAfter = ctx.ctxAfter
    }
  }
}

const acceptBlock = async (b) => {
  if (b.applied) return
  let t = content.value || ''
  let pos = locateAnchor(t, b.target)
  if (!pos) { b.failed = true; ElMessage.error('找不到该修改点对应的原文位置，可能已被其他修改影响'); return }
  // 只折叠替换区内的多余空行（AI 常把多条公式/条目挤在一起），不动全文，避免破坏代码块等
  const replaced = b.replacement.replace(/\n{3,}/g, '\n\n')
  t = t.slice(0, pos.start) + replaced + t.slice(pos.end)
  content.value = t
  b.applied = true
  b.failed = false
  // content.value 已是权威值：跳过 flushEdit 直接保存（避免 diff 块按钮文字被 turndown 转进正文）
  save({ noFlush: true })
  ElMessage.success('已应用该处修改')
  // 其余块位置可能已变，重新定位
  relocateBlocks()
  if (!pendingAiBlocks().length) aiBlocks.value = []
}

const rejectBlock = (b) => {
  aiBlocks.value = aiBlocks.value.filter(x => x.id !== b.id)
  if (!aiBlocks.value.length) return
}

const acceptAllBlocks = async () => {
  const t0 = content.value || ''
  // 一次性定位所有未应用块（基于同一份原文），从后往前应用避免位置漂移
  const located = []
  const failed = []
  for (const b of pendingAiBlocks()) {
    const pos = locateAnchor(t0, b.target)
    if (pos) located.push({ b, start: pos.start, end: pos.end })
    else failed.push(b)
  }
  if (!located.length) { ElMessage.error('没有可应用的修改点'); return }
  located.sort((a, c) => c.start - a.start)
  // 已应用区间（防止 AI 输出的多个 target 相互包含导致重复应用）
  const usedRanges = []
  let t = t0
  let ok = 0
  let skipped = 0
  for (const item of located) {
    // 重叠保护：本块区间与已应用块区间重叠 → 跳过（AI 输出相互包含）
    const overlap = usedRanges.some(r => item.start < r.end && item.end > r.start)
    if (overlap) { skipped++; continue }
    t = t.slice(0, item.start) + item.b.replacement + t.slice(item.end)
    usedRanges.push({ start: item.start, end: item.start + item.b.replacement.length })
    item.b.applied = true; ok++
  }
  content.value = t
  // content.value 已是权威值：跳过 flushEdit 直接保存（避免 diff 块按钮文字被 turndown 转进正文）
  await save({ noFlush: true })
  if (failed.length) ElMessage.warning(`已应用 ${ok} 处；${failed.length} 处找不到原文位置已跳过，${skipped} 处相互重叠已跳过`)
  else if (skipped) ElMessage.warning(`已应用 ${ok} 处修改（${skipped} 处相互重叠已跳过）`)
  else ElMessage.success(`已应用 ${ok} 处修改`)
  aiBlocks.value = aiBlocks.value.filter(b => !b.applied)
}

const rejectAllBlocks = () => { aiBlocks.value = [] }

// 合并新的 AI 修改块到未接受块后面（累积展示，分批接受）；接受/拒绝过的块不在其中
const mergeAiBlocks = (newBlocks) => {
  const kept = pendingAiBlocks()
  // 去重：相同 target+replacement 的块不重复追加
  const dup = newBlocks.filter(nb => kept.some(kb => kb.target === nb.target && kb.replacement === nb.replacement))
  const fresh = newBlocks.filter(nb => !kept.some(kb => kb.target === nb.target && kb.replacement === nb.replacement))
  aiBlocks.scrollDone = false   // 新一轮修改生成时允许重新滚动到第一个
  aiBlocks.value = [...kept, ...fresh]
  return fresh
}

// ── 内嵌渲染：把 aiBlocks 的每个修改点插到 rightEl 对应位置（Cursor 式，替代顶部面板） ──
// 每次先把 rightEl 重建为纯原文（content.value 渲染），再插入所有修改块；
// 接受/拒绝后由 aiBlocks watcher 触发本函数，原文永远从 content.value 恢复，不会丢失
const renderAiBlocksInline = () => {
  if (!rightEl.value) return
  const blocks = pendingAiBlocks().filter(b => b.found)
  // 重建为纯原文（清掉上次插入的 diff 块，恢复被替换的文本）
  rightEl.value.innerHTML = renderMd(content.value)
  bindAnnotations(rightEl.value, annMap.value, { editable: true, onInput: saveAnnText })
  ensureAnnCanvases(rightEl.value)
  const ctx = content.value || ''
  // 从后往前替换：先替换位置靠后的块，避免前面的块被替换成 diff 后，
  // 其内部渲染的 keep 行干扰后面块的锚点匹配（多块 target 相邻/重叠时只显示一个的问题）
  const ordered = [...blocks].sort((a, b) => (b.start || 0) - (a.start || 0))
  for (const b of ordered) {
    const pos = locateAnchor(ctx, b.target)
    if (!pos) continue
    // 定位：取 target 首行/末行去符号文本，在 rightEl 里找包含它们的块级元素（LI/P/DIV/TR 等）。
    // 按元素 textContent 匹配可跨 markdown 拆出的多个文本节点（如 <li><strong>单链表</strong>：…），
    // 避免按文本节点精确匹配必然失败的问题
    const tLines = b.target.split('\n').map(s => normLine(s)).filter(s => s.length > 0)
    const firstPlain = (tLines[0] || '').slice(0, 20)
    const lastPlain = tLines.length > 1 ? (tLines[tLines.length - 1] || '').slice(0, 20) : firstPlain
    if (!firstPlain) continue
    const BLOCK_TAGS = ['LI', 'P', 'DIV', 'TR', 'BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'PRE', 'UL', 'OL']
    // 收集块级元素，定位 target 覆盖的起止元素（首行 → 末行），整体替换成 diff 块。
    // 修复：旧实现只替换「首行所在块」，target 其余原文残留，导致删改大段内容时旧内容删不干净。
    const els = []
    const walker = document.createTreeWalker(rightEl.value, NodeFilter.SHOW_ELEMENT)
    while (walker.nextNode()) {
      const el = walker.currentNode
      if (!BLOCK_TAGS.includes(el.tagName)) continue
      els.push(el)
    }
    let startIdx = -1
    let endIdx = -1
    for (let i = 0; i < els.length; i++) {
      const txt = normLine(els[i].textContent)
      if (startIdx < 0 && txt.includes(firstPlain)) startIdx = i
      if (startIdx >= 0 && txt.includes(lastPlain)) { endIdx = i; break }
    }
    if (startIdx < 0) continue
    if (endIdx < 0) endIdx = startIdx
    const startEl = els[startIdx]
    const endEl = els[endIdx]
    const wrap = document.createElement('div')
    wrap.className = 'ai-inline-diff'
    wrap.setAttribute('contenteditable', 'false')
    wrap.dataset.block = String(b.id)
    const rows = b.parts.map(p =>
      '<div class="ai-diff-row ' + (p.added ? 'add' : p.removed ? 'del' : 'keep') + '">' +
        '<span class="ai-diff-mark">' + (p.added ? '+' : p.removed ? '-' : ' ') + '</span>' +
        '<span class="ai-diff-txt">' + renderMd(p.value) + '</span>' +
      '</div>'
    ).join('')
    wrap.innerHTML = rows + '<div class="ai-diff-ops"><button class="ai-accept" type="button">✓ 接受</button><button class="ai-reject" type="button">✕ 拒绝</button></div>'
    try {
      // 用 diff 块替换 target 覆盖的整段（首行元素到末行元素）：
      // 被删的原文行显示红色、新增行显示绿色（Cursor 式就地预览），
      // 接受/拒绝后 watcher 会重建 rightEl（应用新内容 / 恢复原文）
      const range = document.createRange()
      range.setStartBefore(startEl)
      range.setEndAfter(endEl)
      range.deleteContents()
      range.insertNode(wrap)
    } catch (e) { /* 忽略定位失败 */ }
  }
  // 有新生成的修改块时，滚动到第一个内嵌 diff 并高亮（接受/拒绝后的重渲染不再重复滚动）
  if (blocks.length && !aiBlocks.scrollDone) {
    aiBlocks.scrollDone = true
    locateAiDiff()
  }
}
// aiBlocks 变化后同步内嵌渲染（watch 里调用，避免每次赋值都手动调）
const aiBlocksWatcher = watch(aiBlocks, () => { nextTick(() => renderAiBlocksInline()) }, { deep: true })


// AI 声明改标题（【知屿标题：新标题】）→ 填入标题输入框
const onAiTitle = (e) => {
  const t = (((e.detail || {}).title) || '').trim()
  if (!t) return
  title.value = t
  ElMessage.success('AI 已设置标题：' + t)
}

// 聊天框/草稿 AI 修改 → 完整内容 diff → 内嵌多修改点
const onAiDiff = async (e) => {
  let sug = (e.detail?.suggestion || '').trim()
  const isInsert = !!e.detail?.insert
  if (!sug && e.detail?.fromDraft && isEdit.value) {
    // AI 用工具存了草稿 → 从草稿取内容做对比
    try {
      const dr = await api.get('/docs/' + docId.value + '/draft')
      sug = (dr.data.draft || '').trim()
    } catch (err) {}
  }
  if (!sug) return
  const original = content.value || ''
  if (isInsert) {
    // 插入场景：AI 输出的是「要新增的内容片段」→ 生成一个新增块（定位锚点 + 新内容），走内嵌 diff
    const cleaned = cleanAiInsertText(sug)
    if (!cleaned) { ElMessage.warning('AI 没有返回有效的新增内容，请换个说法重试'); return }
    // 定位插入点：AI 内容含章节号时插到对应 ## 章节末尾；否则全文末尾
    const pos = locateAiInsertPos(cleaned)
    const anchor = pickInsertAnchor(original, pos)
    if (!anchor) { ElMessage.warning('无法定位插入位置，请手动插入'); return }
    // 锚点行作为 target，replacement = 锚点行 + 新内容（diff 里锚点显示为不变，新内容显示为绿色新增）
    const block = makeBlock(anchor, anchor + '\n' + cleaned)
    if (!block.found) { ElMessage.warning('插入位置在正文中找不到，请手动插入'); return }
    mergeAiBlocks([block])
    ElMessage.info('AI 新增内容已内嵌到对应位置（绿色为新增），可接受/拒绝')
  } else {
    // 若 AI 输出明显是「要插入的片段」（含代码块或新小节标题）→ 视为插入，不触发整篇修改的过短拦截
    if (/```|^\s*#{2,4}\s/.test(sug)) {
      const cleaned = cleanAiInsertText(sug)
      if (!cleaned) { ElMessage.warning('AI 没有返回有效的新增内容，请换个说法重试'); return }
      const pos = locateAiInsertPos(cleaned)
      const anchor = pickInsertAnchor(original, pos)
      if (anchor) {
        const block = makeBlock(anchor, anchor + '\n' + cleaned)
        if (block.found) {
          mergeAiBlocks([block])
          ElMessage.info('AI 新增内容已内嵌到对应位置（绿色为新增），可接受/拒绝')
          nextTick(() => { if (aiBlocks.value.length) locateAiDiff() })
          return
        }
      }
    }
    // 安全：AI 输出过短（片段）不应用，避免毁掉整篇
    if (original.length > 0 && sug.length < original.length * 0.3) {
      ElMessage.error('AI 输出的内容像是片段而不是完整笔记，已取消。请让 AI 重新生成完整内容')
      return
    }
    const newBlocks = makeBlocksFromFull(original, sug)
    if (!newBlocks.length) { ElMessage.info('AI 没有产生实际修改（内容一致）'); return }
    mergeAiBlocks(newBlocks)
    ElMessage.info(`AI 修改已生成对比：新增 ${newBlocks.length} 处，可逐个接受/拒绝`)
  }
  nextTick(() => {
    if (aiBlocks.value.length) locateAiDiff()
  })
}

// IDE 式定位：滚动到第一个未应用修改点的内嵌 diff 块（预览区），并同步定位源码 textarea
const locateAiDiff = () => {
  const first = pendingAiBlocks().find(b => b.found)
  if (!first) return
  // 1) 预览区：找到第一个内嵌 diff 块并滚动到可视区 + 高亮
  if (rightEl.value) {
    const blockEl = rightEl.value.querySelector('.ai-inline-diff[data-block]')
    if (blockEl) {
      try {
        blockEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        blockEl.style.outline = '2px solid var(--brand-2)'
        blockEl.style.outlineOffset = '2px'
        setTimeout(() => { blockEl.style.outline = ''; blockEl.style.outlineOffset = '' }, 2500)
      } catch (e) { /* 忽略 */ }
      return
    }
  }
  // 2) 兜底：源码 textarea 定位到锚点行（预览区没渲染出块时）
  const ta = editorRef.value
  if (!ta) return
  const tLines = first.target.split('\n').map(s => s.trim()).filter(Boolean)
  const lines = content.value.split('\n')
  let targetLine = -1
  for (let i = 0; i + tLines.length <= lines.length; i++) {
    let ok = true
    for (let j = 0; j < tLines.length; j++) {
      if (lines[i + j].trim() !== tLines[j]) { ok = false; break }
    }
    if (ok) { targetLine = i; break }
  }
  if (targetLine < 0) return
  let offset = 0
  for (let i = 0; i < Math.min(targetLine, lines.length); i++) offset += lines[i].length + 1
  ta.focus()
  ta.selectionStart = ta.selectionEnd = offset
  const total = lines.length || 1
  ta.scrollTop = Math.max(0, (targetLine / total) * ta.scrollHeight - 80)
}

onMounted(() => {
  // 新建页：载入暂存草稿（zhiyu_draft_new）——AI 预填的直接应用并删除；用户普通暂存（未保存的新建内容）也恢复
  if (!isEdit.value) {
    // 上传流程带来的草稿（md 正文 + 图片已组装成 markdown）：直接应用并清除，之后跳过本地普通草稿恢复
    let appliedUpload = false
    try {
      const upRaw = sessionStorage.getItem('zhiyu_upload_new')
      if (upRaw) {
        const up = JSON.parse(upRaw)
        if (up && (up.content || up.title)) {
          if (up.title) title.value = up.title
          if (up.type) type.value = up.type
          if (up.visibility !== undefined) visibility.value = up.visibility
          if (up.content) {
            content.value = up.content
            nextTick(() => renderRight())
          }
          appliedUpload = true
          ElMessage.success('已载入上传内容（文字+图片），确认后点「保存」')
        }
        sessionStorage.removeItem('zhiyu_upload_new')
      }
    } catch (e) {}
    if (!appliedUpload) {
    try {
      const raw = localStorage.getItem('zhiyu_draft_new')
      if (raw) {
        const d = JSON.parse(raw)
        if (d && d.ai === true) {
          if (d.title) title.value = d.title
          if (d.type) type.value = d.type
          if (d.content) {
            content.value = d.content
            nextTick(() => renderRight())
          }
          localStorage.removeItem('zhiyu_draft_new')
          ElMessage.success('已载入 AI 生成的内容，确认后点「保存」')
        } else if (d && (d.content || d.title)) {
          // 用户自己暂存的新建草稿：恢复标题/分类/内容
          if (d.title) title.value = d.title
          if (d.type) type.value = d.type
          if (d.visibility !== undefined) visibility.value = d.visibility
          if (d.content) {
            content.value = d.content
            nextTick(() => renderRight())
          }
          ElMessage.success('已恢复未保存的新建草稿')
        }
      }
    } catch (e) {}
    }
  }
  load()
  bindAnnGlobal({ onDel: delAnn })
  bindAnnotations(rightEl.value, annMap.value, { editable: true, onInput: saveAnnText })
  loadAnnData()
  document.addEventListener('click', closeSymbolPanel)
  window.addEventListener('zhiyu:ai-insert', onAiInsert)
  window.addEventListener('zhiyu:ai-diff', onAiDiff)
  window.addEventListener('zhiyu:ai-title', onAiTitle)
  window.addEventListener('zhiyu:ann-doodle-save', onAnnDoodleSave)
  document.addEventListener('selectionchange', showSelBar)
  document.addEventListener('mousedown', onSelDown)
  document.addEventListener('mouseup', onSelUp)
  window.addEventListener('scroll', hideSelBar, true)
  // 移动端编辑页隐藏全局导航（页面自带返回按钮）
  document.body.classList.add('editing')
})
onBeforeUnmount(() => {
  document.body.classList.remove('editing')
  window.removeEventListener('zhiyu:ai-insert', onAiInsert)
  window.removeEventListener('zhiyu:ai-diff', onAiDiff)
  window.removeEventListener('zhiyu:ai-title', onAiTitle)
  window.removeEventListener('zhiyu:ann-doodle-save', onAnnDoodleSave)
  document.removeEventListener('selectionchange', showSelBar)
  document.removeEventListener('mousedown', onSelDown)
  document.removeEventListener('mouseup', onSelUp)
  window.removeEventListener('scroll', hideSelBar, true)
})
</script>

<template>
  <div class="edit-page">
    <div class="edit-topbar">
      <button class="back-btn" @click="goBack">← 返回</button>
      <input v-model="title" class="title-input" :placeholder="isEdit ? '笔记标题' : '新笔记标题'" />
      <input v-model="type" class="type-input" placeholder="分类（如：高等数学）" />
      <div class="vis-seg">
        <button class="vis-opt" :class="{ on: visibility === 'private' }" @click="visibility = 'private'">私密</button>
        <button class="vis-opt" :class="{ on: visibility === 'public' }" @click="visibility = 'public'">公开</button>
      </div>
      <span v-if="draftTs && !showDraftRestore" class="draft-badge" data-tip="内容已自动暂存到本机，防刷新丢失">● 已暂存 {{ draftTime }}</span>
      <button class="save-btn" :disabled="busy" @click="save">{{ busy ? '保存中…' : '保存' }}</button>
    </div>

    <div v-if="showDraftRestore" class="draft-restore">
      检测到未保存的暂存（{{ draftTime }}）
      <button @click="restoreDraft">恢复</button>
      <button class="discard" @click="discardDraft">丢弃</button>
    </div>

    <div v-if="loading" class="center">加载中…</div>
    <div v-else-if="notFound" class="center">笔记不存在或没有权限</div>

    <div v-else class="editor-wrap">
      <div class="editor-cols" :class="{ single: !showSource }">
        <div class="preview-area">
          <div class="tb-row" ref="symbolBarRef">
            <span class="tb-btns">
              <button data-tip="加粗" @click="fmt('bold')"><b>B</b></button>
              <button data-tip="斜体" @click="fmt('italic')"><i>I</i></button>
              <button data-tip="删除线" @click="fmt('strikeThrough')"><s>S</s></button>
              <button data-tip="标题 1" @click="fmtBlock('H1')">H1</button>
              <button data-tip="标题 2" @click="fmtBlock('H2')">H2</button>
              <button data-tip="标题 3" @click="fmtBlock('H3')">H3</button>
              <button data-tip="无序列表" @click="fmt('insertUnorderedList')">☰ 列表</button>
              <button data-tip="有序列表" @click="fmt('insertOrderedList')">1. 列表</button>
              <button data-tip="引用" @click="fmtBlock('blockquote')">❝ 引用</button>
              <button data-tip="代码块" @click="fmtBlock('pre')">&lt;/&gt; 代码</button>
              <button data-tip="插入公式（点公式可改源码）" @click="openEqInsert">∑ 公式</button>
              <button data-tip="数学符号面板" @click="symbolPanel = !symbolPanel">∑ 符号</button>
              <button data-tip="插入块级公式" @click="openEqInsertBlock">块公式</button>
              <button data-tip="插入图片（也可直接 Ctrl+V 粘贴）" @click="pickImage">🖼 图片</button>
              <button data-tip="手绘：在笔记上自由涂写画线" @click="openDoodle">✏️ 手绘</button>
              <button data-tip="AI：修改选中文字，或在光标处新增内容" @click="openAiEdit">✨ AI</button>
              <button data-tip="插入批注：以 ① 形式挂在对应文字右侧，点开查看" @click="insertAnnotation">📝 批注</button>
            </span>
            <button v-if="sourceClosed" class="src-toggle" @click="openSource">&lt;/&gt; 源码</button>
            <div v-if="symbolPanel" class="symbol-panel">
              <div class="sym-tabs">
                <button :class="{ on: symbolTab === 'latex' }" @click="symbolTab = 'latex'">LaTeX 公式</button>
                <button :class="{ on: symbolTab === 'uni' }" @click="symbolTab = 'uni'">常用符号</button>
              </div>
              <div class="sym-groups">
                <div v-for="g in (symbolTab === 'latex' ? LATEX_GROUPS : UNICODE_GROUPS)" :key="g.name" class="sym-group">
                  <div class="sym-group-name">{{ g.name }}</div>
                  <div class="sym-items">
                    <button
                      v-for="(it, i) in g.items" :key="i"
                      class="sym-item"
                      @click="symbolTab === 'latex' ? insertLatex(it.code) : insertUnicode(it)"
                    >
                      {{ symbolTab === 'latex' ? it.label : it }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- AI 修改建议：内嵌到正文对应位置（Cursor 式），顶部提供全部接受/拒绝 -->
          <div v-if="aiBlocks.length" class="ai-blocks-toolbar">
            <span class="ai-blocks-toolbar-tip">🤖 已找到 {{ aiBlocks.length }} 处修改建议（已内嵌到正文，逐个接受/拒绝）</span>
            <span class="ai-blocks-toolbar-ops">
              <button class="ai-reject2" type="button" @click="rejectAllBlocks">✕ 全部拒绝</button>
              <button class="ai-accept2" type="button" @click="acceptAllBlocks">✓ 全部接受</button>
            </span>
          </div>
          <div
            ref="rightEl"
            class="markdown-body editable-area"
            contenteditable="true"
            spellcheck="false"
            @input="onEdit"
            @paste.prevent="onPaste"
            @click="onEditorClick"
            @contextmenu.prevent="onEditorCtx"
            @mousedown="onImgZoneDown"
          ></div>
          <input ref="fileInput" type="file" accept="image/*" hidden @change="onFilePick" />
        </div>
        <Transition name="src-slide" @after-leave="onSrcAfterLeave">
        <div v-if="showSource" class="editor-col">
        <div class="src-card">
        <textarea
          ref="editorRef"
          v-model="content"
          class="editor-area"
          placeholder="用 Markdown 写笔记：&#10;# 标题&#10;## 小节&#10;$\\frac{a}{b}$ 行内公式&#10;$$ ... $$ 块级公式&#10;```代码```"
          spellcheck="false"
        ></textarea>
        <button class="src-close" @click="showSource = false">收起 ▸</button>
        </div>
        </div>
        </Transition>
      </div>

      <!-- 光标后悬浮工具条：AI 新增 + 插入批注 -->
      <div
        v-if="caretAi.show"
        class="caret-tools"
        :style="{ left: caretAi.x + 'px', top: caretAi.y + 'px' }"
        @mousedown.prevent
      >
        <button class="caret-ai" data-tip="告诉 AI 在光标处新增内容" @click="openAiEdit">✨</button>
        <button class="caret-ai" data-tip="在光标处插入批注" @click="insertAnnotation">📝</button>
      </div>

      <!-- 选中文字快捷工具条 -->
      <div v-if="selBar.show" class="sel-bar" :style="{ left: selBar.x + 'px', top: selBar.y + 'px' }" @mousedown.prevent>
        <button data-tip="加粗" @click="selFmt('bold')"><b>B</b></button>
        <button data-tip="斜体" @click="selFmt('italic')"><i>I</i></button>
        <button data-tip="删除线" @click="selFmt('strikeThrough')"><s>S</s></button>
        <button data-tip="标题 1" @click="selFmtBlock('H1')">H1</button>
        <button data-tip="标题 2" @click="selFmtBlock('H2')">H2</button>
        <button data-tip="引用" @click="selFmtBlock('blockquote')">❝</button>
        <button data-tip="AI 修改选中文字" @click="openAiEdit">✨ AI</button>
      </div>

      <!-- AI 修改指令弹窗 -->
      <div v-if="aiInstOpen" class="modal-mask" @click.self="aiInstOpen = false">
        <div class="modal">
          <h3>✨ AI 修改选中内容</h3>
          <p class="modal-tip">{{ aiSelRange && aiSelRange.toString().trim() ? '选中：' + aiSelRange.toString().slice(0, 120) : '未选中 → 将在光标处新增' }}</p>
          <textarea v-model="aiInstText" class="eq-input" rows="3" spellcheck="false" placeholder="例如：在二倍角公式后面加半角公式 / 在下方添加一个xxx"></textarea>
          <div class="modal-actions">
            <button class="cancel" @click="aiInstOpen = false">取消</button>
            <button class="save" :disabled="aiSugLoading || !aiInstText.trim()" @click="sendAiEdit">{{ aiSugLoading ? 'AI 生成中…' : '生成修改建议' }}</button>
          </div>
        </div>
      </div>

      <!-- 公式编辑弹窗 -->
      <div v-if="eqOpen" class="modal-mask" @click.self="eqOpen = false">
        <div class="modal">
          <h3>编辑公式（LaTeX）</h3>
          <textarea v-model="eqForm" class="eq-input" rows="3" spellcheck="false"></textarea>
          <label class="eq-display-toggle">显示方式：
            <select v-model="eqInsertDisplay">
              <option :value="false">行内公式</option>
              <option :value="true">块级公式（独立一行）</option>
            </select>
          </label>
          <p class="modal-tip">示例：\frac{a}{b}、\int_{a}^{b} f(x)\,dx、\sum_{i=1}^{n} i^2</p>
          <div class="modal-actions">
            <button class="cancel" @click="eqOpen = false">取消</button>
            <button class="save" @click="saveEq">保存</button>
          </div>
        </div>
      </div>
    </div>
    <DoodleBall target=".editable-area" :doc-id="docId" :is-mine="true" />
  </div>
</template>

<style scoped>
.edit-page {
  height: 100vh; min-height: 0;
  padding: 86px 20px 0;
  box-sizing: border-box;
  display: flex; flex-direction: column;
}
.center { text-align: center; color: var(--text2); padding: 60px 0; }
.editor-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; }

.draft-badge {
  margin-left: 10px; font-size: 12px; color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 30%, transparent);
  padding: 3px 10px; border-radius: 999px; white-space: nowrap; flex-shrink: 0;
}
.draft-restore {
  display: flex; align-items: center; gap: 10px; padding: 8px 16px;
  background: #fff8e6; border-bottom: 1px solid #f0e0b8; color: #8a6d1a; font-size: 13px;
}
.draft-restore button {
  padding: 3px 14px; border-radius: 999px; border: 1px solid #d9c184; background: #fff;
  cursor: pointer; color: #8a6d1a; font-size: 12.5px;
}
.draft-restore button:hover { background: #fdf3d7; }
.draft-restore button.discard { color: #b0a080; }
.edit-topbar {
  display: flex; align-items: center; gap: 10px;
  max-width: 1280px; width: 100%; margin: 0 auto 14px;
  flex-wrap: wrap;
}
.back-btn {
  padding: 8px 16px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--text2); font-size: 13px; cursor: pointer;
}
.back-btn:hover { color: var(--brand-1); }
.title-input {
  flex: 1; min-width: 220px;
  padding: 9px 16px; border-radius: 12px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 16px; font-weight: 600; outline: none;
}
.title-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.type-input {
  width: 150px; padding: 9px 14px; border-radius: 12px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 13.5px; outline: none;
}
.vis-seg {
  display: inline-flex; padding: 3px; border-radius: 999px;
  background: var(--btn-bg); border: 1px solid var(--border);
  flex-shrink: 0;
}
.vis-opt {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 4px 14px; border-radius: 999px; border: none;
  background: transparent; color: var(--text2); font-size: 12.5px;
  cursor: pointer; transition: all .18s; white-space: nowrap;
}
.vis-opt.on {
  color: var(--brand-1); font-weight: 600;
  background: color-mix(in srgb, var(--brand-1) 14%, transparent);
}
.save-btn {
  padding: 9px 26px; border: none; border-radius: 999px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-weight: 600; font-size: 14px; cursor: pointer;
}
.save-btn:disabled { opacity: .5; cursor: not-allowed; }
.modal-mask {
  position: fixed; inset: 0; z-index: 200;
  background: var(--overlay-bg);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  width: 420px; max-width: 92vw;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 18px; padding: 26px;
}
.modal h3 { margin: 0 0 8px; color: var(--text1); }
.modal-tip { font-size: 12.5px; color: var(--text2); line-height: 1.6; margin: 0 0 14px; }
.modal-input {
  width: 100%; box-sizing: border-box;
  padding: 10px 14px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 14px; outline: none;
}
.modal-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.cancel { padding: 8px 18px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text2); cursor: pointer; }
.save { padding: 8px 20px; border: none; border-radius: 999px; background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; cursor: pointer; font-weight: 600; }
.save:disabled { opacity: .5; cursor: not-allowed; }


.symbol-bar {
  max-width: 1280px; width: 100%; margin: 0 auto 10px;
  display: flex; gap: 8px; position: relative; flex-wrap: wrap;
}
.sym-toggle, .sym-block {
  padding: 7px 16px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 12.5px; cursor: pointer;
}
.sym-toggle:hover, .sym-block:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }

.symbol-panel {
  position: absolute; top: 40px; left: 0; z-index: 50;
  width: min(560px, calc(100vw - 40px));
  max-height: 380px; overflow-y: auto;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 16px; padding: 14px;
  box-shadow: var(--shadow-1);
}
.sym-tabs { display: flex; gap: 6px; margin-bottom: 12px; }
.sym-tabs button {
  padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--text2); font-size: 12.5px; cursor: pointer;
}
.sym-tabs button.on { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); }
.sym-group { margin-bottom: 12px; }
.sym-group-name { font-size: 12px; color: var(--text2); margin-bottom: 6px; font-weight: 600; }
.sym-items { display: flex; flex-wrap: wrap; gap: 6px; }
.sym-item {
  padding: 5px 10px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 12.5px; cursor: pointer;
  font-family: 'Cambria Math', 'Times New Roman', serif;
  transition: all .15s;
}
.sym-item:hover { color: var(--brand-1); border-color: var(--brand-1); transform: translateY(-1px); }

.editor-cols {
  display: flex; gap: 12px;
  max-width: 1280px; width: 100%; margin: 0 auto;
  flex: 1; min-height: 0; position: relative;
}
.editor-col { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.src-slide-enter-active, .src-slide-leave-active { transition: transform .28s ease, opacity .28s ease; }
.src-slide-enter-from, .src-slide-leave-to { transform: translateX(70px); opacity: 0; }
.editor-area {
  width: 100%; flex: 1; min-height: 0;
  resize: none; box-sizing: border-box;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 14px; line-height: 1.75;
  font-family: 'Cascadia Code', Consolas, 'Courier New', monospace;
  outline: none;
}
.editor-area:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.preview-area { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; padding: 0; }
.editable-area {
  flex: 1; min-height: 0; overflow-y: auto; outline: none;
  background: var(--card-bg);
  padding: 18px 24px 60px;
  position: relative;
}
.editable-area :deep(img) { max-width: 100%; display: block; }
.editable-area :deep(eq-wrap) {
  vertical-align: middle;
  display: inline-block;
  line-height: normal;
  margin: 0 2px;
}
.editable-area :deep(.img-zone) {
  position: relative; display: inline-block; line-height: 0;
  /* 图片本体给「移动」箭头光标（可拖动）；边缘 rz 手柄的 resize 光标优先级更高会覆盖，
     不再显示 contenteditable 的 I 形文字光标 */
  cursor: move;
}
/* 拉伸手柄：透明热区，仅提供拉伸光标（四角斜向 nwse/nesw、四边上下 ns / 左右 ew） */
.editable-area :deep(.rz) { position: absolute; }
.editable-area :deep(.rz-nw) { left: -4px; top: -4px; width: 16px; height: 16px; cursor: nwse-resize; }
.editable-area :deep(.rz-n)  { left: 50%; top: -5px; width: 48px; height: 20px; margin-left: -24px; cursor: ns-resize; }
.editable-area :deep(.rz-ne) { right: -4px; top: -4px; width: 16px; height: 16px; cursor: nesw-resize; }
.editable-area :deep(.rz-e)  { right: -5px; top: 50%; width: 20px; height: 48px; margin-top: -24px; cursor: ew-resize; }
.editable-area :deep(.rz-se) { right: -4px; bottom: -4px; width: 16px; height: 16px; cursor: nwse-resize; }
.editable-area :deep(.rz-s)  { left: 50%; bottom: -5px; width: 48px; height: 20px; margin-left: -24px; cursor: ns-resize; }
.editable-area :deep(.rz-sw) { left: -4px; bottom: -4px; width: 16px; height: 16px; cursor: nesw-resize; }
.editable-area :deep(.rz-w)  { left: -5px; top: 50%; width: 20px; height: 48px; margin-top: -24px; cursor: ew-resize; }
/* 图片拉伸期间：全局保持拉伸光标（鼠标移出图片到正文也不变回 I 形文字光标） */
body.resizing-ew, body.resizing-ew * { cursor: ew-resize !important; }
body.resizing-ns, body.resizing-ns * { cursor: ns-resize !important; }
body.resizing-nwse, body.resizing-nwse * { cursor: nwse-resize !important; }
body.resizing-nesw, body.resizing-nesw * { cursor: nesw-resize !important; }
.editable-area eq-wrap {
  display: inline-block; padding: 1px 8px; margin: 0 2px;
  border: 1px dashed color-mix(in srgb, var(--brand-1) 55%, transparent);
  border-radius: 8px; cursor: pointer;
  background: color-mix(in srgb, var(--brand-1) 6%, transparent);
  vertical-align: middle;
}
.editable-area eq-wrap:hover { border-color: var(--brand-1); }
.editable-area .eq-err { color: #ef4444; font-size: 12px; }
.hint { font-size: 11px; color: var(--text2); margin-left: 6px; font-weight: 400; }
.tb-row {
  position: relative;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border);
  padding: 8px 12px;
}
.tb-label { font-size: 12px; color: var(--text2); letter-spacing: .06em; white-space: nowrap; font-weight: 600; }
.tb-btns { display: flex; gap: 4px; flex-wrap: wrap; }
.tb-btns button {
  min-width: 30px; padding: 4px 10px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 12.5px; cursor: pointer; line-height: 1.35;
  transition: all .15s;
}
.tb-btns button:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.src-toggle {
  margin-left: auto; padding: 5px 16px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 12.5px; cursor: pointer; white-space: nowrap;
}
.src-toggle:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.src-card { position: relative; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.src-close {
  position: absolute; top: 10px; right: 14px; z-index: 5;
  padding: 4px 14px; border-radius: 999px;
  border: 1px solid var(--border); background: rgba(0,0,0,.05);
  color: var(--text2); font-size: 12px; cursor: pointer; white-space: nowrap;
}
.src-close:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.sel-bar {
  position: fixed; z-index: 120;
  transform: translateX(-50%);
  display: flex; gap: 3px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px 6px;
  box-shadow: var(--shadow-1);
}
.sel-bar button {
  min-width: 26px; padding: 3px 8px; border: none; border-radius: 7px;
  background: transparent; color: var(--text1); font-size: 12.5px; cursor: pointer;
}
.sel-bar button:hover { background: var(--btn-bg); color: var(--brand-1); }
.caret-tools {
  position: fixed; z-index: 120;
  display: flex; gap: 2px; align-items: center;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 3px 6px;
  box-shadow: var(--shadow-1);
}
.caret-ai {
  background: transparent; border: none; padding: 2px 4px; line-height: 1;
  color: var(--brand-1); font-size: 15px; cursor: pointer;
  transition: all .15s;
}
.caret-ai:hover { transform: scale(1.15); color: var(--brand-2); }
.editable-area :deep(.ai-inline-diff) {
  border: 1px solid var(--border);
  border-left: 3px solid var(--brand-1);
  border-radius: 10px; padding: 8px 10px; margin: 6px 0;
  background: var(--bg-soft);
}
.editable-area :deep(.ai-diff-row) { white-space: pre-wrap; word-break: break-word; padding: 2px 8px; border-radius: 6px; margin: 2px 0; line-height: 1.6; font-size: 13.5px; }
.editable-area :deep(.ai-diff-row.add) { background: rgba(16, 185, 129, .14); }
.editable-area :deep(.ai-diff-row.del) { background: rgba(239, 68, 68, .14); text-decoration: line-through; color: var(--text2); }
.editable-area :deep(.ai-diff-row.keep) { color: var(--text2); }
.editable-area :deep(.ai-diff-mark) { display: inline-block; width: 16px; text-align: center; font-weight: 700; margin-right: 4px; }
.editable-area :deep(.ai-diff-row.add .ai-diff-mark) { color: #0a8f5e; }
.editable-area :deep(.ai-diff-row.del .ai-diff-mark) { color: #cf3a3a; }
.editable-area :deep(.ai-diff-ops) { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.editable-area :deep(.ai-accept) {
  padding: 5px 20px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--btn-bg); color: var(--text1); font-weight: 600; font-size: 12.5px; cursor: pointer;
}
.editable-area :deep(.ai-accept:hover) { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.editable-area :deep(.ai-reject) {
  padding: 5px 20px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--btn-bg); color: var(--text2); font-size: 12.5px; cursor: pointer;
}
.editable-area :deep(.ai-reject:hover) { color: #cf3a3a; border-color: rgba(239, 68, 68, .4); background: rgba(239, 68, 68, .08); }
.eq-display-toggle {
  display: flex; align-items: center; gap: 8px; margin-top: 10px;
  font-size: 12.5px; color: var(--text2);
}
.eq-display-toggle select {
  padding: 4px 8px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--card-bg); color: var(--text1); font-size: 12.5px; outline: none;
}
.eq-input {
  width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 13.5px; line-height: 1.6;
  font-family: 'Cascadia Code', Consolas, 'Courier New', monospace;
  resize: vertical; outline: none;
}
.eq-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.preview-label { font-size: 11.5px; color: var(--text2); margin-bottom: 8px; letter-spacing: .08em; }
.markdown-body { line-height: 1.8; font-size: 14.5px; color: var(--text1); }
.markdown-body :deep(h1) { font-size: 1.7rem; margin: 14px 0 12px; }
.markdown-body :deep(h2) { font-size: 1.35rem; margin: 18px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.markdown-body :deep(h3) { font-size: 1.15rem; margin: 14px 0 8px; }
.markdown-body :deep(pre) { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 10px; padding: 14px; overflow-x: auto; }
.markdown-body :deep(code) { background: color-mix(in srgb, var(--text1) 8%, transparent); border-radius: 5px; padding: 2px 6px; font-size: 13px; }
.markdown-body :deep(pre code) { background: transparent; padding: 0; }
.markdown-body :deep(table) { border-collapse: collapse; margin: 12px 0; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid var(--border); padding: 7px 12px; }
.markdown-body :deep(blockquote) { border-left: 3px solid var(--brand-1); margin: 12px 0; padding: 4px 14px; color: var(--text2); background: color-mix(in srgb, var(--brand-1) 6%, transparent); }

@media (max-width: 860px) {
  /* 顶部精简：导航已隐藏（body.editing），页面顶部让位减小 */
  .edit-page { padding: 14px 12px 0; }
  .edit-topbar { gap: 8px; margin-bottom: 10px; }
  /* 第一行：返回 + 标题 + 保存；第二行：分类 + 私密/公开 */
  .back-btn { order: 1; padding: 7px 12px; font-size: 12.5px; flex-shrink: 0; }
  .title-input { order: 1; flex: 1; min-width: 0; padding: 8px 12px; font-size: 15px; }
  .save-btn { order: 1; margin-left: auto; padding: 8px 18px; font-size: 13px; flex-shrink: 0; }
  .type-input { order: 3; flex: 1 1 40%; min-width: 0; }
  .vis-seg { order: 3; }
  .draft-badge { display: none; }
  /* 工具栏：单行横滑，不再换行留空；源码按钮固定最右同一行 */
  .tb-row { padding: 6px 8px; gap: 6px; flex-wrap: nowrap; }
  .tb-btns { flex: 1; min-width: 0; flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  .tb-btns::-webkit-scrollbar { display: none; }
  .tb-btns button { flex-shrink: 0; padding: 4px 8px; font-size: 12px; }
  .src-toggle { flex-shrink: 0; }
  .editor-cols { grid-template-columns: 1fr; }
  .preview-area { min-height: 300px; }
}

/* AI 修改建议操作条（内嵌 diff 已插到正文对应位置，这里只放全局接受/拒绝） */
.ai-blocks-toolbar {
  margin: 0 0 12px;
  padding: 8px 14px;
  border: 1px solid color-mix(in srgb, var(--brand-1) 30%, transparent);
  border-radius: 12px;
  background: linear-gradient(120deg, rgba(0, 198, 255, .06), rgba(227, 5, 247, .06));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
}
.ai-blocks-toolbar-tip { color: var(--brand-1); font-weight: 600; }
.ai-blocks-toolbar-ops { display: flex; gap: 8px; }
.ai-accept2, .ai-reject2 { padding: 8px 22px; border-radius: 999px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s; }
.ai-accept2 { background: linear-gradient(120deg, #10b981, #059669); color: #fff; }
.ai-accept2:hover { filter: brightness(1.1); }
.ai-reject2 { background: var(--btn-bg); border: 1px solid var(--border); color: var(--text2); }
.ai-reject2:hover { color: var(--text1); }
</style>
