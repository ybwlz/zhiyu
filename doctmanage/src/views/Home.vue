<template>
  <div class="kb-home" :data-theme="themeState.id">
    <!-- 鼠标跟随光晕 -->
    <div class="mouse-glow" :style="mouseGlowStyle"></div>


    <div class="kb-content">

      <main class="kb-main">
        <!-- ═══════ Hero ═══════ -->
        <section class="kb-hero" id="top">
          <div class="hero-inner">
            <p class="hero-kicker">{{ site.kicker }}</p>
            <h1 class="hero-title">{{ site.name }}<span class="hero-title-accent">· 个人知识库</span></h1>
            <p class="hero-tagline">{{ site.tagline }}</p>
            <p class="hero-desc">{{ site.desc }}</p>

            <!-- 全局搜索 -->
            <div class="hero-search">
              <span class="search-icon">🔍</span>
              <input
                v-model="searchQuery"
                class="search-input"
                type="text"
                :placeholder="search.placeholder"
                @keyup.enter="doSearch"
              />
              <button class="search-btn" type="button" @click="doSearch">检索</button>
            </div>

            <!-- 登录用户今日概览 -->
            <div v-if="auth.isLogin && today" class="today-strip">
              <span class="ts-item">⏱ 今日阅读 <b>{{ today.today_read_min }}</b> 分钟</span>
              <span class="ts-item">🤖 AI 已用 <b>{{ today.ai_used }}</b>/{{ today.ai_quota }} 次</span>
              <span class="ts-item">🪙 积分 <b>{{ today.points }}</b></span>
              <router-link to="/mall" class="ts-link">去商城 →</router-link>
            </div>
            <!-- 统计 -->
            <div class="hero-stats">
              <CountUp :to="stats.docs" label="篇笔记" />
              <CountUp :to="stats.subjects" label="个科目" />
              <CountUp :to="stats.types" label="个分类" />
              <CountUp :to="stats.days" label="天持续积累" />
            </div>
          </div>
        </section>

        <!-- ═══════ 精选笔记轮播 ═══════ -->
        <SpotlightCarousel :docs="recentDocs" />

        <!-- ═══════ 科目横移区（下滑横向漫游） ═══════ -->
        <section ref="subjectsWrapRef" class="kb-subjects">
          <div class="subjects-sticky">
            <div class="subjects-layout">
              <div class="subjects-copy">
                <p class="section-kicker">SUBJECTS</p>
                <h2 class="section-title">科目<span class="grad">图谱</span></h2>
                <p class="section-desc">408 统考 · 数学 · 英语 · 政治。继续向下滚动，横向漫游你的知识版图。</p>
                <div class="subjects-progress">
                  <div class="progress-fill" :style="{ width: (subjectsProgress * 100) + '%' }"></div>
                </div>
                <p class="subjects-hint">↓ 滚动开始横向探索</p>
              </div>

              <div class="subjects-viewport">
                <div ref="subjectsTrackRef" class="subjects-track" :style="{ transform: `translate3d(${subjectsTranslate}px,0,0)` }">
                  <template v-for="group in subjects" :key="group.group">
                    <div class="subject-card" v-for="card in group.cards" :key="card.name" :style="{ '--accent': card.accent }" @click="goSubject(card.name)">
                      <div class="subject-card-head">
                        <span class="subject-emoji">{{ card.emoji }}</span>
                        <span class="subject-group">{{ group.group }}</span>
                        <span v-if="subjectCount(card.name) > 0" class="subject-count">{{ subjectCount(card.name) }} 篇</span>
                      </div>
                      <h3 class="subject-name">{{ card.name }}</h3>
                      <p class="subject-desc">{{ card.desc }}</p>
                      <div class="subject-foot">
                        <span class="subject-go">进入科目 →</span>
                      </div>
                      <span class="subject-shine"></span>
                    </div>
                  </template>

                  <div class="subject-card subject-more" @click="router.push('/docs')">
                    <div class="subject-emoji">🧭</div>
                    <h3 class="subject-name">全部文档</h3>
                    <p class="subject-desc">浏览知识库中的所有笔记，按分类快速定位。</p>
                    <div class="subject-foot"><span class="subject-go">前往阅览室 →</span></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════ 功能特性 ═══════ -->
        <section class="kb-features">
          <div class="container">
            <p class="section-kicker">CAPABILITIES</p>
            <h2 class="section-title">能力<span class="grad">版图</span></h2>
            <p class="section-desc">全部核心能力已就绪——点卡片直达使用。</p>

            <div class="feature-grid">
              <div class="feature-card" v-for="feat in features" :key="feat.title" :class="{ 'is-ai': feat.title === 'AI 助手' }" @click="onFeatureClick(feat)">
                <div class="feature-icon">{{ feat.icon }}</div>
                <div class="feature-title-row">
                  <h3 class="feature-title">{{ feat.title }}</h3>
                  <span class="feature-tag">{{ feat.tag }}</span>
                </div>
                <p class="feature-desc">{{ feat.desc }}</p>
                <div class="feature-arrow">→</div>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════ 社区数据（匿名统计，不公开个人行为） ═══════ -->
        <section class="kb-feed">
          <div class="container">
            <p class="section-kicker">COMMUNITY</p>
            <h2 class="section-title">社区<span class="grad">数据</span></h2>
            <p class="section-desc">知屿正在生长的足迹——只统计总量，不公开任何个人行为。</p>

            <div class="feed-stats">
              <div class="feed-stat">
                <b>{{ communityStats.notes }}</b><span>篇笔记</span>
              </div>
              <div class="feed-stat">
                <b>{{ communityStats.likes }}</b><span>次点赞</span>
              </div>
              <div class="feed-stat">
                <b>{{ communityStats.favorites }}</b><span>次收藏</span>
              </div>
              <div class="feed-stat">
                <b>{{ communityStats.comments }}</b><span>条评论</span>
              </div>
              <div class="feed-stat">
                <b>{{ communityStats.downloads }}</b><span>次下载</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════ 最近更新 ═══════ -->
        <section class="kb-recent">
          <div class="container">
            <p class="section-kicker">RECENT</p>
            <h2 class="section-title">最近<span class="grad">更新</span></h2>
            <p class="section-desc">知识库最新收录与修订的笔记。</p>

            <div v-if="loading" class="recent-empty">加载中…</div>
            <div v-else-if="recentDocs.length === 0" class="recent-empty">还没有笔记，去「管理后台」上传第一篇吧 📤</div>
            <div v-else class="recent-list">
              <div class="recent-item" v-for="doc in recentDocs" :key="doc.id" @click="goDoc(doc)">
                <span class="recent-type">{{ doc.type }}</span>
                <span class="recent-title">{{ doc.title }}</span>
                <span class="recent-time">{{ fmtDate(doc.updated_at || doc.created_at) }}</span>
                <span class="recent-arrow">→</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ═══════ 底部 ═══════ -->
        <footer class="kb-footer">
          <div class="footer-inner">
            <span class="footer-brand">✦ {{ site.fullName }}</span>
            <span class="footer-tip">用 知屿 沉淀每一份知识 ✨</span>
          </div>
        </footer>
      </main>
    </div>

    <!-- AI 助手浮窗 -->

  </div>
