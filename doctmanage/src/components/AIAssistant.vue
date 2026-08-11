<!-- AI 助手浮窗：阶段① 仅提供完整聊天界面与交互，真实模型接入在阶段② -->
<template>
  <div class="ai-assistant" :style="panelStyle">
    <!-- 聊天面板（由全局工具球 ToolBall 调起） -->
    <Transition name="panel">
      <div v-if="open" class="ai-panel">
        <header class="ai-header" @mousedown="startAiDrag" title="按住拖动">
          <div class="ai-header-left">
            <span class="ai-avatar">
              <!-- 与悬浮球同款线条机器人：不用 🤖 emoji（Android 平板渲染为方块），全平台统一 -->
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 4.6v1.5"/>
                <circle cx="12" cy="3.5" r="1"/>
                <rect x="5" y="7.6" width="14" height="10.4" rx="3.8"/>
                <circle cx="9.4" cy="12.5" r="1.15" fill="#fff" stroke="none"/>
                <circle cx="14.6" cy="12.5" r="1.15" fill="#fff" stroke="none"/>
                <path d="M9.6 15.7h4.8" stroke-width="1.5"/>
              </svg>
            </span>
            <div>
              <div class="ai-title">{{ ai.title }}</div>
              <div class="ai-status">
                <span class="status-dot" :class="{ on: online }"></span>
                {{ online ? '已接入 · DeepSeek' : '登录后使用' }}
                <span v-if="quota" class="quota-tag">{{ quota.used }}/{{ quota.quota }}</span>
              </div>
            </div>
          </div>
          <button class="ai-close" type="button" @click="open = false">✕</button>
        </header>

        <div ref="msgBoxRef" class="ai-messages">
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="ai-msg"
            :class="m.role"
          >
            <div v-if="m.reasoning" class="ai-reasoning">
              <button type="button" class="ai-reasoning-toggle" @click="m.reasoningOpen = !m.reasoningOpen">
                <span class="ai-reasoning-dot">🧠</span>
                <span>{{ m.reasoningOpen ? '收起思考过程' : '查看思考过程' }}</span>
                <span class="ai-reasoning-arrow">{{ m.reasoningOpen ? '▾' : '▸' }}</span>
              </button>
              <div v-if="m.reasoningOpen" class="ai-reasoning-body">{{ m.reasoning }}</div>
            </div>
            <div class="ai-msg-bubble" v-if="m.html" v-html="m.content"></div>
            <div class="ai-msg-bubble" v-else-if="m.role === 'user'">{{ m.content }}</div>
            <div class="ai-msg-bubble" v-else-if="m.content && !m.stream" v-html="renderMd(m.content)"></div>
            <div class="ai-msg-bubble ai-plain" v-else-if="m.content && m.stream">{{ m.content }}</div>
            <div v-if="m.actions && m.actions.length" class="ai-actions">
              <button v-for="(a, ai) in m.actions" :key="ai" class="ai-act" @click="runAction(a)">{{ a.label }}</button>
            </div>
          </div>
          <div v-if="thinking && !messages.some(m => m.stream && (m.content || m.reasoning))" class="ai-msg assistant">
            <div class="ai-msg-bubble typing"><i></i><i></i><i></i></div>
          </div>
        </div>

        <div v-if="!hasUserMessage" class="ai-suggest">
          <button v-for="s in ai.suggestions" :key="s" type="button" class="ai-chip" @click="quickAsk(s)">
            {{ s }}
          </button>
        </div>

        <footer class="ai-footer">
          <input
            v-model="input"
            class="ai-input"
            type="text"
            :placeholder="ai.placeholder"
            @keyup.enter="send"
          />
          <button class="ai-send" type="button" :disabled="!input.trim() || thinking" @click="send">发送</button>
        </footer>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { ElMessage } from 'element-plus'
import { kbConfig } from '@/constants/homeConfig.js'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

