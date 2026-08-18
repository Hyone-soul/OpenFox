/**
 * Auto Updater - 自动更新模块
 * 
 * 使用 electron-updater 实现自动检查更新和安装
 * 支持 GitHub Releases 或自定义更新服务器
 */

const { autoUpdater } = require('electron-updater')
const { dialog } = require('electron')

let mainWindow = null

/**
 * 初始化自动更新
 * @param {Electron.BrowserWindow} win - 主窗口
 */
function init(win) {
  mainWindow = win

  // 配置
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  // 事件监听
  autoUpdater.on('checking-for-update', () => {
    sendStatus('checking-for-update')
  })

  autoUpdater.on('update-available', (info) => {
    sendStatus('update-available', info)
    dialog
      .showMessageBox(mainWindow, {
        type: 'info',
        title: '发现新版本',
        message: `发现新版本 ${info.version}`,
        detail: `当前版本: ${autoUpdater.currentVersion}\n\n是否立即下载更新？`,
        buttons: ['立即下载', '稍后提醒'],
        defaultId: 0,
      })
      .then((result) => {
        if (result.response === 0) {
          autoUpdater.downloadUpdate()
        }
      })
  })

  autoUpdater.on('update-not-available', (info) => {
    sendStatus('update-not-available', info)
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      title: '已是最新版本',
      message: '当前已是最新版本',
      detail: `版本: ${autoUpdater.currentVersion}`,
      buttons: ['确定'],
    })
  })

  autoUpdater.on('download-progress', (progress) => {
    sendStatus('download-progress', {
      percent: progress.percent,
      speed: progress.bytesPerSecond,
      transferred: progress.transferred,
      total: progress.total,
    })
    // 更新托盘 tooltip
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('update:progress', progress.percent)
    }
  })

  autoUpdater.on('update-downloaded', (info) => {
    sendStatus('update-downloaded', info)
    dialog
      .showMessageBox(mainWindow, {
        type: 'info',
        title: '更新已下载',
        message: '更新已下载完成',
        detail: `新版本 ${info.version} 已准备就绪\n\n点击"立即安装"将关闭应用并安装更新`,
        buttons: ['立即安装', '稍后安装'],
        defaultId: 0,
      })
      .then((result) => {
        if (result.response === 0) {
          autoUpdater.quitAndInstall()
        }
      })
  })

  autoUpdater.on('error', (err) => {
    sendStatus('error', { message: err.message })
  })
}

/**
 * 手动检查更新（静默处理错误，不弹窗打扰用户）
 */
function checkForUpdates() {
  if (mainWindow) {
    autoUpdater.checkForUpdates().catch(() => {
      // 静默忽略：未配置 Release 仓库时不出弹窗
    })
  }
}

/**
 * 向渲染进程发送更新状态
 */
function sendStatus(status, data) {
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('update:status', { status, data })
  }
}

module.exports = { init, checkForUpdates }