</template>
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { kbConfig } from '@/constants/homeConfig.js'
import { themeState } from '@/utils/theme.js'
import { useFileListStore } from '@/stores/fileList.js'
import { storeToRefs } from 'pinia'


import SpotlightCarousel from '@/components/SpotlightCarousel.vue'
import CountUp from '@/components/CountUp.vue'

const router = useRouter()
const { site, search, subjects, features } = kbConfig



// ── 鼠标跟随光晕 ───────────────────────────────────────────
const mouse = ref({ x: -400, y: -400 })
const mouseGlowStyle = computed(() => ({ transform: `translate3d(${mouse.value.x}px, ${mouse.value.y}px, 0)` }))
const onMouseMove = (e) => {
  mouse.value.x = e.clientX
  mouse.value.y = e.clientY
}

// ── 数据 ───────────────────────────────────────────────────
const store = useFileListStore()
const { fileListData, typesData, loading } = storeToRefs(store)
const aiOpen = ref(false)
const searchQuery = ref('')

// ── 科目笔记数 ──
const subjectCount = (name) => {
  if (!Array.isArray(fileListData.value)) return 0
  return fileListData.value.filter(d => d.type === name).length
}
// ── 登录用户今日概览（仅本人可见自己的数据） ──
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'
const auth = useAuthStore()
const today = ref(null)
const loadToday = async () => {
  if (!auth.isLogin) return
  try {
    const res = await api.get('/user/today')
    today.value = res.data
  } catch (e) { /* 忽略 */ }
}
// ── 社区数据（匿名聚合统计，不暴露个人行为） ──
const communityStats = computed(() => {
  const all = Array.isArray(fileListData.value) ? fileListData.value : []
  const sum = (k) => all.reduce((a, d) => a + (Number(d[k]) || 0), 0)
  return {
    notes: all.length,
    likes: sum('likes_count'),
    favorites: sum('favorites_count'),
    comments: sum('comments_count'),
    downloads: sum('downloads_count'),
  }
})