const open = defineModel('open', { default: false })
// 面板位置：跟随工具球（球位置由事件 detail 携带）
const panelStyle = ref(null)
if (typeof window !== 'undefined') {
  window.addEventListener('zhiyu:toggle-ai', (e) => {
    open.value = !open.value
    // 打开即刷新次数
    if (open.value) loadQuota()
    // 打开时若还没有对话，把欢迎语换成当前页面的
    if (open.value && !(messages.value && messages.value.some(m => m.role === 'user'))) {
      messages.value = [{ role: 'assistant', content: welcomeMsg() }]
    }
    const d = e.detail
    if (open.value && d && d.x != null) {
      const W = 400
      const H = 560
      let left = Math.max(8, Math.min(d.x, window.innerWidth - W - 8))
      let top = d.y - H - 8                       // 优先球上方
      if (top < 8) {
        top = d.y + 60                            // 上方放不下 → 球下方
        if (top + H > window.innerHeight - 8) {   // 下方也放不下（矮视口）→ 完整收进视口
          top = Math.max(8, window.innerHeight - H - 8)
        }
      }
      panelStyle.value = { left: left + 'px', top: top + 'px' }
    }
  })
}
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// 页面感知：告诉后端当前在哪个页面，AI 回答后渲染对应的动作按钮
const pageInfo = computed(() => {
  const p = route.path
  if (p.startsWith('/edit')) return { kind: 'editor', isNew: !route.params.id, note_id: route.params.id ? Number(route.params.id) : null }
  if (p.startsWith('/notes/')) return { kind: 'note-reader', note_key: route.params.key }
  if (p.startsWith('/docs')) return { kind: 'docs-reader', note_key: route.params.key || undefined }
  if (p === '/notes') return { kind: 'notes-square' }
  return { kind: 'other' }
})

const ai = kbConfig.ai
const input = ref('')
const thinking = ref(false)
const msgBoxRef = ref(null)
const quota = ref(null) // {used, quota}

// ── 面板拖拽移动（按住头部拖动） ──
const aiDrag = ref(null)
const startAiDrag = (e) => {
  const panel = document.querySelector('.ai-assistant')
  if (!panel) return
  e.preventDefault()
  const r = panel.getBoundingClientRect()
  aiDrag.value = { x: e.clientX - r.left, y: e.clientY - r.top }
  window.addEventListener('mousemove', moveAiDrag)
  window.addEventListener('mouseup', endAiDrag)
}
const moveAiDrag = (e) => {
  if (!aiDrag.value) return
  const panel = document.querySelector('.ai-assistant')
  if (panel) {
    panel.style.left = (e.clientX - aiDrag.value.x) + 'px'
    panel.style.top = (e.clientY - aiDrag.value.y) + 'px'
  }
}
const endAiDrag = () => {
  aiDrag.value = null
  window.removeEventListener('mousemove', moveAiDrag)
  window.removeEventListener('mouseup', endAiDrag)
}

const md = new MarkdownIt({ breaks: true, linkify: true })
const escHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
// 公式占位 + KaTeX 渲染（不依赖外部 MathJax 脚本）
const renderMd = (t) => {
  const eqs = []
  // 系统标记隐藏：【原内容】块和声明行去掉，保留【新内容】给用户看效果
  let s = String(t || '').replace(/【原内容】[\s\S]*?【新内容】/g, '【新内容】').replace(/【知屿应用[:：][^】]*】/g, '').replace(/【知屿操作[:：][^】]*】/g, '')
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (m, eq) => { eqs.push({ eq: eq.trim(), display: true }); return '%%EQ%%' + (eqs.length - 1) + '%%' })
  s = s.replace(/\$([^\$\n]+?)\$/g, (m, eq) => { eqs.push({ eq: eq.trim(), display: false }); return '%%EQ%%' + (eqs.length - 1) + '%%' })
  let html = md.render(s)
  html = html.replace(/%%EQ%%(\d+)%%/g, (m, i) => {
    const it = eqs[+i]
    if (!it) return m
    try { return katex.renderToString(it.eq, { displayMode: it.display, throwOnError: false }) } catch (e) { return escHtml(it.eq) }
  })
  return html
}

