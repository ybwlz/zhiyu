<!-- 涂鸦工具面板（由全局工具球 ToolBall 的「🖌 涂鸦」调起，自己不再有球）
     全部工具集成：钢笔/圆珠笔/荧光笔/橡皮/色板/粗细/撤销/清空/保存
     保存：书房笔记直接挂当前笔记，广场笔记询问后复制副本，原版永不动 -->
<template>
  <div class="dball-wrap">
    <Transition name="dball">
      <div v-if="open" ref="panel" class="dball-panel" :style="panelPos" @pointerdown.stop>
        <div class="dball-panel-head" @pointerdown="dragStart" title="按住拖动">
          <span class="dball-tip">{{ tipText }}</span>
          <button class="dball-close" @click="closePanel" data-tip="收起">✕</button>
        </div>
        <!-- 当前笔状态条 -->
        <div class="dball-current">
          <span class="dball-cur-ico">{{ tool === 'eraser' ? '🧽' : (tool === 'pen' ? '🖊' : tool === 'ball' ? '🖋' : tool === 'pencil' ? '✏️' : '🖍') }}</span>
          <span class="dball-cur-name">{{ tool === 'eraser' ? '橡皮' : (tool === 'pen' ? '钢笔' : tool === 'ball' ? '圆珠笔' : tool === 'pencil' ? '铅笔' : '荧光笔') }}</span>
          <span v-if="tool !== 'eraser'" class="dball-cur-color" :style="{ background: color }"></span>
          <span v-if="tool !== 'eraser'" class="dball-cur-line" :style="{ height: Math.max(2, width) + 'px', background: color }"></span>
        </div>
        <!-- 笔类型 -->
        <div class="dball-sec">
          <button class="dball-tool" :class="{ sel: tool === 'pen' }" data-tip="钢笔：细而流畅（默认黑色）" @click="pickTool('pen')">🖊 钢笔</button>
          <button class="dball-tool" :class="{ sel: tool === 'pencil' }" data-tip="铅笔：硬笔细线" @click="pickTool('pencil')">✏️ 铅笔</button>
          <button class="dball-tool" :class="{ sel: tool === 'ball' }" data-tip="圆珠笔：中等圆润" @click="pickTool('ball')">🖋 圆珠笔</button>
          <button class="dball-tool" :class="{ sel: tool === 'hl' }" data-tip="荧光笔：粗而醒目" @click="pickTool('hl')">🖍 荧光笔</button>
          <button class="dball-tool" :class="{ sel: tool === 'eraser' }" data-tip="橡皮擦" @click="pickTool('eraser')">🧽 橡皮</button>
        </div>
        <!-- 颜色 -->
        <div class="dball-sec dball-colors">
          <button
            v-for="c in colors" :key="c"
            class="dball-color" :style="{ background: c }"
            :class="{ sel: color === c && tool !== 'eraser' }"
            @click="color = c; if (tool === 'eraser') tool = 'pen'"
          ></button>
          <label class="dball-color-custom" data-tip="自定义颜色">
            <input type="color" :value="color" @input="color = $event.target.value; if (tool === 'eraser') tool = 'pen'" />
          </label>
        </div>
        <!-- 粗细：自定义横条滑块 -->
        <div class="dball-sec dball-widths">
          <span class="dball-w-label">粗细</span>
          <input type="range" min="1" max="30" step="1" v-model.number="width" class="dball-w-range" />
          <span class="dball-w-val">{{ width }}px</span>
        </div>
        <!-- 操作：先撤销/清空本批，清空后才显示「删已存」 -->
        <div class="dball-sec dball-ops">
          <button class="dball-tool" @click="undo">↩ 撤销</button>
          <button class="dball-tool" @click="clearAll">🧽 清空</button>
          <button v-if="savedStrokes.length && !strokes.length" class="dball-tool del" data-tip="删除已保存的手绘（需先清空本批）" @click="delSaved">🗑️ 删已存</button>
        </div>
        <button class="dball-save" @click="save">{{ saveText }}</button>
      </div>
    </Transition>
    <!-- 涂鸦画布：fixed 覆盖目标卡片，面板展开时拦截绘制 -->
    <canvas
      ref="cvRef"
      class="dball-canvas"
      :class="{ active: open }"
    ></canvas>
  </div>
