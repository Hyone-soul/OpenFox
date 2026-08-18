/**
 * Backend Manager - 管理 OpenFox Python 后端进程
 * 
 * 职责：
 *  1. 查找并启动 openfox-server（Python FastAPI 后端）
 *  2. 轮询健康检查端点，等待后端就绪
 *  3. 提供重启/终止后端进程的接口
 *  4. 通知主进程后端状态变化
 */

const { spawn, execSync } = require('child_process')
const http = require('http')
const path = require('path')
const fs = require('fs')
const { app } = require('electron')

const HEALTH_TIMEOUT_MS = 30000
const HEALTH_POLL_INTERVAL_MS = 500
const BACKEND_PORT = 8000
const BACKEND_HOST = '127.0.0.1'

// 打包进 resources/backend 的后端可执行文件名
const BUNDLED_BACKEND_EXE = 'openfox-backend.exe'
// 首启需要从 resources 初始化到 userData 的子目录/文件
const INIT_RESOURCE_ITEMS = ['skills', 'tools', 'mcps', 'config.yaml']

class BackendManager {
  constructor() {
    this.process = null
    this.port = BACKEND_PORT
    this.host = BACKEND_HOST
    this.isExternal = false
    this.onLog = null
    this.onStatus = null
  }

  /**
   * 查找 Python 可执行文件
   */
  findPython() {
    const candidates = ['python', 'python3', 'py']
    for (const cmd of candidates) {
      try {
        const result = execSync(`${cmd} --version`, { encoding: 'utf-8', timeout: 5000, stdio: 'pipe' })
        if (result.includes('Python 3')) {
          return cmd
        }
      } catch {
        // continue searching
      }
    }
    return null
  }

  /**
   * 检查 openfox-server 是否已在运行
   */
  async checkHealth() {
    return new Promise((resolve) => {
      const req = http.get(
        `http://${this.host}:${this.port}/healthz`,
        { timeout: 2000 },
        (res) => {
          res.resume()
          resolve(res.statusCode === 200)
        }
      )
      req.on('error', () => resolve(false))
      req.on('timeout', () => {
        req.destroy()
        resolve(false)
      })
    })
  }