// 不同页面的欢迎语：让助手显得更专业
const WELCOME_BY_PAGE = {
  'note-reader': '👋 我是知屿 AI。我正在读这篇笔记，可以帮你总结要点、讲解难点、回答疑问，也能帮你写评论。',
  'notes-square': '👋 我是知屿 AI。在笔记广场告诉我你想找什么，我帮你检索相关笔记并直接打开。',
  other: '👋 我是知屿 AI。我已经能基于你的笔记库检索答疑了——直接问我，比如"这篇笔记讲了什么""某个知识点怎么理解"，也可以让我帮你写笔记、总结要点、讲解难点。',
}
// 欢迎语：编辑器区分「新建空笔记」与「编辑已有笔记」
const welcomeMsg = () => {
  const pi = pageInfo.value
  if (pi.kind === 'editor') {
    return pi.isNew
      ? '👋 我是知屿 AI。你正在新建一篇空笔记——直接告诉我你想写什么：主题、提纲、要覆盖的知识点都可以，我帮你生成 Markdown + LaTeX 内容，点「📥 插入正文」即可用。'
      : '👋 我是知屿 AI。正在编辑这篇笔记——续写、总结、润色、解答疑问，告诉我就行。'
  }
  return WELCOME_BY_PAGE[pi.kind] || WELCOME_BY_PAGE.other
}
const messages = ref([
  { role: 'assistant', content: welcomeMsg() },
])

// 切换页面：保留对话（上下文延续），不再显示提示；AI 每轮请求都带当前页面信息，能感知跳转

const hasUserMessage = computed(() => messages.value.some((m) => m.role === 'user'))
const online = computed(() => !!localStorage.getItem('kb_token'))

const scrollToBottom = async () => {
  await nextTick()
  if (msgBoxRef.value) msgBoxRef.value.scrollTop = msgBoxRef.value.scrollHeight
}

const quickAsk = (text) => {
  input.value = text
  send()
}

const pushAssistant = (html) => {
  messages.value.push({ role: 'assistant', content: html, html: true })
  scrollToBottom()
}

