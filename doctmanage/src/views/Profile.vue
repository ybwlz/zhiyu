<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'
import AvatarCrop from '@/components/AvatarCrop.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const uid = computed(() => Number(route.params.id))
const isMe = computed(() => auth.isLogin && auth.user?.id === uid.value)
const profile = ref(null)
const tab = ref('notes') // notes | favorites | likes | mine
const noteQuery = ref('')   // 本页笔记搜索
const filteredNotes = computed(() => {
  const list = lists.value[tab.value] || []
  const q = noteQuery.value.trim()
  return q ? list.filter(n => (n.title || '').includes(q)) : list
})
const lists = ref({ notes: [], favorites: [], likes: [], mine: [], feed: [] })
const loading = ref(true)
const notFound = ref(false)

const heatmap = ref([])
const heatLoading = ref(false)
const heatTotal = ref(0)
const loadHeatmap = async () => {
  heatLoading.value = true
  try {
    const res = await api.get('/user/heatmap', { params: { uid: uid.value } })
    const map = {}
    res.data.data.forEach(d => { map[d.date] = d.seconds })
    // 生成最近 90 天（从 13 周前周一开始，7 列布局）
    const cells = []
    const now = new Date()
    const start = new Date(now)
    start.setDate(start.getDate() - 90)
    start.setDate(start.getDate() - start.getDay()) // 对齐到周日
    for (let i = 0; i < 91; i++) {
      const d = new Date(start)
      d.setDate(start.getDate() + i)
      if (d > now) continue
      const key = d.toISOString().slice(0, 10)
      cells.push({ date: key, seconds: map[key] || 0 })
    }
    heatTotal.value = cells.reduce((s, c) => s + c.seconds, 0)
    heatmap.value = cells
  } catch (e) { /* 忽略 */ }
  heatLoading.value = false
}
const heatLevel = (sec) => {
  if (sec <= 0) return 0
  if (sec < 600) return 1
  if (sec < 1800) return 2
  if (sec < 3600) return 3
  return 4
}
const heatColor = (lvl) => ['var(--btn-bg)', '#9be9a8', '#40c463', '#30a14e', '#216e39'][lvl]

const editOpen = ref(false)
const editForm = ref({ nickname: '', bio: '', interests: '' })

const loadProfile = async () => {
  loading.value = true
  notFound.value = false
  try {
    const res = await api.get('/users/' + uid.value)
    profile.value = res.data
    editForm.value = { nickname: res.data.nickname || '', bio: res.data.bio || '', interests: res.data.interests || '' }
    // 预加载所有标签页列表，标签计数初始即为真实值（否则点赞/收藏等初始显示 0）
    const tabs = ['notes', 'favorites', 'likes', 'feed']
    if (isMe.value) tabs.push('mine')
    await Promise.all(tabs.map(loadTab))
    loadHeatmap()
    loadFollowSide()
  } catch (e) {
    if (e.response?.status === 404) notFound.value = true
    else notFound.value = true // 其它错误同样进入错误态，避免渲染空 profile
  }
  loading.value = false
}

const loadTab = async (t) => {
  const map = {
    notes: `/users/${uid.value}/notes?scope=public`,
    favorites: `/users/${uid.value}/favorites`,
    likes: `/users/${uid.value}/likes`,
    mine: `/users/${uid.value}/notes?scope=mine`,
    feed: `/feed?user_id=${uid.value}`,
  }
  try {
    const res = await api.get(map[t])
    lists.value[t] = res.data
  } catch (e) { lists.value[t] = [] }
}

const switchTab = (t) => { tab.value = t; loadTab(t) }
const feedIcon = (f) => ({ doc: '📝', like: '👍', favorite: '⭐', comment: '💬', user: '👋' }[f.type] || '✨')
const feedText = (f) => {
  const t = f.doc_title ? `《${String(f.doc_title).slice(0, 16)}》` : ''
  return { doc: `发布了笔记 ${t}`, like: `点赞了笔记 ${t}`, favorite: `收藏了笔记 ${t}`, comment: `评论了笔记 ${t}`, user: '加入了知屿' }[f.type] || ''
}
const openNote = (id) => router.push('/notes/' + id)

