<template>
  <div class="study-page" :class="{ collapsed: sideCollapsed }">
    <!-- 左侧：我的笔记目录（多级） -->
    <aside class="study-side">
      <template v-if="!sideCollapsed">
        <div class="side-head">
          <span class="side-title">✧ 我的书房</span>
          <span class="side-count">{{ myNotes.length }} 篇</span>
          <button class="side-toggle" data-tip="收起左侧栏" @click="sideCollapsed = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg>
          </button>
        </div>
        <div class="side-nav">
          <div v-if="loading" class="side-empty">加载中…</div>
          <div v-else-if="!grouped.length" class="side-empty">还没有笔记，点右上角开始创建</div>
          <div v-for="g in grouped" :key="g.type" class="side-group">
            <div class="side-type" :class="{ on: activeType === g.type }" @click="scrollToSection(g.type)">
              <span class="type-caret" :class="{ open: openTypes[g.type] }" @click.stop="toggleType(g.type)">▸</span>
              <span class="type-name">{{ g.type }}</span>
              <span class="type-num">{{ g.items.length }}</span>
            </div>
            <div v-if="openTypes[g.type]" class="type-items">
              <div v-for="n in g.items" :key="n.id" class="type-item" @click="openNote(n.id)">
                <span class="ti-format">{{ n.format && n.format !== 'md' ? '📎' : '' }}</span>
                <span class="ti-title">{{ n.title }}<span v-if="n.origin_id" class="from-square">来自广场</span></span>
              </div>
            </div>
          </div>
        </div>
      </template>
      <button v-else class="sb-rail" data-tip="展开书房" data-tip-align="left" @click="sideCollapsed = false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><line x1="10.2" y1="4" x2="10.2" y2="20"/></svg>
        <span class="sb-rail-text">书房</span>
      </button>
    </aside>

    <!-- 右侧主区：所有标签 + 全部笔记 -->
    <main class="study-main">
      <div class="main-top">
        <div class="top-actions">
          <button class="act-btn primary" @click="newNote">✏️ 新建笔记</button>
          <button class="act-btn ai" @click="aiOpen = true">🤖 AI 构建</button>
          <button class="act-btn" @click="uploadOpen = true">📤 上传</button>
          <button class="act-btn" @click="newDoodle">🖌 手绘</button>
        </div>
        <div class="top-links">
          <router-link to="/friends" class="link-btn">关注</router-link>
          <router-link to="/messages" class="link-btn">私信</router-link>
          <router-link to="/mall" class="link-btn">商城</router-link>
        </div>
      </div>

      <div class="main-head">
        <h2 class="main-title">我的书房</h2>
        <span class="main-sub">共 {{ myNotes.length }} 篇 · 点击进入阅读 / 编辑</span>
      </div>

      <div v-if="!myNotes.length" class="main-empty">还没有笔记，点右上角开始创建</div>
      <div v-for="g in grouped" :key="g.type" class="study-section" :data-type="g.type">
        <div class="section-head">
          <h3 class="section-type">{{ g.type }}</h3>
          <span class="section-num">{{ g.items.length }} 篇</span>
        </div>
        <div class="note-grid">
          <div v-for="n in g.items" :key="n.id" class="note-card" @click="openNote(n.id)">
            <div class="card-top">
              <span class="fmt-badge" :class="'fmt-' + (n.format || 'md')">{{ fmtLabel(n.format) }}</span>
              <span class="vis-badge" :class="{ pub: n.visibility === 'public' }">{{ n.visibility === 'public' ? '公开' : '私密' }}</span>
              <span v-if="n.pinned_until && new Date(n.pinned_until) > new Date()" class="pin-badge">📌</span>
              <span v-if="n.price > 0" class="coin-badge">{{ n.price }} 币</span>
              <span v-if="n.preview_only" class="pv-badge">仅预览</span>
            </div>
            <h3 class="card-title">{{ n.title }}<span v-if="n.origin_id" class="from-square">来自广场</span></h3>
            <p class="card-preview">{{ (n.content || '').slice(0, 60).replace(/[#*$`>]/g, '') }}</p>
            <div class="card-foot">
              <span class="card-time">{{ (n.updated_at || '').slice(0, 10) }}</span>
              <span class="card-room" :class="{ in: roomIds.has(n.id) }" @click.stop="toggleRoom(n)">{{ roomIds.has(n.id) ? '✓ 已在阅览室' : '📖 加入阅览室' }}</span>
              <span class="card-edit" @click.stop="editNote(n.id)">编辑 →</span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 上传弹窗 -->
    <div v-if="uploadOpen" class="modal-mask" @click.self="uploadOpen = false">
      <div class="modal">
        <h3>📤 上传笔记</h3>
        <p class="modal-tip">支持 Markdown / PDF / PPT / Word / 图片 / 文本（md 自动解析为笔记，其他作为附件）</p>
        <input type="file" multiple class="file-input" @change="onPickFiles" />
        <div v-if="uploadFiles.length" class="file-list">
          <span v-for="f in uploadFiles" :key="f.name" class="file-item">{{ f.name }}</span>
        </div>
        <div class="modal-row"><label>科目</label><input v-model="uploadType" class="modal-input" placeholder="如：高等数学" /></div>
        <div class="modal-row">
          <label>公开</label>
          <select v-model="uploadVis" class="modal-input">
            <option value="private">私密（仅自己）</option>
            <option value="public">公开（上笔记广场）</option>
          </select>
        </div>
        <div class="modal-row">
          <label>开放下载</label><input type="checkbox" v-model="uploadDL" />
          <label class="ml">收费（知屿币）</label><input v-model.number="uploadPrice" type="number" min="0" class="modal-input w60" />
        </div>
        <div class="modal-row">
          <label>仅预览</label><input type="checkbox" v-model="uploadPreview" />
          <span class="hint">开启后未购买者只能预览前 500 字</span>
        </div>
        <div class="modal-actions">
          <button class="modal-btn ghost" @click="uploadOpen = false">取消</button>
          <button class="modal-btn primary" :disabled="uploading" @click="doUpload">{{ uploading ? '上传中…' : '确认上传' }}</button>
        </div>
      </div>
    </div>

    <!-- AI 构建弹窗 -->
    <div v-if="aiOpen" class="modal-mask" @click.self="aiOpen = false">
      <div class="modal wide">
        <h3>🤖 AI 构建笔记</h3>
        <div v-if="aiMode === 'draft'">
          <p class="modal-tip">输入主题，AI 基于你的知识库生成一份 Markdown 笔记草稿，预览确认后加入书房。</p>
          <div class="modal-row"><label>主题</label><input v-model="aiTopic" class="modal-input" placeholder="如：二重积分的换序方法" @keyup.enter="aiGenerate" /></div>
          <div class="modal-row"><label>标题</label><input v-model="aiTitle" class="modal-input" placeholder="留空则用主题" /></div>
          <div class="modal-actions">
            <button class="modal-btn ghost" @click="aiOpen = false">取消</button>
            <button class="modal-btn primary" :disabled="aiBusy || !aiTopic.trim()" @click="aiGenerate">{{ aiBusy ? '生成中…' : '生成草稿' }}</button>
          </div>
        </div>
        <div v-else>
          <div class="modal-row"><label>标题</label><input v-model="aiTitle" class="modal-input" /></div>
          <div class="modal-row"><label>科目</label><input v-model="aiType" class="modal-input" /></div>
          <div class="modal-row">
            <label>公开</label>
            <select v-model="aiVis" class="modal-input"><option value="private">私密</option><option value="public">公开</option></select>
            <label class="ml">开放下载</label><input type="checkbox" v-model="aiDL" />
            <label class="ml">收费</label><input v-model.number="aiPrice" type="number" min="0" class="modal-input w60" />
            <label class="ml">仅预览</label><input type="checkbox" v-model="aiPreview" />
          </div>
          <div class="ai-preview"><pre class="ai-gen">{{ aiGen }}</pre></div>
          <div class="modal-actions">
            <button class="modal-btn ghost" @click="aiMode = 'draft'; aiGen = ''">重新生成</button>
            <button class="modal-btn primary" :disabled="aiBusy" @click="aiConfirm">确认加入书房</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api.js'

export default {
  name: 'AdminStudy',
  data() {
    return {
      myNotes: [],
      loading: true,
      openTypes: {},
      activeType: '',
      uploadOpen: false, uploadFiles: [], uploadType: '数学', uploadVis: 'private',
      uploadDL: true, uploadPrice: 0, uploadPreview: false, uploading: false,
      aiOpen: false, aiTopic: '', aiTitle: '', aiType: '数学', aiVis: 'private',
      aiDL: true, aiPrice: 0, aiPreview: false, aiGen: '', aiBusy: false, aiMode: 'draft',
      sideCollapsed: false,
      roomIds: new Set(),
    }
  },
  computed: {
    grouped() {
      const map = new Map()
      for (const n of this.myNotes) {
        const k = n.type || '未分类'
        if (!map.has(k)) map.set(k, [])
        map.get(k).push(n)
      }
      return Array.from(map.entries()).map(([type, items]) => ({ type, items }))
    },
  },
  methods: {
    fmtLabel(f) { return ({ md: 'MD', pdf: 'PDF', ppt: 'PPT', pptx: 'PPTX', doc: 'WORD', docx: 'WORD', png: '图', jpg: '图', jpeg: '图', webp: '图', gif: '图', doodle: '手绘', text: '文本' }[f] || (f || 'MD').toUpperCase()) },
    // 点击侧栏标签：高亮并滚动到主区域对应分区
    scrollToSection(type) {
      this.activeType = type
      this.$nextTick(() => {
        const el = this.$el.querySelector('.study-section[data-type="' + type + '"]')
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    },
    async loadMyNotes() {
      this.loading = true
      try {
        const token = localStorage.getItem('kb_token') || ''
        const resp = await fetch('/api/docs?scope=mine&t=' + Date.now(), { headers: { 'Authorization': 'Bearer ' + token }, cache: 'no-store' })
        const data = await resp.json()
        this.myNotes = data || []
        const types = {}
        for (const n of (data || [])) types[n.type || '未分类'] = true
        this.openTypes = types
        if (!this.activeType && this.grouped.length) this.activeType = this.grouped[0].type
      } catch (e) { /* 忽略 */ }
      this.loading = false
    },
    toggleType(t) {
      const s = { ...this.openTypes }
      if (s[t]) delete s[t]; else s[t] = true
      this.openTypes = s
    },
    openNote(id) { this.$router.push('/notes/' + id) },
    // 阅览室：把书房的笔记放进去（引用），定点学习
    async loadRoom() {
      try {
        const res = await api.get('/reading-list', { params: { t: Date.now() } })
        this.roomIds = new Set((res.data || []).map(d => d.id))
      } catch (e) { /* 忽略 */ }
    },
    async toggleRoom(n) {
      if (this.roomIds.has(n.id)) {
        try { await api.delete('/reading-list/' + n.id) } catch (e) { /* 忽略 */ }
        const s = new Set(this.roomIds); s.delete(n.id); this.roomIds = s
      } else {
        try { await api.post('/reading-list', { doc_id: n.id, source: 'study' }) } catch (e) { /* 忽略 */ }
        const s = new Set(this.roomIds); s.add(n.id); this.roomIds = s
      }
    },
    editNote(id) { this.$router.push('/edit/' + id) },
    newNote() { this.$router.push('/edit') },
    newDoodle() { this.$router.push('/edit?doodle=1') },
    onPickFiles(e) { this.uploadFiles = Array.from(e.target.files || []); e.target.value = '' },
    async doUpload() {
      if (!this.uploadFiles.length) return
      this.uploading = true
      let ok = 0
      for (const file of this.uploadFiles) {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('type', this.uploadType)
        fd.append('title', file.name.replace(/\.[^.]+$/, ''))
        fd.append('visibility', this.uploadVis)
        try { await api.post('/docs', fd); ok++ } catch (e) { /* 忽略 */ }
      }
      this.uploading = false
      this.uploadOpen = false
      this.uploadFiles = []
      if (ok) { this.loadMyNotes() }
    },
    async aiGenerate() {
      const topic = this.aiTopic.trim()
      if (!topic) return
      this.aiBusy = true
      this.aiGen = ''
      this.aiMode = 'preview'
      this.aiTitle = this.aiTitle || topic
      try {
        const token = localStorage.getItem('kb_token') || ''
        const resp = await fetch('/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
          body: JSON.stringify({ question: `请为「${topic}」写一篇结构清晰的 Markdown 学习笔记：包含标题、概述、重点内容（分点）、公式（LaTeX）与小结。直接输出 Markdown 正文。`, stream: true }),
        })
        if (!resp.ok) { this.aiGen = '😅 生成失败' }
        else {
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
                if (obj.delta) this.aiGen += obj.delta
                else if (obj.error) this.aiGen += '\n😅 ' + obj.error
              } catch (e) { /* 忽略 */ }
            }
          }
        }
      } catch (e) { this.aiGen = '😅 网络异常：' + e.message }
      this.aiBusy = false
    },
    async aiConfirm() {
      if (!this.aiGen.trim()) return
      this.aiBusy = true
      try {
        const res = await api.post('/docs', {
          type: this.aiType, title: this.aiTitle.trim() || this.aiTopic.trim(),
          content: this.aiGen, visibility: this.aiVis,
          downloadable: this.aiDL ? 1 : 0, price: Number(this.aiPrice) || 0,
          preview_only: this.aiPreview ? 1 : 0,
        })
        this.aiOpen = false
        this.aiGen = ''
        this.aiMode = 'draft'
        this.loadMyNotes()
        this.$router.push('/edit/' + res.data.id)
      } catch (e) { /* 忽略 */ }
      this.aiBusy = false
    },
  },
  mounted() { this.loadMyNotes(); this.loadRoom() },
}
</script>

<style scoped>
.study-page { display: grid; grid-template-columns: 260px minmax(0, 1fr); min-height: 100vh; padding-top: 60px; box-sizing: border-box; transition: grid-template-columns .25s ease; }
.study-page.collapsed { grid-template-columns: 48px minmax(0, 1fr); }
.side-toggle {
  width: 28px; height: 28px; flex-shrink: 0; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2);
  display: inline-flex; align-items: center; justify-content: center;
  transition: all .2s;
}
.side-toggle:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.side-toggle svg { width: 16px; height: 16px; }
.study-side {
  width: 100%; min-width: 0;
  border-right: 1px solid var(--border);
  padding: 20px 18px;
  height: calc(100vh - 60px); overflow-y: auto;
  position: sticky; top: 60px;
}
.study-page.collapsed .study-side {
  padding: 0; border-right: none; overflow: hidden;
  display: flex;
}
.sb-rail {
  width: 100%; height: 100%;
  border: none; background: transparent; cursor: pointer;
  display: flex; flex-direction: column; align-items: center;
  justify-content: flex-start;
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
.side-head { display: flex; align-items: center; gap: 8px; padding: 0 6px 14px; }
.side-title { flex: 1; font-size: 15px; font-weight: 800; color: var(--text1); }
.side-count { font-size: 12px; color: var(--text2); background: var(--btn-bg); border: 1px solid var(--border); padding: 2px 10px; border-radius: 999px; }
.side-empty { color: var(--text2); font-size: 13px; padding: 20px 8px; text-align: center; }
.side-group { margin-bottom: 4px; }
.side-type { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 10px; cursor: pointer; color: var(--text2); transition: all .15s; }
.side-type:hover { background: color-mix(in srgb, var(--brand-1) 7%, transparent); }
.side-type.on { color: var(--brand-1); font-weight: 600; background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.type-caret { font-size: 10px; transition: transform .2s; }
.type-caret.open { transform: rotate(90deg); }
.type-name { flex: 1; font-size: 13.5px; }
.type-num { font-size: 11px; color: var(--text2); background: var(--btn-bg); border: 1px solid var(--border); border-radius: 999px; padding: 0 8px; }
.type-items { padding-left: 18px; }
.type-item { display: flex; gap: 6px; align-items: center; padding: 6px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text2); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.type-item:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 6%, transparent); }
.ti-format { font-size: 11px; }
.ti-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.study-main { flex: 1; padding: 24px 56px 60px; min-width: 0; }
.main-top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 22px; }
.top-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.act-btn { padding: 9px 18px; border-radius: 999px; cursor: pointer; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2); font-size: 13.5px; transition: all .2s; }
.act-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); transform: translateY(-1px); }
.act-btn.primary { color: #fff; border-color: transparent; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); }
.act-btn.ai { color: #fff; border-color: transparent; background: linear-gradient(120deg, #6366f1, #8b5cf6); }
.top-links { display: flex; gap: 4px; }
.link-btn { padding: 8px 16px; border-radius: 10px; cursor: pointer; color: var(--text2); text-decoration: none; font-size: 13.5px; transition: all .15s; }
.link-btn:hover { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.main-head { margin-bottom: 18px; }
.main-title { font-size: 22px; font-weight: 800; color: var(--text1); margin: 0 0 6px; }
.main-sub { font-size: 12.5px; color: var(--text2); }
.main-empty { padding: 60px 0; text-align: center; color: var(--text2); }
.study-section { margin-bottom: 34px; scroll-margin-top: 130px; }
.section-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.section-type { font-size: 16px; font-weight: 800; color: var(--text1); margin: 0; }
.section-num { font-size: 12px; color: var(--text2); background: var(--btn-bg); border: 1px solid var(--border); padding: 2px 10px; border-radius: 999px; }
.note-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.note-card { padding: 16px 18px; border-radius: 16px; cursor: pointer; background: var(--bg-soft); border: 1px solid var(--border); transition: all .2s; }
.note-card:hover { transform: translateY(-3px); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); box-shadow: var(--shadow-1); }
.card-top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.fmt-badge, .vis-badge, .pin-badge, .coin-badge, .pv-badge { font-size: 10.5px; padding: 1px 8px; border-radius: 999px; }
.fmt-badge { color: #64748b; background: #e2e8f0; }
.fmt-pdf { color: #dc2626; background: #fee2e2; }
.fmt-ppt { color: #d97706; background: #fef3c7; }
.fmt-doc { color: #2563eb; background: #dbeafe; }
.fmt-png, .fmt-jpg { color: #059669; background: #d1fae5; }
.vis-badge { color: #64748b; background: #e2e8f0; }
.vis-badge.pub { color: #059669; background: #d1fae5; }
.pin-badge { color: #d97706; background: #fef3c7; }
.coin-badge { color: #b45309; background: #fde68a; }
.pv-badge { color: #7c3aed; background: #ede9fe; }
.card-title { font-size: 15px; font-weight: 700; color: var(--text1); margin: 0 0 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-preview { font-size: 12.5px; color: var(--text2); margin: 0 0 12px; height: 36px; overflow: hidden; }
.card-foot { display: flex; align-items: center; justify-content: space-between; }
.card-time { font-size: 11.5px; color: var(--text2); }
.card-edit { font-size: 12px; color: var(--brand-1); font-weight: 600; }
.card-room {
  font-size: 11.5px; color: var(--text2); border: 1px solid var(--border);
  border-radius: 999px; padding: 2px 10px; cursor: pointer; white-space: nowrap;
  transition: all .15s;
}
.card-room:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.card-room.in { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); backdrop-filter: blur(4px); z-index: 200; display: flex; align-items: center; justify-content: center; }
.modal { width: 460px; max-width: 92vw; max-height: 86vh; overflow-y: auto; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 18px; padding: 26px 28px; }
.modal.wide { width: 640px; }
.modal h3 { margin: 0 0 8px; font-size: 17px; color: var(--text1); }
.modal-tip { font-size: 12.5px; color: var(--text2); margin: 0 0 16px; line-height: 1.7; }
.file-input { margin-bottom: 10px; }
.file-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.file-item { font-size: 12px; color: var(--text2); background: var(--btn-bg); border: 1px solid var(--border); border-radius: 8px; padding: 3px 10px; }
.modal-row { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.modal-row label { font-size: 13px; color: var(--text2); width: 62px; flex-shrink: 0; }
.modal-row label.ml { width: auto; }
.modal-input { flex: 1; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1); font-size: 13.5px; }
.modal-input.w60 { width: 70px; flex: none; }
.hint { font-size: 11.5px; color: var(--text2); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.modal-btn { padding: 9px 22px; border-radius: 999px; cursor: pointer; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2); font-size: 13.5px; }
.modal-btn.primary { color: #fff; border-color: transparent; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); }
.modal-btn.ghost:hover { color: var(--brand-1); }
.ai-preview { border: 1px solid var(--border); border-radius: 12px; padding: 14px; max-height: 300px; overflow-y: auto; background: var(--btn-bg); }
.ai-gen { margin: 0; white-space: pre-wrap; font-size: 12.5px; line-height: 1.7; color: var(--text1); font-family: inherit; }
@media (max-width: 860px) {
  .study-page { grid-template-columns: 1fr; }
  .study-page.collapsed { grid-template-columns: 1fr; }
  .study-side { width: 100%; position: static; height: auto; max-height: none; border-right: none; border-bottom: 1px solid var(--border); }
  .side-toggle, .side-rail { display: none; }
  .note-grid { grid-template-columns: 1fr; }
}

.from-square { font-size: 10px; color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent); border: 1px solid color-mix(in srgb, var(--brand-1) 30%, transparent); padding: 1px 6px; border-radius: 999px; margin-left: 6px; vertical-align: middle; white-space: nowrap; }
</style>
