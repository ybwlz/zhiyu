<template>
  <div class="square-page">
    <div class="square-head">
      <h1 class="square-title">笔记广场</h1>
      <p class="square-sub">把散落的笔记，汇成一座共享的知识岛</p>
    </div>

    <div class="toolbar">
      <input v-model="search" class="search-input" placeholder="搜索笔记标题、内容或科目…" @keyup.enter="load" />
      <button class="refresh-btn" @click="load">刷新</button>
    </div>

    <div ref="layout" class="square-layout">
      <!-- ── 左栏：科目导航 + 快捷入口 ── -->
      <aside class="sq-left">
        <div class="panel">
          <div class="panel-title">📂 科目导航</div>
          <div class="cat-list">
            <div class="cat-item" :class="{ on: typeFilter === '' }" @click="setType('')">🌐 全部笔记</div>
            <div v-for="t in types" :key="t" class="cat-item" :class="{ on: typeFilter === t }" @click="setType(t)">{{ t }}</div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">🔀 排序方式</div>
          <div class="cat-list">
            <div class="cat-item" :class="{ on: sortBy === 'new' }" @click="sortBy = 'new'">🕐 最新发布</div>
            <div class="cat-item" :class="{ on: sortBy === 'hot' }" @click="sortBy = 'hot'">🔥 最热笔记</div>
            <div class="cat-item" :class="{ on: sortBy === 'fav' }" @click="sortBy = 'fav'">⭐ 我的收藏</div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">🧭 快捷入口</div>
          <div class="cat-list">
            <div class="cat-item" @click="$router.push('/admin')">🏠 我的书房</div>
            <div class="cat-item" @click="$router.push('/edit')">✍️ 发布笔记</div>
          </div>
        </div>
      </aside>

      <!-- ── 中栏：笔记流 ── -->
      <main class="sq-main">
        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="notes.length === 0" class="empty">还没有公开笔记，去书房发布第一篇吧</div>

        <div class="feed">
          <div v-for="n in visibleNotes" :key="n.id" class="feed-row">
            <div class="row-avatar-wrap" @click="goUser(n.author_public_id || n.user_id)">
              <img v-if="n.author_avatar" class="row-avatar" :src="n.author_avatar" alt="" />
              <span v-else class="row-avatar row-avatar-ph">{{ (n.author_nickname || n.author_username || '?').slice(0, 1) }}</span>
            </div>
            <div class="row-body">
              <div class="row-author">
                <span class="row-author-name" @click="goUser(n.author_public_id || n.user_id)">{{ n.author_nickname || n.author_username || '系统' }}</span>
                <span class="type-badge">{{ n.type }}</span>
                <span v-if="n.pinned_until && new Date(n.pinned_until) > new Date()" class="pin-badge">📌</span>
                <span v-if="n.price > 0" class="coin-badge">💎 {{ n.price }}</span>
                <span v-if="n.preview_only" class="pv-badge">🔒 仅预览</span>
                <span v-if="n.downloadable === 0" class="no-dl">📵 不可下载</span>
                <span class="row-time">{{ timeAgo(n.updated_at) }}</span>
              </div>
              <h3 class="row-title" @click="openNote(n.public_id || n.id)">{{ n.title }}</h3>
              <p class="row-preview" @click="openNote(n.public_id || n.id)">{{ previewText(n) }}</p>
              <div v-if="imagesOf(n).length" class="row-imgs" @click="openNote(n.public_id || n.id)">
                <img v-for="(img, i) in imagesOf(n)" :key="i" :src="img" alt="" />
              </div>
              <div class="row-actions">
                <button class="fa-btn" :class="{ on: liked[n.id] }" @click="toggleLike(n)">
                  {{ liked[n.id] ? '❤️' : '🤍' }} {{ n.likes_count || 0 }}
                </button>
                <button class="fa-btn" :class="{ on: faved[n.id] }" @click="toggleFav(n)">
                  {{ faved[n.id] ? '⭐' : '☆' }} {{ (n.favorites_count || 0) + (faved[n.id] ? 1 : 0) }}
                </button>
                <button class="fa-btn" @click="openNoteComment(n.public_id || n.id)">💬 {{ n.comments_count || 0 }}</button>
                <button class="fa-btn" @click="downloadNote(n)">⬇ {{ n.downloads_count || 0 }}</button>
                <button class="fa-btn add" :class="{ in: isCollected(n) }" :data-tip="isCollected(n) ? '已在你的书房（归你所有，可编辑）' : '加入书房（复制一份归你所有）'" @click="toggleCollect(n)">
                  {{ isCollected(n) ? '✓ 已在书房' : '📥 加入书房' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="visibleCount < sortedNotes.length" class="more-wrap">
          <button class="more-btn" @click="showMore">加载更多（{{ sortedNotes.length - visibleCount }} 篇）</button>
        </div>
      </main>

      <!-- ── 右栏：热门榜 / 最新 / 社区数据 ── -->
      <aside class="sq-right">
        <div class="panel">
          <div class="panel-title">🔥 热门榜</div>
          <div v-for="(n, i) in hotNotes" :key="n.id" class="rank-item" @click="openNote(n.public_id || n.id)">
            <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
            <span v-if="n.pinned_until && new Date(n.pinned_until) > new Date()" class="pin-badge">📌</span>
            <span class="rank-title">{{ n.title }}</span>
            <span class="rank-meta">👍 {{ n.likes_count || 0 }}</span>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">✨ 最新收录</div>
          <div v-for="n in recentNotes" :key="n.id" class="rank-item" @click="openNote(n.public_id || n.id)">
            <span class="rank-dot"></span>
            <span class="rank-title">{{ n.title }}</span>
            <span class="rank-meta">{{ timeAgo(n.updated_at) }}</span>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">📊 社区数据</div>
          <div class="stat-grid">
            <div class="stat-cell"><b>{{ comm.notes }}</b><span>篇笔记</span></div>
            <div class="stat-cell"><b>{{ comm.likes }}</b><span>次点赞</span></div>
            <div class="stat-cell"><b>{{ comm.comments }}</b><span>条评论</span></div>
            <div class="stat-cell"><b>{{ comm.downloads }}</b><span>次下载</span></div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api.js'
import { cleanText } from '@/utils/mdText.js'

export default {
  name: 'NotesSquareFeed',
  data() {
    return {
      notes: [], loading: true, search: '', typeFilter: '',
      sortBy: 'new', visibleCount: 9, PAGE_STEP: 9,
      allTypes: [],   // 全量分类缓存（在「全部」视图算一次，过滤后不再缩水，标签栏保持完整）
      liked: {}, faved: {}, roomIds: new Set(),      // 阅览室（临时引用）
      collectedIds: new Set(), // 已加入书房的原笔记 id（买过的）
      originMap: new Map(),    // 原笔记 id -> 书房副本 id
    }
  },
  computed: {
    types() { return this.allTypes.length ? this.allTypes : [...new Set(this.notes.map(n => n.type).filter(Boolean))] },
    visibleNotes() { return this.sortedNotes.slice(0, this.visibleCount) },
    sortedNotes() {
      const list = [...this.notes]
      if (this.sortBy === 'hot') list.sort((a, b) => (b.likes_count || 0) - (a.likes_count || 0))
      else if (this.sortBy === 'fav') {
        // 「⭐ 收藏」= 筛选出我收藏过的笔记（按收藏时间倒序近似：收藏数降序）
        return this.pinnedFirst(list.filter(n => this.faved[n.id]).sort((a, b) => (b.favorites_count || 0) - (a.favorites_count || 0)))
      }
      else list.sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || '')))
      return this.pinnedFirst(list)
    },
    hotNotes() {
      return this.pinnedFirst([...this.notes].sort((a, b) => (b.likes_count || 0) - (a.likes_count || 0))).slice(0, 5)
    },
    recentNotes() {
      return this.pinnedFirst([...this.notes].sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || '')))).slice(0, 5)
    },
    comm() {
      const sum = (k) => this.notes.reduce((a, d) => a + (Number(d[k]) || 0), 0)
      return { notes: this.notes.length, likes: sum('likes_count'), comments: sum('comments_count'), downloads: sum('downloads_count') }
    },
  },
  methods: {
    // 置顶优先：pinned_until 未过期的笔记排最前（次级排序保持原序）
    pinnedFirst(list) {
      const now = Date.now()
      const isPinned = (n) => n.pinned_until && new Date(n.pinned_until).getTime() > now
      return [...list].sort((a, b) => (isPinned(b) ? 1 : 0) - (isPinned(a) ? 1 : 0))
    },
    async load() {
      this.loading = true
      try {
        const params = new URLSearchParams({ scope: 'public', t: Date.now() })
        if (this.search) params.set('search', this.search)
        if (this.typeFilter) params.set('type', this.typeFilter)
        const res = await api.get('/docs?' + params.toString())
        this.notes = res.data || []
        // 只有「全部」视图才刷新全量分类，避免过滤后标签栏缩水
        if (!this.typeFilter && !this.search) {
          this.allTypes = [...new Set(this.notes.map(n => n.type).filter(Boolean))]
        }
        // 恢复点赞/收藏状态
        this.liked = {}; this.faved = {}
        for (const n of this.notes) {
          if (n.liked_by_me) this.liked[n.id] = true
          if (n.faved_by_me) this.faved[n.id] = true
        }
        this.loadRoom()
      } catch (e) { /* 忽略 */ }
      this.loading = false
      this.visibleCount = this.PAGE_STEP
    },
    async loadRoom() {
      try {
        const res = await api.get('/reading-list', { params: { t: Date.now() } })
        const list = res.data || []
        this.roomIds = new Set(list.map(d => d.id))
        this.collectedIds = new Set(list.filter(d => d.origin_id).map(d => d.origin_id))
        this.originMap = new Map(list.filter(d => d.origin_id).map(d => [d.origin_id, d.id]))
      } catch (e) { /* 忽略 */ }
    },
    async toggleLike(n) {
      if (this.liked[n.id]) {
        // 已赞 → 取消点赞（DELETE）
        try { await api.delete('/notes/' + n.id + '/like') } catch (e) { /* 忽略 */ }
        this.liked[n.id] = false
        if (typeof n.likes_count === 'number') n.likes_count = Math.max(0, n.likes_count - 1)
      } else {
        try {
          const res = await api.post('/notes/' + n.id + '/like')
          this.liked[n.id] = true
          if (res.data && typeof res.data.likes_count === 'number') n.likes_count = res.data.likes_count
          else if (typeof n.likes_count === 'number') n.likes_count += 1
        } catch (e) { /* 未登录或失败 */ }
      }
    },
    async toggleFav(n) {
      if (this.faved[n.id]) {
        try { await api.delete('/notes/' + n.id + '/favorite') } catch (e) { /* 忽略 */ }
        this.faved[n.id] = false
      } else {
        try {
          const res = await api.post('/notes/' + n.id + '/favorite')
          this.faved[n.id] = true
        } catch (e) { /* 未登录或失败 */ }
      }
    },
    // 加入/移出阅览室：临时引用，不复制
    async toggleRoom(n) {
      if (this.roomIds.has(n.id)) {
        try { await api.delete('/reading-list/' + n.id) } catch (e) { /* 忽略 */ }
        const s = new Set(this.roomIds); s.delete(n.id); this.roomIds = s
      } else {
        try { await api.post('/reading-list', { doc_id: n.id, source: 'square' }) } catch (e) { /* 忽略 */ }
        const s = new Set(this.roomIds); s.add(n.id); this.roomIds = s
      }
    },
    // 加入书房：复制一份归我所有（买书），并放进我的书房/阅览室
    async toggleCollect(n) {
      if (this.collectedIds.has(n.id)) {
        ElMessage.info('这篇笔记已在你的书房（我买的）')
        return
      }
      try {
        const res = await api.post('/docs/' + n.id + '/collect')
        if (res.data && res.data.id) {
          const s = new Set(this.collectedIds); s.add(n.id); this.collectedIds = s
          this.originMap.set(n.id, res.data.id)
          const s2 = new Set(this.roomIds); s2.add(res.data.id); this.roomIds = s2
          ElMessage.success('已加入你的书房（成为你的版本）')
        }
      } catch (e) { ElMessage.error(e.response?.data?.error || '加入失败') }
    },
    isCollected(n) { return this.collectedIds.has(n.id) },
    async downloadNote(n) {
      try {
        const res = await api.post('/notes/' + n.id + '/download')
        if (res.data && res.data.content) {
          const blob = new Blob([res.data.content], { type: 'text/markdown' })
          const a = document.createElement('a')
          a.href = URL.createObjectURL(blob)
          a.download = (n.title || 'note') + '.md'
          a.click()
          URL.revokeObjectURL(a.href)
          n.downloads_count = (n.downloads_count || 0) + 1
        }
      } catch (e) {
        if (e.response && (e.response.status === 402 || e.response.status === 403)) {
          alert(e.response.data.error || '无法下载')
        }
      }
    },
    openNote(id) { this.$router.push('/notes/' + id) },
    // 打开笔记并滚动到评论区（?focus=comment）
    openNoteComment(id) { this.$router.push('/notes/' + id + '?focus=comment') },
    goUser(uid) { if (uid) this.$router.push('/user/' + uid) },
    setType(t) { this.typeFilter = t; this.load() },
    showMore() { this.visibleCount += this.PAGE_STEP },
    // 预览：清洗 markdown + LaTeX 公式转成可读文字（sin²α + cos²α = 1）
    // 截到 1.5 行字数：第一行满 + 第二行文字到中间，然后省略号
    previewText(n) {
      let s = cleanText(n.content)
      if (s.length > 85) s = s.slice(0, 85) + '…'   // 每行约 57 字，85 = 满行 + 半行
      return s
    },
    // 正文里的图片（优先用后端提取的 preview_imgs，不受内容截断影响），最多 5 张，一行排列
    imagesOf(n) {
      if (n.preview_imgs && n.preview_imgs.length) return n.preview_imgs.slice(0, 5)
      const urls = []
      const re = /!\[[^\]]*\]\(([^)\s]+)\)/g
      let m
      const c = n.content || ''
      while ((m = re.exec(c)) && urls.length < 5) {
        const u = m[1]
        if (/^\/uploads\//.test(u) || /\.(?:png|jpe?g|gif|webp)(?:[?#]|$)/i.test(u)) urls.push(u)
      }
      return urls
    },
    timeAgo(s) {
      if (!s) return ''
      const d = new Date(String(s).replace(' ', 'T'))
      const diff = (Date.now() - d.getTime()) / 1000
      if (diff < 3600) return Math.max(1, Math.floor(diff / 60)) + ' 分钟前'
      if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
      return Math.floor(diff / 86400) + ' 天前'
    },
  },
  mounted() {
    // 支持从首页/科目图谱带 ?search= / ?type= 进来：预填并直接过滤
    const sq = this.$route.query.search
    if (sq) this.search = String(sq)
    const tp = this.$route.query.type
    if (tp) this.typeFilter = String(tp)
    this.load()
  },
}
</script>