  /**
   * 等待后端健康检查通过
   */
  async waitForHealth(timeoutMs = HEALTH_TIMEOUT_MS) {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const healthy = await this.checkHealth()
      if (healthy) return true
      await new Promise((r) => setTimeout(r, HEALTH_POLL_INTERVAL_MS))
    }
    return false
  }

  /**
   * 获取后端工作目录
   * 开发模式：项目根目录（desktop 的上一级）
   * 生产模式：userData 目录（可写，避免安装目录无写权限）
   */
  getBackendCwd() {
    if (app.isPackaged) {
      return app.getPath('userData')
    }
    // 开发模式：项目根目录（desktop 的上一级）
    return path.resolve(__dirname, '..')
  }

  /**
   * 首启初始化：把 resources 中的只读资源同步到 userData（可写目录）。
   * - config.yaml / skills / tools / mcps：用户可改，不覆盖已存在的文件
   * - 升级后新增的文件会补齐，用户的修改保留
   */
  initUserData() {
    if (!app.isPackaged) return

    const srcRoot = process.resourcesPath
    const dstRoot = app.getPath('userData')
    if (!srcRoot || !dstRoot) return

    const copyIfNewer = (src, dst) => {
      try {
        const st = fs.statSync(src)
        if (st.isDirectory()) {
          if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true })
          for (const entry of fs.readdirSync(src)) {
            copyIfNewer(path.join(src, entry), path.join(dst, entry))
          }
        } else if (st.isFile()) {
          // 目标不存在，或源文件更新时复制（保留用户改动）
          if (!fs.existsSync(dst) || fs.statSync(src).mtimeMs > fs.statSync(dst).mtimeMs) {
            fs.mkdirSync(path.dirname(dst), { recursive: true })
            fs.copyFileSync(src, dst)
            this._emitLog(`初始化资源: ${dst}`, 'info')
          }
        }
      } catch (err) {
        this._emitLog(`初始化资源失败: ${src} → ${err.message}`, 'error')
      }
    }

    for (const item of INIT_RESOURCE_ITEMS) {
      copyIfNewer(path.join(srcRoot, item), path.join(dstRoot, item))
    }
  }

  /**
   * 启动后端
   * @returns {Promise<{reused: boolean, error?: string}>}
   */
  async start() {
    this._emitStatus('starting')

    // 先检查是否已有后端在运行
    const alreadyRunning = await this.checkHealth()
    if (alreadyRunning) {
      this.isExternal = true
      this._emitStatus('running')
      this._emitLog('后端已在运行，直接复用', 'info')
      return { reused: true }
    }

    this.isExternal = false

    // 生产模式且存在内置后端 exe：无需系统 Python，直接启动
    let bundled = null
    if (app.isPackaged) {
      const candidate = path.join(process.resourcesPath, 'backend', BUNDLED_BACKEND_EXE)
      if (fs.existsSync(candidate)) bundled = candidate
    }

    // 查找 Python（仅在内置 exe 不存在时才需要）
    const pythonCmd = bundled ? null : this.findPython()
    if (!pythonCmd && !bundled) {
      this._emitStatus('error')
      this._emitLog('未找到 Python 3，请确保已安装 Python 3.10+ 并添加到 PATH', 'error')
      return { reused: false, error: 'Python not found' }
    }

    // 确定启动命令
    const cwd = this.getBackendCwd()
    let exe, args

    // 生产模式：优先启动打包进 resources 的后端 exe
    if (bundled) {
      // 首启把 resources 资源同步到 userData
      this.initUserData()
      exe = bundled
      args = ['--host', this.host, '--port', String(this.port), '--no-color']
      this._emitLog(`启动内置后端: ${exe}`, 'info')
      this._emitLog(`后端工作目录: ${cwd}`, 'info')
    } else if (app.isPackaged) {
      // 打包但无内置 exe：回退系统 Python
      this._emitLog('未找到内置后端 exe，回退到系统 Python', 'warn')
      exe = pythonCmd
      args = ['-m', 'open_fox.server', '--host', this.host, '--port', String(this.port)]
    } else {
      // 开发模式：尝试 openfox-server 入口点，失败则 python -m
      try {
        execSync('openfox-server --help', { encoding: 'utf-8', timeout: 5000, stdio: 'pipe' })
        exe = 'openfox-server'
        args = ['--host', this.host, '--port', String(this.port)]
      } catch {
        // 回退到 python -m open_fox.server
        exe = pythonCmd
        args = ['-m', 'open_fox.server', '--host', this.host, '--port', String(this.port)]
      }
      this._emitLog(`启动后端: ${exe} ${args.join(' ')}`, 'info')
      this._emitLog(`工作目录: ${cwd}`, 'info')
    }

    this._emitLog(`启动后端: ${exe} ${args.join(' ')}`, 'info')
    this._emitLog(`工作目录: ${cwd}`, 'info')

    // 启动子进程
    this.process = spawn(exe, args, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
      },
    })

    // 捕获输出
    this.process.stdout.on('data', (data) => {
      const lines = data.toString().trim()
      if (lines) this._emitLog(lines, 'stdout')
    })

    this.process.stderr.on('data', (data) => {
      const lines = data.toString().trim()
      if (lines) this._emitLog(lines, 'stderr')
    })

    this.process.on('error', (err) => {
      this._emitLog(`后端进程错误: ${err.message}`, 'error')
      this._emitStatus('error')
    })

    this.process.on('exit', (code) => {
      this._emitLog(`后端进程退出，退出码: ${code}`, 'info')
      if (code !== 0 && code !== null) {
        this._emitStatus('crashed')
      }
      this.process = null
    })

    // 等待健康检查
    this._emitStatus('waiting')
    const healthy = await this.waitForHealth()

    if (healthy) {
      this._emitStatus('running')
      this._emitLog('后端已就绪', 'info')
      return { reused: false }
    } else {
      this._emitStatus('error')
      this._emitLog('后端启动超时，请检查 Python 环境和依赖', 'error')
      return { reused: false, error: 'Health check timeout' }
    }
  }

  /**
   * 终止后端进程
   */
  kill() {
    if (!this.process || this.isExternal) return

    try {
      if (process.platform === 'win32') {
        // Windows: 使用 taskkill 终止进程树
        execSync(`taskkill /pid ${this.process.pid} /f /t`, { stdio: 'ignore' })
      } else {
        this.process.kill('SIGTERM')
        setTimeout(() => {
          if (this.process) this.process.kill('SIGKILL')
        }, 3000)
      }
    } catch {
      // 进程可能已退出
    }
    this.process = null
  }

  /**
   * 重启后端
   */
  async restart() {
    this.kill()
    await new Promise((r) => setTimeout(r, 1000))
    return this.start()
  }

  /**
   * 是否在运行
   */
  isRunning() {
    return this.process !== null || this.isExternal
  }

  _emitLog(message, level) {
    if (this.onLog) this.onLog(message, level)
  }

  _emitStatus(status) {
    if (this.onStatus) this.onStatus(status)
  }
}

module.exports = { BackendManager }
