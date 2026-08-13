// 知屿 Electron preload：暴露标题栏/窗口控制给渲染进程
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
})
