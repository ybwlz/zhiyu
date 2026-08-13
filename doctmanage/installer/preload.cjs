// 知屿自绘安装器 - preload
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('installer', {
  minimize: () => ipcRenderer.send('win-minimize'),
  close: () => ipcRenderer.send('win-close'),
  toggleMax: () => ipcRenderer.send('win-toggle-max'),
  getDefaultDir: () => ipcRenderer.invoke('get-default-dir'),
  chooseDir: () => ipcRenderer.invoke('choose-dir'),
  install: (payload) => ipcRenderer.invoke('install', payload),
  launchApp: (dir) => ipcRenderer.invoke('launch-app', dir),
  onProgress: (cb) => ipcRenderer.on('install-progress', (_e, d) => cb(d)),
})
