/**
 * Native Menu - 原生应用菜单
 * 
 * 提供标准的 Windows/macOS 应用菜单栏
 */

const { Menu, app, shell, dialog } = require('electron')
const path = require('path')

/**
 * 构建应用菜单
 * @param {Electron.BrowserWindow} mainWindow - 主窗口
 * @param {object} callbacks - 回调函数
 */
function buildMenu(mainWindow, callbacks = {}) {
  const isMac = process.platform === 'darwin'

  const template = [
    // App 菜单 (macOS)
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: 'about', label: '关于 OpenFox' },
              { type: 'separator' },
              {
                label: '开机自启',
                type: 'checkbox',
                checked: app.getLoginItemSettings().openAtLogin,
                click: (item) => {
                  app.setLoginItemSettings({
                    openAtLogin: item.checked,
                    args: ['--hidden'],
                  })
                },
              },
              { type: 'separator' },
              { role: 'services' },
              { type: 'separator' },
              { role: 'hide' },
              { role: 'hideOthers' },
              { role: 'unhide' },
              { type: 'separator' },
              { role: 'quit', label: '退出 OpenFox' },
            ],
          },
        ]
      : []),

    // 文件菜单
    {
      label: '文件',
      submenu: [
        {
          label: '新建会话',
          accelerator: 'CmdOrCtrl+N',
          click: () => mainWindow.webContents.send('menu:action', 'new-chat'),
        },
        { type: 'separator' },
        {
          label: '关闭窗口',
          accelerator: 'CmdOrCtrl+W',
          click: () => mainWindow.hide(),
        },
        ...(isMac
          ? []
          : [
              { type: 'separator' },
              {
                label: '退出',
                accelerator: 'CmdOrCtrl+Q',
                click: () => callbacks.onQuit?.(),
              },
            ]),
      ],
    },

    // 编辑菜单
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' },
        { type: 'separator' },
        {
          label: '查找',
          accelerator: 'CmdOrCtrl+F',
          click: () => mainWindow.webContents.send('menu:action', 'find'),
        },
      ],
    },

    // 视图菜单
    {
      label: '视图',
      submenu: [
        {
          label: '聊天工作台',
          accelerator: 'CmdOrCtrl+1',
          click: () => mainWindow.webContents.send('menu:navigate', '/chat'),
        },
        {
          label: '智能体管理',
          accelerator: 'CmdOrCtrl+2',
          click: () => mainWindow.webContents.send('menu:navigate', '/agents'),
        },
        {
          label: '模型管理',
          accelerator: 'CmdOrCtrl+3',
          click: () => mainWindow.webContents.send('menu:navigate', '/models'),
        },
        {
          label: '记忆管理',
          accelerator: 'CmdOrCtrl+4',
          click: () => mainWindow.webContents.send('menu:navigate', '/memory'),
        },
        {
          label: 'Skill 管理',
          accelerator: 'CmdOrCtrl+5',
          click: () => mainWindow.webContents.send('menu:navigate', '/skills'),
        },
        {
          label: 'MCP 管理',
          accelerator: 'CmdOrCtrl+6',
          click: () => mainWindow.webContents.send('menu:navigate', '/mcps'),
        },
        {
          label: '用量管理',
          accelerator: 'CmdOrCtrl+7',
          click: () => mainWindow.webContents.send('menu:navigate', '/usage'),
        },
        { type: 'separator' },
        { role: 'reload', label: '重新加载' },
        { role: 'forceReload', label: '强制重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' },
      ],
    },

    // 后端菜单
    {
      label: '后端',
      submenu: [
        {
          label: '重启后端',
          click: () => callbacks.onRestartBackend?.(),
        },
        {
          label: '查看后端日志',
          click: () => mainWindow.webContents.send('menu:action', 'show-backend-log'),
        },
        { type: 'separator' },
        {
          label: '重新加载 Skills',
          click: () => callbacks.onReloadSkills?.(),
        },
        {
          label: '重新加载工具',
          click: () => callbacks.onReloadTools?.(),
        },
      ],
    },

    // 帮助菜单
    {
      label: '帮助',
      submenu: [
        {
          label: '关于 OpenFox',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '关于 OpenFox',
              message: 'OpenFox Desktop',
              detail: `版本: 

OpenFox - 自研 Agent Skills 框架\n吉祥物: 派蒙\n\n基于 Electron + Vue3 + FastAPI\nMIT License`,
              icon: path.join(__dirname, 'assets', 'icon.png'),
            })
          },
        },
        {
          label: '检查更新',
          click: () => callbacks.onCheckUpdate?.(),
        },
        { type: 'separator' },
        {
          label: '打开项目目录',
          click: () => {
            const projectPath = callbacks.getProjectPath?.()
            if (projectPath) shell.openPath(projectPath)
          },
        },
        {
          label: 'GitHub 仓库',
          click: () => shell.openExternal('https://github.com/OpenFox/OpenFox'),
        },
        { type: 'separator' },
        {
          label: '开发者工具',
          accelerator: 'F12',
          click: () => mainWindow.webContents.toggleDevTools(),
        },
      ],
    },
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
  return menu
}

module.exports = { buildMenu }
