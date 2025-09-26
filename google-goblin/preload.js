const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  createAccount: (data) => ipcRenderer.invoke('create-account', data),
  getHistory: () => ipcRenderer.invoke('get-history'),
  exportHistory: () => ipcRenderer.invoke('export-history'),
  nukeData: () => ipcRenderer.invoke('nuke-data'),
  onProgress: (callback) => ipcRenderer.on('progress-update', callback)
});