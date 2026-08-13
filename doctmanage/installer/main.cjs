// 知屿自绘安装器 - 主进程
// 功能：毛玻璃窗口、欢迎页、选主题、安装（复制绿色版+快捷方式+开机自启）、进度、完成
const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const fsp = fs.promises
const { execFile } = require('child_process')
const os = require('os')

const isDev = !app.isPackaged
// 卸载模式：--uninstall 参数，或 exe 文件名含「卸载」（双击 知屿卸载.exe 直接进卸载界面）
const isUninstallMode = process.argv.includes('--uninstall') || path.basename(process.execPath).includes('卸载')
// 卸载键（HKCU + HKLM 都查/写，兼容管理员安装）
const UNINST_KEY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\知屿'
function regQueryString(subKey, name) {
  return new Promise((resolve) => {
    execFile('reg', ['query', subKey, '/v', name], (err, stdout) => {
      if (err) return resolve('')
      const m = stdout.match(/REG_SZ\s+(.+)/)
      resolve(m ? m[1].trim() : '')
    })
  })
}
// 已安装信息：读注册表 InstallLocation（用户安装根目录）
async function getInstalled() {
  for (const hive of ['HKCU', 'HKLM']) {
    const key = hive + '\\' + UNINST_KEY
    const root = await regQueryString(key, 'InstallLocation')
    if (root && fs.existsSync(path.join(root, '知屿', '知屿.exe'))) {
      return { installed: true, root, appDir: path.join(root, '知屿'), uninstallDir: path.join(root, '卸载器') }
    }
  }
  return { installed: false }
}
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
  // --finalize：卸载收尾进程（临时副本）——静默删除整个安装目录（含卸载器自身）+ 临时副本后退出
  if (process.argv.includes('--finalize')) {
    const rootArg = process.argv.find(a => a.startsWith('--root='))
    setTimeout(() => {
      try { if (rootArg) fs.rmSync(rootArg.slice(7), { recursive: true, force: true }) } catch (e) { /* 忽略 */ }
      try { fs.rmSync(process.execPath, { force: true }) } catch (e) { /* 忽略 */ }
      app.exit(0)
    }, 1200)
    return
  }
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
    // 二级目录结构：<root>\知屿\（主程序）+ <root>\卸载器\（卸载入口）
    const root = payload.targetDir
    const target = path.join(root, '知屿')
    const uninstallDir = path.join(root, '卸载器')
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
      if (done % 100 === 0 || done === total) send('copy', pct, '正在安装核心组件…')
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

    // 6. 卸载入口：复制安装器完整运行文件（exe + dll + resources，排除绿色版）→ <root>\卸载器\
    //    统一命名为「知屿卸载.exe」（不复制原「知屿安装器.exe」，避免同文件两份）
    send('copy', 90, '创建卸载入口…')
    try {
      await fsp.mkdir(uninstallDir, { recursive: true })
      const selfName = path.basename(process.execPath)
      await fsp.cp(path.dirname(process.execPath), uninstallDir, {
        recursive: true,
        force: true,
        filter: (src) => !src.includes('知屿-win32-x64') && path.basename(src) !== selfName,
      })
      await fsp.copyFile(process.execPath, path.join(uninstallDir, '知屿卸载.exe'))
    } catch (e) { /* 复制失败不中断 */ }

    // 7. 注册卸载信息（控制面板「程序和功能」可卸载）
    await registerUninstall(root, target, uninstallDir)

    send('copy', 95, '完成安装配置…')
    await new Promise(r => setTimeout(r, 300))
    send('done', 100, '安装完成')
    return { ok: true, target: root }
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

// ── 安装完成：启动知屿（可选，exe 在 <root>\知屿\ 子目录） ──
ipcMain.handle('launch-app', (e, root) => {
  const exe = path.join(root, '知屿', '知屿.exe')
  if (fs.existsSync(exe)) execFile(exe, [], { detached: true, stdio: 'ignore' }).unref()
  return true
})

// ── 注册卸载信息（控制面板「程序和功能」） ──
function registerUninstall(root, appDir, uninstallDir) {
  const uninstaller = path.join(uninstallDir, '知屿卸载.exe')
  const run = (args) => new Promise(r => execFile('reg', args, () => r()))
  return Promise.all([
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'DisplayName', '/t', 'REG_SZ', '/d', '知屿']),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'DisplayVersion', '/t', 'REG_SZ', '/d', '1.2.0']),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'Publisher', '/t', 'REG_SZ', '/d', '知屿']),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'DisplayIcon', '/t', 'REG_SZ', '/d', path.join(appDir, '知屿.exe') + ',0']),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'InstallLocation', '/t', 'REG_SZ', '/d', root]),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'UninstallString', '/t', 'REG_SZ', '/d', '"' + uninstaller + '" --uninstall']),
    run(['add', 'HKCU\\' + UNINST_KEY, '/f', '/v', 'EstimatedSize', '/t', 'REG_DWORD', '/d', '220000']),
  ])
}

// ── 卸载：删除主程序目录/快捷方式/注册表/开机自启（卸载器目录最后自删） ──
ipcMain.handle('uninstall', async (e, { root }) => {
  const win = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0]
  const send = (stage, pct, msg) => win && win.webContents.send('install-progress', { stage, pct, msg })
  try {
    send('uninstall', 10, '结束知屿进程…')
    execFile('taskkill', ['/f', '/im', '知屿.exe'], () => {})
    execFile('reg', ['delete', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run', '/v', '知屿', '/f'], () => {})
    await new Promise(r => setTimeout(r, 600))

    // 删除桌面快捷方式（用户桌面 + 公共桌面）
    send('uninstall', 30, '删除快捷方式…')
    for (const dir of [path.join(os.homedir(), 'Desktop'), path.join(process.env.PUBLIC || 'C:\\Users\\Public', 'Desktop')]) {
      try { const p = path.join(dir, '知屿.lnk'); if (fs.existsSync(p)) fs.rmSync(p, { force: true }) } catch (e) { /* 忽略 */ }
    }

    // 删除注册表卸载项
    send('uninstall', 45, '删除注册表项…')
    execFile('reg', ['delete', 'HKCU\\' + UNINST_KEY, '/f'], () => {})
    execFile('reg', ['delete', 'HKLM\\' + UNINST_KEY, '/f'], () => {})

    // 删除主程序目录
    send('uninstall', 60, '删除安装目录…')
    if (root) { try { fs.rmSync(path.join(root, '知屿'), { recursive: true, force: true }) } catch (e) { /* 忽略 */ } }

    send('uninstall', 90, '清理完成')
    await new Promise(r => setTimeout(r, 250))
    send('done', 100, '已卸载')
    return { ok: true }
  } catch (err) {
    send('error', 0, String(err && err.message || err))
    return { ok: false, error: String(err && err.message || err) }
  }
})

// ── 卸载收尾：复制自己到临时目录，静默删除整个安装目录（含卸载器自身）后退出 ──
ipcMain.handle('finish-uninstall', async (e, { root }) => {
  try {
    const tmp = path.join(os.tmpdir(), 'zhiyu-uninstall-tmp.exe')
    await fsp.copyFile(process.execPath, tmp)
    execFile(tmp, ['--finalize', '--root=' + root], { detached: true, stdio: 'ignore' }).unref()
  } catch (e) { /* 忽略 */ }
  app.exit(0)
})

// ── 已安装检测 / 卸载模式 ──
ipcMain.handle('get-installed', () => getInstalled())
ipcMain.handle('is-uninstall-mode', () => isUninstallMode)
