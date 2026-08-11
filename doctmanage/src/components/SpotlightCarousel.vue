<!-- 精选笔记轮播：redbook 同款 3D 层叠卡片，左右箭头 / 点击切换，点中间卡片直达阅读 -->
<template>
  <section class="kb-spotlight">
    <div class="container">
      <p class="section-kicker">FEATURED</p>
      <h2 class="section-title">精选<span class="grad">笔记</span></h2>
      <p class="section-desc">最近收录的优质内容，点中间卡片直达阅读，点两侧卡片切换</p>

      <div class="spot-carousel">
        <button class="spot-nav spot-prev" type="button" aria-label="上一张" @click="shift(-1)">‹</button>

        <div class="spot-stage">
          <div
            v-for="(doc, i) in items"
            :key="doc.id"
            class="spot-card"
            :class="{ active: i === activeIndex, hidden: hiddenCards.has(i) }"
            :style="cardStyle(i)"
            @click="onCard(i)"
          >
            <div class="spot-card-inner">
              <span class="spot-type">{{ doc.type }}</span>
              <span class="spot-emoji">{{ emojiFor(doc.type) }}</span>
              <h3 class="spot-title">{{ doc.title }}</h3>
              <p class="spot-desc">{{ excerpt(doc) }}</p>
              <span class="spot-date">{{ fmtDate(doc.updated_at || doc.created_at) }}</span>
            </div>
          </div>
        </div>

        <button class="spot-nav spot-next" type="button" aria-label="下一张" @click="shift(1)">›</button>
      </div>

      <div class="spot-dots">
        <span
          v-for="(d, i) in items"
          :key="i"
          class="spot-dot"
          :class="{ on: i === activeIndex }"
          @click="activeIndex = i; resetAuto()"
        ></span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { cleanText } from '@/utils/mdText.js'

const props = defineProps({ docs: { type: Array, default: () => [] } })
const router = useRouter()
const activeIndex = ref(0)

const items = computed(() => (props.docs || []).slice(0, 5))

// ── 自动轮播：4s 自动切一张，持续轮播不因鼠标悬停暂停，交互后重新计时 ──
let autoTimer = null
const AUTO_MS = 2500
const startAuto = () => {
  stopAuto()
  if (items.value.length > 1) autoTimer = setInterval(() => shift(1), AUTO_MS)
}
const stopAuto = () => { clearInterval(autoTimer); autoTimer = null }
const resetAuto = () => { if (autoTimer) startAuto() }

onMounted(startAuto)
onUnmounted(stopAuto)

// 数据异步到达（docs 从空变多）后启动自动轮播
watch(() => items.value.length, (n) => {
  if (n > 1 && !autoTimer) startAuto()
})

const PALETTES = [
  ['#0ea5e9', '#6366f1'],
  ['#8b5cf6', '#ec4899'],
  ['#10b981', '#38bdf8'],
  ['#f59e0b', '#ef4444'],
  ['#ec4899', '#8b5cf6'],
]

const TYPE_EMOJI = {
  高等数学: '∫',
  中学公式: '∑',
  线性代数: '🧮',
  概率论: '🎲',
  数据结构: '🌳',
  计算机组成原理: '⚙️',
  操作系统: '🛠️',
  计算机网络: '🌐',
  英语: '🔤',
  政治: '📜',
}

const emojiFor = (type) => TYPE_EMOJI[type] || '📄'

const excerpt = (doc) => {
  const t = cleanText(doc.content)
  return t ? t.slice(0, 58) + '…' : '点击进入阅读完整内容'
}

const fmtDate = (s) => (s || '').slice(0, 10)

// 循环距离：-2..2
const diffOf = (i) => {
  const n = items.value.length
  if (n <= 1) return 0
  let d = i - activeIndex.value
  if (d > n / 2) d -= n
  if (d < -n / 2) d += n
  return d
}