</template>

<script>
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

export default {
  name: 'DoodleBall',
  props: {
    // 要覆盖的正文卡片 selector（NoteReader 用 .reader-card，阅览室用 .doc-card）
    target: { type: String, default: '.reader-card' },
    docId: { type: Number, default: null },
    isMine: { type: Boolean, default: false },
  },
  data() {
    return {
      open: false,
      tool: 'pen',
      color: '#1a1a1a',
      width: 3,
      colors: ['#1a1a1a', '#ffd93d', '#6bcb77', '#ff8fa3', '#6bb3ff', '#c792ea'],
      widths: [{ v: 3, label: '细' }, { v: 7, label: '中' }, { v: 14, label: '粗' }],
      strokes: [],                      // 本次新画的笔迹（未保存，仅预览）
      savedStrokes: [],                 // 本笔记已保存的涂鸦（显示用）
      savedAnnId: null,                 // 已保存涂鸦记录的 id（用于删除）
      savedWH: { w: 0, h: 0 },
      annBaseStrokes: [],               // 批注块已有的笔迹（独立会话，不混用全页手绘状态）
      annBaseWH: { w: 0, h: 0 },
      panelPos: null,                   // 面板位置（跟随工具球）
      dragOff: null,                     // 面板拖拽偏移
      drawing: false,
      curStroke: null,
      renderedPointCount: 0,
      rafId: null,
    }
  },
  computed: {
    tipText() {
      if (this._tgtCanvas) return '在批注框内手绘，完成后并入批注内容'
      return this.isMine ? '在笔记上自由手绘，保存即存到当前笔记' : '在笔记上自由手绘（仅预览，不改原版）'
    },
    saveText() {
      if (this._tgtCanvas) return '✔ 完成并并入批注'
      return this.isMine ? '💾 保存手绘' : '💾 保存并加入书房'
    },
  },
  watch: {
    // 阅览室切换文档 / 阅读页跳转时重新加载涂鸦并重定位画布
    docId(v) {
      this.strokes = []
      this.savedStrokes = []
      if (v) this.loadAnn()
      if (this.open) this.$nextTick(() => this.attachCanvas())
    },
  },
  mounted() {
    window.addEventListener('zhiyu:toggle-doodle', this.onToggle)
    window.addEventListener('zhiyu:delete-doodle', this.onDeleteReq)
    window.addEventListener('zhiyu:doodle-reflow', this.onReflow)
    if (this.docId) this.loadAnn()
  },
  beforeUnmount() {
    window.removeEventListener('zhiyu:toggle-doodle', this.onToggle)
    window.removeEventListener('zhiyu:delete-doodle', this.onDeleteReq)
    window.removeEventListener('zhiyu:doodle-reflow', this.onReflow)
    if (this.rafId) cancelAnimationFrame(this.rafId)
  },
  methods: {
    // 由全局工具球调起/收起（面板跟随球位置；已画笔迹常驻显示，关闭面板只停用绘制）
    onToggle(e) {
      this.open = !this.open
      const d = e && e.detail
      // 批注框手绘：目标为批注框内的 canvas（复用同一套画笔）；否则是全页/卡片手绘
      this._tgtCanvas = (d && d.target && d.target.tagName === 'CANVAS') ? d.target : null
      this._tgt = null
      // 批注框会话：载入该批注块已有的笔迹，新笔迹叠加其上（不再借用全页手绘的 savedStrokes）
      if (this._tgtCanvas) {
        this.annBaseStrokes = Array.isArray(d && d.strokes) ? d.strokes : []
        this.annBaseWH = { w: (d && d.canvas_w) || 0, h: (d && d.canvas_h) || 0 }
        // 打开批注会话时清空本批未保存笔迹，从该块已有笔迹基础上重新开始
        if (this.open) { this.strokes = []; this.renderedPointCount = 0 }
      }
      if (this.open) {
        this.$nextTick(() => {
          if (d) {
            if (this._tgtCanvas) {
              const r = this._tgtCanvas.getBoundingClientRect()
              this.positionPanel({ x: r.left + r.width / 2, y: r.top + r.height / 2 })
            } else if (d.x != null) {
              this.positionPanel(d)
            }
          }
          this.attachCanvas()
        })
      } else {
        this.setCanvasInteractive(false)
      }
    },
    closePanel() { this.open = false; this.setCanvasInteractive(false) },
    setCanvasInteractive(on) {
      const cv = this._tgtCanvas || this.$refs.cvRef
      if (!cv) return
      cv.style.pointerEvents = on ? 'auto' : 'none'
      // 关键：完成后必须移除 .active——否则 CSS 的 `.active ~ .ann-body { pointer-events:none }` 一直生效，文字区点不进去
      cv.classList.toggle('active', on)
    },
    // 编辑区重建（renderRight）后 canvas 被销毁，有笔迹时重新挂载
    onReflow() {
      if (this._tgtCanvas && !this._tgtCanvas.isConnected) { this._tgtCanvas = null; this.cv = null }
      if (this.open || this.strokes.length || this.savedStrokes.length) {
        this.$nextTick(() => this.attachCanvas())
      }
    },
    // AI 助手“删除涂鸦”动作 → 删除已保存的涂鸦
    onDeleteReq() {
      if (!this.savedAnnId) { ElMessage.info('这篇笔记没有已保存的手绘'); return }
      this.delSaved()
    },
    positionPanel(d) {
      const panel = this.$refs.panel
      const pw = panel ? panel.offsetWidth : 248
      const ph = panel ? panel.offsetHeight : 320
      let left = d.x
      if (left + pw > window.innerWidth - 8) left = d.x - pw - 8
      left = Math.max(8, left)
      let top = d.y + 48
      top = Math.max(8, Math.min(top, window.innerHeight - ph - 8))
      this.applyPanelPos({ left, top })
    },
    // 定位面板：更新状态 + 直接设置 DOM style（避免 :style 绑定不生效）
    applyPanelPos(pos) {
      this.panelPos = pos
      const panel = this.$refs.panel
      if (panel && pos) {
        panel.style.left = pos.left + 'px'
        panel.style.top = pos.top + 'px'
      }
    },
    // 面板可拖拽移动（按住头部拖动）
    dragStart(e) {
      if (e.target && e.target.closest && e.target.closest('button')) return
      e.preventDefault()
      const panel = this.$refs.panel
      if (!panel) return
      if (e.pointerId != null && e.currentTarget.setPointerCapture) {
        try { e.currentTarget.setPointerCapture(e.pointerId) } catch (_) { /* 兼容旧浏览器 */ }
      }
      const rect = panel.getBoundingClientRect()
      this.dragOff = { x: e.clientX - rect.left, y: e.clientY - rect.top }
      window.addEventListener('pointermove', this.dragMove)
      window.addEventListener('pointerup', this.dragEnd)
    },
    dragMove(e) {
      if (!this.dragOff) return
      this.applyPanelPos({ left: e.clientX - this.dragOff.x, top: e.clientY - this.dragOff.y })
    },
    dragEnd() {
      this.dragOff = null
      window.removeEventListener('pointermove', this.dragMove)
      window.removeEventListener('pointerup', this.dragEnd)
    },
    // 删除已保存的涂鸦（上次保存的笔迹）
    async delSaved() {
      if (!this.savedAnnId) return
      try {
        await ElMessageBox.confirm('确定删除已保存的手绘？只删历史，本批新画的不受影响。', '删除已保存的手绘', {
          confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
          customClass: 'zhy-doodle-confirm',
        })
      } catch (e) { return }
      try {
        await api.delete('/annotations/' + this.savedAnnId)
        ElMessage.success('已删除已保存的手绘')
        this.savedStrokes = []
        this.savedAnnId = null
        this.savedWH = { w: 0, h: 0 }
        this.redraw()
        this.loadAnn()
      } catch (e) { ElMessage.error(e.response?.data?.error || '删除失败') }
    },
    // ── 工具 ──
    pickTool(t) {
      this.tool = t
      if (t === 'pen') this.color = '#000'
      else if (t === 'pencil') this.color = '#3a3a3a'
      else if (t === 'ball') this.color = '#1a1a1a'
      else if (t === 'hl') this.color = '#ffd93d'
      // 不重置粗细：保留用户选择的宽度
    },
    // ── 画布跟随：canvas 插入目标内容层（absolute），随内容滚动天然跟随、不抖 ──
    attachCanvas() {
      // 批注框手绘：直接用批注框的画布（不移动 DOM，事件绑到它上面）
      if (this._tgtCanvas) {
        this.cv = this._tgtCanvas
        this.cv.classList.add('active')
        this.cv.style.pointerEvents = this.open ? 'auto' : 'none'
        this.bindCvEvents()
        this.redraw()
        return
      }
      const cv = this.$refs.cvRef
      if (!cv) return
      const el = document.querySelector(this.target)
      if (!el) return
      if (cv.parentNode !== el) el.appendChild(cv)
      const dpr = window.devicePixelRatio || 1
      const w = el.clientWidth
      const h = el.scrollHeight || el.clientHeight
      cv.width = Math.max(1, Math.round(w * dpr))
      cv.height = Math.max(1, Math.round(h * dpr))
      cv.style.position = 'absolute'
      cv.style.left = '0px'
      cv.style.top = '0px'
      cv.style.width = w + 'px'
      cv.style.height = h + 'px'
      cv.style.zIndex = '5'
      cv.style.pointerEvents = this.open ? 'auto' : 'none'
      this.cv = cv
      this.bindCvEvents()
      this.redraw()
    },
    // 绘制事件统一绑定（全页画布 / 批注框画布共用；元素重建后幂等重绑）
    bindCvEvents() {
      const cv = this.cv
      if (!cv || cv._doodleBound) return
      cv._doodleBound = true
      cv.addEventListener('pointerdown', this.onDown)
      cv.addEventListener('pointermove', this.onMove)
      cv.addEventListener('pointerup', this.onUp)
    },
    unbindCvEvents() {
      const cv = this.cv
      if (!cv) return
      cv.removeEventListener('pointerdown', this.onDown)
      cv.removeEventListener('pointermove', this.onMove)
      cv.removeEventListener('pointerup', this.onUp)
      cv._doodleBound = false
    },
    detachCanvas() {
      // 批注框画布：不删除（属于批注框），只解除绘制状态
      if (this._tgtCanvas) {
        this.unbindCvEvents()
        if (this.cv) this.cv.classList.remove('active')
        return
      }
      const cv = this.$refs.cvRef
      if (!cv) return
      if (cv.parentNode && cv.parentNode !== document.body) {
        cv.parentNode.removeChild(cv)
      }
      cv.style.pointerEvents = 'none'
    },
    // ── 绘制 ──
    annPos(e) {
      const cv = this.cv
      const rect = cv.getBoundingClientRect()
      let x = (e.clientX - rect.left) * (cv.width / rect.width)
      let y = (e.clientY - rect.top) * (cv.height / rect.height)
      // 批注块手绘严格裁剪到画布（=批注可视边框）内：pointer capture 移出框外也不落笔到框外
      x = Math.max(0, Math.min(cv.width, x))
      y = Math.max(0, Math.min(cv.height, y))
      return { x, y }
    },
    onDown(e) {
      if (!this.open) return
      e.preventDefault()
      if (e.pointerId != null && this.cv.setPointerCapture) {
        try { this.cv.setPointerCapture(e.pointerId) } catch (_) { /* 兼容旧浏览器 */ }
      }
      this.drawing = true
      const p = this.annPos(e)
      this.curStroke = { points: [p], color: this.tool === 'eraser' ? 'erase' : this.color, width: this.width }
      this.strokes.push(this.curStroke)
    },
    onMove(e) {
      if (!this.drawing || !this.curStroke) return
      e.preventDefault()
      const pts = this.curStroke.points
      const events = typeof e.getCoalescedEvents === 'function' ? e.getCoalescedEvents() : [e]
      for (const pointEvent of events) {
        const p = this.annPos(pointEvent)
        const last = pts[pts.length - 1]
        // 快速移动时插值补点，保证笔迹连续不断点
        if (last) {
          const dx = p.x - last.x
          const dy = p.y - last.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > 3) {
            const steps = Math.ceil(dist / 3)
            for (let i = 1; i < steps; i++) pts.push({ x: last.x + dx * i / steps, y: last.y + dy * i / steps })
          }
        }
        pts.push(p)
      }
      if (!this.rafId) {
        this.rafId = requestAnimationFrame(() => {
          this.rafId = null
          this.redraw()
        })
      }
    },
    onUp(e) {
      if (e && e.pointerId != null && this.cv && this.cv.releasePointerCapture) {
        try { this.cv.releasePointerCapture(e.pointerId) } catch (_) { /* 已释放 */ }
      }
      this.drawing = false
      this.curStroke = null
    },
    drawPendingStroke() {
      if (!this.curStroke || !this.cv) return
      const pts = this.curStroke.points
      const ctx = this.cv.getContext('2d')
      ctx.save()
      if (this.curStroke.color === 'erase') {
        ctx.globalCompositeOperation = 'destination-out'
        ctx.strokeStyle = 'rgba(0,0,0,1)'
      } else ctx.strokeStyle = this.curStroke.color
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.lineWidth = this.curStroke.width
      for (let i = Math.max(1, this.renderedPointCount); i < pts.length; i++) {
        ctx.beginPath()
        ctx.moveTo(pts[i - 1].x, pts[i - 1].y)
        ctx.lineTo(pts[i].x, pts[i].y)
        ctx.stroke()
      }
      if (pts.length === 1 && this.renderedPointCount === 1) {
        ctx.beginPath(); ctx.arc(pts[0].x, pts[0].y, this.curStroke.width / 2, 0, Math.PI * 2); ctx.fill()
      }
      ctx.restore()
      this.renderedPointCount = pts.length
    },
    // 平滑笔迹：二次贝塞尔（中点平滑）；橡皮用 destination-out 真擦除像素
    drawStroke(ctx, s, kx, ky) {
      const pts = s.points
      if (!pts.length) return
      ctx.save()
      if (s.color === 'erase') {
        ctx.globalCompositeOperation = 'destination-out'
        ctx.globalAlpha = 1   // 橡皮必须满强度，否则擦不干净
      }
      ctx.strokeStyle = s.color === 'erase' ? 'rgba(0,0,0,1)' : s.color
      ctx.lineWidth = s.width * (kx + ky) / 2
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.beginPath()
      ctx.moveTo(pts[0].x * kx, pts[0].y * ky)
      if (pts.length === 1) {
        ctx.lineTo(pts[0].x * kx + 0.1, pts[0].y * ky)
      } else if (pts.length === 2) {
        ctx.lineTo(pts[1].x * kx, pts[1].y * ky)
      } else {
        for (let i = 1; i < pts.length - 1; i++) {
          const mx = (pts[i].x + pts[i + 1].x) / 2 * kx
          const my = (pts[i].y + pts[i + 1].y) / 2 * ky
          ctx.quadraticCurveTo(pts[i].x * kx, pts[i].y * ky, mx, my)
        }
        const last = pts[pts.length - 1]
        ctx.lineTo(last.x * kx, last.y * ky)
      }
      ctx.stroke()
      ctx.restore()
    },
    redraw() {
      const cv = this.cv || this.$refs.cvRef
      if (!cv) return
      const ctx = cv.getContext('2d')
      ctx.clearRect(0, 0, cv.width, cv.height)
      ctx.globalAlpha = 0.5
      // 批注块手绘：画该批注块已有的笔迹（按原保存尺寸等比缩放）+ 本批新笔迹；不画全页 savedStrokes
      if (this._tgtCanvas) {
        const s = this.annBaseWH.w ? cv.width / this.annBaseWH.w : 1
        for (const st of this.annBaseStrokes) this.drawStroke(ctx, st, s, s)
        for (const st of this.strokes) this.drawStroke(ctx, st, 1, 1)
      } else {
        const sx = this.savedWH.w ? cv.width / this.savedWH.w : 1
        const sy = this.savedWH.h ? cv.height / this.savedWH.h : 1
        for (const s of this.savedStrokes) this.drawStroke(ctx, s, sx, sy)
        for (const s of this.strokes) this.drawStroke(ctx, s, 1, 1)
      }
      ctx.globalAlpha = 1
    },
    undo() { this.strokes.pop(); this.redraw() },
    clearAll() { this.strokes = []; this.redraw() },
    // ── 加载已保存涂鸦 ──
    async loadAnn() {
      if (!this.docId) return
      try {
        const res = await api.get(`/notes/${this.docId}/annotations`)
        const doodles = (res.data || []).filter(a => a.kind === 'doodle')
        if (doodles.length) {
          const last = doodles[doodles.length - 1]
          this.savedStrokes = Array.isArray(last.strokes) ? last.strokes : []
          this.savedAnnId = last.id
          this.savedWH = { w: last.canvas_w || 0, h: last.canvas_h || 0 }
        } else {
          this.savedStrokes = []
          this.savedAnnId = null
          this.savedWH = { w: 0, h: 0 }
        }
      } catch (e) {
        this.savedStrokes = []
        this.savedAnnId = null
        this.savedWH = { w: 0, h: 0 }
      }
      this.$nextTick(() => { if (this.savedStrokes.length || this.open) this.attachCanvas() })
    },
    // ── 保存：书房直接挂当前笔记 / 广场询问后复制副本 ──
    async save() {
      const auth = useAuthStore()
      if (!auth.isLogin) { ElMessage.warning('请先登录再保存涂鸦'); return }
      if (!this.strokes.length) { ElMessage.info('还没有画内容，先涂几笔再保存'); return }
      // 新建笔记（尚未保存，docId 为 NaN/空）时无法把涂鸦挂到笔记上：先保存笔记再手绘
      if (!this._tgtCanvas && !(Number.isFinite(this.docId) && this.docId > 0)) {
        ElMessage.warning('请先保存笔记，再保存手绘')
        return
      }
      // 批注框手绘：把笔迹交给编辑页，合并进批注内容
      if (this._tgtCanvas) {
        window.dispatchEvent(new CustomEvent('zhiyu:ann-doodle-save', { detail: { canvas: this._tgtCanvas, strokes: this.strokes } }))
        this.strokes = []
        this.redraw()
        this.closePanel()
        return
      }
      const cv = this.$refs.cvRef
      const payload = { strokes: this.strokes, canvas_w: cv ? cv.width : 0, canvas_h: cv ? cv.height : 0 }
      if (!this.isMine) {
        try {
          await ElMessageBox.confirm('将复制一份（含涂鸦）到你的书房，作者原版不受影响。', '保存并加入书房？', { confirmButtonText: '保存到书房', cancelButtonText: '不保存', type: 'info' })
        } catch (e) {
          ElMessage.info('已丢弃涂鸦，未保存')
          return
        }
      }
      try {
        const res = await api.post(`/docs/${this.docId}/copy-to-studio`, payload)
        this.strokes = []
        this.redraw()
        if (res.data.copied) ElMessage.success('已保存到书房：' + res.data.title)
        else { ElMessage.success('涂鸦已保存到当前笔记'); this.loadAnn() }
      } catch (e) { ElMessage.error(e.response?.data?.error || '保存失败') }
    },
  },
}
</script>

