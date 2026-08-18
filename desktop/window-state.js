/**
 * Window State - 窗口状态持久化
 * 
 * 保存和恢复窗口的位置、大小和最大化状态
 * 数据存储在 Electron 的 userData 目录中
 */

const { app } = require('electron')
const path = require('path')
const fs = require('fs')

const STATE_FILE = 'window-state.json'

const DEFAULT_STATE = {
  x: undefined,
  y: undefined,
  width: 960,
  height: 680,
  isMaximized: false,
}

let cachedState = null

function getStatePath() {
  return path.join(app.getPath('userData'), STATE_FILE)
}

/**
 * 读取窗口状态
 */
function load() {
  if (cachedState) return cachedState

  try {
    const filePath = getStatePath()
    if (fs.existsSync(filePath)) {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'))
      cachedState = { ...DEFAULT_STATE, ...data }
    } else {
      cachedState = { ...DEFAULT_STATE }
    }
  } catch {
    cachedState = { ...DEFAULT_STATE }
  }

  // 确保窗口不会太小
  cachedState.width = Math.max(cachedState.width || DEFAULT_STATE.width, 400)
  cachedState.height = Math.max(cachedState.height || DEFAULT_STATE.height, 300)

  return cachedState
}

/**
 * 保存窗口状态
 */
function save(window) {
  if (!window) return

  const state = {
    isMaximized: window.isMaximized(),
  }

  if (!state.isMaximized) {
    const bounds = window.getBounds()
    state.x = bounds.x
    state.y = bounds.y
    state.width = bounds.width
    state.height = bounds.height
  } else {
    // 最大化时保留之前的状态
    const prev = load()
    state.x = prev.x
    state.y = prev.y
    state.width = prev.width
    state.height = prev.height
  }

  cachedState = state

  try {
    const filePath = getStatePath()
    fs.writeFileSync(filePath, JSON.stringify(state, null, 2))
  } catch {
    // 忽略写入错误
  }
}

module.exports = { load, save }
