<!-- 深空星际主题背景：星空图 + canvas 闪烁星点 + 星云光晕 + 一闪而过的流星 -->
<template>
  <div class="starfield-backdrop" aria-hidden="true">
    <!-- orbit-site 同款星云背景图（浅透明） -->
    <div class="space-img" :style="{ backgroundImage: 'url(' + spaceBg + ')' }"></div>

    <canvas ref="canvasRef" class="stars-canvas"></canvas>
    <div class="nebula nebula-1"></div>
    <div class="nebula nebula-2"></div>
    <div class="nebula nebula-3"></div>
    <div class="aurora aurora-1"></div>
    <div class="aurora aurora-2"></div>

    <!-- 流星：同一时刻只有一颗，从左往右一闪而过划过屏幕 -->
    <div
      v-if="meteor"
      :key="meteor.id"
      class="meteor"
      :style="{
        left: meteor.x,
        top: meteor.y + '%',
        '--dist': meteor.dist,
        '--rot': meteor.rot,
        '--dur': meteor.dur + 's',
      }"
    ></div>

    <div class="mesh-grid"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import spaceBg from '@/assets/space-bg.jpg'

const canvasRef = ref(null)
let raf = null
let ctx = null
let stars = []

// ── 流星：同一时刻只有一颗，从左往右一闪而过划过屏幕 ──
// 用 setTimeout 链调度：划完 → 随机停顿 → 换随机轨迹再来一颗
const meteor = ref(null)
let meteorId = 0
let meteorTimer = null

const fireMeteor = () => {
  const w = window.innerWidth
  const h = window.innerHeight
  meteorId += 1
  // 整体沿斜线斜飞（3~6° 小角度，向右上）：拖尾方向 = 移动方向，整条流星线沿斜线划过屏幕
  // 左侧屏幕外滑入 → 贯穿整个屏幕 → 右侧屏幕外滑出
  const deg = 3 + Math.random() * 3
  meteor.value = {
    id: meteorId,
    x: '-280px',                          // left：整颗（含 240px 拖尾）完全在左屏幕外
    y: 25 + Math.random() * 30,           // top：中高空（25% ~ 55%），小角度上飘不会出顶
    dist: Math.round(w + 520) + 'px',     // 沿斜线贯穿到右屏幕外（头部+拖尾全部滑出）
    rot: (-deg) + 'deg',                  // 3~6° 右上斜飞角，位移沿该角度方向
    dur: 1.5 + Math.random() * 1.0,       // 1.5~2.5s 横穿全程（比之前慢约 20%）
  }
}

const scheduleMeteor = (delay) => {
  meteorTimer = setTimeout(() => {
    fireMeteor()
    // 划过时长 + 短暂停顿后再来下一颗（保证一次只有一颗）
    scheduleMeteor(meteor.value.dur * 1000 + 1800 + Math.random() * 3200)
  }, delay)
}

function buildStars() {
  stars = Array.from({ length: 170 }, () => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    r: 0.4 + Math.random() * 1.3,
    base: 0.25 + Math.random() * 0.75,
    speed: 0.4 + Math.random() * 1.2,
    phase: Math.random() * Math.PI * 2,
  }))
}

