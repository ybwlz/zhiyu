<template>
  <div class="friends-page">
    <h2 class="page-title">关注 · 粉丝</h2>

    <div class="f-tabs">
      <button class="f-tab" :class="{ on: tab === 'following' }" @click="switchTab('following')">我的关注 ({{ following.length }})</button>
      <button class="f-tab" :class="{ on: tab === 'followers' }" @click="switchTab('followers')">我的粉丝 ({{ followers.length }})</button>
      <button class="f-tab" :class="{ on: tab === 'discover' }" @click="switchTab('discover')">发现用户</button>
    </div>

    <!-- 我的关注 -->
    <div v-if="tab === 'following'" class="f-list">
      <div v-if="!following.length" class="center empty">还没有关注任何人，去「发现用户」找找吧</div>
      <div v-for="u in following" :key="u.id" class="f-row">
        <div class="f-avatar" @click="goUser(u.other_public_id || u.other_id || u.id)">
          <img v-if="u.avatar" :src="u.avatar" alt="" />
          <span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span>
        </div>
        <div class="f-info" @click="goUser(u.other_public_id || u.other_id || u.id)">
          <div class="f-name">{{ u.nickname || u.username }}</div>
          <div class="f-id">@{{ u.username }} · 知屿币 {{ u.points }}</div>
        </div>
        <div class="f-acts">
          <button class="msg-btn sm" data-tip="私信" @click="openChat(u.other_public_id || u.other_id || u.id)">✉️</button>
          <button class="follow-btn sm on" @click="toggle(u)">已关注</button>
        </div>
      </div>
    </div>

    <!-- 我的粉丝 -->
    <div v-else-if="tab === 'followers'" class="f-list">
      <div v-if="!followers.length" class="center empty">还没有粉丝</div>
      <div v-for="u in followers" :key="u.id" class="f-row">
        <div class="f-avatar" @click="goUser(u.other_public_id || u.other_id || u.id)">
          <img v-if="u.avatar" :src="u.avatar" alt="" />
          <span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span>
        </div>
        <div class="f-info" @click="goUser(u.other_public_id || u.other_id || u.id)">
          <div class="f-name">{{ u.nickname || u.username }}</div>
          <div class="f-id">@{{ u.username }} · 知屿币 {{ u.points }}</div>
        </div>
        <div class="f-acts">
          <button class="msg-btn sm" data-tip="私信" @click="openChat(u.other_public_id || u.other_id || u.id)">✉️</button>
          <button v-if="!u.is_me" class="follow-btn sm" :class="{ on: u.is_following }" @click="toggle(u)">{{ u.is_following ? '已关注' : '回关' }}</button>
        </div>
      </div>
    </div>

    <!-- 发现用户 -->
    <div v-else class="f-search">
      <div class="search-row">
        <input v-model="q" class="search-input" placeholder="输入 ID（@用户名）或昵称搜索用户" @keyup.enter="search" />
        <button class="search-btn" @click="search">搜索</button>
      </div>
      <div v-if="searched" class="f-list">
        <div v-if="!results.length" class="center empty">没有找到相关用户</div>
        <div v-for="u in results" :key="u.id" class="f-row">
          <div class="f-avatar" @click="goUser(u.other_public_id || u.other_id || u.id)">
            <img v-if="u.avatar" :src="u.avatar" alt="" />
            <span v-else>{{ (u.nickname || u.username || '?').slice(0, 1) }}</span>
          </div>
          <div class="f-info" @click="goUser(u.other_public_id || u.other_id || u.id)">
            <div class="f-name">{{ u.nickname || u.username }}</div>
            <div class="f-id">@{{ u.username }} · 知屿币 {{ u.points }}</div>
          </div>
          <div class="f-acts">
            <button class="msg-btn sm" data-tip="私信" @click="openChat(u.other_public_id || u.other_id || u.id)">✉️</button>
            <button v-if="!u.is_me" class="follow-btn sm" :class="{ on: u.is_following }" @click="toggle(u)">{{ u.is_following ? '已关注' : '+ 关注' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

const router = useRouter()
const auth = useAuthStore()
const tab = ref('following')
const following = ref([])
const followers = ref([])
const q = ref('')
const results = ref([])
const searched = ref(false)

const meId = () => auth.user?.id

const load = async () => {
  if (!auth.isLogin) { router.push('/login'); return }
  try {
    const [f1, f2] = await Promise.all([
      api.get('/users/' + meId() + '/following'),
      api.get('/users/' + meId() + '/followers'),
    ])
    following.value = f1.data
    followers.value = f2.data
  } catch (e) { /* 忽略 */ }
}

const switchTab = (t) => { tab.value = t; if (t !== 'discover') load() }

const search = async () => {
  const kw = q.value.trim()
  if (!kw) { ElMessage.warning('请输入关键词'); return }
  try {
    const res = await api.get('/users/search?q=' + encodeURIComponent(kw))
    results.value = res.data
    searched.value = true
  } catch (e) { ElMessage.error(e.response?.data?.error || '搜索失败') }
}

const toggle = async (u) => {
  try {
    const res = await api.post('/follows/toggle', { user_id: u.id })
    u.is_following = res.data.following
    if (!u.is_following && tab.value === 'following') {
      following.value = following.value.filter(x => x.id !== u.id)
    }
  } catch (e) { ElMessage.error(e.response?.data?.error || '操作失败') }
}

const goUser = (id) => { router.push('/user/' + id) }
const openChat = (id) => { router.push('/messages?with=' + id) }

onMounted(load)
</script>

<style scoped>
.friends-page { max-width: 720px; margin: 0 auto; padding: 92px 18px 60px; }
.page-title { font-size: 24px; font-weight: 800; color: var(--text1); margin: 0 0 18px; }
.f-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.f-tab {
  padding: 8px 18px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 13px; transition: all .18s;
}
.f-tab.on {
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; border-color: transparent; font-weight: 600;
}
.f-list { display: flex; flex-direction: column; gap: 10px; }
.f-acts { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.msg-btn {
  padding: 6px 12px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 13px; transition: all .18s; flex-shrink: 0;
}
.msg-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.f-row {
  display: flex; align-items: center; gap: 14px; padding: 12px 14px;
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 14px; transition: border-color .18s;
}
.f-row:hover { border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.f-avatar {
  width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0; cursor: pointer;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 17px;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.f-avatar img { width: 100%; height: 100%; object-fit: cover; }
.f-info { flex: 1; min-width: 0; cursor: pointer; }
.f-name { font-size: 14px; font-weight: 700; color: var(--text1); }
.f-id { font-size: 12px; color: var(--text2); margin-top: 3px; }
.follow-btn {
  padding: 6px 18px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--brand-1); background: transparent; color: var(--brand-1);
  font-size: 12.5px; font-weight: 600; transition: all .18s; flex-shrink: 0;
}
.follow-btn:hover { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.follow-btn.on {
  background: color-mix(in srgb, var(--brand-1) 16%, transparent);
  color: var(--brand-1);
  border-color: color-mix(in srgb, var(--brand-1) 42%, transparent);
}
.f-search .search-row { display: flex; gap: 10px; margin-bottom: 16px; }
.search-input {
  flex: 1; padding: 10px 16px; border-radius: 12px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 13.5px; outline: none; transition: border-color .18s;
}
.search-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.search-btn {
  padding: 10px 22px; border-radius: 12px; cursor: pointer;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 13.5px; font-weight: 600; border: none; transition: opacity .18s;
}
.search-btn:hover { opacity: .88; }
.center.empty { text-align: center; color: var(--text2); font-size: 13px; padding: 40px 0; }
</style>
