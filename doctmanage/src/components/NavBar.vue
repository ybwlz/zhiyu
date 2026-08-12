<!-- 全局导航栏：品牌在左、导航链接居中、右侧管理后台(同款样式) + 主题下拉；无边框无阴影 -->
<template>
  <nav ref="navBarRoot" class="kb-navbar">
    <div class="nav-inner">
      <router-link class="nav-brand" to="/">
        <span class="brand-mark">
          <svg viewBox="0 0 64 64" width="26" height="26" aria-hidden="true">
            <path d="M31 7 C 37 7, 39 11, 34 16
                     A 10 10 0 0 0 34 36
                     A 16 16 0 0 0 34 58
                     A 16 16 0 0 0 34 26"
                  fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="brand-name">知屿</span>
      </router-link>

      <!-- 居中导航：五个页面入口 -->
      <div class="nav-links">
        <router-link
          v-for="link in links"
          :key="link.label"
          class="nav-link"
          :class="{ active: isNavActive(link) }"
          :to="link.to"
        >{{ link.label }}</router-link>
      </div>

      <div class="nav-right" :class="{ 'logged-out': !auth.isLogin }">
        <!-- 移动端汉堡菜单 -->
        <button class="nav-burger" data-tip="菜单" data-tip-align="right" @click="menuOpen = !menuOpen">☰</button>
        <!-- 主题下拉 -->
        <ThemeDropdown />
        <!-- 消息通知铃铛（登录后） -->
        <router-link v-if="auth.isLogin" to="/messages" class="msg-link" data-tip="私信" data-tip-align="right">
          <svg class="msg-svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3C6.5 3 2 6.9 2 11.7c0 2.6 1.3 4.9 3.4 6.5-.1 1.2-.5 2.3-1.2 3.2-.2.3 0 .6.3.6 1.9 0 3.6-.7 4.8-1.5 1 .2 1.8.3 2.7.3 5.5 0 10-3.9 10-8.7S17.5 3 12 3z"/></svg>
        </router-link>
        <div v-if="auth.isLogin" ref="bellWrap" class="bell-wrap">
          <button class="bell-btn" :class="{ has: unread > 0 }" data-tip="消息通知" data-tip-align="right" @click="toggleBell">
            <svg class="bell-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
            <span v-if="unread > 0" class="bell-dot">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
          <Transition name="bell-panel">
            <div v-if="bellOpen" class="bell-panel">
              <div class="bell-head">
                <span class="bell-title">消息通知</span>
                <button class="bell-readall" @click="readAll">全部已读</button>
              </div>
              <div v-if="notifications.length === 0" class="bell-empty">暂无消息</div>
              <div
                v-for="n in notifications" :key="n.id"
                class="bell-item"
                :class="{ unread: !n.is_read }"
                @click="openNoti(n)"
                @contextmenu.prevent="delNoti(n)"
              >
                <span class="bell-icon">{{ notiIcon(n.type) }}</span>
                <span class="bell-text">{{ notiText(n) }}</span>
                <span class="bell-time">{{ n.created_at?.slice(5, 16) }}</span>
                <button class="bell-del" data-tip="删除" @click.stop="delNoti(n)">✕</button>
                <div v-if="n.type === 'digest' && expandedDigest === n.id" class="bell-digest">{{ n.extra }}</div>
              </div>
            </div>
          </Transition>
        </div>
        <!-- 个人主页头像（登录后） -->
        <router-link v-if="auth.isLogin && auth.user" class="me-link" :to="'/user/' + (auth.user.public_id || auth.user.id)" data-tip="个人主页">
          <img v-if="auth.user.avatar" class="me-avatar" :src="auth.user.avatar" alt="avatar" />
          <span v-else class="me-avatar">{{ (auth.user.nickname || auth.user.username || '?').slice(0, 1) }}</span>
        </router-link>
        <!-- 登录 / 书房：未登录显示登录入口，已登录进入书房（管理） -->
        <router-link v-if="!auth.isLogin" class="nav-link admin-link" to="/login" active-class="active">登录</router-link>
        <router-link v-else class="nav-link admin-link" to="/admin" active-class="active">书房</router-link>
      </div>
    </div>
    <!-- 移动端菜单面板 -->
    <Transition name="bell-panel">
      <div v-if="menuOpen" class="nav-mobile-menu">
        <router-link v-for="link in links" :key="link.label" class="mm-link" :to="link.to" :class="{ active: isNavActive(link) }" @click="menuOpen = false">{{ link.label }}</router-link>
        <router-link v-if="auth.isLogin" class="mm-link" to="/admin" @click="menuOpen = false">书房</router-link>
        <router-link v-if="auth.isLogin" class="mm-link" to="/friends" @click="menuOpen = false">关注</router-link>
        <router-link v-if="auth.isLogin" class="mm-link" to="/messages" @click="menuOpen = false">私信</router-link>
        <router-link v-if="auth.isLogin" class="mm-link" to="/mall" @click="menuOpen = false">商城</router-link>
        <router-link v-if="auth.isLogin" class="mm-link" to="/settings" @click="menuOpen = false">设置</router-link>
      </div>
    </Transition>
  </nav>