// ── 单向关注 / 私信 ──
const followingList = ref([])
const followersList = ref([])
const followListOpen = ref(null) // 'following' | 'followers' | null
const followList = ref([])
const loadFollowSide = async () => {
  try {
    const [f1, f2] = await Promise.all([
      api.get('/users/' + uid.value + '/following'),
      api.get('/users/' + uid.value + '/followers'),
    ])
    followingList.value = f1.data
    followersList.value = f2.data
  } catch (e) { /* 忽略 */ }
}
const toggleFollow = async () => {
  if (!auth.isLogin) { ElMessage.warning('请先登录'); return }
  try {
    const res = await api.post('/follows/toggle', { user_id: uid.value })
    profile.value.is_following = res.data.following
    profile.value.followers_count = res.data.followers_count
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
const openChat = () => { router.push('/messages?with=' + uid.value) }
const openFollowList = async (kind) => {
  followListOpen.value = kind
  try {
    const res = await api.get('/users/' + uid.value + (kind === 'following' ? '/following' : '/followers'))
    followList.value = res.data
  } catch (e) { followList.value = [] }
}
const toggleFollowUser = async (u) => {
  if (!auth.isLogin) { ElMessage.warning('请先登录'); return }
  try {
    const res = await api.post('/follows/toggle', { user_id: u.id })
    u.is_following = res.data.following
    if (u.id === uid.value) profile.value.is_following = res.data.following
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}
const goUser = (id) => { router.push('/user/' + id) }

const onAvatarChange = (e) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  cropFile.value = file
  cropVisible.value = true
  e.target.value = ''
}
const cropVisible = ref(false)
const cropFile = ref(null)
const viewAvatar = ref(false)
const onCropDone = async (file) => {
  cropVisible.value = false
  try {
    const res = await auth.uploadAvatar(file)
    profile.value.avatar = res.avatar
    ElMessage.success('头像已更新')
  } catch (err) { ElMessage.error(err.response?.data?.error || '上传失败') }
}

const onCoverChange = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('cover', file)
    const res = await api.post('/user/cover', fd)
    profile.value.cover = res.data.cover
    if (auth.user) { auth.user.cover = res.data.cover; localStorage.setItem('kb_user', JSON.stringify(auth.user)) }
    loadCovers()
    ElMessage.success('背景已更新')
  } catch (err) { ElMessage.error(err.response?.data?.error || '上传失败') }
  e.target.value = ''
}

const saveProfile = async () => {
  try {
    await auth.updateProfile(editForm.value)
    profile.value.nickname = editForm.value.nickname
    profile.value.bio = editForm.value.bio
    profile.value.interests = editForm.value.interests
    editOpen.value = false
    ElMessage.success('资料已保存')
  } catch (e) { ElMessage.error('保存失败') }
}

const fmtSeconds = (s) => {
  if (!s) return '0 分钟'
  return Math.floor(s / 60) + ' 分钟'
}
// 加入年月：'2026-08-01 12:00:00' → '2026年8月'
const joinYear = (ts) => {
  if (!ts) return ''
  const m = String(ts).slice(0, 7).split('-')
  return m.length === 2 ? m[0] + '年' + Number(m[1]) + '月' : ''
}

const goSettings = () => { router.push('/settings') }
const PRESETS = [
  { name: '初始', cover: null },
  { name: '晴空', cover: '/uploads/presets/preset_1.png' },
  { name: '梦境', cover: '/uploads/presets/preset_2.png' },
  { name: '晨风', cover: '/uploads/presets/preset_3.png' },
  { name: '蜜语', cover: '/uploads/presets/preset_4.png' },
  { name: '海盐', cover: '/uploads/presets/preset_5.png' },
  { name: '云白', cover: '/uploads/presets/preset_6.png' },
  { name: '落樱', cover: '/uploads/presets/preset_7.png' },
  { name: '糖霜', cover: '/uploads/presets/preset_8.png' },
  { name: '雾蓝', cover: '/uploads/presets/preset_9.png' },
]
const bgOpen = ref(false)
const coverList = ref([])
const loadCovers = async () => {
  try { const res = await api.get('/user/covers'); coverList.value = res.data.covers || [] } catch (e) { /* 忽略 */ }
}
const applyCover = async (cover) => {
  try {
    await api.post('/user/cover/apply', { cover })
    profile.value.cover = cover
    if (auth.user) { auth.user.cover = cover; localStorage.setItem('kb_user', JSON.stringify(auth.user)) }
    loadCovers()
    ElMessage.success('背景已应用')
  } catch (e) { ElMessage.error(e.response?.data?.error || '应用失败') }
}
const resetCover = async () => {
  try {
    await api.post('/user/cover/reset')
    profile.value.cover = null
    if (auth.user) { auth.user.cover = null; localStorage.setItem('kb_user', JSON.stringify(auth.user)) }
    loadCovers()
    ElMessage.success('已恢复初始背景')
  } catch (e) { ElMessage.error('恢复失败') }
}
const copyId = async () => {
  const id = String(profile.value?.username || uid.value)
  try { await navigator.clipboard.writeText(id) } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = id
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  ElMessage.success('我的 ID 已复制: ' + id)
}

