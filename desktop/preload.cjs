const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('frameGetDesktop', Object.freeze({
  chooseDirectory: () => ipcRenderer.invoke('desktop:choose-directory'),
  currentDirectory: () => ipcRenderer.invoke('desktop:save-directory'),
  saveFiles: (files, overwriteMode) => ipcRenderer.invoke('desktop:save-files', files, overwriteMode),
  revealFile: (absolutePath) => ipcRenderer.invoke('desktop:reveal-file', absolutePath),
}));