</template>

<script setup>
import ThemeDropdown from '@/components/ThemeDropdown.vue'
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'

import api from '@/utils/api.js'

const auth = useAuthStore()
const route = useRoute()

// 导航高亮：vue-router 内置 active 要求 name 相等，带参数子路由（如 /docs/:key）会让父入口（/docs）不亮。
// 改为按路径匹配：exact 项（首页）精确匹配，其余前缀匹配。
const isNavActive = (link) => {
  const p = route.path
  if (link.exact) return p === link.to
  const to = String(link.to).replace(/\/$/, '')
  return p === to || p.startsWith(to + '/')
}

const bellOpen = ref(false)
const menuOpen = ref(false)

// ── 易收起：点击外部 / 滚轮滚动时自动收起所有下拉（与主题下拉同款逻辑） ──
const bellWrap = ref(null)
const navBarRoot = ref(null)
const onAnyOutside = (e) => {
  if (navBarRoot.value && !navBarRoot.value.contains(e.target)) {
    bellOpen.value = false
    menuOpen.value = false
    return
  }
  if (bellWrap.value && !bellWrap.value.contains(e.target) && !e.target.closest('.bell-btn')) bellOpen.value = false
  if (!e.target.closest('.nav-burger') && !e.target.closest('.nav-mobile-menu')) menuOpen.value = false
}
const onAnyWheel = () => { bellOpen.value = false; menuOpen.value = false }
const unread = ref(0)
const notifications = ref([])

const loadNoti = async () => {
  if (!auth.isLogin) return
  try {
    const res = await api.get('/notifications')
    notifications.value = res.data.list
    unread.value = res.data.unread
  } catch (e) { /* 忽略 */ }
}
const toggleBell = async () => {
  bellOpen.value = !bellOpen.value
  if (bellOpen.value) loadNoti()
}
const readAll = async () => {
  try { await api.post('/notifications/read') } catch (e) { /* 忽略 */ }
  unread.value = 0
  notifications.value.forEach(n => (n.is_read = 1))
}
const expandedDigest = ref(null)
const delNoti = async (n) => {
  try { await api.delete('/notifications/' + n.id) } catch (e) { /* 忽略 */ }
  notifications.value = notifications.value.filter(x => x.id !== n.id)
  if (!n.is_read) unread.value = Math.max(0, unread.value - 1)
}
const openNoti = async (n) => {
  if (!n.is_read) {
    try { await api.post('/notifications/read', { id: n.id }) } catch (e) { /* 忽略 */ }
    n.is_read = 1
    unread.value = Math.max(0, unread.value - 1)
  }
  // 每日摘要：面板内展开文字，不跳转
  if (n.type === 'digest') {
    expandedDigest.value = expandedDigest.value === n.id ? null : n.id
    return
  }
  bellOpen.value = false
  if (n.type === 'message') { window.location.href = '/zhiyu/messages?with=' + (n.actor_public_id || n.actor_id); return }
  if (n.doc_id) window.location.href = '/zhiyu/notes/' + (n.public_id || n.doc_id) + '?focus=' + n.type
  else if (n.type === 'friend_request') window.location.href = '/zhiyu/friends'
  else if (n.actor_id) window.location.href = '/zhiyu/user/' + (n.actor_public_id || n.actor_id)
}
const notiIcon = (t) => ({ like: '👍', favorite: '⭐', comment: '💬', friend_request: '👋', digest: '🤖', message: '✉️' }[t] || '🔔')
const notiText = (n) => {
  if (n.type === 'digest') return '每日摘要'
  const who = n.nickname || n.username || '有人'
  const t = {
    like: `点赞了你的笔记「${(n.doc_title || '').slice(0, 12)}」`,
    favorite: `收藏了你的笔记「${(n.doc_title || '').slice(0, 12)}」`,
    comment: `评论了你的笔记「${(n.doc_title || '').slice(0, 12)}」`,
    friend_request: '请求添加你为好友',
    message: '给你发来一条私信',
  }[n.type]
  return who + ' ' + (t || '有新动态')
}

