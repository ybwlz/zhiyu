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

  <!-- 关闭确认弹窗（站内风格）：默认缩小到托盘，可勾选不再询问 -->
  <div v-if="isElectron && closeModal" class="modal-mask" @click.self="closeModal = false">
    <div class="modal">
      <div class="modal-head">
        <b>退出知屿？</b>
        <button class="modal-close" @click="closeModal = false">✕</button>
      </div>
      <div class="modal-body">
        <p class="modal-desc">关闭后知屿将缩小到系统托盘，仍在后台运行，随时可恢复。</p>
        <label class="dont-ask"><input type="checkbox" v-model="dontAsk" /> 不再询问（记住本次选择）</label>
      </div>
      <div class="modal-foot">
        <button class="ap-btn ghost" @click="doQuit">直接退出</button>
        <button class="ap-btn" @click="doHide">缩小到托盘</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const isElectron = typeof navigator !== 'undefined' && navigator.userAgent.includes('Electron')
const minimize = () => window.desktop?.windowControls?.minimize()
const maximize = () => window.desktop?.windowControls?.maximize()

const closeModal = ref(false)
const dontAsk = ref(false)
const STORE_KEY = 'zhiyu_close_action'

const close = () => {
  // 已记住选择：直接执行（默认缩小到托盘）
  const saved = localStorage.getItem(STORE_KEY)
  if (saved === 'hide') { window.desktop?.hideToTray?.(); return }
  if (saved === 'quit') { window.desktop?.quitApp?.(); return }
  closeModal.value = true
}
const remember = (act) => { if (dontAsk.value) localStorage.setItem(STORE_KEY, act) }
const doHide = () => { remember('hide'); closeModal.value = false; window.desktop?.hideToTray?.() }
const doQuit = () => { remember('quit'); closeModal.value = false; window.desktop?.quitApp?.() }
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
  z-index: 999;
}
.wc-btn {
  width: 46px;
  background: transparent;
  border: none;
  color: var(--text2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background .15s;
}
.wc-btn:hover { background: rgba(255,255,255,.08); color: var(--text1); }
.wc-close:hover { background: #e81123; color: #fff; }

/* ── 关闭确认弹窗（站内风格） ── */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .62);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(8px);
}
.modal {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 16px;
  width: 380px;
  max-width: 92vw;
  box-shadow: 0 24px 64px rgba(0, 0, 0, .35);
  overflow: hidden;
  -webkit-app-region: no-drag;
}
/* 弹窗背景必须不透明：主题玻璃变量是半透明的，会被深色遮罩透过来导致文字看不清 */
html[data-theme="starlight"] .modal { background: #0d1220; }
html[data-theme="sky"] .modal,
html[data-theme="minimal"] .modal { background: #ffffff; }
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 0;
  font-size: 16px;
  color: var(--text1);
}
.modal-close {
  background: none;
  border: none;
  color: var(--text2);
  font-size: 15px;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
}
.modal-close:hover { background: rgba(255,255,255,.08); color: var(--text1); }
.modal-body { padding: 14px 20px 8px; }
.modal-desc {
  color: var(--text2);
  font-size: 14px;
  line-height: 1.7;
  margin: 0 0 16px;
}
.dont-ask {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text2);
  cursor: pointer;
  user-select: none;
}
.dont-ask input { accent-color: var(--brand-1); width: 15px; height: 15px; }
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px 18px;
}
.ap-btn {
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  background: var(--brand-1);
  color: #fff;
  transition: filter .15s;
}
.ap-btn:hover { filter: brightness(1.08); }
.ap-btn.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text2);
}
.ap-btn.ghost:hover { border-color: var(--brand-1); color: var(--brand-1); }
</style>
