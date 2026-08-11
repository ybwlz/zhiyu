<template>
  <div class="nf-page">
    <div class="nf-card">
      <div class="nf-code">4<span class="nf-zero">0</span>4</div>
      <h2 class="nf-title">这片星域还没有笔记 ✨</h2>
      <p class="nf-desc">你访问的页面不存在，可能已被移动或删除。</p>
      <div class="nf-actions">
        <button class="nf-btn primary" @click="router.push('/')">🏠 返回首页</button>
        <button class="nf-btn" @click="router.push('/notes')">📚 逛逛笔记广场</button>
        <button class="nf-btn" @click="router.push('/docs')">📖 前往阅览室</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.nf-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 100px 24px 60px;
  box-sizing: border-box;
}
.nf-card {
  text-align: center;
  max-width: 520px;
  padding: 56px 44px;
  border-radius: 24px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
}
.nf-code {
  font-size: 88px; font-weight: 900; line-height: 1;
  letter-spacing: 4px;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 18px;
}
.nf-zero {
  display: inline-block;
  background: linear-gradient(120deg, var(--brand-2), var(--brand-1));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: nf-float 2.6s ease-in-out infinite;
}
@keyframes nf-float {
  0%, 100% { transform: translateY(0) rotate(-4deg); }
  50% { transform: translateY(-14px) rotate(4deg); }
}
.nf-title { font-size: 20px; font-weight: 700; color: var(--text1); margin: 0 0 10px; }
.nf-desc { font-size: 13.5px; color: var(--text2); margin: 0 0 30px; }
.nf-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.nf-btn {
  padding: 10px 20px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border);
  background: var(--btn-bg); color: var(--text2);
  font-size: 13.5px;
  transition: all .2s;
}
.nf-btn:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); transform: translateY(-2px); }
.nf-btn.primary {
  color: #fff; border-color: transparent;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
}
@media (max-width: 520px) {
  .nf-card { padding: 40px 24px; }
  .nf-code { font-size: 64px; }
}
</style>