// 登录后定时刷新未读数（60s）
let notiTimer = null
onMounted(() => { loadNoti(); notiTimer = setInterval(loadNoti, 60000) })
onMounted(() => {
  document.addEventListener('click', onAnyOutside)
  document.addEventListener('wheel', onAnyWheel, { passive: true })
})
onBeforeUnmount(() => clearInterval(notiTimer))
onBeforeUnmount(() => {
  document.removeEventListener('click', onAnyOutside)
  document.removeEventListener('wheel', onAnyWheel)
})

const links = [
  { to: '/', label: '首页', exact: true },
  { to: '/docs', label: '阅览室' },
  { to: '/notes', label: '笔记广场' },
  { to: '/guide', label: '使用引导' },
  { to: '/activity', label: '修改记录' },
  { to: '/changelog', label: '更新日志' },
]
</script>

<style scoped>
.kb-navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  /* 极淡蒙版：不加 blur，只保留顶部渐变过渡，让导航有轻微底色但无"蒙版条"感 */
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--bg) 72%, transparent) 0%,
    color-mix(in srgb, var(--bg) 32%, transparent) 46px,
    color-mix(in srgb, var(--bg) 8%, transparent) 100%
  );
}
.nav-inner {
  max-width: var(--layout-max-width);
  margin: 0 auto;
  padding: 0 var(--layout-padding);
  height: 60px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--text1);
  font-weight: 700;
  font-size: 17px;
  flex-shrink: 0;
}
.brand-mark {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--brand-1) 45%, transparent);
}

/* 居中导航 */
.nav-links {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 4px;
}

/* 链接统一样式：文字 + hover 高亮 + 当前页渐变下划线 */
.nav-link {
  position: relative;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text2);
  text-decoration: none;
  padding: 8px 14px;
  border-radius: 10px;
  white-space: nowrap;
  transition: color .25s, background .25s;
}
.nav-link:hover {
  color: var(--text1);
  background: color-mix(in srgb, var(--text1) 7%, transparent);
}
.nav-link.active {
  color: var(--text1);
  font-weight: 600;
}
.nav-link.active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 5px;
  height: 2.5px;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
/* 管理后台与导航链接同款（模组颜色） */
.admin-link {
  font-weight: 500;
}

