// ── MathJax 外部化集成 ──
// MathJax 组件化加载与 vite 打包不兼容（TDZ/死锁黑屏），改为运行时从本地 tex-svg.js 加载：
//   - index.html 预置 window.MathJax 配置 + <script src="./mathjax/tex-svg.js">
//   - mathInlinePlugin：markdown-it 插件，$...$ / $$...$$ 用 MathJax.tex2svg 同步渲染成 SVG
//     （tex2svg 为同步 API，不依赖 startup.promise / typesetPromise / 字体，稳定可靠）
//   - typesetMath(el)：备用辅助（渲染后手动触发 typeset，目前渲染器用不到）

/**
 * markdown-it 插件：行内规则匹配 $...$（行内）与 $$...$$（独立显示），
 * 放在 emphasis 规则之前，避免公式内的 * _ 被 markdown 解析破坏。
 */
export function mathInlinePlugin(md) {
  md.inline.ruler.before('emphasis', 'math_inline', (state, silent) => {
    const src = state.src
    if (src[state.pos] !== '$') return false
    let i = state.pos + 1
    let isDisplay = false
    if (src[i] === '$') { isDisplay = true; i++ }
    const contentStart = i
    while (i < src.length && src[i] !== '$') i++
    if (i >= src.length) return false // 无闭合 $，按普通文本
    if (isDisplay) {
      if (src[i + 1] !== '$') return false
      i++
    } else if (src[i + 1] === '$') {
      return false // 这是 $$，交给 display 分支
    }
    const content = src.slice(contentStart, i - (isDisplay ? 1 : 0))
    if (!content.trim()) return false
    if (content.includes('\n') && !isDisplay) return false // 行内公式不允许换行
    if (!silent) {
      const token = state.push('math_inline', 'math', 0)
      token.content = content
      token.meta = { display: isDisplay }
      state.pos = i + (isDisplay ? 2 : 1)
      return true
    }
    return true
  })

  // 渲染规则：tex2svg 同步输出 SVG（失败则回退显示原样公式）
  md.renderer.rules.math_inline = (tokens, idx) => {
    const tex = tokens[idx].content
    const display = !!(tokens[idx].meta && tokens[idx].meta.display)
    try {
      if (window.MathJax && window.MathJax.tex2svg) {
        return window.MathJax.tex2svg(tex, { display }).outerHTML
      }
    } catch (e) { /* fallback */ }
    const esc = tex.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return display
      ? `<div class="math-fallback" style="text-align:center;padding:8px 0;">$$${esc}$$</div>`
      : `<span class="math-fallback">$${esc}$</span>`
  }
}

/** 渲染后触发 MathJax 处理容器内未渲染的公式（备用；当前渲染器用 tex2svg 同步渲染） */
export function typesetMath(el) {
  if (!el || !window.MathJax) return
  const run = () => {
    try {
      if (window.MathJax.typesetPromise) window.MathJax.typesetPromise([el]).catch(() => {})
    } catch (e) { /* 忽略 */ }
  }
  if (window.MathJax.typesetPromise) run()
  else if (window.MathJax.startup && window.MathJax.startup.promise) {
    window.MathJax.startup.promise.then(run).catch(() => {})
  }
}