const send = async () => {
  const text = input.value.trim()
  if (!text || thinking.value) return
  if (!auth.isLogin) {
    ElMessage.warning('请先登录使用 AI 助手')
    router.push('/login')
    return
  }
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  thinking.value = true
  scrollToBottom()
  // 流式回答（打字机）：reasoning（思考）+ content 都实时累加，气泡不提前空显示
  const assistantMsg = { role: 'assistant', content: '', reasoning: '', stream: true, actions: [], reasoningOpen: false }
  messages.value.push(assistantMsg)
  scrollToBottom()
  // 打字机节流：Vue 响应式是异步批处理，同一批到达的 delta 若直接 += 只触发一次渲染（正文“唰”地一次性出现）。
  // 把 delta 先累积到 typeBuf，由定时器逐字追加到 content（16ms/字 ≈ 60字/秒）。
  // flushType 仅用于：流结束等待超时兜底 / 异常路径（错误信息覆盖正文）；正常流结束靠等待循环自然收尾。
  let typeBuf = ''
  let typeTimer = null
  const flushType = () => {
    if (typeTimer) { clearInterval(typeTimer); typeTimer = null }
    if (typeBuf) { assistantMsg.content += typeBuf; typeBuf = '' }
  }
  const startType = () => {
    if (typeTimer) return
    typeTimer = setInterval(() => {
      if (typeBuf) {
        // 逐字打字机：无论网络一次到达多少字符，都按固定速率逐字显示（16ms/字 ≈ 60字/秒），
        // 避免整批 delta 在一次 read 到达时被整体渲染成“一次性出现”
        assistantMsg.content += typeBuf.slice(0, 1)
        typeBuf = typeBuf.slice(1)
        scrollToBottom()
      } else {
        clearInterval(typeTimer)
        typeTimer = null
      }
    }, 16)
  }
  let ctxNotes = []
  let aiChanged = false
  try {
    const token = localStorage.getItem('kb_token') || ''
    // 编辑页：优先带本地未保存的暂存草稿，让 AI 知道最新修改（比数据库已保存内容新）
    let draftContent
    if (pageInfo.value.kind === 'editor' && pageInfo.value.note_id) {
      try {
        const d = JSON.parse(localStorage.getItem('zhiyu_draft_' + pageInfo.value.note_id) || 'null')
        if (d && d.content) draftContent = d.content
      } catch (e) {}
    }
    const resp = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({
        question: text,
        stream: true,
        page: pageInfo.value.kind,
        note_id: pageInfo.value.note_id || undefined,
        note_slug: pageInfo.value.note_slug || undefined,
        draft_content: draftContent,
        history: messages.value.slice(-7, -1).filter(m => !m.stream && m.role !== 'sys').map(m => ({ role: m.role, content: m.content })),
      }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      if (resp.status === 402) assistantMsg.content = '⚠️ 免费额度已用完，可去积分商城兑换 AI 次数'
      else if (resp.status === 401) assistantMsg.content = '请先登录后使用 AI 助手。'
      else assistantMsg.content = '😅 AI 服务暂时不可用：' + (err.error || '网络异常')
      assistantMsg.stream = false
      scrollToBottom()
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
          const raw = line.slice(5).trim()
          if (!raw || raw === '[DONE]') continue
          try {
            const obj = JSON.parse(raw)
            if (obj.reasoning) {
              // 思考过程（工具轮思考 / DeepSeek reasoning_content）实时累加，默认展开让用户看到思考
              assistantMsg.reasoning += obj.reasoning
              assistantMsg.reasoningOpen = true
              scrollToBottom()
            } else if (obj.delta) {
              typeBuf += obj.delta
              startType()
            } else if (obj.error) {
              assistantMsg.content += '\n\n😅 ' + obj.error
            } else if (obj.action) {
              // AI 工具触发的前端动作：跳转页面 / 新建笔记
              const a = obj.action
              if (a.type === 'navigate' && a.to) {
                router.push(a.to)
              } else if (a.type === 'new_note') {
                try {
                  localStorage.setItem('zhiyu_draft_new', JSON.stringify({ title: a.title || '', type: a.category || '', visibility: 'private', content: a.content || '', ts: Date.now(), ai: true }))
                } catch (e) {}
                router.push('/edit')
              }
            } else if (obj.done) {
              ctxNotes = obj.context_notes || []
              // AI 通过工具改了笔记/存了草稿 → 通知当前页面刷新
              if (obj.changed) {
                aiChanged = true
                window.dispatchEvent(new CustomEvent('zhiyu:ai-changed'))
                if (pageInfo.value.kind === 'docs-reader') ElMessage.success('AI 已修改笔记，正在刷新…')
              }
            }
          } catch (e) { /* 忽略坏帧 */ }
        }
      }
      // 流结束：不一次性补齐（否则整批 delta 在一次 read 到达时会被 flushType 瞬间倒出，打字机失效）。
      // 等逐字定时器把残余 typeBuf 输出完（打字机自然收尾），超时/异常才兜底补齐，保证 content 完整。
      const tWait0 = Date.now()
      while (typeBuf && Date.now() - tWait0 < 10000) {
        await new Promise(r => setTimeout(r, 20))
      }
      flushType()
      assistantMsg.stream = false
      // 思考识别：DeepSeek-chat 的思考是 content 开头的叙述段（无 reasoning_content 字段），
      // 把开头「我来/我先/根据/用户要求/需要/好的/接下来/这是插入…」等思考口吻的段落挪进 reasoning 折叠框
      if (!assistantMsg.reasoning) {
        const c = (assistantMsg.content || '').trim()
        const thinkRe = /^(?:我来|我先|根据|用户要求|需要|这是(?:插入|修改|新增)|我已经|我检查|我读取|我看了|这是给|在(?:给|为).{0,20}(?:添加|加|补充|写))/m
        const m = c.match(thinkRe)
        if (m) {
          // 思考段 = 从开头到第一个"正文转折"（空行+标题/代码块/【知屿操作】之前）
          const cut = c.search(/\n\s*(?:#{1,4}\s|```|【知屿操作|>|[-*] )/)
          const sep = cut > 0 ? cut : c.length
          const thinkText = c.slice(0, sep).trim()
          const rest = c.slice(sep).trim()
          if (thinkText && rest && thinkText.length < rest.length) {
            assistantMsg.reasoning = thinkText
            assistantMsg.content = rest
          }
        }
      }
      // 动作按钮：检索到的笔记可打开 + 页面能力 + 生成内容可存为笔记
      const acts = []
      for (const n of ctxNotes) acts.push({ type: 'open', id: n.id, label: '📄 打开《' + n.title + '》' })
      const lastUser = [...messages.value].reverse().find(m => m.role === 'user')
      const intent = lastUser ? (lastUser.content || '') : ''
      // 意图判定：区分「诊断/检查」与「生成/写入」——"看看这篇有什么问题"是检查，不是让 AI 生成内容
      const diagIntent = /看看|检查|审查|审阅|体检|有什么问题|有没有问题|有问题吗|毛病|评价一下|咋样|怎么样|挑错|找茬|质量/.test(intent)
      const writeIntent = /写|生成|起草|总结|整理|编排|补全|续写|制作|提纲|大纲|笔记|文章|补一个|建一个|记录/.test(intent)
      // 编辑器页：让 AI 自己声明操作（插入/修改/回答），前端照执行；AI 没声明才用意图兜底
      const insertIntent = /插入|追加|末尾|后面|新增|补充|补(?:充|一个|上)?|加(?:上|一个|个|几个|一些|点|段)?|代码|示例|例子/.test(intent)
      const applyIntent = /改|修|换|替换|重写|更新|调整|润色|优化|整理|排版|理顺/.test(intent)
      if (pageInfo.value.kind === 'editor') {
        // AI 声明改标题（【知屿标题：新标题】）→ 通知编辑页填入标题输入框
        const aiTitle = (assistantMsg.content.match(/【知屿标题[:：]\s*(.+?)】/) || [])[1]?.trim()
        if (aiTitle) {
          window.dispatchEvent(new CustomEvent('zhiyu:ai-title', { detail: { title: aiTitle } }))
        }
        const op = (assistantMsg.content.match(/【知屿操作[:：](.+?)】/) || [])[1]?.trim()
        const aiText = (assistantMsg.content || '').trim()
        // 结构转换意图（把 X 写成/改成/转成/整理成表格等）→ 一定是修改，走 diff，覆盖 AI 误判的「插入」
        const convertIntent = /把.{1,40}(?:成|为)|写成|改成|换成|转成|整理成|排成/.test(intent)
        if (aiChanged) {
          // AI 用了工具（存草稿/改笔记）→ 自动弹红绿 diff，不追加不跳转
          window.dispatchEvent(new CustomEvent('zhiyu:ai-diff', { detail: { fromDraft: true } }))
        } else if (convertIntent && aiText) {
          window.dispatchEvent(new CustomEvent('zhiyu:ai-diff', { detail: { suggestion: assistantMsg.content } }))
        } else if (op === '插入' && aiText) {
          // 插入也走红绿 diff 预览（不直接写正文）：用户在编辑区确认后才应用，避免误插到末尾
          window.dispatchEvent(new CustomEvent('zhiyu:ai-diff', { detail: { suggestion: assistantMsg.content, insert: true } }))
        } else if (op === '修改') {
          window.dispatchEvent(new CustomEvent('zhiyu:ai-diff', {
            detail: aiChanged ? { fromDraft: true } : { suggestion: assistantMsg.content },
          }))
        } else if (!op) {
          // AI 没声明 → 意图兜底：修改优先走 diff，明确插入也走 diff 预览（不直接改正文）
          if (applyIntent || convertIntent || (insertIntent && aiText)) {
            window.dispatchEvent(new CustomEvent('zhiyu:ai-diff', {
              detail: aiChanged ? { fromDraft: true } : { suggestion: assistantMsg.content, insert: insertIntent },
            }))
          }
        }
        // op === '回答' → 无操作，正常显示
      }
      // 阅览室：按钮选择权交给 AI——按回复末尾【知屿应用：xxx】声明决定显示哪个按钮；AI 未声明才用意图兜底
      if (pageInfo.value.kind === 'docs-reader') {
        const meta = (assistantMsg.content.match(/【知屿应用[:：](.+?)】/) || [])[1]?.trim()
        // 局部替换：AI 输出了「原内容/新内容」结构 → 精确定位替换后进编辑页
        const om = assistantMsg.content.match(/【原内容】\n([\s\S]*?)【新内容】\n([\s\S]*)$/)
        if (meta === '局部替换' && om && om[1].trim() && om[2].trim()) {
          const replacement = om[2].replace(/【知屿应用[:：][^】]*】/g, '').trim()
          if (replacement) {
            window.dispatchEvent(new CustomEvent('zhiyu:ai-local-edit', { detail: { original: om[1].trim(), replacement } }))
          }
        } else if (/^#{1,6}\s/.test(assistantMsg.content.trim())) {
          // AI 输出了笔记内容（整篇或片段，无论是否带声明）→ 自动进编辑页预览，AI 自己判断，无需用户触发
          window.dispatchEvent(new CustomEvent('zhiyu:ai-goto-edit', { detail: { text: assistantMsg.content } }))
        } else if (meta === '追加到末尾') acts.push({ type: 'insert-doc', label: '📥 追加到末尾' })
      }
      // 声明行是给系统的指令，从用户看到的回复里去掉
      assistantMsg.content = assistantMsg.content.replace(/【知屿应用[:：][^】]*】/g, '').replace(/【知屿操作[:：][^】]*】/g, '').replace(/【知屿标题[:：][^】]*】/g, '').trim()
      // 用户让 AI 写/生成内容 → 存为笔记（仅当 AI 真的输出了正文内容，短句/操作反馈/诊断检查不显示）
      // 若 AI 回复是「询问/对话」（在征询用户意见、让用户回复确认），不弹存为笔记，避免把对话存成笔记
      const aiContent = (assistantMsg.content || '').trim()
      const aiIsQuestion = /(?:你看|你(?:觉得|想|说)|请问|要不要|是否要|回复「|请(?:告诉|回复|选择)|你可以选择|需要我).{0,30}(?:吗|吧|呢|？|\?|即可|告诉|回复)/.test(aiContent)
      if (writeIntent && !diagIntent && !aiIsQuestion && aiContent.length > 100 && !aiChanged) {
        // aiChanged（AI 已通过 save_draft/write_note 存草稿/改笔记）时不再弹「存为笔记/插入」：
        // 内容已进草稿，再存会把 AI 的对话总结误存成新笔记（脏数据）
        acts.push({ type: 'save-note', label: '📥 存为笔记' })
        // 正在编辑 / 正在阅读某篇具体笔记时，AI 内容可插入（更新）当前笔记（编辑器已自动插入的场合不再显示按钮）
        if (pageInfo.value.kind === 'editor' && !insertIntent) acts.push({ type: 'insert', label: '📥 插入正文' })
        if (pageInfo.value.kind === 'note-reader') acts.push({ type: 'insert', label: '📥 插入笔记' })
      }
      // AI 已通过工具改了笔记/存草稿 → 任何页面都提供「去编辑页查看红绿 diff」入口
      if (aiChanged) {
        acts.push({ type: 'goto-edit-current', label: '✏️ 去编辑页查看修改' })
      }
      if (pageInfo.value.kind === 'note-reader') acts.push({ type: 'comment', label: '💬 写评论' })
      assistantMsg.actions = acts
      scrollToBottom()
    }
  } catch (e) {
    flushType()
    assistantMsg.content = '😅 网络异常，AI 回答中断：' + e.message
    assistantMsg.stream = false
    scrollToBottom()
  }
  thinking.value = false
  // 刷新额度
  loadQuota()
}

