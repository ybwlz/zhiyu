<template>
  <div v-if="visible" class="crop-mask" @click.self="close">
    <div class="crop-panel">
      <h3>裁剪头像</h3>
      <p class="crop-tip">拖动图片调整位置 · 下方滑块缩放</p>
      <div ref="stage" class="crop-stage" @pointerdown="startDrag" @pointermove="onDrag" @pointerup="endDrag" @pointercancel="endDrag" @wheel.prevent="onWheel">
        <img ref="imgEl" class="crop-img" :src="src" :style="imgStyle" draggable="false" @load="onImgLoad" />
        <div class="crop-box"></div>
      </div>
      <div class="crop-ctrl">
        <span class="crop-lbl">缩放</span>
        <input type="range" v-model.number="scale" min="0.1" max="0.8" step="0.01" class="crop-range" />
        <span class="crop-val">{{ Math.round(scale * 100) }}%</span>
      </div>
      <div class="crop-actions">
        <button class="crop-btn" @click="close">取消</button>
        <button class="crop-btn primary" @click="confirm">确定</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AvatarCrop',
  props: {
    visible: { type: Boolean, default: false },
    file: { type: File, default: null },
  },
  data() {
    return {
      src: '',
      pw: 0, ph: 0,
      scale: 1,
      cssX: 0, cssY: 0,
      dragging: null,
      _url: '',
    }
  },
  computed: {
    boxPx() { return 200 },   // 固定裁剪框：200px（之前 280 太大）
    imgStyle() {
      return {
        left: this.cssX + 'px',
        top: this.cssY + 'px',
        width: Math.round(this.pw * this.scale) + 'px',
        height: Math.round(this.ph * this.scale) + 'px',
      }
    },
  },
  watch: {
    visible(v) {
      if (v && this.file) {
        if (this._url) URL.revokeObjectURL(this._url)
        this._url = URL.createObjectURL(this.file)
        this.src = this._url
        this.scale = 1
        this.cssX = 0
        this.cssY = 0
      }
    },
    scale(nv, ov) {
      // 以裁剪框中心为锚点缩放：框固定不动，图片从框中心展开/收缩
      if (ov && this.pw) {
        const cx = 150, cy = 150   // 裁剪框中心（舞台 300×300，框居中）
        // 缩放前框中心对应的图片源坐标
        const sx0 = (cx - this.cssX) / ov
        const sy0 = (cy - this.cssY) / ov
        // 缩放后把该源坐标放回框中心 → 图片围绕框中心缩放
        this.cssX = cx - sx0 * nv
        this.cssY = cy - sy0 * nv
      }
      this.clampPos()
    },
  },
  methods: {
    onImgLoad() {
      const el = this.$refs.imgEl
      if (!el) return
      this.pw = el.naturalWidth || 300
      this.ph = el.naturalHeight || 300
      // 初始：整张图片完整放进圆形裁剪框内并居中（打开就能看到整图）
      const b = this.boxPx
      this.scale = Math.min(b / this.pw, b / this.ph)
      this.centerImg()
    },
    centerImg() {
      this.cssX = (300 - this.pw * this.scale) / 2
      this.cssY = (300 - this.ph * this.scale) / 2
    },
    clampPos() {
      const w = this.pw * this.scale
      const h = this.ph * this.scale
      const b = this.boxPx
      // 裁剪框边界：舞台 300×300，框 200 居中 → 左/上 50，右/下 250
      const boxL = 50, boxR = 250, boxT = 50, boxB = 250
      // 图片必须覆盖整个裁剪框：图片左缘 ≤ 框左、右缘 ≥ 框右
      if (w <= b) this.cssX = boxL + (b - w) / 2          // 图片比框小：相对框居中
      else this.cssX = Math.min(boxL, Math.max(boxR - w, this.cssX))
      if (h <= b) this.cssY = boxT + (b - h) / 2
      else this.cssY = Math.min(boxT, Math.max(boxB - h, this.cssY))
    },
    startDrag(e) {
      this.dragging = { id: e.pointerId, sx: e.clientX - this.cssX, sy: e.clientY - this.cssY }
      e.currentTarget.setPointerCapture(e.pointerId)
    },
    onDrag(e) {
      if (!this.dragging) return
      this.cssX = e.clientX - this.dragging.sx
      this.cssY = e.clientY - this.dragging.sy
      this.clampPos()
    },
    endDrag(e) {
      if (this.dragging && this.dragging.id === e.pointerId) this.dragging = null
    },
    onWheel(e) {
      const d = e.deltaY > 0 ? 0.9 : 1.1
      this.scale = Math.min(0.8, Math.max(0.1, this.scale * d))
    },
    confirm() {
      const img = this.$refs.imgEl
      if (!img || !this.pw) return
      const s = this.scale
      const b = this.boxPx
      // 源坐标限制在图片范围内，避免框外空白
      const sx = Math.max(0, Math.min(this.pw - 1, (10 - this.cssX) / s))
      const sy = Math.max(0, Math.min(this.ph - 1, (10 - this.cssY) / s))
      let sw = b / s
      sw = Math.max(1, Math.min(sw, this.pw - sx, this.ph - sy))
      const canvas = document.createElement('canvas')
      canvas.width = 280
      canvas.height = 280
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, sx, sy, sw, sw, 0, 0, 280, 280)
      canvas.toBlob((blob) => {
        if (blob) this.$emit('done', new File([blob], 'avatar.png', { type: 'image/png' }))
      }, 'image/png')
    },
    close() {
      this.$emit('close')
    },
  },
  beforeUnmount() {
    if (this._url) URL.revokeObjectURL(this._url)
  },
}
</script>

<style scoped>
.crop-mask { position: fixed; inset: 0; z-index: 300; background: rgba(0,0,0,.55); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; }
.crop-panel { width: 380px; max-width: 92vw; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 16px; padding: 22px 24px; box-shadow: var(--shadow-1); }
.crop-panel h3 { margin: 0 0 4px; font-size: 16px; color: var(--text1); }
.crop-tip { font-size: 12px; color: var(--text2); margin: 0 0 14px; }
.crop-stage { position: relative; width: 300px; height: 300px; margin: 0 auto 14px; border-radius: 12px; overflow: hidden; background: #111; cursor: grab; user-select: none; touch-action: none; }
.crop-stage:active { cursor: grabbing; }
.crop-img { position: absolute; max-width: none; }
.crop-box {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  border: 2px solid #fff; border-radius: 50%;   /* 头像圆形裁剪框 */
  box-shadow: 0 0 0 9999px rgba(0,0,0,.5);
  pointer-events: none;
  width: v-bind(boxPx + 'px'); height: v-bind(boxPx + 'px');
}
.crop-ctrl { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.crop-lbl { font-size: 12.5px; color: var(--text2); }
.crop-range { flex: 1; accent-color: var(--brand-1); }
.crop-val { font-size: 12px; color: var(--text2); width: 44px; text-align: right; }
.crop-actions { display: flex; justify-content: flex-end; gap: 10px; }
.crop-btn { padding: 8px 20px; border-radius: 999px; cursor: pointer; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text2); font-size: 13px; transition: all .2s; }
.crop-btn.primary { color: #fff; border-color: transparent; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); }
.crop-btn:hover { opacity: .9; }
</style>
