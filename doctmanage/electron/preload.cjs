// 知屿 Electron preload：暴露标题栏/窗口控制/更新检查给渲染进程
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  // 主题切换时同步窗口底色（跟随星空/蓝天/简约主题）
  setTitleBarColor: (color) => {
    ipcRenderer.send('set-titlebar', { color })
  },
  // 前端绘制的窗口控制按钮（- □ ×）
  windowControls: {
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),
  },
  // 版本与更新检查
  appVersion: () => ipcRenderer.invoke('get-app-version'),
  // 开机自启动
  setAutoLaunch: (enabled) => ipcRenderer.invoke('set-auto-launch', enabled),
  getAutoLaunch: () => ipcRenderer.invoke('get-auto-launch'),
  checkUpdate: () => ipcRenderer.invoke('check-update'),
  onUpdateAvailable: (cb) => {
    ipcRenderer.on('update-available', (_e, data) => cb(data))
  },
  // 应用内下载并自动安装更新（支持暂停/继续/取消）
  downloadUpdate: (url) => ipcRenderer.invoke('download-update', url),
  pauseUpdate: () => ipcRenderer.send('update-pause'),
  cancelUpdate: () => ipcRenderer.send('update-cancel'),
  onUpdateProgress: (cb) => {
    ipcRenderer.on('update-progress', (_e, data) => cb(data))
  },
  onUpdateCancelled: (cb) => {
    ipcRenderer.on('update-cancelled', () => cb())
  },
})
