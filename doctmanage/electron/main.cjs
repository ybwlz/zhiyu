// 知屿 · Electron 桌面版主进程
// 主进程内起本地 HTTP 服务（127.0.0.1 随机端口）：
//   - 静态文件：dist-electron 产物（module 脚本在 http 下正常执行）
//   - /api、/uploads：代理到本地后端（http://localhost:5000）
//   - /zhiyu/*：前端路由回落 index.html
const { app, BrowserWindow, shell, ipcMain, net, Tray, Menu, nativeImage } = require('electron')
const http = require('http')
const path = require('path')
const fs = require('fs')
const { exec } = require('child_process')

// ── 更新检查：对比服务器 version.json（放 /downloads/version.json） ──
// 注：域名 www.zhiyur.cn 备案通过前会被腾讯云拦截，故更新检查用 IP 直连
const UPDATE_URL = process.env.ZHIYU_UPDATE_URL || 'http://182.254.209.123/downloads/version.json'
function compareVersion(a, b) {
  const pa = String(a).split('.').map(Number)
  const pb = String(b).split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    const x = pa[i] || 0
    const y = pb[i] || 0
    if (x !== y) return x - y
  }
  return 0
}
async function checkForUpdate() {
  try {
    const res = await net.fetch(UPDATE_URL, { cache: 'no-store' })
    if (!res.ok) return null
    const data = await res.json()
    if (data && data.version && compareVersion(data.version, app.getVersion()) > 0) return data
    return null
  } catch (e) {
    return null
  }
}

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

let isQuiting = false
let tray = null
function createTray() {
  try {
    const iconPath = path.join(process.resourcesPath, 'icon.ico')
    tray = new Tray(nativeImage.createFromPath(iconPath))
    tray.setToolTip('知屿')
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: '显示知屿', click: () => { const w = BrowserWindow.getAllWindows()[0]; if (w) { w.show(); w.focus() } } },
      { type: 'separator' },
      { label: '退出', click: () => { isQuiting = true; app.quit() } },
    ]))
    tray.on('click', () => { const w = BrowserWindow.getAllWindows()[0]; if (w) { w.show(); w.focus() } })
  } catch (e) { /* 托盘创建失败不阻塞 */ }
}

// 单实例：二次启动（桌面图标/任务栏）激活已有窗口，固定端口下避免 EADDRINUSE
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const w = BrowserWindow.getAllWindows()[0]
    if (w) { if (w.isMinimized()) w.restore(); w.show(); w.focus() }
  })

