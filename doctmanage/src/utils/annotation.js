// 批注系统（annotation）：
// 语法 `:::annotation <id>`（新格式）：<id> 对应 note_annotations 记录，
// 批注的文字(note_text) 与手绘笔迹(strokes) 都存记录里，编辑时防抖局部保存，不碰正文 markdown。
// 旧格式 `:::annotation\n文字\n:::` 仍兼容：内容直接渲染在框内（无记录）。
// 批注框 = 一张自由白纸：手绘笔迹 canvas 垫底（z-index 低），文字 contenteditable 在上层，
// 两者共存一框；回车换行由浏览器原生处理，框随内容长高，不拦截。
import container from 'markdown-it-container'

const CN = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'

// markdown-it-container 的 close token 不带 info，用模块级状态记录本次 open 的 id 来区分新旧格式
// （md.render 是同步的，状态在同一次渲染内有效）
let _annOpenId = ''

// 注册 markdown-it annotation 容器（在 md 实例上调用）
export function setupAnnotation(md) {
  md.use(container, 'annotation', {
    validate: (p) => p.trim().match(/^annotation(?:\s+\S+)?/),
    render(tokens, idx) {
      const t = tokens[idx]
      if (t.nesting === 1) {
        const parts = (t.info || '').trim().split(/\s+/)
        const id = (parts.length > 1 && parts[1]) ? parts[1] : ''
        _annOpenId = id
        if (id) {
          // 新格式：文字区用 textarea（独立控件，不参与 contenteditable 嵌套——回车/删除/多行全在框内）
          return '<div class="ann-block" data-ann-id="' + id + '">'
            + '<div class="ann-badge" data-ann-toggle></div>'
            + '<textarea class="ann-body" rows="3" spellcheck="false" placeholder="输入批注内容…"></textarea>'
            + '<div class="ann-foot"><button class="ann-del" data-ann-del>🗑 删除批注</button></div>'
            + '</div>'
        }
        // 旧格式：内容渲染进 div（兼容）
        return '<div class="ann-block" data-ann-id="">'
          + '<div class="ann-badge" data-ann-toggle></div>'
          + '<div class="ann-body">'
      }
      // close token
      const isNew = !!_annOpenId
      _annOpenId = ''
      if (isNew) return ''
      return '</div><div class="ann-foot"><button class="ann-del" data-ann-del>🗑 删除批注</button></div></div>'
    },
  })
}

// 删除回调由各页面通过 onDel 选项注入（编辑页删块+同步，阅读页删块+存后端）
let _opts = {}

// 注入删除回调（无事件绑定；批注交互已直接绑在元素上）
export function bindAnnGlobal(opts = {}) {
  _opts = opts
}

