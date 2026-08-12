<!-- 最近更新：笔记较多时双行反向跑马灯（第一行向右、第二行向左，持续滚动不因悬停暂停），少时垂直列表 -->
<template>
  <div v-if="docs.length >= 8" class="recent-marquee">
    <div class="marquee-row">
      <div class="marquee-track track-right" :style="{ animationDuration: marqueeDur(row1) }">
        <div class="marquee-item" v-for="(doc, i) in doubled(row1)" :key="doc.id + '-r1-' + i" :style="marqueeCardStyle(i)" @click="goDoc(doc)">
          <span class="marquee-type">{{ doc.type }}</span>
          <span class="marquee-emoji">{{ marqueeEmoji(doc.type) }}</span>
          <h3 class="marquee-title">{{ doc.title }}</h3>
          <p class="marquee-desc">{{ marqueeExcerpt(doc) }}</p>
          <span class="marquee-date">{{ fmtDate(doc.updated_at || doc.created_at) }}</span>
        </div>
      </div>
    </div>
    <div class="marquee-row">
      <div class="marquee-track track-left" :style="{ animationDuration: marqueeDur(row2) }">
        <div class="marquee-item" v-for="(doc, i) in doubled(row2)" :key="doc.id + '-r2-' + i" :style="marqueeCardStyle(i)" @click="goDoc(doc)">
          <span class="marquee-type">{{ doc.type }}</span>
          <span class="marquee-emoji">{{ marqueeEmoji(doc.type) }}</span>
          <h3 class="marquee-title">{{ doc.title }}</h3>
          <p class="marquee-desc">{{ marqueeExcerpt(doc) }}</p>
          <span class="marquee-date">{{ fmtDate(doc.updated_at || doc.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="recent-list">
    <div class="recent-item" v-for="doc in docs" :key="doc.id" @click="goDoc(doc)">
      <span class="recent-type">{{ doc.type }}</span>
      <span class="recent-title">{{ doc.title }}</span>
      <span class="recent-time">{{ fmtDate(doc.updated_at || doc.created_at) }}</span>
      <span class="recent-arrow">→</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { cleanText } from '@/utils/mdText.js'

const props = defineProps({ docs: { type: Array, default: () => [] } })
const router = useRouter()

// 交错拆成两行（第一行 0,2,4… 第二行 1,3,5…），滚动更均匀
const row1 = computed(() => props.docs.filter((_, i) => i % 2 === 0))
const row2 = computed(() => props.docs.filter((_, i) => i % 2 === 1))
// 无缝循环：每行渲染两份（动画位移 50% 恰好一份宽度）
const doubled = (arr) => [...arr, ...arr]
// 滚动速度随卡片数自适应（偏慢，持续滚动）
const marqueeDur = (arr) => Math.max(30, arr.length * 7) + 's'

const TYPE_EMOJI = {
  高等数学: '∫', 中学公式: '∑', 线性代数: '🧮', 概率论: '🎲', 数据结构: '🌳',
  计算机组成原理: '⚙️', 操作系统: '🛠️', 计算机网络: '🌐', 英语: '🔤', 政治: '📜',
}
const marqueeEmoji = (type) => TYPE_EMOJI[type] || '📄'
const PALETTES = [
  ['#0ea5e9', '#6366f1'], ['#8b5cf6', '#ec4899'], ['#10b981', '#38bdf8'],
  ['#f59e0b', '#ef4444'], ['#ec4899', '#8b5cf6'],
]
const marqueeCardStyle = (i) => {
  const [c1, c2] = PALETTES[i % PALETTES.length]
  return { '--c1': c1, '--c2': c2 }
}
const marqueeExcerpt = (doc) => {
  const t = cleanText(doc.content)
  return t ? t.slice(0, 50) + '…' : '点击进入阅读完整内容'
}
const fmtDate = (s) => (s || '').slice(0, 10)
const goDoc = (doc) => router.push(`/docs/${doc.public_id}`)
</script>

<style scoped>
/* ── 双行反向跑马灯 ── */
.recent-marquee {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: hidden;
}
.marquee-row {
  overflow: hidden;
  /* 左右淡出遮罩，滚动进出更柔和 */
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent);
}
.marquee-track {
  display: flex;
  gap: 14px;
  width: max-content;
  will-change: transform;
}
.track-left  { animation-name: marquee-left;  animation-timing-function: linear; animation-iteration-count: infinite; }
.track-right { animation-name: marquee-right; animation-timing-function: linear; animation-iteration-count: infinite; }
/* 第二行向左：0 → -50%（一份内容宽度），无缝循环 */
@keyframes marquee-left  { from { transform: translateX(0); }    to { transform: translateX(-50%); } }
/* 第一行向右：从 -50% → 0，视觉上向右移动 */
@keyframes marquee-right { from { transform: translateX(-50%); } to { transform: translateX(0); } }
.marquee-item {
  flex-shrink: 0;
  position: relative;
  width: 300px;
  height: 185px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 22px 22px 18px;
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  /* 与精选笔记卡片同款渐变底 */
  background:
    radial-gradient(120% 90% at 85% -10%, color-mix(in srgb, var(--c1) 30%, transparent), transparent 55%),
    radial-gradient(110% 100% at 10% 110%, color-mix(in srgb, var(--c2) 26%, transparent), transparent 55%),
    var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.14);
  transition: border-color .25s, transform .25s, box-shadow .25s;
}
.marquee-item:hover {
  border-color: color-mix(in srgb, var(--brand-1) 45%, var(--border));
  transform: translateY(-3px);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.18);
}
.marquee-type {
  align-self: flex-start;
  font-size: 12px;
  color: var(--c1);
  background: color-mix(in srgb, var(--c1) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--c1) 35%, transparent);
  padding: 3px 11px;
  border-radius: 999px;
}
.marquee-emoji {
  position: absolute;
  right: 18px;
  top: 12px;
  font-size: 64px;
  font-weight: 800;
  opacity: 0.14;
  line-height: 1;
  user-select: none;
  pointer-events: none;
}
.marquee-title {
  font-size: 17px;
  font-weight: 700;
  margin: 16px 0 8px;
  color: var(--text1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.marquee-desc {
  flex: 1;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text2);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.marquee-date {
  font-size: 12px;
  color: var(--text2);
  margin-top: 10px;
}

/* ── 少量数据：垂直列表 ── */
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
</style>