app.whenReady().then(() => {
  const server = http.createServer((req, res) => {    const u = new URL(req.url, 'http://127.0.0.1')
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

  // 固定本地端口：origin（含端口）稳定，localStorage 才能跨启动持久（随机端口会导致每次重开掉登录）
  const LOCAL_PORT = 51780
  server.listen(LOCAL_PORT, '127.0.0.1', () => {
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
      // 窗口按钮（- □ ×）由前端绘制（WindowControls），背景完全融入导航栏/主题
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        spellcheck: false,
        preload: require('path').join(__dirname, 'preload.cjs'),
      },
    })
    win.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:/.test(url)) shell.openExternal(url)
      return { action: 'deny' }
    })
    // 前端主题切换 → 更新窗口底色（跟随星空/蓝天/简约主题）
    ipcMain.on('set-titlebar', (e, { color }) => {
      try {
        if (color) win.setBackgroundColor(color)
      } catch (err) { /* 非 Windows 平台忽略 */ }
    })
    // 前端绘制的窗口控制按钮（- □ ×）
    ipcMain.on('window-minimize', () => win.minimize())
    ipcMain.on('window-maximize', () => { if (win.isMaximized()) win.unmaximize(); else win.maximize() })
    ipcMain.on('window-close', () => win.close())
    // 版本与更新检查
    ipcMain.handle('get-app-version', () => app.getVersion())
  // 开机自启动（Windows 登录时自动运行）
  ipcMain.handle('set-auto-launch', (e, enabled) => { app.setLoginItemSettings({ openAtLogin: !!enabled }) })
  ipcMain.handle('get-auto-launch', () => app.getLoginItemSettings().openAtLogin)
    ipcMain.handle('check-update', async () => await checkForUpdate())

    // ── 应用内下载并自动安装更新（支持暂停/继续/取消，断点续传） ──
    let updateState = null // { url, tmpDir, extractDir, zipPath, file, aborter, received, paused, cancelled }
    const sendProgress = (pct, extra = {}) => {
      if (!win.isDestroyed()) win.webContents.send('update-progress', { pct, ...extra })
    }
    const finishUpdate = async () => {
      const s = updateState
      updateState = null
      // 解压 zip
      await new Promise((resolve, reject) => {
        exec(`tar -xf "${s.zipPath}" -C "${s.extractDir}"`, { windowsHide: true }, (err) => (err ? reject(err) : resolve()))
      })
      // 写更新脚本：等退出 → 杀进程 → 覆盖 exe 目录 → 重启
      const appDir = path.dirname(process.execPath)
      const batPath = path.join(appDir, 'update.bat')
      const bat = [
        '@echo off',
        'chcp 65001 >nul',
        'timeout /t 3 /nobreak >nul',
        'taskkill /f /im 知屿.exe >nul 2>&1',
        'timeout /t 2 /nobreak >nul',
        `robocopy "${s.extractDir}" "${appDir}" /E /IS /IT >nul`,
        `start "" "${appDir}\\知屿.exe"`,
        ''
      ].join('\r\n')
      fs.writeFileSync(batPath, '\ufeff' + bat)
      exec(`start "" "${batPath}"`, { windowsHide: true }, () => {})
      sendProgress(100)
      app.quit()
      return { ok: true }
    }
    ipcMain.handle('download-update', async (_e, url) => {
      const target = url || UPDATE_URL
      try {
        // 已暂停 → 从断点续传
        if (updateState && updateState.paused && updateState.url === target) {
          updateState.paused = false
          updateState.aborter = new AbortController()
          const s = updateState
          s.file = fs.createWriteStream(s.zipPath, { flags: 'a' })
          const res = await net.fetch(target, {
            cache: 'no-store', signal: s.aborter.signal,
            headers: s.received > 0 ? { Range: `bytes=${s.received}-` } : {},
          })
          if (!res.ok && res.status !== 206) throw new Error('download failed: ' + res.status)
          const remaining = Number(res.headers.get('content-length')) || 0
          const total = s.received + remaining
          const reader = res.body.getReader()
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            s.file.write(Buffer.from(value))
            s.received += value.length
            sendProgress(Math.round((s.received / total) * 100))
          }
          s.file.end()
          return await finishUpdate()
        }
        // 下载进行中（未暂停）→ 拒绝重复发起
        if (updateState && !updateState.paused) return { ok: false, error: 'download in progress' }
        // 全新下载
        const tmpDir = path.join(require('os').tmpdir(), 'zhiyu-update-' + Date.now())
        const extractDir = path.join(tmpDir, 'app')
        fs.mkdirSync(extractDir, { recursive: true })
        const zipPath = path.join(tmpDir, 'update.zip')
        const aborter = new AbortController()
        updateState = { url: target, tmpDir, extractDir, zipPath, file: fs.createWriteStream(zipPath), aborter, received: 0, paused: false, cancelled: false }
        const res = await net.fetch(target, { cache: 'no-store', signal: aborter.signal })
        if (!res.ok) throw new Error('download failed: ' + res.status)
        const total = Number(res.headers.get('content-length')) || 0
        const reader = res.body.getReader()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          updateState.file.write(Buffer.from(value))
          updateState.received += value.length
          if (total) sendProgress(Math.round((updateState.received / total) * 100))
        }
        updateState.file.end()
        return await finishUpdate()
      } catch (err) {
        // 用户暂停/取消（AbortError）
        if (updateState && (err.name === 'AbortError' || /abort|interrupt/i.test(String(err)))) {
          if (updateState.cancelled) {
            updateState = null
            return { ok: false, cancelled: true }
          }
          updateState.paused = true
          updateState.file.end()
          sendProgress(updateState.received, { paused: true })
          return { ok: false, paused: true, received: updateState.received }
        }
        updateState = null
        return { ok: false, error: String((err && err.message) || err) }
      }
    })
    ipcMain.on('update-pause', () => {
      if (updateState && !updateState.paused && !updateState.cancelled) updateState.aborter.abort()
    })
    ipcMain.on('update-cancel', () => {
      if (updateState) {
        updateState.cancelled = true
        updateState.aborter.abort()
        try { fs.rmSync(updateState.tmpDir, { recursive: true, force: true }) } catch (e) { /* 忽略 */ }
        updateState = null
      }
      if (!win.isDestroyed()) win.webContents.send('update-cancelled')
    })
    // 启动数秒后静默检查更新，有新版本通知前端提示
    setTimeout(async () => {
      const upd = await checkForUpdate()
      if (upd && !win.isDestroyed()) win.webContents.send('update-available', upd)
    }, 8000)
    win.loadURL('http://127.0.0.1:' + port + '/')
    // ── 系统托盘：点 × 隐藏到托盘（菜单栏常驻），托盘菜单可退出 ──
    win.on('close', (e) => {
      if (!isQuiting) { e.preventDefault(); win.hide() }
    })
    createTray()
    ipcMain.on('hide-to-tray', () => { win.hide() })
    ipcMain.on('quit-app', () => { isQuiting = true; app.quit() })
  })
})
} // end single-instance lock

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
