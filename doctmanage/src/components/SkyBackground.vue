<!-- 蓝天大气主题背景：天空渐变 + 太阳 + 漂浮云朵 + 柔和光晕 -->
<template>
  <div class="sky-backdrop" aria-hidden="true">
    <div class="sun"></div>
    <div class="sky-glow glow-left"></div>
    <div class="sky-glow glow-right"></div>
    <div class="cloud cloud-1"></div>
    <div class="cloud cloud-2"></div>
    <div class="cloud cloud-3"></div>
    <div class="cloud cloud-4"></div>
    <div class="haze"></div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.sky-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 75% -10%, rgba(255, 255, 255, 0.9), transparent 45%),
    linear-gradient(180deg, #a5d8ff 0%, #c9e9ff 34%, #e9f5ff 68%, #f4f9fe 100%);
}

.sun {
  position: absolute;
  top: -60px;
  right: 8%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 220, 0.95), rgba(255, 236, 170, 0.55) 45%, transparent 70%);
  filter: blur(6px);
  box-shadow: 0 0 90px 30px rgba(255, 236, 170, 0.4);
}

.sky-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
}
.glow-left {
  width: 520px;
  height: 520px;
  left: -180px;
  top: 30%;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.22), transparent 70%);
}
.glow-right {
  width: 480px;
  height: 480px;
  right: -160px;
  top: 46%;
  background: radial-gradient(circle, rgba(129, 140, 248, 0.16), transparent 70%);
}

/* CSS 云朵 */
.cloud {
  position: absolute;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  filter: blur(1px);
  box-shadow: 0 18px 40px rgba(90, 140, 190, 0.12);
}
.cloud::before,
.cloud::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  background: inherit;
}
.cloud-1 {
  width: 220px;
  height: 56px;
  top: 14%;
  left: -120px;
  animation: cloud-move 60s linear infinite;
}
.cloud-1::before { width: 90px; height: 90px; top: -44px; left: 40px; }
.cloud-1::after { width: 120px; height: 120px; top: -70px; left: 90px; }

.cloud-2 {
  width: 180px;
  height: 46px;
  top: 26%;
  left: -140px;
  opacity: 0.75;
  animation: cloud-move 78s linear infinite 10s;
}
.cloud-2::before { width: 80px; height: 80px; top: -40px; left: 30px; }
.cloud-2::after { width: 100px; height: 100px; top: -62px; left: 75px; }

.cloud-3 {
  width: 260px;
  height: 62px;
  top: 8%;
  right: -160px;
  opacity: 0.7;
  animation: cloud-move 96s linear infinite 30s;
}
.cloud-3::before { width: 110px; height: 110px; top: -52px; left: 45px; }
.cloud-3::after { width: 140px; height: 140px; top: -82px; left: 105px; }

.cloud-4 {
  width: 160px;
  height: 40px;
  top: 38%;
  right: -120px;
  opacity: 0.6;
  animation: cloud-move 66s linear infinite 20s;
}
.cloud-4::before { width: 70px; height: 70px; top: -36px; left: 28px; }
.cloud-4::after { width: 90px; height: 90px; top: -56px; left: 66px; }

/* 底部柔和雾层，让内容区过渡自然 */
.haze {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -60px;
  height: 320px;
  background: linear-gradient(180deg, transparent, rgba(244, 249, 254, 0.95));
}

@keyframes cloud-move {
  from { transform: translateX(0); }
  to { transform: translateX(calc(100vw + 300px)); }
}
</style>