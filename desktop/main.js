/**
 * OpenFox Desktop - Electron 主进程
 * 
 * 职责：
 *  1. 应用生命周期管理（单例锁、启动、退出）
 *  2. Python 后端进程管理（自动启动、健康检查、优雅关闭）
 *  3. 主窗口与启动屏（Splash → Main Window 流程）
 *  4. 系统托盘 + 原生菜单
 *  5. 全局快捷键（Ctrl+Shift+Space 呼出窗口）
 *  6. 开机自启支持
 *  7. 自动更新
 *  8. IPC 通信层
 */

const { app, BrowserWindow, globalShortcut, ipcMain, shell, dialog, Menu } = require('electron')
const path = require('path')
const fs = require('fs')

const { BackendManager } = require('./backend')
const { createTray, updateMenu, destroy: destroyTray } = require('./tray')
const { buildMenu } = require('./menu')
const updater = require('./updater')
const windowState = require('./window-state')

app.setName('OpenFox')

// ============================================================
// 全局状态
// ============================================================

const isDev = process.env.ELECTRON_DEV === 'true' || !app.isPackaged

// 启动屏最短显示时间（毫秒），避免后端秒回时启动屏一闪而过
const SPLASH_MIN_DISPLAY_MS = 1500

let mainWindow = null
let splashWindow = null
let tray = null
let backend = null
let isQuitting = false
let backendLogBuffer = []

// ============================================================
// 单例锁
// ============================================================

const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    // 有人试图运行第二个实例，聚焦到主窗口
    if (mainWindow) {
      if (!mainWindow.isVisible()) mainWindow.show()
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

// ============================================================
// 启动屏
// ============================================================

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 420,
    height: 280,
    frame: false,
    resizable: false,
    center: true,
    show: true,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  })

  splashWindow.__createdAt = Date.now()
  splashWindow.loadFile(path.join(__dirname, 'splash.html'))
  splashWindow.on('closed', () => {
    splashWindow = null
  })
}

/**
 * 关闭启动屏（保证最短显示时间）
 */
function closeSplashIfNeeded() {
  if (!splashWindow) return

  const elapsed = Date.now() - (splashWindow.__createdAt || 0)
  const remaining = SPLASH_MIN_DISPLAY_MS - elapsed

  if (remaining <= 0) {
    splashWindow.close()
    splashWindow = null
  } else {
    setTimeout(() => {
      if (splashWindow) {
        splashWindow.close()
        splashWindow = null
      }
    }, remaining)
  }
}

function sendSplashStatus(data) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.send('splash:status', data)
  }
}

// ============================================================
// 主窗口
// ============================================================

function getRendererUrl() {
  if (isDev) {
    return 'http://localhost:5173'
  }
  // 生产模式：从 resources 目录加载
  const rendererPath = path.join(process.resourcesPath, 'web', 'index.html')
  return `file://${rendererPath}`
}

function createMainWindow() {
  const state = windowState.load()

  mainWindow = new BrowserWindow({
    width: state.width,
    height: state.height,
    x: state.x,
    y: state.y,
    minWidth: 400,
    minHeight: 300,
    show: false,
    title: 'OpenFox',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    backgroundColor: '#f9fafb',
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: !isDev,
    },
  })

  // 最大化状态恢复
  if (state.isMaximized) {
    mainWindow.maximize()
  }

  // 加载前端页面
  const url = getRendererUrl()
  mainWindow.loadURL(url)

  // 窗口准备好后显示
  mainWindow.once('ready-to-show', () => {
    closeSplashIfNeeded()

    // 检查是否需要隐藏启动（开机自启 --hidden 模式）
    const shouldStartHidden = process.argv.includes('--hidden')
    if (!shouldStartHidden) {
      mainWindow.show()
    }
  })

  // 保存窗口状态
  const saveStateDebounced = debounce(() => windowState.save(mainWindow), 500)
  mainWindow.on('resize', saveStateDebounced)
  mainWindow.on('move', saveStateDebounced)
  mainWindow.on('maximize', saveStateDebounced)
  mainWindow.on('unmaximize', saveStateDebounced)

  // 关闭窗口 → 最小化到托盘
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
      
      // 首次最小化到托盘时提示
      const hasShownNotification = app.userData?.trayNotificationShown
      if (!hasShownNotification) {
        if (tray) {
          tray.displayBalloon({
            iconType: 'info',
    title: 'OpenFox',
            content: '应用已最小化到系统托盘，点击托盘图标可恢复窗口。',
          })
        }
        // 标记已提示
        const flagPath = path.join(app.getPath('userData'), 'tray_notified.json')
        fs.writeFileSync(flagPath, '{"shown":true}')
      }
    }
  })

  // 窗口失焦时保存状态
  mainWindow.on('blur', () => {
    windowState.save(mainWindow)
  })

  // 外部链接用系统浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  return mainWindow
}

