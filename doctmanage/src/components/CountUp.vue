<!-- 数字滚动组件：进入视口后从 0 递增到目标值 -->
<template>
  <div ref="elRef" class="kb-stat">
    <span class="stat-num">{{ display }}<span v-if="suffix" class="stat-suffix">{{ suffix }}</span></span>
    <span class="stat-label">{{ label }}</span>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  to: { type: Number, default: 0 },
  label: { type: String, default: '' },
  suffix: { type: String, default: '' },
})

const elRef = ref(null)
const display = ref(0)
let raf = null
let started = false

const start = (force = false) => {
  if (started && !force) return
  started = true
  cancelAnimationFrame(raf)
  const from = display.value
  const target = Math.max(0, props.to)
  const t0 = performance.now()
  const dur = 1100
  const tick = (t) => {
    const p = Math.min(1, (t - t0) / dur)
    const ease = 1 - Math.pow(1 - p, 3)
    display.value = Math.round(from + (target - from) * ease)
    if (p < 1) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

// 数据异步到达（to 变化）时重新动画
watch(() => props.to, (v) => { if (v > 0) start(true) })

onMounted(() => {
  if (!('IntersectionObserver' in window)) { start(); return }
  const io = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) { start(); io.disconnect() }
  }, { threshold: 0.4 })
  io.observe(elRef.value)
})

onUnmounted(() => cancelAnimationFrame(raf))
</script>

<style scoped>
.kb-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px 0;
}
.stat-num {
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
  background: var(--kb-grad);
  background-size: 260% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-variant-numeric: tabular-nums;
  animation: stat-flow 10s ease-in-out infinite alternate;
}
.stat-suffix { font-size: 16px; margin-left: 2px; }
.stat-label {
  font-size: 13px;
  color: var(--text2);
}
@keyframes stat-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}
</style>