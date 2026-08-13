<template>
  <div v-if="isElectron" class="wc-controls">
    <button class="wc-btn" title="最小化" aria-label="最小化" @click="minimize">
      <svg width="11" height="11" viewBox="0 0 11 11"><line x1="0.5" y1="5.5" x2="10.5" y2="5.5" stroke="currentColor" stroke-width="1.1" /></svg>
    </button>
    <button class="wc-btn" title="最大化/还原" aria-label="最大化" @click="maximize">
      <svg width="11" height="11" viewBox="0 0 11 11"><rect x="0.8" y="0.8" width="9.4" height="9.4" fill="none" stroke="currentColor" stroke-width="1.1" /></svg>
    </button>
    <button class="wc-btn wc-close" title="关闭" aria-label="关闭" @click="close">
      <svg width="11" height="11" viewBox="0 0 11 11"><line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" stroke-width="1.1" /><line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" stroke-width="1.1" /></svg>
    </button>
  </div>
</template>

<script setup>
const isElectron = typeof navigator !== 'undefined' && navigator.userAgent.includes('Electron')
const minimize = () => window.desktop?.windowControls?.minimize()
const maximize = () => window.desktop?.windowControls?.maximize()
const close = () => window.desktop?.windowControls?.close()
</script>

<style scoped>
/* 前端自绘窗口按钮：背景完全透明（融入导航栏/主题），跟随主题文字色 */
.wc-controls {
  position: fixed;
  top: 0;
  right: 0;
  height: 40px;
  display: flex;
  align-items: stretch;
  -webkit-app-region: no-drag;
  z-index: 2147483001;
}
.wc-btn {
  width: 46px;
  border: none;
  background: transparent;
  color: var(--text1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.wc-btn:hover {
  background: color-mix(in srgb, var(--text1) 13%, transparent);
}
.wc-btn:active {
  background: color-mix(in srgb, var(--text1) 22%, transparent);
}
.wc-close:hover {
  background: #e81123;
  color: #fff;
}
</style>
