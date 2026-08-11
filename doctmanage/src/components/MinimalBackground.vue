<!-- 纯色简约主题背景：素净底色 + 极淡网格 + 一点柔和光晕 -->
<template>
  <div class="minimal-backdrop" aria-hidden="true">
    <div class="m-glow m-glow-1"></div>
    <div class="m-glow m-glow-2"></div>
    <div class="m-dots"></div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.minimal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
  background: linear-gradient(180deg, #fdfdfd 0%, #f7f7f8 100%);
}

.m-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
}
.m-glow-1 {
  width: 420px;
  height: 420px;
  right: -140px;
  top: -120px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.07), transparent 70%);
}
.m-glow-2 {
  width: 380px;
  height: 380px;
  left: -120px;
  bottom: -100px;
  background: radial-gradient(circle, rgba(100, 116, 139, 0.06), transparent 70%);
}

.m-dots {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, rgba(30, 30, 30, 0.055) 1px, transparent 1px);
  background-size: 26px 26px;
}
</style>