onMounted(loadProfile)

// 同一组件内路由参数变化（user/1 -> user/5）时重新加载，否则页面停留旧用户数据
watch(() => route.params.id, () => {
  loading.value = true
  heatmap.value = []
  loadProfile()
})
</script>

<template>
  <div class="profile-page">
    <div v-if="loading" class="center">加载中…</div>
    <div v-else-if="notFound || !profile" class="center">用户不存在或加载失败</div>

    <div v-else class="profile-wrap">
      <div class="profile-main-col">
      <!-- 资料卡 -->
      <div class="profile-card">
        <div v-if="profile.cover" class="profile-bg" :style="{ backgroundImage: 'url(' + profile.cover + ')' }"></div>
        <div class="cover" :class="{ 'has-cover': profile.cover }">
          <button v-if="isMe" class="cover-edit" @click="bgOpen = true; loadCovers()">🎨 背景</button>
        </div>
        <div v-if="!isMe" class="profile-actions-bar">
          <button class="follow-btn" :class="{ on: profile.is_following }" @click="toggleFollow">{{ profile.is_following ? '✓ 已关注' : '+ 关注' }}</button>
          <button class="msg-btn" @click="openChat">✉️ 私信</button>
        </div>
        <div class="profile-main">
          <div class="avatar-wrap">
            <div class="avatar-big" :class="{ clickable: profile.avatar }" @click="profile.avatar && (viewAvatar = true)" data-tip="点击查看大图">
              <img v-if="profile.avatar" :src="profile.avatar" alt="avatar" />
              <span v-else>{{ (profile.nickname || profile.username || '?').slice(0, 1) }}</span>
            </div>
            <label v-if="isMe" class="avatar-edit" data-tip="更换头像">
              换
              <input type="file" accept="image/*" hidden @change="onAvatarChange" />
            </label>
          </div>
          <h2 class="nickname">
            {{ profile.nickname || profile.username }}
            <span v-if="profile.badge === 'scholar'" class="badge-scholar" data-tip="学霸徽章">🏅 学霸</span>
          </h2>
          <div v-if="isMe" class="my-id" data-tip="点击复制我的 ID" @click="copyId">ID: {{ profile.username }} 📋</div>
          <p v-if="profile.bio" class="bio">{{ profile.bio }}</p>
          <p v-if="profile.interests" class="interests">🎯 {{ profile.interests }}</p>
          <div class="stats-row">
            <div v-if="isMe" class="stat clickable" @click="openFollowList('following')"><b>{{ profile.following_count }}</b><span>关注</span></div>
            <div v-if="isMe" class="stat clickable" @click="openFollowList('followers')"><b>{{ profile.followers_count }}</b><span>粉丝</span></div>
            <div class="stat"><b>{{ profile.public_notes }}</b><span>笔记</span></div>
            <div class="stat"><b>{{ profile.received_likes }}</b><span>获赞</span></div>
            <div class="stat"><b>{{ profile.points }}</b><span>积分</span></div>
            <div class="stat"><b>{{ fmtSeconds(profile.read_seconds) }}</b><span>阅读</span></div>
          </div>
      <!-- 编辑资料/设置（自己主页，卡片内 stats 下方） -->
      <div v-if="isMe" class="profile-actions-me">
        <button class="p-btn" @click="editOpen = true">✏️ 编辑资料</button>
        <button class="p-btn" @click="goSettings">⚙️ 设置</button>
      </div>
        </div>
      </div>


      <!-- 学习热力图（仅本人可见） -->
      <!-- 热力图已移至右侧栏 -->

      <!-- 标签页 -->
      <div class="tabs-row">
        <div class="tabs-btns">
          <button class="tab" :class="{ on: tab === 'notes' }" @click="switchTab('notes')">笔记 {{ lists.notes.length }}</button>
          <button class="tab" :class="{ on: tab === 'favorites' }" @click="switchTab('favorites')">收藏 {{ lists.favorites.length }}</button>
          <button class="tab" :class="{ on: tab === 'likes' }" @click="switchTab('likes')">点赞 {{ lists.likes.length }}</button>
          <button v-if="isMe" class="tab" :class="{ on: tab === 'mine' }" @click="switchTab('mine')">私密 {{ lists.mine.length }}</button>
          <button class="tab" :class="{ on: tab === 'feed' }" @click="switchTab('feed')">动态 {{ lists.feed.length }}</button>
        </div>
        <div class="tabs-side">
          <input v-if="tab !== 'feed'" v-model="noteQuery" class="tabs-search" placeholder="搜索本页笔记…" />
          <button v-if="isMe" class="p-btn new-note" @click="$router.push('/edit')">✍️ 发布笔记</button>
        </div>
      </div>

      <div v-if="tab !== 'feed' && lists[tab].length === 0" class="center empty">这里还空空的</div>
      <div v-else-if="tab !== 'feed' && filteredNotes.length === 0" class="center empty">没有匹配「{{ noteQuery }}」的笔记</div>
      <div v-if="tab === 'feed'" class="feed-list">
        <div v-if="lists.feed.length === 0" class="center empty">TA 还没有动态</div>
        <div v-for="(f, i) in lists.feed" :key="i" class="feed-item" @click="f.doc_id && openNote(f.doc_id)">
          <span class="feed-ic">{{ feedIcon(f) }}</span>
          <span class="feed-txt">{{ feedText(f) }}</span>
          <span class="feed-time">{{ String(f.ts || '').slice(0, 16) }}</span>
        </div>
      </div>
      <div v-if="tab !== 'feed'" class="note-grid">
        <div v-for="n in filteredNotes" :key="n.id" class="note-card" @click="openNote(n.id)">
          <div class="card-top">
            <span class="type-badge">{{ n.type }}</span>
            <span class="vis" v-if="tab === 'mine'">{{ n.visibility === 'public' ? '公开' : '私密' }}</span>
          </div>
          <h3 class="card-title">{{ n.title }}</h3>
          <div class="card-stats">
            <span>👍 {{ n.likes_count }}</span>
            <span>⭐ {{ n.favorites_count }}</span>
            <span>💬 {{ n.comments_count }}</span>
          </div>
        </div>
      </div>
      </div>

      <!-- 右侧栏：关注/粉丝仅本人可见（隐私）；他人显示 TA 的最新公开笔记 -->
      <aside class="profile-aside">
        <template v-if="isMe">
          <div class="as-card">
            <div class="as-head">
              <span class="as-title">我的关注</span>
              <button v-if="profile.following_count > 5" class="as-more" @click="openFollowList('following')">全部 {{ profile.following_count }}</button>
            </div>
            <div v-if="!followingList.length" class="as-empty">还没有关注任何人</div>
            <div v-for="u in followingList.slice(0, 5)" :key="u.id" class="as-user" @click="goUser(u.id)">
              <span class="as-avatar"><img v-if="u.avatar" :src="u.avatar" alt="" /><span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span></span>
              <span class="as-name">{{ u.nickname || u.username }}</span>
              <span class="as-id">@{{ u.username }}</span>
            </div>
          </div>
          <div class="as-card">
            <div class="as-head">
              <span class="as-title">我的粉丝</span>
              <button v-if="profile.followers_count > 5" class="as-more" @click="openFollowList('followers')">全部 {{ profile.followers_count }}</button>
            </div>
            <div v-if="!followersList.length" class="as-empty">还没有粉丝</div>
            <div v-for="u in followersList.slice(0, 5)" :key="u.id" class="as-user" @click="goUser(u.id)">
              <span class="as-avatar"><img v-if="u.avatar" :src="u.avatar" alt="" /><span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span></span>
              <span class="as-name">{{ u.nickname || u.username }}</span>
              <span class="as-id">@{{ u.username }}</span>
            </div>
          </div>
          <div class="as-card">
            <div class="as-head"><span class="as-title">📊 我的阅读热力图</span></div>
            <div class="as-heat-grid">
              <span v-for="(c, i) in heatmap" :key="i" class="as-heat-cell" :style="{ background: heatColor(heatLevel(c.seconds)) }" :data-tip="c.date + '：' + Math.round(c.seconds / 60) + ' 分钟'"></span>
            </div>
            <div class="as-heat-total">近 90 天累计阅读 {{ Math.round(heatTotal / 60) }} 分钟</div>
          </div>
        </template>
        <template v-else>
          <div class="as-card">
            <div class="as-head"><span class="as-title">📚 TA 的最新公开笔记</span></div>
            <div v-if="!lists.notes.length" class="as-empty">TA 还没有公开笔记</div>
            <div v-for="n in lists.notes.slice(0, 6)" :key="n.id" class="as-note" @click="openNote(n.id)">
              <span class="as-note-type">{{ n.type }}</span>
              <span class="as-note-title">{{ n.title }}</span>
              <span class="as-note-meta">👍 {{ n.likes_count || 0 }} · 💬 {{ n.comments_count || 0 }}</span>
            </div>
          </div>
          <div class="as-card">
            <div class="as-head"><span class="as-title">👤 关于 TA</span></div>
            <div class="as-bio">{{ profile.bio || '这个人很懒，什么也没写' }}</div>
            <div class="as-meta">
              <span v-if="profile.created_at">🕐 {{ joinYear(profile.created_at) }} 加入</span>
              <span>🪙 {{ profile.points || 0 }} 知屿币</span>
              <span>⏱ 阅读 {{ fmtSeconds(profile.read_seconds) }}</span>
              <span v-if="profile.interests">🎯 {{ profile.interests }}</span>
            </div>
          </div>
          <div class="as-card">
            <div class="as-head"><span class="as-title">📊 阅读热力图</span></div>
            <div class="as-heat-grid">
              <span v-for="(c, i) in heatmap" :key="i" class="as-heat-cell" :style="{ background: heatColor(heatLevel(c.seconds)) }" :data-tip="c.date + '：' + Math.round(c.seconds / 60) + ' 分钟'"></span>
            </div>
            <div class="as-heat-total">近 90 天累计阅读 {{ Math.round(heatTotal / 60) }} 分钟</div>
          </div>
        </template>
      </aside>
    </div>

    <!-- 关注/粉丝列表弹窗 -->
    <div v-if="followListOpen" class="modal-mask" @click.self="followListOpen = null">
      <div class="modal">
        <h3>{{ followListOpen === 'following' ? 'TA 的关注' : 'TA 的粉丝' }}（{{ followList.length }}）</h3>
        <div v-if="!followList.length" class="center empty">这里还空空的</div>
        <div class="fl-scroll">
          <div v-for="u in followList" :key="u.id" class="fl-row" @click="goUser(u.id)">
            <span class="as-avatar"><img v-if="u.avatar" :src="u.avatar" alt="" /><span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span></span>
            <div class="fl-info">
              <div class="fl-name">{{ u.nickname || u.username }}</div>
              <div class="fl-id">@{{ u.username }}</div>
            </div>
            <button v-if="!u.is_me" class="follow-btn sm" :class="{ on: u.is_following }" @click.stop="toggleFollowUser(u)">{{ u.is_following ? '已关注' : '+ 关注' }}</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="editOpen" class="modal-mask" @click.self="editOpen = false">
      <div class="modal">
        <h3>编辑资料</h3>
        <label class="field">昵称<input v-model="editForm.nickname" maxlength="32" /></label>
        <label class="field">简介<textarea v-model="editForm.bio" maxlength="200" rows="3"></textarea></label>
        <label class="field">喜好（逗号分隔）<input v-model="editForm.interests" maxlength="200" /></label>
        <div class="modal-actions">
          <button class="cancel" @click="editOpen = false">取消</button>
          <button class="save" @click="saveProfile">保存</button>
        </div>
      </div>
    </div>

    <!-- 更换背景面板 -->
    <div v-if="bgOpen" class="modal-mask" @click.self="bgOpen = false">
      <div class="modal bg-modal">
        <h3>更换背景</h3>
        <div class="bg-section">
          <div class="bg-sec-title">默认方案</div>
          <div class="cover-grid">
            <div
              v-for="p in PRESETS" :key="p.name"
              class="cover-thumb"
              :class="{ on: p.cover === null ? !profile.cover : profile.cover === p.cover }"
              :style="p.cover ? { backgroundImage: 'url(' + p.cover + ')' } : {}"
              @click="p.cover ? applyCover(p.cover) : resetCover()"
            >
              <span v-if="!p.cover" class="cover-thumb-default">▦</span>
              <span class="cover-thumb-name">{{ p.name }}</span>
            </div>
          </div>
        </div>
        <div v-if="coverList.length" class="bg-section">
          <div class="bg-sec-title">历史背景</div>
          <div class="cover-grid">
            <div
              v-for="(h, i) in coverList" :key="i"
              class="cover-thumb"
              :class="{ on: h.current }"
              :style="{ backgroundImage: 'url(' + h.cover + ')' }"
              @click="applyCover(h.cover)"
            ></div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="cancel" @click="bgOpen = false">取消</button>
          <label class="save upload-bg">上传新背景<input type="file" accept="image/*" hidden @change="onCoverChange" /></label>
        </div>
      </div>
    </div>

    <!-- 查看大头像 -->
    <div v-if="viewAvatar && profile.avatar" class="avatar-view" @click="viewAvatar = false">
      <img :src="profile.avatar" alt="avatar" />
    </div>

    <!-- 头像裁剪 -->
    <AvatarCrop :visible="cropVisible" :file="cropFile" @done="onCropDone" @close="cropVisible = false" />
  </div>