// ============================================================
// 后端管理
// ============================================================

function initBackend() {
  backend = new BackendManager()

  // 后端日志 → 转发给渲染进程
  backend.onLog = (message, level) => {
    backendLogBuffer.push({ message, level, time: Date.now() })
    if (backendLogBuffer.length > 500) backendLogBuffer.shift()
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:log', { message, level, time: Date.now() })
    }
    // 开发模式下同时打印到控制台
    if (isDev) {
      const prefix = level === 'error' ? '[ERROR]' : level === 'stderr' ? '[STDERR]' : '[LOG]'
      console.log(`${prefix} ${message}`)
    }
  }

  backend.onStatus = (status) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend:status', { status })
    }
    // 映射状态到启动屏
    const splashMap = {
      starting: { text: '正在启动后端服务...', progress: 20 },
      waiting: { text: '等待后端就绪...', progress: 50 },
      running: { text: '后端已就绪，正在加载...', progress: 90 },
      error: { text: '后端启动失败', progress: 100 },
      crashed: { text: '后端崩溃', progress: 100 },
    }
    if (splashMap[status]) {
      sendSplashStatus(splashMap[status])
    }
  }
}

async function startBackend() {
  initBackend()
  const result = await backend.start()
  
  if (result.error) {
    sendSplashStatus({ text: '后端启动失败，请检查环境', progress: 100 })
    
    // 显示错误对话框
    dialog.showErrorBox(
      '后端启动失败',
      'OpenFox 后端服务启动失败。请确保：\n\n1. 已安装 Python 3.10+\n2. 已执行 pip install -e . 安装依赖\n3. 端口 8000 未被占用\n\n错误信息: ' + (result.error || 'Unknown')
    )
    
    // 仍然打开主窗口（用户可以手动重启后端）
    if (!mainWindow) createMainWindow()
    return
  }
  
  return result
}

async function restartBackend() {
  if (!backend) return
  
  sendSplashStatus({ text: '正在重启后端...', progress: 0 })
  
  const result = await backend.restart()
  
  if (mainWindow && !mainWindow.isDestroyed()) {
    dialog.showMessageBox(mainWindow, {
      type: result.error ? 'error' : 'info',
      title: '后端重启',
      message: result.error ? '后端重启失败' : '后端重启成功',
      detail: result.error || '后端服务已恢复运行',
      buttons: ['确定'],
    })
  }
}

// ============================================================
// 全局快捷键
// ============================================================

function registerShortcuts() {
  // Ctrl+Shift+Space → 切换窗口显示/隐藏
  globalShortcut.register('CommandOrControl+Shift+Space', () => {
    if (!mainWindow) return
    
    if (mainWindow.isVisible() && mainWindow.isFocused()) {
      mainWindow.hide()
    } else {
      mainWindow.show()
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  // Ctrl+Shift+N → 新建会话
  globalShortcut.register('CommandOrControl+Shift+N', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
      mainWindow.webContents.send('menu:action', 'new-chat')
    }
  })
}

function unregisterShortcuts() {
  globalShortcut.unregisterAll()
}

// ============================================================
// IPC 处理
// ============================================================

function setupIpc() {
  // === 窗口控制 ===
  ipcMain.on('window:minimize', () => mainWindow?.minimize())
  ipcMain.on('window:maximize', () => mainWindow?.maximize())
  ipcMain.on('window:toggleMaximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) mainWindow.unmaximize()
      else mainWindow.maximize()
    }
  })
  ipcMain.on('window:close', () => mainWindow?.close())
  ipcMain.on('window:hide', () => mainWindow?.hide())
  ipcMain.on('window:show', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })

  ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() || false)

  // === 后端控制 ===
  ipcMain.on('backend:restart', () => restartBackend())
  ipcMain.handle('backend:status', () => {
    if (!backend) return { status: 'unknown' }
    return {
      status: backend.isRunning() ? 'running' : 'stopped',
      port: backend.port,
      host: backend.host,
      isExternal: backend.isExternal,
    }
  })

  // === 应用信息 ===
  ipcMain.handle('app:version', () => app.getVersion())
  ipcMain.handle('app:backend-url', () => `http://${backend?.host || '127.0.0.1'}:${backend?.port || 8000}`)

  // === 更新 ===
  ipcMain.on('update:check', () => updater.checkForUpdates())

  // === 外部链接 ===
  ipcMain.on('shell:open-external', (_, url) => {
    if (typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
      shell.openExternal(url)
    }
  })
  ipcMain.on('shell:open-path', (_, p) => {
    if (typeof p === 'string') shell.openPath(p)
  })

  // === 文件选择对话框 ===
  ipcMain.handle('dialog:select-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    })
    if (result.canceled) return { canceled: true }
    return { canceled: false, path: result.filePaths[0] }
  })
}