// 拉取 AI 次数（已用/总额）
const loadQuota = async () => {
  try {
    const t = await api.get('/user/today')
    quota.value = { used: t.data.ai_used, quota: t.data.ai_quota }
  } catch (e) { /* 忽略 */ }
}

// 动作按钮点击：打开笔记 / 插入编辑器正文 / 填入评论框
const runAction = async (act) => {
  const msg = messages.value.find(m => m.actions && m.actions.includes(act))
  if (act.type === 'apply-doc') {
    const text = (msg?.content || '').replace(/^```(?:markdown)?\s*/m, '').replace(/\s*```$/, '').trim()
    // 载入阅览室预览框，用户看效果后再决定是否应用
    window.dispatchEvent(new CustomEvent('zhiyu:ai-preview-doc', { detail: { text } }))
    return
  }
  if (act.type === 'goto-edit-current') {
    // 阅览室：AI 已改当前笔记 → 跳到编辑页看红绿 diff（由 Docs.vue 用当前文档 id 处理）
    window.dispatchEvent(new CustomEvent('zhiyu:ai-goto-current-edit'))
    return
  }
  if (act.type === 'open') {
    // 阅览室：就地打开对应笔记（切到当前阅览室的该篇），不跳笔记广场
    if (pageInfo.value.kind === 'docs-reader') {
      window.dispatchEvent(new CustomEvent('zhiyu:ai-open-note', { detail: { id: act.id, public_id: act.public_id } }))
      return
    }
    router.push('/notes/' + (act.public_id || act.id))
    return
  }
  if (act.type === 'insert' || act.type === 'insert-doc') {
    const text = (msg?.content || '').replace(/^```(?:markdown)?\s*/m, '').replace(/\s*```$/, '').trim()
    window.dispatchEvent(new CustomEvent('zhiyu:ai-insert', { detail: { text } }))
    ElMessage.success('已插入到当前笔记末尾，请检查修改')
    return
  }
  if (act.type === 'save-note') {
    // 剥离 AI 回复中的对话性叙述（"我注意到…你看要不要…回复「新建」即可"），只存真正的正文
    let text = (msg?.content || '').replace(/^```(?:markdown)?\s*/m, '').replace(/\s*```$/, '').trim()
    text = text
      .replace(/^(我(?:注意到|查看|看了|发现)|根据|你(?:提到|说|想要)|这是(?:给|在)[^\n]*)[^\n]*\n+/g, '')
      .replace(/(?:你看|你觉得|你想|要不要|是否要|回复「|请(?:告诉|回复|选择)|你可以选择|需要我)[^\n]*\n+/g, '')
      .replace(/^\s*(新建|确定|还是|或者|告诉|请回复)[：:][^\n]*\n+/g, '')
      .trim()
    // 标题：取正文第一个 Markdown 标题行；没有则用正文首行
    const title = (text.match(/^#\s+(.+)$/m) || [])[1]?.trim() || text.split('\n').find(l => l.trim())?.slice(0, 20) || 'AI 笔记'
    try {
      const res = await api.post('/docs', { type: 'AI 笔记', title: title.slice(0, 50), content: text || (msg?.content || ''), visibility: 'private' })
      ElMessage.success('已保存到书房')
      router.push('/edit/' + res.data.id)
    } catch (e) { ElMessage.error(e.response?.data?.error || '保存失败') }
    return
  }
  if (act.type === 'comment') {
    window.dispatchEvent(new CustomEvent('zhiyu:ai-comment', { detail: { text: msg?.content || '' } }))
    ElMessage.success('评论草稿已填入评论框，可修改后发表')
  }
}

watch(open, (v) => { if (v) scrollToBottom() })
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  z-index: 2000;
}

.ai-panel {
  position: relative;
  width: min(400px, calc(100vw - 40px));
  height: 560px;
  max-height: calc(100vh - 16px);
  border-radius: 22px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(20px);
}

.ai-header { cursor: move; user-select: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(120deg, rgba(0, 198, 255, 0.08), rgba(227, 5, 247, 0.08));
}
.ai-header-left { display: flex; align-items: center; gap: 10px; }
.ai-avatar {
  width: 38px; height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.ai-title { font-weight: 700; font-size: 15px; color: var(--text1); }
.ai-status { font-size: 12px; color: var(--text2); display: flex; align-items: center; gap: 5px; }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.8);
}
.status-dot.on {
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.8);
}
.quota-tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--btn-bg);
  border: 1px solid var(--border);
}
.ai-close {
  border: none; background: transparent; color: var(--text2);
  font-size: 15px; cursor: pointer; padding: 6px;
  border-radius: 8px;
}
.ai-close:hover { background: var(--btn-bg-hover); color: var(--text1); }

