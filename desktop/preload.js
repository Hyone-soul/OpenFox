/**
 * Preload Script - 预加载脚本
 * 
 * 在渲染进程（Vue 前端）中暴露安全的 Electron API
 * 通过 contextBridge 限制只暴露必要的接口
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // 环境标识
  isElectron: true,
  platform: process.platform,

  // === 窗口控制 ===
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
  hide: () => ipcRenderer.send('window:hide'),
  show: () => ipcRenderer.send('window:show'),
  toggleMaximize: () => ipcRenderer.send('window:toggleMaximize'),

  // === 后端控制 ===
  restartBackend: () => ipcRenderer.send('backend:restart'),
  getBackendStatus: () => ipcRenderer.invoke('backend:status'),

  // === 应用信息 ===
  getVersion: () => ipcRenderer.invoke('app:version'),
  getBackendUrl: () => ipcRenderer.invoke('app:backend-url'),

  // === 更新 ===
  checkUpdate: () => ipcRenderer.send('update:check'),
  onUpdateStatus: (callback) => ipcRenderer.on('update:status', (_, data) => callback(data)),
  onUpdateProgress: (callback) => ipcRenderer.on('update:progress', (_, data) => callback(data)),

  // === 菜单事件 ===
  onMenuAction: (callback) => ipcRenderer.on('menu:action', (_, action) => callback(action)),
  onMenuNavigate: (callback) => ipcRenderer.on('menu:navigate', (_, path) => callback(path)),

  // === 后端日志 ===
  onBackendLog: (callback) => ipcRenderer.on('backend:log', (_, data) => callback(data)),
  onBackendStatus: (callback) => ipcRenderer.on('backend:status', (_, data) => callback(data)),

  // === 外部链接 ===
  openExternal: (url) => ipcRenderer.send('shell:open-external', url),
  openPath: (p) => ipcRenderer.send('shell:open-path', p),

  // === 文件选择对话框 ===
  selectDirectory: () => ipcRenderer.invoke('dialog:select-directory'),

  // === 系统信息 ===
  isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
})
