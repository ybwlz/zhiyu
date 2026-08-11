<!-- AI 球：唯一悬浮球（zy + 白色外圈，可拖拽），点击打开 AI 助手面板（跟随球位置） -->
<template>
  <div
    ref="ballEl"
    class="tball"
    :class="{ placed: !!ballPos }"
    :style="ballStyle"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
  >
    <div class="tball-inner">🤖</div>
  </div>
</template>

<script>
export default {
  name: 'ToolBall',
  data() {
    return {
      ballPos: null,        // 拖拽后的位置（null = CSS 默认右下角）
      drag: null,
    }
  },
  computed: {
    ballStyle() {
      return this.ballPos ? { left: this.ballPos.x + 'px', top: this.ballPos.y + 'px' } : null
    },
  },
  methods: {
    onDown(e) {
      if (e.currentTarget.setPointerCapture) e.currentTarget.setPointerCapture(e.pointerId)
      const rect = e.currentTarget.getBoundingClientRect()
      this.ballPos = { x: rect.left, y: rect.top }
      this.drag = { dx: e.clientX - rect.left, dy: e.clientY - rect.top, moved: false, sx: e.clientX, sy: e.clientY }
    },
    onMove(e) {
      if (!this.drag) return
      if (Math.abs(e.clientX - this.drag.sx) > 4 || Math.abs(e.clientY - this.drag.sy) > 4) this.drag.moved = true
      const x = Math.max(8, Math.min(e.clientX - this.drag.dx, window.innerWidth - 52 - 8))
      const y = Math.max(8, Math.min(e.clientY - this.drag.dy, window.innerHeight - 52 - 8))
      this.ballPos = { x, y }
    },
    onUp(e) {
      if (!this.drag) return
      const wasClick = !this.drag.moved
      this.drag = null
      if (e.currentTarget.releasePointerCapture) {
        try { e.currentTarget.releasePointerCapture(e.pointerId) } catch (err) { /* 忽略 */ }
      }
      // 点击（按下未拖动）→ 打开 AI 助手
      if (wasClick) this.openAI()
    },
    openAI() {
      const r = this.$refs.ballEl ? this.$refs.ballEl.getBoundingClientRect() : null
      const pos = r ? { x: r.left, y: r.top } : { x: window.innerWidth - 76, y: window.innerHeight - 76 }
      window.dispatchEvent(new CustomEvent('zhiyu:toggle-ai', { detail: pos }))
    },
  },
}
</script>

<style scoped>
.tball {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2147483000;
  width: 52px;
  height: 52px;
}
.tball.placed { right: auto; }
.tball-inner {
  position: absolute;
  inset: 0;
  width: 52px; height: 52px;
  box-sizing: border-box;
  border-radius: 50%;
  border: 2.5px solid #fff;              /* 最外圈白色（缩小一倍） */
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 24px; font-weight: 800; letter-spacing: 0;
  cursor: grab;
  touch-action: none;
  user-select: none;
  transition: box-shadow .2s, transform .15s;
}
.tball-inner:hover { transform: scale(1.06); box-shadow: 0 12px 36px rgba(0, 0, 0, 0.38); }
</style>
