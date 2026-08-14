// 知屿卸载页 preload：暴露卸载窗口控制与卸载动作给渲染进程
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('uninstaller', {
  minimize: () => ipcRenderer.send('uninstall-minimize'),
  close: () => ipcRenderer.send('uninstall-close'),
  getRoot: () => ipcRenderer.invoke('uninstall-get-root'),
  uninstall: (payload) => ipcRenderer.invoke('uninstall-do', payload),
  finishUninstall: () => ipcRenderer.send('uninstall-finish'),
  openWeb: (url) => ipcRenderer.invoke('uninstall-open-web', url),
})