</template>

<style scoped>
.profile-page { min-height: 100vh; padding: 92px 24px 60px; box-sizing: border-box; }
.center { text-align: center; color: var(--text2); padding: 80px 0; }
.profile-wrap {
  max-width: 1060px; margin: 0 auto;
  display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 18px;
  align-items: start;
}
.profile-main-col { min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.profile-aside { display: flex; flex-direction: column; gap: 16px; }
.as-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 14px 16px; }
.as-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.as-title { font-size: 13.5px; font-weight: 700; color: var(--text1); }
.as-more { font-size: 12px; color: var(--brand-1); background: none; border: none; cursor: pointer; }
.as-empty { font-size: 12.5px; color: var(--text2); padding: 10px 0; }
.as-note {
  display: flex; align-items: center; gap: 10px; padding: 8px 0; cursor: pointer;
  border-radius: 10px; transition: background .15s; border-bottom: 1px solid color-mix(in srgb, var(--border) 55%, transparent);
}
.as-note:last-child { border-bottom: none; }
.as-note:hover { background: color-mix(in srgb, var(--brand-1) 7%, transparent); }
.as-note-type {
  flex-shrink: 0; font-size: 10.5px; color: #6366f1; background: #eef2ff;
  border-radius: 999px; padding: 2px 8px;
}
.as-note-title { flex: 1; min-width: 0; font-size: 12.5px; color: var(--text1); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.as-note-meta { flex-shrink: 0; font-size: 11px; color: var(--text2); }
.as-bio { font-size: 12.5px; color: var(--text2); line-height: 1.7; margin-bottom: 8px; }
.as-meta { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--text2); }
.as-heat-grid { display: grid; grid-template-columns: repeat(13, 1fr); gap: 3px; margin: 4px 0 6px; }
.as-heat-cell { aspect-ratio: 1; border-radius: 2px; }
.as-heat-total { font-size: 11px; color: var(--text2); }
.as-user { display: flex; align-items: center; gap: 10px; padding: 7px 0; cursor: pointer; border-radius: 10px; transition: background .15s; }
.as-user:hover { background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.as-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; overflow: hidden;
}
.as-avatar img { width: 100%; height: 100%; object-fit: cover; }
.as-name { flex: 1; font-size: 13px; color: var(--text1); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.as-id { font-size: 11px; color: var(--text2); }
.stat.clickable { cursor: pointer; border-radius: 10px; padding: 2px 10px; transition: background .15s; }
.stat.clickable:hover { background: color-mix(in srgb, var(--brand-1) 10%, transparent); }
.follow-btn {
  padding: 8px 22px; border-radius: 999px; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--brand-1) 55%, transparent);
  background: transparent; color: var(--brand-1);
  font-size: 13px; font-weight: 600; transition: all .18s;
  backdrop-filter: blur(4px);
}
.follow-btn:hover { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.follow-btn.on {
  background: color-mix(in srgb, var(--brand-1) 16%, transparent);
  color: var(--brand-1);
  border-color: color-mix(in srgb, var(--brand-1) 42%, transparent);
}
.follow-btn.sm { padding: 4px 14px; font-size: 12px; }
.profile-actions-bar {
  position: absolute; top: 14px; right: 16px; z-index: 2;
  display: flex; gap: 10px;
}
.profile-actions-bar .follow-btn,
.profile-actions-bar .msg-btn {
  background: color-mix(in srgb, var(--bg-soft) 70%, transparent);
  backdrop-filter: blur(6px);
}
.profile-actions-me { display: flex; gap: 10px; margin: 14px 0 4px; }
.p-btn {
  padding: 9px 26px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 13.5px; font-weight: 600; transition: all .18s;
}
.p-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 50%, transparent); }
.msg-btn {
  padding: 9px 22px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 13.5px; font-weight: 600; transition: all .18s;
}
.msg-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 50%, transparent); }
.profile-actions-bar .follow-btn {
  background: var(--btn-bg);
}
/* 星空主题：主页文字用 difference 混合自动对比（亮底显黑、暗底显白），背景保持原样不动 */
html[data-theme="starlight"] .nickname,
html[data-theme="starlight"] .my-id,
html[data-theme="starlight"] .bio,
html[data-theme="starlight"] .interests,
html[data-theme="starlight"] .stat b,
html[data-theme="starlight"] .stat span {
  color: #fff;
  mix-blend-mode: difference;
  text-shadow: none;
}
.fl-scroll { max-height: 55vh; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.fl-row { display: flex; align-items: center; gap: 12px; padding: 9px 4px; cursor: pointer; border-radius: 12px; transition: background .15s; }
.fl-row:hover { background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
.fl-info { flex: 1; min-width: 0; }
.fl-name { font-size: 13.5px; color: var(--text1); font-weight: 600; }
.fl-id { font-size: 11.5px; color: var(--text2); }
@media (max-width: 900px) { .profile-wrap { grid-template-columns: minmax(0, 1fr); } }

.profile-card {
  position: relative;
  background: var(--card-bg);
  background-size: cover;
  background-position: center;
  border: 1px solid var(--border);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(12px);
  margin-bottom: 22px;
}
/* 背景图独立层：星空下直接调低不透明度（背景图透明度调高 = 变淡） */
.profile-bg {
  position: absolute; inset: 0; z-index: 0;
  background-size: cover; background-position: center;
  pointer-events: none;
}
.profile-card > .cover,
.profile-card > .profile-main { position: relative; z-index: 1; }
html[data-theme="starlight"] .profile-bg { opacity: .32; }
.cover {
  position: relative;
  height: 96px;
  background: linear-gradient(120deg, color-mix(in srgb, var(--brand-1) 30%, transparent), color-mix(in srgb, var(--brand-2) 25%, transparent));
  background-size: cover;
  background-position: center;
}
.cover.has-cover { background: linear-gradient(180deg, rgba(0,0,0,.10) 0%, rgba(0,0,0,0) 42%, color-mix(in srgb, var(--card-bg) 60%, transparent) 100%); }
.profile-main { padding: 0 28px 24px; position: relative; background: color-mix(in srgb, var(--card-bg) 60%, transparent); }
.avatar-wrap { position: relative; display: inline-block; margin-top: -34px; }
.avatar-big {
  width: 72px; height: 72px; border-radius: 50%;
  border: 3px solid var(--bg);
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 28px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.avatar-big img { width: 100%; height: 100%; object-fit: cover; }
.avatar-big.clickable { cursor: zoom-in; }
.avatar-view { position: fixed; inset: 0; z-index: 300; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; cursor: zoom-out; }
.avatar-view img { width: 220px; height: 220px; border-radius: 50%; object-fit: cover; border: 3px solid #fff; box-shadow: 0 8px 40px rgba(0,0,0,.5); }
.avatar-edit {
  position: absolute; bottom: 2px; right: 2px;
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--btn-bg); border: 1px solid var(--border);
  color: var(--text2); font-size: 11px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.nickname { font-size: 21px; font-weight: 800; margin: 10px 0 4px; color: var(--text1); display: flex; align-items: center; gap: 10px; }
.badge-scholar {
  font-size: 11.5px; font-weight: 700;
  padding: 3px 12px; border-radius: 999px;
  color: #8a5a00;
  background: linear-gradient(135deg, #ffe066, #ffb300);
  border: 1px solid #e6a800;
  box-shadow: 0 2px 8px rgba(255, 179, 0, .35);
  mix-blend-mode: normal; /* 防止继承父级 difference 混合导致金色变蓝 */
}
.bio { color: var(--text2); font-size: 14px; margin: 4px 0; }
.interests { color: var(--text2); font-size: 13px; margin: 4px 0; }
.stats-row { display: flex; gap: 26px; margin: 16px 0 14px; }
.stat { display: flex; flex-direction: column; align-items: center; }
.stat b { font-size: 17px; color: var(--text1); }
.stat span { font-size: 12px; color: var(--text2); margin-top: 2px; }
.edit-btn {
  padding: 8px 20px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--text1); font-size: 13px; cursor: pointer;
}
.edit-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.my-id {
  display: inline-block; font-size: 12.5px; color: var(--text2);
  background: var(--btn-bg); border: 1px solid var(--border);
  padding: 2px 12px; border-radius: 999px; cursor: pointer; margin: 0 0 8px;
}
.my-id:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }

.cover-edit {
  position: absolute; top: 10px; right: 12px;
  padding: 4px 12px; border-radius: 999px;
  background: rgba(0,0,0,.35); color: #fff; font-size: 12px; cursor: pointer;
  backdrop-filter: blur(4px); z-index: 2;
}
.cover-edit:hover { background: rgba(0,0,0,.5); }
.bg-modal { max-width: 460px; }
.bg-section { margin-bottom: 16px; }
.bg-sec-title { font-size: 12.5px; color: var(--text2); margin-bottom: 8px; }
.cover-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.cover-thumb {
  position: relative; aspect-ratio: 1; border-radius: 10px;
  background-size: cover; background-position: center;
  border: 2px solid var(--border); cursor: pointer; overflow: hidden;
  transition: transform .15s;
}
.cover-thumb:hover { transform: scale(1.06); }
.cover-thumb::after {
  content: '';
  position: absolute; left: 0; right: 0; bottom: 0; height: 46%;
  background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.38) 100%);
  border-radius: 0 0 8px 8px;
  pointer-events: none;
}
.cover-thumb.on { border-color: var(--brand-1); box-shadow: 0 0 0 2px color-mix(in srgb, var(--brand-1) 40%, transparent); }
.cover-thumb-default {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 24px; color: var(--text2); background: var(--btn-bg);
}
.cover-thumb-name { position: absolute; left: 6px; bottom: 5px; z-index: 1; font-size: 10.5px; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,.55); }
.upload-bg { display: inline-flex; align-items: center; }