.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ai-msg { display: flex; flex-direction: column; align-items: flex-start; }
.ai-msg.user { align-items: flex-end; }
.ai-msg-bubble {
  max-width: 86%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  color: var(--text1);
}
.ai-msg.assistant .ai-msg-bubble {
  background: var(--btn-bg);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}
/* 流式中的纯文本气泡：避免每帧全量 markdown 渲染卡住 UI（渲染放到流式结束后） */
.ai-msg-bubble.ai-plain {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Cascadia Code', Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}
.ai-reasoning {
  width: 100%;
  margin-bottom: 6px;
}
.ai-reasoning-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  border: 1px dashed var(--border);
  border-radius: 999px;
  background: var(--bg-soft);
  color: var(--text2);
  font-size: 12px;
  cursor: pointer;
  transition: all .2s;
}
.ai-reasoning-toggle:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.ai-reasoning-dot { font-size: 13px; }
.ai-reasoning-arrow { font-size: 10px; }
.ai-reasoning-body {
  margin-top: 6px;
  padding: 10px 12px;
  border-left: 3px solid var(--border);
  border-radius: 8px;
  background: var(--bg-soft);
  color: var(--text2);
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.ai-msg.assistant .ai-msg-bubble :deep(p) { margin: 0 0 8px; }
.ai-msg.assistant .ai-msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.ai-msg.assistant .ai-msg-bubble :deep(code) {
  background: color-mix(in srgb, var(--text1) 9%, transparent);
  border-radius: 4px; padding: 1px 5px; font-size: 12.5px;
}
.ai-msg.assistant .ai-msg-bubble :deep(pre) {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 12px; overflow-x: auto; margin: 8px 0;
}
.ai-msg.assistant .ai-msg-bubble :deep(ul), .ai-msg.assistant .ai-msg-bubble :deep(ol) {
  padding-left: 20px; margin: 6px 0;
}
.ai-msg.user .ai-msg-bubble {
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff;
  border-top-right-radius: 4px;
}
.ai-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.ai-msg.user .ai-actions { justify-content: flex-end; }
.ai-act {
  padding: 6px 13px; border-radius: 999px; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--brand-1) 40%, transparent);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  color: var(--brand-1); font-size: 12.5px;
  transition: all .15s;
}
.ai-act:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; border-color: transparent; }
.typing { display: flex; gap: 5px; align-items: center; padding: 12px 14px; }
.typing i {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--text2);
  animation: typing 1.2s ease-in-out infinite;
}
.typing i:nth-child(2) { animation-delay: 0.18s; }
.typing i:nth-child(3) { animation-delay: 0.36s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-5px); opacity: 1; }
}

.ai-suggest {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 16px 10px;
}
.ai-chip {
  border: 1px solid var(--border);
  background: var(--btn-bg);
  color: var(--text1);
  font-size: 12.5px;
  padding: 7px 12px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s;
}
.ai-chip:hover {
  border-color: var(--brand-1);
  color: var(--brand-1);
}

.ai-footer {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--border);
  background: var(--bg-soft);
}
.ai-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 9px 16px;
  font-size: 14px;
  background: var(--card-bg);
  color: var(--text1);
  outline: none;
  transition: border-color 0.2s;
}
.ai-input:focus { border-color: var(--brand-1); }
.ai-input::placeholder { color: var(--text2); }
.ai-send {
  border: none;
  border-radius: 999px;
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff;
  transition: opacity 0.2s;
}
.ai-send:disabled { opacity: 0.45; cursor: not-allowed; }

.panel-enter-active, .panel-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(16px) scale(0.97); }
</style>