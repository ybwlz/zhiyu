// 笔记文本工具：把 LaTeX 公式转成可读文字 + markdown 清洗（广场预览 / 精选卡片共用）
const GREEK = { alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', theta: 'θ', lambda: 'λ', mu: 'μ', pi: 'π', sigma: 'σ', tau: 'τ', phi: 'φ', omega: 'ω', psi: 'ψ', xi: 'ξ', eta: 'η', epsilon: 'ε', zeta: 'ζ', rho: 'ρ', Delta: 'Δ', Sigma: 'Σ', Pi: 'Π', Omega: 'Ω', Alpha: 'Α', Beta: 'Β', Gamma: 'Γ', Theta: 'Θ', Lambda: 'Λ', Phi: 'Φ', Psi: 'Ψ' }
const SYM = { cdot: '·', times: '×', div: '÷', pm: '±', mp: '∓', sqrt: '√', infty: '∞', le: '≤', ge: '≥', gt: '>', lt: '<', neq: '≠', approx: '≈', equiv: '≡', in: '∈', notin: '∉', subset: '⊂', subseteq: '⊆', cup: '∪', cap: '∩', forall: '∀', exists: '∃', rightarrow: '→', leftarrow: '←', Rightarrow: '⇒', Leftarrow: '⇐', iff: '⇔', to: '→', mapsto: '↦', dots: '…', ldots: '…', cdots: '…', angle: '∠', perp: '⊥', parallel: '∥', sum: 'Σ', prod: '∏', int: '∫', iint: '∬', iiint: '∭', oint: '∮', oiint: '∮', partial: '∂', nabla: '∇', sim: '~', mid: '|', prime: "'", circ: '°', lim: 'lim', max: 'max', min: 'min', sin: 'sin', cos: 'cos', tan: 'tan', cot: 'cot', sec: 'sec', csc: 'csc', arcsin: 'arcsin', arccos: 'arccos', arctan: 'arctan', log: 'log', ln: 'ln', mathbf: '', mathbb: '', mathrm: '', bm: '', displaystyle: '', text: '', left: '', right: '', big: '', Big: '', bigg: '', Bigg: '', overline: '', bar: '', vec: '', hat: '', widehat: '', widebar: '', tilde: '', widetilde: '' }
const SUP = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '=': '⁼', 'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ' }
const SUB = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', '=': '₌', 'a': 'ₐ', 'e': 'ₑ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ', 'r': 'ᵣ', 't': 'ₜ', 'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ' }
const sup = (d) => d.split('').map(c => SUP[c] || c).join('')
const sub = (d) => d.split('').map(c => SUB[c] || c).join('')

// LaTeX → 可读文字（预览用）
export const texToText = (tex) => tex
  .replace(/\\d?frac\{((?:[^{}]|\{[^{}]*\})+)\}\{((?:[^{}]|\{[^{}]*\})+)\}/g, (m, a, b) => '(' + a + ')/(' + b + ')')
  .replace(/\\sqrt\{([^{}]+)\}/g, '√($1)')
  .replace(/\\begin\{[a-zA-Z*]+\}/g, ' ')
  .replace(/\\end\{[a-zA-Z*]+\}/g, ' ')
  .replace(/\\\\/g, ' ')
  .replace(/\\,/g, ' ')
  .replace(/\\([a-zA-Z]+)/g, (m, name) => GREEK.hasOwnProperty(name) ? GREEK[name] : (SYM.hasOwnProperty(name) ? SYM[name] : name))
  .replace(/\{|\}/g, '')
  .replace(/\^\{?([\w+=\-]+)\}?/g, (m, d) => sup(d))
  .replace(/_\{?([\w+=\-]+)\}?/g, (m, d) => sub(d))
  .replace(/&/g, ' ')
  .replace(/\\/g, '')
  .trim()

// markdown + 公式清洗 → 可读纯文本（压成单行）
export const cleanText = (content) => String(content || '')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')            // 图片
  .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')           // 链接 → 文字
  .replace(/\$\$([\s\S]+?)\$\$|\$([^$\n]+)\$/g, (m, a, b) => ' ' + texToText(a || b) + ' ') // 公式转文字
  .replace(/[#*_`>|~]/g, ' ')                        // markdown 符号
  .replace(/-{2,}/g, ' ')                            // 分隔线
  .replace(/\[[\s\S]*?\]/g, ' ')                     // 残留括号语法
  .replace(/\s+/g, ' ')
  .trim()
