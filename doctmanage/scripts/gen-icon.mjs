// 用 favicon.svg 生成多尺寸 .ico（electron-packager 用）
import sharp from 'sharp'
import pngToIco from 'png-to-ico'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const svg = path.join(root, 'public', 'favicon.svg')
const outIco = path.join(root, 'electron', 'icon.ico')

// 生成多个尺寸 PNG
const sizes = [16, 24, 32, 48, 64, 128, 256]
const pngs = []
for (const s of sizes) {
  const buf = await sharp(svg).resize(s, s).png().toBuffer()
  pngs.push(buf)
  console.log('  PNG %dx%d ok', s, s)
}

const ico = await pngToIco(pngs)
fs.writeFileSync(outIco, ico)
console.log('ICO 已生成:', outIco, fs.statSync(outIco).size, 'bytes')
