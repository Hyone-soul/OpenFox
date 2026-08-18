/**
 * System Tray - 系统托盘
 * 
 * 提供最小化到托盘、快捷操作菜单
 */

const { Tray, Menu, nativeImage, app } = require('electron')
const path = require('path')

let tray = null

/**
 * 创建系统托盘
 * @param {Electron.BrowserWindow} mainWindow - 主窗口
 * @param {object} callbacks - 回调函数
 */
function createTray(mainWindow, callbacks = {}) {
  const iconPath = path.join(__dirname, 'assets', 'icon.png')
  let icon = nativeImage.createFromPath(iconPath)
  
  // 托盘图标使用小尺寸
  icon = icon.resize({ width: 32, height: 32 })

  tray = new Tray(icon)
  tray.setToolTip('OpenFox - Agent Skills Framework')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        mainWindow.show()
        if (mainWindow.isMinimized()) {
          mainWindow.restore()
        }
        mainWindow.focus()
      },
    },
    {
      label: '新建会话',
      click: () => {
        mainWindow.show()
        mainWindow.focus()
        mainWindow.webContents.send('menu:action', 'new-chat')
      },
    },
    { type: 'separator' },
    {
      label: '重启后端',
      click: () => {
        if (callbacks.onRestartBackend) callbacks.onRestartBackend()
      },
    },
    {
      label: '检查更新',
      click: () => {
        if (callbacks.onCheckUpdate) callbacks.onCheckUpdate()
      },
    },
    { type: 'separator' },
    {
      label: '开机自启',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (menuItem) => {
        app.setLoginItemSettings({
          openAtLogin: menuItem.checked,
          args: ['--hidden'],
        })
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        if (callbacks.onQuit) callbacks.onQuit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  // 点击托盘图标显示窗口
  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      if (mainWindow.isFocused()) {
        mainWindow.hide()
      } else {
        mainWindow.focus()
      }
    } else {
      mainWindow.show()
      mainWindow.focus()
    }
  })

  // 双击托盘图标
  tray.on('double-click', () => {
    mainWindow.show()
    if (mainWindow.isMinimized()) {
      mainWindow.restore()
    }
    mainWindow.focus()
  })

  return tray
}

/**
 * 更新托盘菜单（用于更新开机自启状态）
 */
function updateMenu(mainWindow, callbacks = {}) {
  if (!tray) return
  // 重新创建菜单
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        mainWindow.show()
        if (mainWindow.isMinimized()) mainWindow.restore()
        mainWindow.focus()
      },
    },
    {
      label: '新建会话',
      click: () => {
        mainWindow.show()
        mainWindow.focus()
        mainWindow.webContents.send('menu:action', 'new-chat')
      },
    },
    { type: 'separator' },
    {
      label: '重启后端',
      click: () => callbacks.onRestartBackend?.(),
    },
    {
      label: '检查更新',
      click: () => callbacks.onCheckUpdate?.(),
    },
    { type: 'separator' },
    {
      label: '开机自启',
      type: 'checkbox',
      checked: app.getLoginItemSettings().openAtLogin,
      click: (menuItem) => {
        app.setLoginItemSettings({
          openAtLogin: menuItem.checked,
          args: ['--hidden'],
        })
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => callbacks.onQuit?.(),
    },
  ])
  tray.setContextMenu(contextMenu)
}

function destroy() {
  if (tray) {
    tray.destroy()
    tray = null
  }
}

module.exports = { createTray, updateMenu, destroy }