.heatmap-card {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 18px; padding: 18px 22px;
  margin-bottom: 20px; backdrop-filter: blur(8px);
}
.heatmap-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px; flex-wrap: wrap; gap: 6px;
}
.heatmap-title { font-size: 14.5px; font-weight: 700; color: var(--text1); }
.heatmap-total { font-size: 12.5px; color: var(--text2); }
.heat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(11px, 1fr));
  gap: 3px;
}
.heat-cell {
  aspect-ratio: 1;
  border-radius: 3px;
  transition: transform .15s;
}
.heat-cell:hover { transform: scale(1.25); }
.heat-legend {
  display: flex; align-items: center; gap: 4px;
  margin-top: 10px; justify-content: flex-end;
  font-size: 11px; color: var(--text2);
}
.heat-cell.mini { width: 11px; height: 11px; aspect-ratio: auto; }
.center.small { font-size: 12.5px; padding: 12px 0; }

.tabs-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.tabs-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.tabs-side { flex: 1; display: flex; align-items: center; gap: 8px; min-width: 0; }
.tabs-search {
  flex: 1; min-width: 0;
  padding: 7px 12px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--text1); font-size: 12.5px; outline: none;
  transition: border-color .18s;
}
.tabs-search:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.tabs-search::placeholder { color: var(--text2); }
.new-note { white-space: nowrap; }
.tab {
  padding: 8px 18px; border: none; border-radius: 999px;
  background: transparent; color: var(--text2); font-size: 13.5px; cursor: pointer;
  transition: all .2s;
}
.tab.on { background: var(--card-bg); color: var(--brand-1); font-weight: 600; box-shadow: var(--shadow-1); }