// 把笔迹画到画布（points 为像素坐标 {x,y}；按像素宽等比缩放，框宽高变化后笔迹不变形）
export function drawStrokes(cv, strokes, baseW, baseH) {
  if (!cv || !strokes || !strokes.length) return
  const ctx = cv.getContext('2d')
  if (!ctx) return
  const s = (baseW && baseW > 0) ? cv.width / baseW : 1
  ctx.clearRect(0, 0, cv.width, cv.height)
  for (const st of strokes) {
    if (!st || !st.points || !st.points.length) continue
    ctx.save()
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.lineWidth = Math.max(1, (st.width || 3) * s)
    ctx.strokeStyle = st.color === 'erase' ? 'rgba(0,0,0,1)' : (st.color || '#ffd93d')
    ctx.globalCompositeOperation = st.color === 'erase' ? 'destination-out' : 'source-over'
    ctx.beginPath()
    st.points.forEach((p, i) => {
      const x = p.x * s
      const y = p.y * s
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.restore()
  }
}

// 创建/确保批注框内垫底手绘画布
// 关键：收起时（display:none）clientWidth 为 0，绝不能把 canvas 像素重设为 0/1（会清空笔迹、展开后拉伸变形）
export function ensureDoodleCanvas(block, baseW, baseH) {
  let cv = block.querySelector('canvas.ann-doodle')
  if (!cv) {
    cv = document.createElement('canvas')
    cv.className = 'ann-doodle'
    cv.setAttribute('data-ann-doodle', '')
    block.insertBefore(cv, block.querySelector('.ann-body') || block.lastChild)
    const r = block.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    cv.width = Math.max(1, Math.round((r.width || 100) * dpr))
    cv.height = Math.max(1, Math.round((r.height || 100) * dpr))
    return cv
  }
  // 已有画布：仅在尺寸明显变化（>50%）时更新像素，且收起（宽=0）时保持原像素不清空
  const r = block.getBoundingClientRect()
  if (!r.width || !r.height) return cv
  const dpr = window.devicePixelRatio || 1
  const w = Math.max(1, Math.round(r.width * dpr))
  const h = Math.max(1, Math.round(r.height * dpr))
  if (Math.abs(cv.width - w) > w * 0.5 || Math.abs(cv.height - h) > h * 0.5) {
    cv.width = w
    cv.height = h
  }
  return cv
}

// 把光标聚焦到批注框文字区（textarea 或旧格式 div）末尾
function focusAnnBody(b, editable) {
  if (!editable) return
  const body = b.querySelector('.ann-body')
  if (!body) return
  body.focus()
  if (typeof body.setSelectionRange === 'function') {
    const len = body.value ? body.value.length : 0
    body.setSelectionRange(len, len)
  } else {
    const r = document.createRange()
    r.selectNodeContents(body)
    r.collapse(false)
    const sel = window.getSelection()
    sel.removeAllRanges()
    sel.addRange(r)
  }
}

// 读/写批注框文字（textarea 用 value，旧格式 div 用文本）
const annBodyVal = (body) => (body && body.tagName === 'TEXTAREA') ? (body.value || '') : (body ? (body.innerText || '') : '')

// 让批注框文字区随内容自适应高度
function autosizeAnnBody(body) {
  if (!body || body.tagName !== 'TEXTAREA') return
  body.style.height = 'auto'
  body.style.height = Math.max(60, body.scrollHeight) + 'px'
}

// 渲染后填充批注块：
// annMap = { [id]: { note_text, strokes, canvas_w, canvas_h } }
// opts: { editable, onInput(id, text), onSaveDoodle(id, strokes, w, h) }
export function bindAnnotations(root, annMap, opts = {}) {
  if (!root) return
  const blocks = root.querySelectorAll('.ann-block')
  blocks.forEach((b, i) => {
    const badge = b.querySelector('.ann-badge')
    const body = b.querySelector('.ann-body')
    const id = b.getAttribute('data-ann-id') || ''
    const rec = annMap && id ? annMap[id] : null
    const isTextarea = !!(body && body.tagName === 'TEXTAREA')
    if (body) {
      if (isTextarea) {
        // 新格式：textarea 原生可编辑（不参与 contenteditable 嵌套，回车/删除/多行全在框内）
        body.value = rec ? (rec.note_text || '') : ''
        body.readOnly = !opts.editable
        autosizeAnnBody(body)
        if (opts.editable && !body._annBound) {
          body._annBound = true
          let t = null
          body.addEventListener('input', () => {
            // 连续输入/回车期间零布局：不读 scrollHeight、不碰高度——连点回车完全不卡
            // 停止 200ms 后一次性增高 + 防抖局部保存
            clearTimeout(t)
            t = setTimeout(() => {
              autosizeAnnBody(body)
              if (opts.onInput) opts.onInput(id, body.value)
            }, 200)
          })
        }
      } else {
        // 旧格式：内容在 div 里
        body.contentEditable = opts.editable ? 'true' : 'false'
        if (!rec && opts.editable && !body._annBound) {
          body._annBound = true
          let t = null
          body.addEventListener('input', () => {
            clearTimeout(t)
            t = setTimeout(() => {
              if (opts.onInput) opts.onInput(id, body.innerText)
            }, 800)
          })
        }
      }
      if (rec && rec.strokes && rec.strokes.length) {
        const cv = ensureDoodleCanvas(b, rec.canvas_w || 100, rec.canvas_h || 100)
        requestAnimationFrame(() => drawStrokes(cv, rec.strokes, rec.canvas_w || 100, rec.canvas_h || 100))
      }
    }
    if (badge) {
      badge.textContent = CN[i] || ('[' + (i + 1) + ']')
      badge.onclick = (e) => {
        e.preventDefault()
        e.stopPropagation()
        b.classList.toggle('open')
        if (b.classList.contains('open')) {
          // 展开后：文字区自适应高度（收起时 display:none 高度归零，展开要重新撑开）+ 光标进框
          const tb = b.querySelector('.ann-body')
          if (tb) autosizeAnnBody(tb)
          focusAnnBody(b, opts.editable)
          if (rec && rec.strokes && rec.strokes.length) {
            requestAnimationFrame(() => {
              const cv = ensureDoodleCanvas(b, rec.canvas_w || 100, rec.canvas_h || 100)
              drawStrokes(cv, rec.strokes, rec.canvas_w || 100, rec.canvas_h || 100)
            })
          }
        }
      }
      badge.oncontextmenu = (e) => {
        e.preventDefault()
        e.stopPropagation()
        const all = Array.from(root.querySelectorAll('.ann-block'))
        const idx = all.indexOf(b)
        if (_opts.onDel) _opts.onDel(b, idx)
        else b.remove()
      }
    }
    const del = b.querySelector('.ann-del')
    if (del) {
      if (!opts.editable) {
        // 阅读页（非编辑模式）不显示删除按钮——批注是只读展示
        del.style.display = 'none'
        del.onclick = null
      } else {
        del.onclick = (e) => {
          e.preventDefault()
          e.stopPropagation()
          const all = Array.from(root.querySelectorAll('.ann-block'))
          const idx = all.indexOf(b)
          if (_opts.onDel) _opts.onDel(b, idx)
          else b.remove()
        }
      }
    }
    // 整个批注框可点击：收起态点任意处展开；展开态点击非文字区把光标移回框内（防 Delete/回车落到框外）
    if (!b._annBlockClick) {
      b._annBlockClick = true
      b.addEventListener('click', (e) => {
        e.stopPropagation()   // 不冒泡到编辑区，避免编辑区干扰选区
        if (e.target.closest('.ann-del')) return
        if (!b.classList.contains('open')) {
          b.classList.add('open')
          focusAnnBody(b, opts.editable)
          if (rec && rec.strokes && rec.strokes.length) {
            requestAnimationFrame(() => {
              const cv = ensureDoodleCanvas(b, rec.canvas_w || 100, rec.canvas_h || 100)
              drawStrokes(cv, rec.strokes, rec.canvas_w || 100, rec.canvas_h || 100)
            })
          }
          return
        }
        // 已展开：点击非文字区（空白/画布/页脚）→ 光标移回文字区末尾
        if (!e.target.closest('.ann-body')) {
          focusAnnBody(b, opts.editable)
        }
      })
    }
  })
}
