<!-- 服务条款 / 隐私协议（PC 端独立页面，移动端由登录页弹窗承载） -->
<template>
  <div class="legal-page">
    <div class="legal-container">
      <p class="legal-kicker">{{ isTerms ? 'TERMS OF SERVICE' : 'PRIVACY POLICY' }}</p>
      <h1 class="legal-title">{{ isTerms ? '知屿 · 服务条款' : '知屿 · 隐私协议' }}</h1>
      <p class="legal-meta">最后更新：2026-08-12 · 适用于知屿全部服务</p>

      <div class="legal-body">
        <section v-for="sec in sections" :key="sec.title" class="legal-sec">
          <h2 class="legal-sec-title">{{ sec.title }}</h2>
          <p v-for="(p, i) in sec.paras" :key="i" class="legal-para" :class="{ 'is-bold': p.includes('加粗') || i === 0 }">{{ p }}</p>
        </section>
      </div>

      <div class="legal-back">
        <router-link to="/login" class="legal-back-btn">← 返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { TERMS_SECTIONS, PRIVACY_SECTIONS } from '@/constants/legal.js'

const route = useRoute()
const isTerms = computed(() => route.path === '/terms')
const sections = computed(() => (isTerms.value ? TERMS_SECTIONS : PRIVACY_SECTIONS))
</script>

<style scoped>
.legal-page {
  min-height: 100vh;
  padding: 100px 24px 60px;
  box-sizing: border-box;
}
.legal-container {
  max-width: 760px;
  margin: 0 auto;
}
.legal-kicker {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--brand-1);
  font-weight: 700;
  margin: 0 0 10px;
}
.legal-title {
  font-size: 32px;
  font-weight: 800;
  color: var(--text1);
  margin: 0 0 8px;
}
.legal-meta {
  font-size: 13px;
  color: var(--text2);
  margin: 0 0 30px;
}
.legal-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.legal-sec {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 24px 26px;
  box-shadow: var(--shadow-1);
}
.legal-sec-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text1);
  margin: 0 0 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.legal-para {
  font-size: 14px;
  line-height: 1.85;
  color: var(--text2);
  margin: 0 0 12px;
}
.legal-para:last-child { margin-bottom: 0; }
.legal-para.is-bold { color: var(--text1); }
.legal-back {
  margin-top: 28px;
  text-align: center;
}
.legal-back-btn {
  display: inline-block;
  padding: 10px 26px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  color: var(--text2);
  text-decoration: none;
  font-size: 14px;
  transition: all .25s;
}
.legal-back-btn:hover {
  color: var(--brand-1);
  border-color: color-mix(in srgb, var(--brand-1) 45%, var(--border));
}
</style>
