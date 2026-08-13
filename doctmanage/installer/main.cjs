// 知屿自绘安装器 - 主进程
// 功能：毛玻璃窗口、欢迎页、选主题、安装（复制绿色版+快捷方式+开机自启）、进度、完成
const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const fsp = fs.promises
const { execFile } = require('child_process')
const os = require('os')

const isDev = !app.isPackaged
// 绿色版所在位置：打包后 extraResource 会放到 resources/知屿-win32-x64
function greenDir() {
  if (isDev) return path.join(__dirname, '..', '..', '..', 'doctmanage', 'release', '知屿-win32-x64')
  return path.join(process.resourcesPath, '知屿-win32-x64')
}

function createWindow() {
  const win = new BrowserWindow({
    width: 860, height: 600,
    minWidth: 720, minHeight: 520,
    frame: false,               // 无边框（自绘标题栏/关闭按钮）
    transparent: true,          // 透明窗口（配合 CSS backdrop-filter 做毛玻璃）
    backgroundColor: '#00000000',
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'))
  return win
}

app.whenReady().then(() => {
  const win = createWindow()
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
})

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })

// ── 窗口控制 ──
ipcMain.on('win-minimize', () => BrowserWindow.getFocusedWindow()?.minimize())
ipcMain.on('win-close', () => BrowserWindow.getFocusedWindow()?.close())
ipcMain.on('win-toggle-max', () => {
  const w = BrowserWindow.getFocusedWindow()
  if (!w) return
  if (w.isMaximized()) w.unmaximize(); else w.maximize()
})

// ── 获取安装默认目录（用户级 LOCALAPPDATA，无需管理员权限） ──
ipcMain.handle('get-default-dir', () => {
  const dir = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), '知屿')
  const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0]
  if (win) win.__defaultDir = dir
  return dir
})

// ── 浏览选择安装目录 ──
ipcMain.handle('choose-dir', async () => {
  const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0]
  const r = await dialog.showOpenDialog(win, {
    title: '选择安装位置',
    properties: ['openDirectory', 'createDirectory'],
    defaultPath: (win && win.__defaultDir) || undefined,
  })
  if (r.canceled || !r.filePaths.length) return null
  const dir = r.filePaths[0]
  if (win) win.__defaultDir = dir
  return dir
})

// ── 开始安装 ──
// payload: { targetDir, theme, autoStart, createShortcut }
ipcMain.handle('install', async (e, payload) => {
  const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0]
  const send = (stage, pct, msg) => win.webContents.send('install-progress', { stage, pct, msg })
  try {
    const src = greenDir()
    const target = payload.targetDir
    if (!fs.existsSync(src)) throw new Error('安装资源缺失：' + src)

    // 1. 创建目标目录
    send('copy', 5, '准备安装目录…')
    await fsp.mkdir(target, { recursive: true })

    // 2. 复制绿色版（逐文件带进度）
    send('copy', 8, '正在复制文件…')
    const allFiles = []
    ;(function walk(d) {
      for (const f of fs.readdirSync(d)) {
        const fp = path.join(d, f)
        const st = fs.statSync(fp)
        if (st.isDirectory()) walk(fp)
        else allFiles.push(fp)
      }
    })(src)
    const total = allFiles.length
    let done = 0
    let skipped = 0
    for (const fp of allFiles) {
      const rel = path.relative(src, fp)
      const dest = path.join(target, rel)
      try {
        await fsp.mkdir(path.dirname(dest), { recursive: true })
        await fsp.copyFile(fp, dest)
      } catch (err) {
        // 个别文件复制失败（如符号链接/路径异常）不中断安装
        skipped++
        try { if (fs.existsSync(dest)) fs.rmSync(dest, { force: true }) } catch (e) { /* 忽略 */ }
      }
      done++
      const pct = 8 + Math.round((done / total) * 62) // 8% → 70%
      if (done % 50 === 0 || done === total) send('copy', pct, `正在复制文件… ${done}/${total}`)
    }

    // 3. 主题写入本地配置（桌面端启动读取）
    send('copy', 72, '写入主题配置…')
    const confDir = path.join(app.getPath('appData'), 'zhiyu')
    await fsp.mkdir(confDir, { recursive: true })
    const confFile = path.join(confDir, 'config.json')
    let conf = {}
    try { conf = JSON.parse(await fsp.readFile(confFile, 'utf-8')) } catch (e) { /* 首次 */ }
    conf.theme = payload.theme || 'starlight'
    await fsp.writeFile(confFile, JSON.stringify(conf, null, 2))

    // 4. 创建桌面快捷方式
    if (payload.createShortcut !== false) {
      send('copy', 78, '创建桌面快捷方式…')
      const desktop = path.join(os.homedir(), 'Desktop')
      const exe = path.join(target, '知屿.exe')
      const lnk = path.join(desktop, '知屿.lnk')
      await createShortcut(exe, lnk, target)
    }

    // 5. 开机自启动（注册表 HKCU Run）
    if (payload.autoStart) {
      send('copy', 86, '设置开机自启动…')
      await setAutoStart(path.join(target, '知屿.exe'))
    }

    send('copy', 95, '完成安装配置…')
    await new Promise(r => setTimeout(r, 300))
    send('done', 100, '安装完成')
    return { ok: true, target }
  } catch (err) {
    send('error', 0, String(err && err.message || err))
    return { ok: false, error: String(err && err.message || err) }
  }
})

// ── 创建 .lnk 快捷方式（PowerShell WScript.Shell） ──
function createShortcut(exe, lnk, workDir) {
  return new Promise((resolve, reject) => {
    const ps = [
      '$ws = New-Object -ComObject WScript.Shell',
      `$s = $ws.CreateShortcut('${lnk.replace(/'/g, "''")}')`,
      `$s.TargetPath = '${exe.replace(/'/g, "''")}'`,
      `$s.WorkingDirectory = '${(workDir || path.dirname(exe)).replace(/'/g, "''")}'`,
      `$s.Description = '知屿 - 个人知识库'`,
      `$s.Save()`,
    ].join('; ')
    execFile('powershell.exe', ['-NoProfile', '-Command', ps], (err) => err ? reject(err) : resolve())
  })
}

// ── 开机自启动（注册表 HKCU Run） ──
function setAutoStart(exe) {
  return new Promise((resolve, reject) => {
    execFile('reg', ['add', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run', '/v', '知屿', '/t', 'REG_SZ', '/d', `"${exe}"`, '/f'],
      (err) => err ? reject(err) : resolve())
  })
}

// ── 安装完成：启动知屿（可选） ──
ipcMain.handle('launch-app', (e, targetDir) => {
  const exe = path.join(targetDir, '知屿.exe')
  if (fs.existsSync(exe)) execFile(exe, [], { detached: true, stdio: 'ignore' }).unref()
  return true
})