const hiddenCards = computed(() => {
  const s = new Set()
  items.value.forEach((_, i) => { if (Math.abs(diffOf(i)) > 2) s.add(i) })
  return s
})

const cardStyle = (i) => {
  const d = diffOf(i)
  const abs = Math.abs(d)
  const [c1, c2] = PALETTES[i % PALETTES.length]
  return {
    transform: `translateX(${d * 56}%) scale(${1 - abs * 0.12})`,
    opacity: abs === 0 ? 1 : abs === 1 ? 0.62 : abs === 2 ? 0.3 : 0,
    zIndex: 10 - abs,
    '--c1': c1,
    '--c2': c2,
  }
}

const shift = (dir) => {
  const n = items.value.length
  if (n === 0) return
  activeIndex.value = (activeIndex.value + dir + n) % n
  resetAuto()
}

const onCard = (i) => {
  if (i === activeIndex.value) {
    const doc = items.value[i]
    if (doc && doc.public_id) router.push(`/docs/${doc.public_id}`)
  } else {
    activeIndex.value = i
    resetAuto()
  }
}
</script>

<style scoped>
.kb-spotlight {
  padding: 56px 0 20px;
}
.container {
  max-width: var(--layout-max-width);
  margin: 0 auto;
  padding: 0 var(--layout-padding);
}
.section-kicker {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--brand-1);
  font-weight: 700;
  margin: 0 0 10px;
}
.section-title {
  font-size: clamp(28px, 3.6vw, 44px);
  font-weight: 800;
  line-height: 1.12;
  margin: 0 0 12px;
}
.grad {
  background: var(--kb-grad);
  background-size: 260% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.section-desc {
  color: var(--text2);
  font-size: 15px;
  margin: 0 0 30px;
}

.spot-carousel {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
}
.spot-stage {
  position: relative;
  flex: 1;
  height: 340px;
}
.spot-card {
  position: absolute;
  top: 0;
  left: 50%;
  width: 320px;
  margin-left: -160px;
  height: 100%;
  border-radius: 24px;
  overflow: hidden;
  cursor: pointer;
  background:
    radial-gradient(120% 90% at 85% -10%, color-mix(in srgb, var(--c1) 30%, transparent), transparent 55%),
    radial-gradient(110% 100% at 10% 110%, color-mix(in srgb, var(--c2) 26%, transparent), transparent 55%),
    var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.22);
  transition: transform .55s cubic-bezier(.22, 1, .36, 1), opacity .45s ease;
  will-change: transform, opacity;
}
.spot-card.hidden { pointer-events: none; }
.spot-card-inner {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 26px 26px 22px;
  box-sizing: border-box;
}
.spot-type {
  align-self: flex-start;
  font-size: 12px;
  color: var(--c1);
  background: color-mix(in srgb, var(--c1) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--c1) 35%, transparent);
  padding: 4px 12px;
  border-radius: 999px;
}
.spot-emoji {
  position: absolute;
  right: 20px;
  top: 14px;
  font-size: 72px;
  font-weight: 800;
  opacity: 0.14;
  line-height: 1;
  user-select: none;
}
.spot-title {
  font-size: 22px;
  font-weight: 700;
  margin: 34px 0 12px;
  color: var(--text1);
}
.spot-desc {
  flex: 1;
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--text2);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.spot-date {
  font-size: 12.5px;
  color: var(--text2);
  margin-top: 14px;
}

.spot-nav {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text1);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  transition: all .25s;
  box-shadow: var(--shadow-1);
}
.spot-nav:hover {
  border-color: var(--brand-1);
  color: var(--brand-1);
  transform: scale(1.06);
}

.spot-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
}
.spot-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--border);
  cursor: pointer;
  transition: all .3s;
}
.spot-dot.on {
  width: 24px;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
}

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}

@media (max-width: 720px) {
  .spot-stage { height: 300px; }
  .spot-card { width: 240px; margin-left: -120px; }
  .spot-nav { display: none; }
}
</style>