onMounted(() => {
  store.fetchDocs()
  loadToday()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  onScroll()
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('mousemove', onMouseMove)
})

// ── 统计（数字滚动） ───────────────────────────────────────
const stats = computed(() => {
  const docs = Array.isArray(fileListData.value) ? fileListData.value : []
  const types = Array.isArray(typesData.value) ? typesData.value : []
  const subjCount = subjects.reduce((n, g) => n + g.cards.length, 0)
  // 知识库已积累天数：取最早一篇文档创建时间算起
  let days = 1
  if (docs.length > 0) {
    const dates = docs.map((d) => d.created_at || d.updated_at).filter(Boolean).map((s) => new Date(s.replace(' ', 'T')).getTime()).filter(Number.isFinite)
    if (dates.length > 0) {
      days = Math.max(1, Math.floor((Date.now() - Math.min(...dates)) / 86400000))
    }
  }
  return { docs: docs.length, subjects: subjCount, types: types.length, days }
})

// ── 最近更新 ───────────────────────────────────────────────
const recentDocs = computed(() => {
  const docs = Array.isArray(fileListData.value) ? [...fileListData.value] : []
  return docs
    .sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''))
    .slice(0, 6)
})

const fmtDate = (s) => (s || '').slice(0, 10)

// ── 跳转 ───────────────────────────────────────────────────
const doSearch = async () => {
  const q = searchQuery.value.trim()
  // 搜索结果统一去笔记广场展示（带搜索词过滤），让用户自己挑选
  router.push({ path: '/notes', query: q ? { search: q } : {} })
}
const goSubject = (name) => router.push({ path: '/notes', query: { type: name } })
const goDoc = (doc) => router.push(`/docs/${doc.slug}`)

const onFeatureClick = (feat) => {
  if (feat.title === 'AI 助手') { aiOpen.value = true; return }
  if (feat.title === '上传 PDF / Markdown') { router.push('/admin'); return }
  if (feat.title === '全文检索') { document.querySelector('.search-input')?.focus(); return }
  // 图片转笔记：下一阶段由 AI 处理，先打开助手
  aiOpen.value = true
}

// ── 科目横向漫游（下滑驱动 translateX） ───────────────────
const subjectsWrapRef = ref(null)
const subjectsTrackRef = ref(null)
const subjectsTranslate = ref(0)
const subjectsProgress = ref(0)

const onScroll = () => {
  const wrap = subjectsWrapRef.value
  if (!wrap) return
  const total = wrap.offsetHeight - window.innerHeight
  if (total <= 0) return
  let p = -wrap.getBoundingClientRect().top / total
  p = Math.min(1, Math.max(0, p))
  subjectsProgress.value = p
  const track = subjectsTrackRef.value
  const viewport = wrap.querySelector('.subjects-viewport')
  if (track && viewport) {
    const maxX = Math.max(0, track.scrollWidth - viewport.clientWidth)
    subjectsTranslate.value = -p * maxX
  }
}
</script>
<style scoped>
.kb-home {
  position: relative;
  min-height: 100vh;
  color: var(--text1);
  transition: color .4s ease, background .4s ease;
}
.kb-content {
  position: relative;
  z-index: 1;
}

