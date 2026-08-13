<template>
  <Transition name="upd-fade">
    <div v-if="show && data" class="update-notice">
      <div class="upd-icon">🎉</div>
      <div class="upd-body">
        <div class="upd-title">发现新版本 v{{ data.version }}</div>
        <div class="upd-notes" v-if="!downloading">{{ data.notes }}</div>
        <div v-else class="upd-progress">
          <div class="upd-bar"><div class="upd-fill" :style="{ width: pct + '%' }"></div></div>
          <div class="upd-pct">{{ pct }}% · {{ pct >= 100 ? '正在重启应用…' : '正在下载更新…' }}</div>
        </div>
      </div>
      <div class="upd-actions" v-if="!downloading">
        <button class="upd-btn" @click="startDownload">立即下载</button>
        <button class="upd-btn ghost" @click="dismiss">暂不更新</button>
      </div>
      <div class="upd-actions" v-else>
        <button class="upd-btn ghost" @click="paused ? resume() : pause()">{{ paused ? '继续' : '暂停' }}</button>
        <button class="upd-btn ghost" @click="cancel">取消</button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const show = ref(false)
const data = ref(null)
const downloading = ref(false)
const paused = ref(false)
const pct = ref(0)

function dismiss() {
  show.value = false
  try { localStorage.setItem('kb-update-dismissed', data.value?.version || '') } catch (e) {}
}
async function startDownload() {
  if (!window.desktop?.downloadUpdate || !data.value?.url) return
  downloading.value = true
  paused.value = false
  pct.value = 0
  const r = await window.desktop.downloadUpdate(data.value.url).catch((e) => ({ ok: false, error: e.message }))
  if (r && r.ok === false && !r.paused && !r.cancelled) {
    downloading.value = false
    data.value = { ...data.value, notes: '下载失败：' + (r.error || '网络异常') }
  }
}
function pause() {
  window.desktop?.pauseUpdate?.()
}
async function resume() {
  paused.value = false
  const r = await window.desktop.downloadUpdate(data.value.url).catch((e) => ({ ok: false, error: e.message }))
  if (r && r.ok === false && !r.paused && !r.cancelled) {
    paused.value = true
    data.value = { ...data.value, notes: '继续下载失败：' + (r.error || '网络异常') }
  }
}
function cancel() {
  window.desktop?.cancelUpdate?.()
}

onMounted(() => {
  if (!window.desktop?.onUpdateAvailable) return
  const dismissed = localStorage.getItem('kb-update-dismissed')
  window.desktop.onUpdateAvailable((d) => {
    if (d && d.version && d.version !== dismissed) {
      data.value = d
      show.value = true
    }
  })
  window.desktop.onUpdateProgress?.((v) => {
    if (v && typeof v === 'object') {
      pct.value = Math.round(v.pct || 0)
      if (v.paused) { paused.value = true; downloading.value = true }
    }
  })
  window.desktop.onUpdateCancelled?.(() => {
    downloading.value = false
    paused.value = false
    pct.value = 0
  })
})
</script>

<style scoped>
.update-notice {
  position: fixed;
  right: 96px;
  bottom: 24px;
  z-index: 2147483002;
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 420px;
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--card-bg, var(--bg));
  border: 1px solid var(--border);
  box-shadow: 0 12px 40px rgba(0, 0, 0, .35);
}
.upd-icon { font-size: 22px; flex-shrink: 0; }
.upd-body { flex: 1; min-width: 0; }
.upd-title { font-size: 14px; font-weight: 700; color: var(--text1); margin-bottom: 3px; }
.upd-notes {
  font-size: 12px; color: var(--text2); line-height: 1.5;
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
/* 下载进度 */
.upd-progress { min-width: 190px; }
.upd-bar {
  height: 6px; border-radius: 999px;
  background: color-mix(in srgb, var(--text2) 18%, transparent);
  overflow: hidden; margin: 4px 0 6px;
}
.upd-fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--brand-1), var(--brand-2));
  transition: width .2s;
}
.upd-pct { font-size: 11.5px; color: var(--text2); }
.upd-actions { display: flex; gap: 8px; flex-shrink: 0; }
.upd-btn {
  padding: 7px 14px; border: none; border-radius: 999px; cursor: pointer;
  font-size: 12.5px; font-weight: 600;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; white-space: nowrap;
}
.upd-btn.ghost {
  background: transparent; color: var(--text2); border: 1px solid var(--border);
}
.upd-btn:hover { opacity: .88; }

.upd-fade-enter-active, .upd-fade-leave-active { transition: opacity .3s, transform .3s; }
.upd-fade-enter-from, .upd-fade-leave-to { opacity: 0; transform: translateY(12px); }
</style>
