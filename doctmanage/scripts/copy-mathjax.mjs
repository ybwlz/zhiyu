// 复制 node_modules/mathjax/es5 → public/mathjax（MathJax 运行时资源，不参与 vite 打包）
// 由 predev / prebuild 自动执行，保证克隆项目后 dev/build 即有完整 MathJax 资源
import { cpSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const src = path.join(root, 'node_modules', 'mathjax', 'es5')
const dst = path.join(root, 'public', 'mathjax')

if (existsSync(src)) {
  cpSync(src, dst, { recursive: true, force: true })
  console.log('[copy-mathjax] 已复制 MathJax 运行时资源到 public/mathjax')
} else {
  console.warn('[copy-mathjax] node_modules/mathjax 不存在，跳过（请先 npm install）')
}
