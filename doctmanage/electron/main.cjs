// 知屿 · Electron 桌面版主进程
// 主进程内起本地 HTTP 服务（127.0.0.1 随机端口）：
//   - 静态文件：dist-electron 产物（module 脚本在 http 下正常执行）
//   - /api、/uploads：代理到本地后端（http://localhost:5000）
//   - /zhiyu/*：前端路由回落 index.html
const { app, BrowserWindow, shell } = require('electron')
const http = require('http')
const path = require('path')
const fs = require('fs')

// 后端地址优先级：环境变量 ZHIYU_BACKEND > exe 同目录 config.json > 默认云端服务器
// config.json 示例：{ "backend": "http://182.254.209.123" }（切回本地调试改为 http://localhost:5000）
function resolveBackend() {
  if (process.env.ZHIYU_BACKEND) return process.env.ZHIYU_BACKEND
  try {
    const cfgPath = path.join(path.dirname(process.execPath), 'config.json')
    if (fs.existsSync(cfgPath)) {
      const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'))
      if (cfg && typeof cfg.backend === 'string' && cfg.backend) return cfg.backend
    }
  } catch (e) { /* 配置缺失/损坏时使用默认 */ }
  return 'http://182.254.209.123'
}

const BACKEND = resolveBackend()
const DIST = path.join(__dirname, '..', 'dist-electron')
const INDEX_HTML = path.join(DIST, 'index.html')

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.md': 'text/markdown; charset=utf-8',
  '.map': 'application/json',
}

function serveFile(res, file) {
  const ext = path.extname(file).toLowerCase()
  res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream')
  fs.createReadStream(file).on('error', () => {
    res.writeHead(404); res.end('Not Found')
  }).pipe(res)
}

app.whenReady().then(() => {
  const server = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1')
    const p = decodeURIComponent(u.pathname)

    // 1) API 与上传 -> 后端代理（方法/请求体原样转发）
    if (p.startsWith('/api/') || p.startsWith('/uploads/')) {
      const proxy = http.request(BACKEND + p + u.search, {
        method: req.method,
        headers: { ...req.headers, host: new URL(BACKEND).host },
      }, (pres) => {
        res.writeHead(pres.statusCode || 500, pres.headers)
        pres.pipe(res)
      })
      proxy.on('error', () => { res.writeHead(502); res.end('Backend unavailable') })
      req.pipe(proxy)
      return
    }

    // 2) 前端路由（History 模式）-> index.html
    if (p.startsWith('/zhiyu')) {
      res.setHeader('Content-Type', 'text/html; charset=utf-8')
      fs.createReadStream(INDEX_HTML).pipe(res)
      return
    }

    // 3) 静态文件（防目录穿越）
    const rel = p.replace(/^\/+/, '') || 'index.html'
    const target = path.normalize(path.join(DIST, rel))
    if (!target.startsWith(DIST)) { res.writeHead(403); res.end('Forbidden'); return }
    if (!fs.existsSync(target) || fs.statSync(target).isDirectory()) {
      if (p === '/' || p === '') {
        res.setHeader('Content-Type', 'text/html; charset=utf-8')
        fs.createReadStream(INDEX_HTML).pipe(res)
      } else { res.writeHead(404); res.end('Not Found') }
      return
    }
    serveFile(res, target)
  })

  server.listen(0, '127.0.0.1', () => {
    const port = server.address().port
    const win = new BrowserWindow({
      width: 1280,
      height: 860,
      minWidth: 940,
      minHeight: 640,
      autoHideMenuBar: true,
      title: '知屿',
      backgroundColor: '#070b16',
      // 自定义深色标题栏（跟随知屿星空主题，Windows 10+ 生效）
      titleBarStyle: 'hidden',
      titleBarOverlay: {
        color: '#070b16',
        symbolColor: '#e8ecf8',
        height: 40,
      },
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        spellcheck: false,
      },
    })
    win.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:/.test(url)) shell.openExternal(url)
      return { action: 'deny' }
    })
    win.loadURL('http://127.0.0.1:' + port + '/')
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
