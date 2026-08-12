// 压缩 SAC 截图：缩到 800px 宽 + 转 webp（减小体积、加快加载）
import sharp from 'sharp'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const dir = path.join(path.dirname(path.dirname(fileURLToPath(import.meta.url))), 'public', 'sacl-guide')

for (let i = 1; i <= 4; i++) {
  const src = path.join(dir, `sacl-${i}.png`)
  const out = path.join(dir, `sacl-${i}.webp`)
  const buf = await sharp(src).resize({ width: 800, withoutEnlargement: true }).webp({ quality: 72 }).toBuffer()
  fs.writeFileSync(out, buf)
  const before = fs.statSync(src).size
  console.log(`sacl-${i}: ${(before / 1024).toFixed(0)}KB -> ${(buf.length / 1024).toFixed(0)}KB webp`)
}
console.log('完成')