function resize() {
  const c = canvasRef.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  c.width = c.clientWidth * dpr
  c.height = c.clientHeight * dpr
  ctx = c.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function draw(t) {
  if (!ctx) return
  const w = canvasRef.value.clientWidth
  const h = canvasRef.value.clientHeight
  ctx.clearRect(0, 0, w, h)
  const time = t / 1000
  for (const s of stars) {
    const alpha = s.base * (0.55 + 0.45 * Math.sin(time * s.speed + s.phase))
    const x = (s.x / 100) * w
    const y = (s.y / 100) * h
    ctx.beginPath()
    ctx.arc(x, y, s.r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(3)})`
    ctx.fill()
  }
  raf = requestAnimationFrame(draw)
}

onMounted(() => {
  buildStars()
  resize()
  window.addEventListener('resize', resize)
  raf = requestAnimationFrame(draw)
  scheduleMeteor(2500 + Math.random() * 4000)  // 首颗在 2.5~6.5s 后出现
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  clearTimeout(meteorTimer)
  window.removeEventListener('resize', resize)
})
</script>

<style scoped>
.starfield-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 50% -10%, rgba(41, 66, 128, 0.55), transparent 55%),
    linear-gradient(180deg, #05080f 0%, #070b16 55%, #0a0f1f 100%);
}

/* orbit-site 同款星空背景图（浅透明浮层） */
.space-img {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0.26;
}

.stars-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.nebula {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
}
.nebula-1 {
  width: 560px;
  height: 560px;
  left: -160px;
  top: 12%;
  background: radial-gradient(circle, rgba(0, 198, 255, 0.16), transparent 70%);
  animation: drift 26s ease-in-out infinite alternate;
}
.nebula-2 {
  width: 640px;
  height: 640px;
  right: -200px;
  top: 22%;
  background: radial-gradient(circle, rgba(227, 5, 247, 0.14), transparent 70%);
  animation: drift 32s ease-in-out infinite alternate-reverse;
}
.nebula-3 {
  width: 500px;
  height: 500px;
  left: 38%;
  bottom: -180px;
  background: radial-gradient(circle, rgba(65, 150, 255, 0.12), transparent 70%);
  animation: drift 40s ease-in-out infinite alternate;
}

.aurora {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  mix-blend-mode: screen;
}
.aurora-1 {
  width: 420px;
  height: 120px;
  left: 8%;
  top: -60px;
  background: linear-gradient(90deg, transparent, rgba(0, 230, 200, 0.14), transparent);
  transform: rotate(-8deg);
}
.aurora-2 {
  width: 520px;
  height: 140px;
  right: 4%;
  top: -80px;
  background: linear-gradient(90deg, transparent, rgba(150, 120, 255, 0.16), transparent);
  transform: rotate(6deg);
}

/* ── 流星：水滴状亮头 + 长亮拖尾 + 辉光照亮周围，随飞行距离渐暗，沿 3~6° 斜线划过 ── */
.meteor {
  position: absolute;
  width: 340px;
  height: 3px;
  border-radius: 999px;
  /* 左端=拖尾（透明）→ 右端=头部（最亮），随元素一起旋转成倾斜角 */
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.95) 62%, rgba(255, 190, 200, 1));
  filter: blur(0.4px);
  opacity: 0;
  animation: meteor-fly var(--dur) ease-out 1 forwards;
}
/* 水滴状头部：圆润大亮头 + 强暖光晕 */
.meteor::before {
  content: '';
  position: absolute;
  right: -7px;
  top: 50%;
  width: 17px;
  height: 17px;
  margin-top: -8.5px;
  border-radius: 55% 55% 45% 45%;
  background: radial-gradient(circle at 38% 32%, #fffef8, #ffd9a8 62%, #ffb47a);
  box-shadow:
    0 0 22px 6px rgba(255, 244, 214, 1),
    0 0 70px 22px rgba(255, 205, 175, 0.55);
}
/* 辉光层：照亮周围的宇宙空间（随动画整体衰减 = 随距离渐暗） */
.meteor::after {
  content: '';
  position: absolute;
  right: -70px;
  top: 50%;
  width: 150px;
  height: 150px;
  margin-top: -75px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 244, 214, 0.32) 0%, rgba(170, 210, 255, 0.16) 34%, transparent 68%);
  filter: blur(4px);
}
@keyframes meteor-fly {
  0% {
    /* rotate 前置 + translate3d 沿局部 x 轴：位移被旋转成斜线方向，整颗流星沿斜线飞 */
    transform: rotate(var(--rot)) translate3d(0, 0, 0);
    opacity: 0;
  }
  2% {
    transform: rotate(var(--rot)) translate3d(0, 0, 0);
    opacity: 1;
  }
  35% {
    opacity: 1; /* 中段最亮，照亮周围 */
  }
  100% {
    transform: rotate(var(--rot)) translate3d(var(--dist), 0, 0);
    opacity: 0; /* 随距离渐暗，辉光消散 */
  }
}

.mesh-grid {
  position: absolute;
  left: 10%;
  right: -18%;
  bottom: -40px;
  height: 440px;
  opacity: 0.14;
  background-image:
    linear-gradient(rgba(120, 150, 255, 0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120, 150, 255, 0.18) 1px, transparent 1px);
  background-size: 52px 52px;
  transform: perspective(1200px) rotateX(76deg);
  mask-image: linear-gradient(180deg, transparent 0%, rgba(0, 0, 0, 0.85) 32%, transparent 100%);
}

@keyframes drift {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(40px, -30px, 0) scale(1.08); }
}
</style>