<template>
  <Teleport to="body">
    <div v-if="visible" class="img-viewer" @click.self="close">
      <img :src="url" alt="大图预览" @click.stop />
      <button class="iv-close" @click="close" title="关闭 (Esc)">✕</button>
      <span class="iv-hint">点击空白处关闭 · Esc 关闭</span>
    </div>
  </Teleport>
</template>

<script>
export default {
  name: 'ImageViewer',
  props: {
    visible: { type: Boolean, default: false },
    url: { type: String, default: '' },
  },
  emits: ['close'],
  watch: {
    visible(v) {
      if (v) {
        this._onKey = (e) => { if (e.key === 'Escape') this.close() }
        window.addEventListener('keydown', this._onKey)
      } else if (this._onKey) {
        window.removeEventListener('keydown', this._onKey)
        this._onKey = null
      }
    },
  },
  beforeUnmount() {
    if (this._onKey) window.removeEventListener('keydown', this._onKey)
  },
  methods: {
    close() { this.$emit('close') },
  },
}
</script>

<style scoped>
.img-viewer {
  position: fixed; inset: 0; z-index: 500;
  background: rgba(0, 0, 0, .8);
  display: flex; align-items: center; justify-content: center;
  cursor: zoom-out;
}
.img-viewer img {
  max-width: 92vw; max-height: 86vh;
  border-radius: 10px;
  box-shadow: 0 12px 60px rgba(0, 0, 0, .65);
  cursor: default;
}
.iv-close {
  position: fixed; top: 18px; right: 22px;
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: rgba(255, 255, 255, .14); color: #fff; font-size: 16px;
  cursor: pointer; transition: background .15s;
}
.iv-close:hover { background: rgba(255, 255, 255, .3); }
.iv-hint { position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%); font-size: 12px; color: rgba(255,255,255,.55); }
</style>