// ============================================================
// 工具函数
// ============================================================

function debounce(fn, delay) {
  let timer = null
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

function getProjectPath() {
  if (app.isPackaged) {
    return path.dirname(app.getPath('exe'))
  }
  return path.resolve(__dirname, '..')
}

// ============================================================
// 应用生命周期
// ============================================================

app.whenReady().then(async () => {
  // 1. 显示启动屏
  createSplash()
  sendSplashStatus({ text: '正在初始化...', progress: 10 })

  // 2. 启动后端
  await startBackend()
  sendSplashStatus({ text: '正在加载界面...', progress: 95 })

  // 3. 创建主窗口
  createMainWindow()

  // 4. 设置系统托盘
  const trayCallbacks = {
    onRestartBackend: restartBackend,
    onCheckUpdate: () => updater.checkForUpdates(),
    onQuit: () => {
      isQuitting = true
      app.quit()
    },
  }
  tray = createTray(mainWindow, trayCallbacks)

  // 5. 设置原生菜单
  buildMenu(mainWindow, {
    onRestartBackend: restartBackend,
    onCheckUpdate: () => updater.checkForUpdates(),
    onReloadSkills: () => {
      // 调用后端的 /v1/reload 接口
      const http = require('http')
      const req = http.request(
        `http://${backend?.host || '127.0.0.1'}:${backend?.port || 8000}/v1/reload`,
        { method: 'POST' },
        (res) => {
          res.resume()
          if (mainWindow) {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '重新加载',
              message: 'Skills 和工具已重新加载',
              buttons: ['确定'],
            })
          }
        }
      )
      req.on('error', () => {})
      req.end()
    },
    onReloadTools: () => {
      // 同上
      const http = require('http')
      const req = http.request(
        `http://${backend?.host || '127.0.0.1'}:${backend?.port || 8000}/v1/reload`,
        { method: 'POST' },
        (res) => {
          res.resume()
        }
      )
      req.on('error', () => {})
      req.end()
    },
    getProjectPath: getProjectPath,
    onQuit: () => {
      isQuitting = true
      app.quit()
    },
  })
  // Windows uses the renderer's custom title bar instead of a separate native menu.
  Menu.setApplicationMenu(null)

  // 6. 注册全局快捷键
  registerShortcuts()

  // 7. 设置 IPC
  setupIpc()

  // 8. 初始化自动更新（生产模式，但不自动检查，避免无 Release 时弹窗报错）
  if (!isDev) {
    updater.init(mainWindow)
  }

  // 9. 检查是否已提示过托盘最小化
  try {
    const flagPath = path.join(app.getPath('userData'), 'tray_notified.json')
    if (fs.existsSync(flagPath)) {
      app.userData = app.userData || {}
      app.userData.trayNotificationShown = true
    }
  } catch {
    // ignore
  }
})

// 所有窗口关闭
app.on('window-all-closed', () => {
  // 不退出应用（保持托盘运行）
  // macOS: 保持应用活跃直到显式退出
  // Windows: 窗口已隐藏到托盘
})

// 应用激活（macOS）
app.on('activate', () => {
  if (mainWindow) {
    mainWindow.show()
    mainWindow.focus()
  }
})

// 应用退出前清理
app.on('before-quit', (e) => {
  if (!isQuitting) {
    e.preventDefault()
    isQuitting = true
    app.quit()
    return
  }

  // 终止后端进程
  if (backend) {
    backend.kill()
  }
  // 注销快捷键
  unregisterShortcuts()
  // 销毁托盘
  destroyTray()
})

// 应用将退出
app.on('will-quit', () => {
  unregisterShortcuts()
})

// 安全设置
app.on('web-contents-created', (_, contents) => {
  contents.on('will-attach-webview', (event, webPreferences) => {
    // 禁用 preload 注入
    delete webPreferences.preload
    webPreferences.nodeIntegration = false
  })
})

// 防止导航到外部页面
app.on('web-contents-created', (_, contents) => {
  contents.on('will-navigate', (event, url) => {
    const allowedOrigins = isDev
      ? ['http://localhost:5173']
      : [`file://${path.join(process.resourcesPath, 'web')}`]
    
    const isAllowed = allowedOrigins.some((origin) => url.startsWith(origin))
    if (!isAllowed) {
      event.preventDefault()
    }
  })
})