/* 主题背景淡入淡出 */
.bg-fade-enter-active, .bg-fade-leave-active { transition: opacity 0.45s ease; }
.bg-fade-enter-from, .bg-fade-leave-to { opacity: 0; }

/* 鼠标跟随光晕：即时跟手（无长过渡），位于内容之上、导航之下 */
.mouse-glow {
  position: fixed;
  top: 0;
  left: 0;
  width: 340px;
  height: 340px;
  margin: -170px 0 0 -170px;
  border-radius: 50%;
  pointer-events: none;
  z-index: 40;
  background: radial-gradient(circle, color-mix(in srgb, var(--brand-1) 18%, transparent) 0%, color-mix(in srgb, var(--brand-2) 9%, transparent) 45%, transparent 68%);
  filter: blur(14px);
  opacity: 0.9;
  transform: translate3d(0, 0, 0);
  will-change: transform;
}

/* ═══════════ 导航栏 ═══════════ */
.kb-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  background: color-mix(in srgb, var(--bg) 55%, transparent);
  border-bottom: 1px solid transparent;
  transition: border-color .3s ease, background .3s ease;
}
.kb-nav.scrolled {
  border-bottom-color: var(--border);
  background: color-mix(in srgb, var(--bg) 82%, transparent);
}
.nav-inner {
  max-width: var(--layout-max-width);
  margin: 0 auto;
  padding: 0 var(--layout-padding);
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  font-size: 16px;
  box-shadow: 0 4px 14px color-mix(in srgb, var(--brand-1) 45%, transparent);
}
.nav-links { display: flex; gap: 22px; }
.nav-link {
  font-size: 14px;
  font-weight: 500;
  color: var(--text2);
  text-decoration: none;
  transition: color .2s;
  position: relative;
  padding: 4px 0;
}
.nav-link:hover, .nav-link.active { color: var(--text1); }
.nav-link.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
}

.theme-switcher {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  background: var(--btn-bg);
  border: 1px solid var(--border);
}
.theme-opt {
  display: flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: transparent;
  color: var(--text2);
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
  transition: all .2s;
}
.theme-opt:hover { color: var(--text1); }
.theme-opt.active {
  background: var(--card-bg);
  color: var(--text1);
  box-shadow: 0 2px 10px color-mix(in srgb, var(--brand-1) 25%, transparent);
  border: 1px solid var(--border);
  padding: 5px 11px;
}
.theme-icon { font-size: 14px; line-height: 1; }
.theme-label { font-weight: 500; }

/* ═══════════ Hero ═══════════ */
.kb-hero {
  min-height: calc(100vh - 40px);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 96px 24px 40px;
}
.hero-inner { max-width: 860px; }
.hero-kicker {
  font-size: 13px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--brand-1);
  font-weight: 600;
  margin-bottom: 18px;
}
.hero-title {
  font-size: clamp(44px, 7vw, 76px);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.02em;
  margin: 0 0 18px;
  color: var(--text1);
}
/* 仅"个人知识库"渐变色：缓缓流动（14s 一个来回） */
.hero-title-accent {
  background: var(--kb-grad);
  background-size: 260% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.hero-tagline {
  font-size: clamp(17px, 2.4vw, 22px);
  color: var(--text1);
  font-weight: 600;
  margin: 0 0 10px;
}
.hero-desc { color: var(--text2); font-size: 15px; margin: 0 0 34px; }

.hero-search {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 560px;
  margin: 0 auto 36px;
  padding: 8px 8px 8px 18px;
  border-radius: 999px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(10px);
  transition: border-color .25s, box-shadow .25s;
}
.hero-search:focus-within {
  border-color: var(--brand-1);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--brand-1) 14%, transparent), var(--shadow-1);
}
.search-icon { font-size: 16px; }
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 15px;
  color: var(--text1);
}
.search-input::placeholder { color: var(--text2); }
.search-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 22px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  transition: opacity .2s, transform .2s;
}
.search-btn:hover { opacity: .9; transform: translateY(-1px); }

