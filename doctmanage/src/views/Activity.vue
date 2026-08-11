<!-- 修改记录：笔记库最近的上传/更新明细（按更新时间倒序） -->
<template>
  <div class="activity-page">
    <div class="page-header">
      <p class="kicker">ACTIVITY</p>
      <h1 class="title">修改<span class="grad">记录</span></h1>
      <p class="desc">你在书房的笔记更新明细（仅本人可见），共 {{ total }} 条。</p>
    </div>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-if="typeOptions.length > 1" class="act-filters">
      <button class="af-chip" :class="{ on: typeFilter === '' }" @click="typeFilter = ''">全部</button>
      <button v-for="t in typeOptions" :key="t" class="af-chip" :class="{ on: typeFilter === t }" @click="typeFilter = t">{{ t }}</button>
    </div>
    <div v-if="!auth.isLogin" class="empty">
      登录后查看<b>你自己的</b>修改记录
      <button class="login-btn" @click="router.push('/login')">去登录 →</button>
    </div>
    <div v-else-if="!loading && filteredRecords.length === 0" class="empty">你还没有修改记录，去书房创建第一篇吧 ✍️</div>
    <div v-if="!loading && filteredRecords.length > 0" class="act-list">
      <div class="act-day" v-for="day in grouped" :key="day.label">
        <p class="day-label">{{ day.label }} <span class="day-count">{{ day.items.length }} 条</span></p>
        <div class="day-items">
          <div class="act-item" v-for="r in day.items" :key="r.id" @click="goDoc(r.slug)">
            <span class="act-type" :style="{ color: r.color, borderColor: r.color + '55', background: r.color + '14' }">{{ r.type }}</span>
            <span class="act-title">{{ r.title }}</span>
            <span class="act-action">更新</span>
            <span class="act-time">{{ fmtTime(r.updated_at || r.created_at) }}</span>
            <span class="act-arrow">→</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const mineDocs = ref([])
const loadMine = async () => {
  loading.value = true
  try {
    const res = await api.get('/docs?scope=mine&t=' + Date.now())
    mineDocs.value = res.data || []
  } catch (e) { mineDocs.value = [] }
  loading.value = false
}
onMounted(() => { if (auth.isLogin) loadMine(); else loading.value = false })

const TYPE_COLORS = {
  高等数学: '#ec4899',
  中学公式: '#f59e0b',
  线性代数: '#6366f1',
  概率论: '#14b8a6',
  数据结构: '#10b981',
  计算机组成原理: '#0ea5e9',
  操作系统: '#8b5cf6',
  计算机网络: '#f59e0b',
  英语: '#3b82f6',
  政治: '#ef4444',
}

const records = computed(() => {
  const docs = mineDocs.value || []
  return docs
    .map((d) => ({ id: d.id, type: d.type, title: d.title, slug: d.slug, updated_at: d.updated_at || d.created_at, color: TYPE_COLORS[d.type] || '#3b82f6' }))
    .sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
    .slice(0, 60)
})

const typeFilter = ref('')
const typeOptions = computed(() => [...new Set(records.value.map(r => r.type).filter(Boolean))])
const filteredRecords = computed(() => typeFilter.value ? records.value.filter(r => r.type === typeFilter.value) : records.value)
const total = computed(() => filteredRecords.value.length)

const fmtDay = (s) => {
  const d = (s || '').slice(0, 10)
  const today = new Date().toISOString().slice(0, 10)
  const yest = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  if (d === today) return '今天'
  if (d === yest) return '昨天'
  return d
}
const fmtTime = (s) => (s || '').slice(0, 16).replace('T', ' ')

const grouped = computed(() => {
  const map = new Map()
  filteredRecords.value.forEach((r) => {
    const k = fmtDay(r.updated_at)
    if (!map.has(k)) map.set(k, [])
    map.get(k).push(r)
  })
  return Array.from(map.entries()).map(([label, items]) => ({ label, items }))
})

const goDoc = (slug) => { if (slug) router.push(`/docs/${slug}`) }


</script>

<style scoped>
.act-filters { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 0 0 22px; }
.af-chip {
  padding: 6px 16px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 12.5px;
  transition: all .2s;
}
.af-chip:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.af-chip.on {
  color: #fff; border-color: transparent;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
}
.activity-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 110px 28px 70px;
  min-height: calc(100vh - 60px);
  box-sizing: border-box;
}
.page-header { text-align: center; margin-bottom: 40px; }
.kicker {
  font-size: 12px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--brand-1); font-weight: 700; margin: 0 0 10px;
}
.title { font-size: clamp(30px, 4vw, 46px); font-weight: 800; margin: 0 0 12px; }
.grad {
  background: var(--kb-grad); background-size: 260% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.desc { color: var(--text2); font-size: 15px; margin: 0; }

.act-list { display: flex; flex-direction: column; gap: 26px; }
.act-day { }
.day-label {
  font-size: 13px; font-weight: 700; color: var(--text1);
  margin: 0 0 10px;
  display: flex; align-items: center; gap: 8px;
}
.day-count { font-size: 12px; color: var(--text2); font-weight: 400; }
.day-items {
  display: flex; flex-direction: column; gap: 8px;
  border-left: 2px solid var(--border);
  padding-left: 18px;
  margin-left: 4px;
}
.act-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  border-radius: 14px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all .25s;
}
.act-item:hover {
  border-color: color-mix(in srgb, var(--brand-1) 40%, var(--border));
  transform: translateX(4px);
  box-shadow: var(--shadow-1);
}
.act-type {
  flex-shrink: 0;
  font-size: 11.5px;
  padding: 4px 11px;
  border-radius: 999px;
  border: 1px solid;
  min-width: 70px;
  text-align: center;
}
.act-title { flex: 1; font-size: 14.5px; font-weight: 500; color: var(--text1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.act-action { flex-shrink: 0; font-size: 11.5px; color: #10b981; background: rgba(16, 185, 129, .12); padding: 3px 9px; border-radius: 999px; }
.act-time { flex-shrink: 0; font-size: 12.5px; color: var(--text2); }
.act-arrow { color: var(--text2); }
.act-item:hover .act-arrow { color: var(--brand-1); transform: translateX(2px); }

.empty { text-align: center; padding: 80px 0; min-height: 40vh; display: flex; align-items: center; justify-content: center; color: var(--text2); border: 1px dashed var(--border); border-radius: 16px; }

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}
.login-btn { margin-left: 10px; padding: 6px 18px; border-radius: 999px; border: none; cursor: pointer; color: #fff; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); font-size: 13px; }</style>