.feed-list { display: flex; flex-direction: column; gap: 6px; }
.feed-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-radius: 12px;
  background: var(--bg-soft); border: 1px solid var(--border);
  cursor: pointer; transition: all .2s;
}
.feed-item:hover { transform: translateX(4px); border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.feed-ic { font-size: 16px; }
.feed-txt { flex: 1; font-size: 13.5px; color: var(--text1); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.feed-time { font-size: 12px; color: var(--text2); flex-shrink: 0; }
.note-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.note-card {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 16px; padding: 18px 20px; cursor: pointer;
  transition: transform .25s, border-color .25s;
}
.note-card:hover { transform: translateY(-3px); border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.card-top { display: flex; justify-content: space-between; margin-bottom: 8px; }
.type-badge {
  font-size: 11px; padding: 2px 9px; border-radius: 999px;
  color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 12%, transparent);
}
.vis { font-size: 11px; color: var(--text2); }
.card-title { font-size: 15px; font-weight: 700; margin: 0 0 10px; color: var(--text1); line-height: 1.4; }
.card-stats { display: flex; gap: 12px; font-size: 12px; color: var(--text2); }
.empty { color: var(--text2); }

.modal-mask {
  position: fixed; inset: 0; z-index: 200;
  background: var(--overlay-bg);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  width: 400px; max-width: 92vw;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 18px; padding: 26px;
}
.modal h3 { margin: 0 0 16px; color: var(--text1); }
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; color: var(--text2); font-size: 13px; }
.field input, .field textarea {
  padding: 9px 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 14px; outline: none; resize: none;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
.cancel { padding: 8px 18px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text2); cursor: pointer; }
.save { padding: 8px 20px; border: none; border-radius: 999px; background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; cursor: pointer; font-weight: 600; }
</style>