.today-strip {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 18px;
  margin: 18px auto 0; padding: 12px 22px;
  max-width: 640px; border-radius: 999px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  font-size: 13px; color: var(--text2);
}
.ts-item b { color: var(--brand-1); font-size: 14px; }
.ts-link {
  color: #fff; text-decoration: none;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  padding: 5px 14px; border-radius: 999px; font-size: 12.5px;
}
.hero-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  max-width: 640px;
  margin: 0 auto;
  padding: 26px 20px;
  border-radius: 22px;
  background: color-mix(in srgb, var(--card-bg) 72%, transparent);
  border: 1px solid var(--border);
  backdrop-filter: blur(12px);
}

/* ═══════════ 科目横向漫游 ═══════════ */
.kb-subjects {
  position: relative;
  height: 280vh;
}
.subjects-sticky {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  align-items: center;
  overflow: hidden;
}
.subjects-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 44px;
  align-items: center;
  width: 100%;
  padding: 0 6vw;
}
.subjects-copy { padding-left: 2vw; }
.section-kicker {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--brand-1);
  font-weight: 700;
  margin: 0 0 10px;
}
.section-title {
  font-size: clamp(30px, 4vw, 48px);
  font-weight: 800;
  line-height: 1.12;
  margin: 0 0 14px;
}
.grad {
  background: var(--kb-grad);
  background-size: 260% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.section-desc { color: var(--text2); font-size: 15px; line-height: 1.8; margin: 0; max-width: 460px; }
.subjects-progress {
  margin-top: 28px;
  width: 180px;
  height: 4px;
  border-radius: 4px;
  background: var(--btn-bg);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
  transition: width .1s linear;
}
.subjects-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text2);
}

.subjects-viewport {
  overflow: hidden;
  mask-image: linear-gradient(90deg, transparent 0, #000 5%, #000 96%, transparent 100%);
}
.subjects-track {
  display: flex;
  gap: 20px;
  width: max-content;
  will-change: transform;
}

.subject-card {
  position: relative;
  width: 292px;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  padding: 26px 24px 22px;
  border-radius: 26px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(10px);
  cursor: pointer;
  overflow: hidden;
  transition: transform .35s ease, border-color .35s ease, box-shadow .35s ease;
}
.subject-card:hover {
  transform: translateY(-8px);
  border-color: color-mix(in srgb, var(--accent, var(--brand-1)) 55%, var(--border));
  box-shadow: 0 26px 60px color-mix(in srgb, var(--accent, var(--brand-1)) 22%, transparent);
}
.subject-count {
  margin-left: auto;
  font-size: 11px; font-weight: 600;
  color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 25%, transparent);
  padding: 2px 9px; border-radius: 999px;
}
.subject-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
}
.subject-emoji {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--accent, var(--brand-1)) 14%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
}
.subject-group {
  font-size: 12px;
  color: var(--text2);
  background: var(--btn-bg);
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: 999px;
}
.subject-name { font-size: 21px; font-weight: 700; margin: 0 0 10px; }
.subject-desc { font-size: 14px; color: var(--text2); line-height: 1.7; margin: 0; flex: 1; }
.subject-foot { margin-top: 20px; }
.subject-go {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent, var(--brand-1));
}
.subject-card:hover .subject-go::after { content: ' →'; }
.subject-more {
  border-style: dashed;
  justify-content: center;
  text-align: center;
  align-items: center;
}
.subject-more .subject-name { margin-top: 14px; }
.subject-shine {
  position: absolute;
  top: -60%;
  left: -30%;
  width: 60%;
  height: 180%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.06), transparent);
  transform: rotate(24deg);
  transition: left .6s ease;
}
.subject-card:hover .subject-shine { left: 130%; }