<style scoped>
.square-page { max-width: 1680px; margin: 0 auto; padding: 96px 24px 60px; min-height: 100vh; box-sizing: border-box; }
.square-head { text-align: center; margin-bottom: 24px; }
.square-title { font-size: 30px; font-weight: 800; margin: 0 0 8px; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.square-sub { color: var(--text2); margin: 0; font-size: 14px; }

.toolbar { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 18px; }
.search-input { flex: none; width: 340px; max-width: 70%; padding: 10px 16px; border-radius: 12px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1); font-size: 13.5px; }
.refresh-btn { padding: 6px 16px; border-radius: 999px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2); font-size: 12.5px; cursor: pointer; white-space: nowrap; }
.refresh-btn:hover { color: var(--brand-1); }

/* ── 三栏布局 ── */
.square-layout { display: flex; gap: 20px; align-items: flex-start; justify-content: center; }
.sq-main { flex: 0 1 780px; min-width: 0; }
.sq-left { width: 220px; flex-shrink: 0; position: sticky; top: 86px; display: flex; flex-direction: column; gap: 14px; }
.sq-right { width: 280px; flex-shrink: 0; position: sticky; top: 86px; display: flex; flex-direction: column; gap: 14px; }

.panel { display: flex; flex-direction: column; }
.panel + .panel { margin-top: 18px; padding-top: 16px; border-top: 1px solid rgba(130, 134, 162, 0.14); }
.panel-title { font-size: 13px; font-weight: 700; color: var(--text1); margin-bottom: 10px; }
.cat-list { display: flex; flex-direction: column; gap: 2px; }
.cat-item {
  padding: 8px 10px; border-radius: 9px; font-size: 13px; color: var(--text2);
  cursor: pointer; transition: all .15s; display: flex; align-items: center; gap: 6px;
}
.cat-item:hover { background: color-mix(in srgb, var(--brand-1) 9%, transparent); color: var(--brand-1); }
.cat-item.on { background: color-mix(in srgb, var(--brand-1) 13%, transparent); color: var(--brand-1); font-weight: 600; }