<style scoped>
.dball-wrap { display: contents; }
.dball-panel {
  position: fixed;
  z-index: 2147483000;
  width: 248px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
  display: flex; flex-direction: column; gap: 8px;
}
.dball-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; cursor: move; user-select: none; touch-action: none; }
.dball-tip { font-size: 12px; color: var(--text2); line-height: 1.5; flex: 1; }
.dball-close {
  border: none; background: none; cursor: pointer;
  color: var(--text2); font-size: 14px; padding: 2px 6px; border-radius: 6px;
}
.dball-close:hover { color: #ef4444; background: color-mix(in srgb, #ef4444 10%, transparent); }
/* 当前笔状态条 */
.dball-current {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--btn-bg);
}
.dball-cur-ico { font-size: 16px; }
.dball-cur-name { font-size: 12.5px; font-weight: 600; color: var(--text1); }
.dball-cur-color {
  width: 16px; height: 16px; border-radius: 50%;
  border: 1px solid var(--border); margin-left: auto;
}
.dball-cur-line {
  width: 26px; border-radius: 999px;
  margin-left: 2px;
}
.dball-sec { display: flex; flex-wrap: wrap; gap: 6px; }
.dball-tool {
  padding: 5px 11px; border-radius: 8px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 12.5px;
  transition: all .15s;
}
.dball-tool:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.dball-tool.sel { color: #fff; border-color: transparent; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); }
.dball-colors { display: flex; gap: 8px; }
.dball-color {
  width: 26px; height: 26px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform .15s;
}
.dball-color.sel { border-color: var(--text1); transform: scale(1.18); }
.dball-color-custom {
  width: 26px; height: 26px;
  border-radius: 50%;
  border: 2px dashed var(--border);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--text2);
  overflow: hidden;
  transition: transform .15s;
}
.dball-color-custom:hover { transform: scale(1.15); }
.dball-color-custom input {
  position: absolute; opacity: 0; width: 100%; height: 100%; cursor: pointer;
}
.dball-ops { justify-content: space-between; }
.dball-widths { display: flex; align-items: center; gap: 8px; }
.dball-w-label { font-size: 12px; color: var(--text2); flex-shrink: 0; }
.dball-w-range { flex: 1; accent-color: var(--brand-1); cursor: pointer; }
.dball-w-val { font-size: 12px; color: var(--text1); min-width: 30px; text-align: right; flex-shrink: 0; }
.dball-tool.del {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.08);
  border-color: rgba(220, 38, 38, 0.35);
  display: inline-flex; align-items: center; gap: 4px;
  font-weight: 600;
}
.dball-tool.del:hover { color: #fff; background: #ef4444; border-color: transparent; }
.dball-save {
  padding: 10px 0; border: none; border-radius: 10px;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  color: #fff; font-weight: 600; font-size: 13.5px; cursor: pointer;
}
.dball-canvas {
  position: absolute;
  z-index: 5;
  border-radius: 22px;
  pointer-events: none;
}
.dball-canvas.active {
  pointer-events: auto;
  cursor: crosshair;
  /* 涂鸦开启时锁定浏览器手势，避免触控笔第一段被当成下拉刷新而取消。 */
  touch-action: none;
}
.dball-enter-active, .dball-leave-active { transition: opacity .18s ease, transform .18s ease; }
.dball-enter-from, .dball-leave-to { opacity: 0; transform: translateY(8px); }
</style>