/* ═══════════ 功能特性 ═══════════ */
.kb-features, .kb-feed {
  padding: 60px 0 20px;
}
.feed-stats {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}
.feed-stat {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 22px 10px;
  border-radius: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  transition: transform .2s, border-color .2s;
}
.feed-stat:hover { transform: translateY(-3px); border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.feed-stat b {
  font-size: 30px; font-weight: 800; line-height: 1;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.feed-stat span { font-size: 12.5px; color: var(--text2); }
@media (max-width: 720px) {
  .feed-stats { grid-template-columns: repeat(2, 1fr); }
}

.kb-recent {
  padding: 80px 0 56px;
}
.container {
  max-width: var(--layout-max-width);
  margin: 0 auto;
  padding: 0 var(--layout-padding);
}
.kb-features .section-desc, .kb-recent .section-desc { margin-bottom: 40px; }

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}
.feature-card {
  position: relative;
  padding: 24px;
  border-radius: 22px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  cursor: pointer;
  transition: transform .3s ease, border-color .3s ease, box-shadow .3s ease;
  overflow: hidden;
}
.feature-card:hover {
  transform: translateY(-5px);
  border-color: color-mix(in srgb, var(--brand-1) 45%, var(--border));
  box-shadow: 0 20px 46px color-mix(in srgb, var(--brand-1) 16%, transparent);
}
.feature-card.is-ai {
  border: 1px solid color-mix(in srgb, var(--brand-2) 55%, var(--border));
  background: linear-gradient(150deg, color-mix(in srgb, var(--brand-1) 10%, var(--card-bg)), var(--card-bg));
}
.feature-icon { font-size: 30px; margin-bottom: 14px; }
.feature-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.feature-title { font-size: 17px; font-weight: 700; margin: 0; }
.feature-tag {
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 999px;
  white-space: nowrap;
  background: color-mix(in srgb, #10b981 14%, transparent);
  color: #10b981;
  border: 1px solid color-mix(in srgb, #10b981 32%, transparent);
}
.feature-desc { font-size: 13.5px; color: var(--text2); line-height: 1.7; margin: 0; }
.feature-arrow {
  position: absolute;
  right: 18px;
  bottom: 14px;
  color: var(--text2);
  opacity: 0;
  transform: translateX(-6px);
  transition: all .25s;
}
.feature-card:hover .feature-arrow { opacity: 1; transform: translateX(0); color: var(--brand-1); }

/* ═══════════ 最近更新 ═══════════ */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.recent-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 15px 20px;
  border-radius: 16px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all .25s;
}
.recent-item:hover {
  border-color: color-mix(in srgb, var(--brand-1) 45%, var(--border));
  transform: translateX(5px);
  box-shadow: var(--shadow-1);
}
.recent-type {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 28%, transparent);
  padding: 4px 12px;
  border-radius: 999px;
  min-width: 74px;
  text-align: center;
}
.recent-title { flex: 1; font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-time { font-size: 13px; color: var(--text2); flex-shrink: 0; }
.recent-arrow { color: var(--text2); transition: all .2s; }
.recent-item:hover .recent-arrow { color: var(--brand-1); transform: translateX(3px); }
.recent-empty {
  padding: 40px;
  text-align: center;
  color: var(--text2);
  border: 1px dashed var(--border);
  border-radius: 18px;
}

/* ═══════════ 页脚 ═══════════ */
.kb-footer {
  padding: 36px 0 96px;
}
.footer-inner {
  max-width: var(--layout-max-width);
  margin: 0 auto;
  padding: 20px var(--layout-padding);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  border-top: 1px solid var(--border);
}
.footer-brand { font-weight: 600; font-size: 14px; }
.footer-tip { color: var(--text2); font-size: 13px; }

/* ═══════════ 响应式 ═══════════ */
@media (max-width: 1024px) {
  .subjects-layout { grid-template-columns: 1fr; gap: 24px; }
  .subjects-copy { padding-left: 0; }
  .subjects-viewport { width: 100%; }
  .feature-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 720px) {
  .nav-links { display: none; }
  .theme-label { display: none; }
  .today-strip {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 18px;
  margin: 18px auto 0; padding: 12px 22px;
  max-width: 640px; border-radius: 999px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  font-size: 13px; color: var(--text2);
}
.ts-item b { color: var(--brand-1); font-size: 14px; }
.ts-link {
  color: #fff; text-decoration: none;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  padding: 5px 14px; border-radius: 999px; font-size: 12.5px;
}
.hero-stats { grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .feature-grid { grid-template-columns: 1fr; }
  .subject-card { width: 258px; min-height: 330px; }
  .recent-time { display: none; }
}
@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}
</style>