.rank-item {
  display: flex; align-items: center; gap: 8px; padding: 7px 4px; border-radius: 8px;
  cursor: pointer; transition: background .15s;
}
.rank-item:hover { background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.rank-no { width: 20px; height: 20px; border-radius: 6px; background: var(--btn-bg); color: var(--text2); font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rank-no.top { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; }
.rank-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--brand-1); opacity: .6; flex-shrink: 0; }
.rank-title { flex: 1; min-width: 0; font-size: 12.5px; color: var(--text1); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.rank-meta { font-size: 11px; color: var(--text2); flex-shrink: 0; }

.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stat-cell {
  background: var(--btn-bg); border-radius: 10px; padding: 10px 4px;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.stat-cell b { font-size: 18px; font-weight: 800; color: var(--text1); line-height: 1.1; }
.stat-cell span { font-size: 11px; color: var(--text2); }

.loading, .empty { text-align: center; color: var(--text2); padding: 50px 0; }

/* 时间线式：无卡片、无间隔，只靠淡边框分割 */
.feed { display: flex; flex-direction: column; }
.feed-row { display: flex; gap: 16px; padding: 22px 10px; background: transparent; border-bottom: 1px solid rgba(130, 134, 162, 0.14); transition: background .15s; }
.feed-row:hover { background: rgba(130, 134, 162, 0.05); }
.feed-row:last-child { border-bottom: none; }
.row-avatar-wrap { flex-shrink: 0; cursor: pointer; align-self: flex-start; }
.row-avatar { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; display: block; }
.row-avatar-ph { display: flex; align-items: center; justify-content: center; font-size: 17px; font-weight: 700; color: #fff; background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); }
.row-body { flex: 1; min-width: 0; }
.row-author { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.row-author-name { font-size: 14.5px; font-weight: 700; color: var(--text1); cursor: pointer; }
.row-author-name:hover { color: var(--brand-1); }
.type-badge { color: #6366f1; background: #eef2ff; border-radius: 999px; padding: 0 8px; font-size: 10.5px; }
.pin-badge { color: #d97706; background: #fef3c7; border-radius: 999px; padding: 0 6px; font-size: 10.5px; }
.coin-badge { color: #b45309; background: #fde68a; border-radius: 999px; padding: 0 6px; font-size: 10.5px; }
.pv-badge { color: #7c3aed; background: #ede9fe; border-radius: 999px; padding: 0 6px; font-size: 10.5px; }
.no-dl { color: #dc2626; background: #fee2e2; border-radius: 999px; padding: 0 6px; font-size: 10.5px; }
.row-time { color: var(--text2); font-size: 12px; margin-left: auto; white-space: nowrap; }
.row-title { font-size: 19px; font-weight: 800; color: var(--text1); margin: 0 0 6px; cursor: pointer; line-height: 1.5; }
.row-title:hover { color: var(--brand-1); }
.row-preview { font-size: 13.5px; color: var(--text2); margin: 0 0 10px; line-height: 1.75; height: calc(1.75em * 2); overflow: hidden; cursor: pointer; }
.row-imgs { display: flex; flex-wrap: nowrap; gap: 8px; margin: 2px 0 12px; cursor: pointer; overflow: hidden; }
.row-imgs img { width: 148px; height: 100px; object-fit: cover; border-radius: 8px; flex-shrink: 0; display: block; background: var(--btn-bg); }
.row-actions { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.fa-btn { border: none; background: none; color: var(--text2); font-size: 12.5px; padding: 6px 10px; border-radius: 999px; cursor: pointer; transition: all .15s; }
.fa-btn:hover { background: color-mix(in srgb, var(--brand-1) 8%, transparent); color: var(--brand-1); transform: translateY(-1px); }
.fa-btn.on { color: #e11d48; }
.fa-btn.add { border: none; color: var(--brand-1); font-weight: 600; }
.fa-btn.add:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; transform: translateY(-1px); }
.fa-btn.add.in { color: var(--text2); border-color: transparent; background: none; }
.more-wrap { display: flex; justify-content: center; margin-top: 30px; }
.more-btn { padding: 10px 34px; border-radius: 999px; cursor: pointer; border: 1px solid color-mix(in srgb, var(--brand-1) 45%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); color: var(--brand-1); font-size: 13.5px; transition: all .2s; }
.more-btn:hover { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; }
@media (max-width: 1080px) {
  .sq-left, .sq-right { display: none; }
  .feed-row { padding: 18px 6px; gap: 12px; }
  .row-avatar { width: 40px; height: 40px; }
}
/* 手机端：单列铺满、头部与操作适配 */
@media (max-width: 720px) {
  .square-page { padding: 82px 12px 48px; }
  .square-head { margin-bottom: 16px; }
  .square-title { font-size: 24px; }
  .toolbar { flex-wrap: nowrap; }
  .search-input { flex: 1 1 auto; width: auto; max-width: none; min-width: 0; }
  .sq-main { flex: 1 1 100%; width: 100%; max-width: 100%; }
  .feed-row { padding: 16px 4px; gap: 10px; }
  .row-avatar { width: 36px; height: 36px; }
  .row-title { font-size: 17px; }
  .row-imgs { overflow-x: auto; }
  .row-imgs img { width: 120px; height: 82px; }
  .more-btn { width: 100%; }
}
</style>