.bell-wrap { position: relative; }
.msg-link {
  position: relative;
  width: 32px; height: 32px;
  border-radius: 50%;
  background: var(--btn-bg);
  border: 1px solid var(--border);
  color: var(--text2);
  display: inline-flex; align-items: center; justify-content: center;
  transition: transform .2s, color .2s, border-color .2s;
  text-decoration: none;
}
.msg-link:hover { transform: scale(1.1); color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 50%, transparent); }
.msg-svg { width: 17px; height: 17px; }
.bell-btn {
  position: relative;
  width: 32px; height: 32px;
  border: none; border-radius: 50%;
  background: var(--btn-bg);
  border: 1px solid var(--border);
  font-size: 15px; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: transform .2s;
}
.bell-btn:hover { transform: scale(1.1); }
.bell-btn.has { border-color: color-mix(in srgb, var(--brand-1) 50%, transparent); }
.bell-dot {
  position: absolute; top: -4px; right: -4px;
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: 999px;
  background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.bell-panel {
  position: absolute; top: 42px; right: -60px;
  width: 320px; max-height: 380px; overflow-y: auto;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-1);
  z-index: 300;
}
.bell-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--bg-soft);
}
.bell-title { font-size: 14px; font-weight: 700; color: var(--text1); }
.bell-readall {
  border: none; background: none;
  color: var(--brand-1); font-size: 12px; cursor: pointer;
}
.bell-empty { padding: 30px 0; text-align: center; color: var(--text2); font-size: 13px; }
.bell-item {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 16px;
  cursor: pointer;
  transition: background .15s;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
}
.bell-item:hover { background: color-mix(in srgb, var(--brand-1) 6%, transparent); }
.bell-item.unread { background: color-mix(in srgb, var(--brand-1) 4%, transparent); }
.bell-item.unread::before {
  content: '●'; font-size: 9px; color: var(--brand-1); flex-shrink: 0;
}
.bell-icon { font-size: 16px; flex-shrink: 0; }
.bell-text {
  flex: 1; font-size: 13px; color: var(--text1);
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.bell-time { font-size: 11px; color: var(--text2); flex-shrink: 0; }
/* 单条删除按钮（右侧 ✕，hover 变红） */
.bell-del {
  flex-shrink: 0;
  width: 20px; height: 20px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 50%;
  background: transparent;
  color: var(--text2);
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s, background .15s, color .15s;
}
.bell-item:hover .bell-del { opacity: 1; }
.bell-del:hover { background: color-mix(in srgb, var(--danger, #e5484d) 12%, transparent); color: var(--danger, #e5484d); }
.bell-panel-enter-active, .bell-panel-leave-active { transition: opacity .18s ease, transform .18s ease; }
.bell-panel-enter-from, .bell-panel-leave-to { opacity: 0; transform: translateY(-6px); }

.me-link { text-decoration: none; }
.me-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 13px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
  border: 2px solid var(--bg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  transition: transform .2s;
  overflow: hidden;
}
.me-avatar img { width: 100%; height: 100%; object-fit: cover; }
.me-link:hover .me-avatar { transform: scale(1.08); }

@media (max-width: 900px) {
  .nav-links { display: none; }
  /* 移动端：去掉书房/登录文字按钮（入口已收进汉堡菜单） */
  .nav-right .admin-link { display: none !important; }
  /* 移动端重排：nav-right 占满剩余宽度——主题+通知+消息居中，头像+汉堡靠右贴边 */
  .nav-right { flex: 1; gap: 6px; }
  /* 导航内容占满视口（--layout-max-width 1152px 在手机端不适用，否则两侧 logo/头像被挤出视口） */
  .nav-inner { max-width: 100%; padding: 0 12px; }
  .nav-right .bell-wrap { order: 1; margin-left: auto; }
  .nav-right .kb-theme-wrap { order: 2; }
  .nav-right .msg-link { order: 3; }
  .nav-right .me-link { order: 4; margin-left: auto; }
  .nav-right .nav-burger { order: 5; }
  /* 未登录：主题居中，登录在主题右侧、汉堡菜单左侧，汉堡贴最右 */
  .nav-right.logged-out .kb-theme-wrap { order: 0; margin-left: auto; margin-right: auto; }
  .nav-right.logged-out .admin-link { display: inline-flex !important; align-items: center; order: 1; }
  .nav-right.logged-out .nav-burger { order: 2; }
  /* 通知按钮更小 */
  .nav-right .bell-btn { width: 26px; height: 26px; }
  .nav-right .bell-btn .bell-svg { width: 14px; height: 14px; }
  .nav-right .bell-dot { min-width: 13px; height: 13px; font-size: 9px; padding: 0 3px; }
  /* 头像与汉堡菜单靠右贴边 */
  .kb-navbar { padding-right: 8px; }
}
.nav-burger { display: none; background: none; border: none; color: var(--text2); font-size: 20px; cursor: pointer; padding: 4px 8px; }
.nav-mobile-menu { position: fixed; top: 56px; right: 12px; z-index: 130; min-width: 170px; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 14px; padding: 8px; box-shadow: var(--shadow-1); display: flex; flex-direction: column; }
.mm-link { padding: 10px 16px; border-radius: 10px; color: var(--text2); text-decoration: none; font-size: 14px; }
.mm-link:hover, .mm-link.active { color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 8%, transparent); }
@media (max-width: 900px) {
  .nav-burger { display: inline-block; }
}.bell-digest { grid-column: 1 / -1; margin: 2px 0 4px; padding: 10px 12px; background: var(--btn-bg); border: 1px solid var(--border); border-radius: 10px; font-size: 12.5px; color: var(--text1); line-height: 1.7; white-space: pre-wrap; }</style>