import axios from 'axios'

// ========== 基础配置 ==========

// Electron 模式：直连后端（file:// 协议下无法走 Vite 代理）
// Web 模式：使用 Vite 代理（/v1 → 127.0.0.1:8000）
const isElectron = import.meta.env.VITE_ELECTRON === 'true'
  || (typeof window !== 'undefined' && window.electronAPI?.isElectron)

const baseURL = isElectron ? 'http://127.0.0.1:8000/v1' : '/v1'
const http = axios.create({ baseURL })

// ========== 请求拦截器：自动附加 JWT ==========

http.interceptors.request.use(config => {
  const token = localStorage.getItem('openfox_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ========== 响应拦截器：401 自动登出 ==========

http.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // token 过期或无效 → 清除本地状态并跳转登录
      localStorage.removeItem('openfox_token')
      localStorage.removeItem('openfox_user')
      // 避免在 /login 页面反复跳转
      if (window.location.pathname !== '/login' && window.location.hash !== '#/login') {
        if (isElectron) {
          window.location.hash = '#/login'
        } else {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// ========== API ==========

export const authApi = {
  login: (data) => http.post('/auth/login', data).then(r => r.data),
  register: (data) => http.post('/auth/register', data).then(r => r.data),
  me: () => http.get('/auth/me').then(r => r.data),
}

export const agentApi = {
  list: () => http.get('/agents').then(r => r.data.agents),
  create: (data) => http.post('/agents', data).then(r => r.data),
  update: (id, data) => http.put(`/agents/${id}`, data).then(r => r.data),
  remove: (id) => http.delete(`/agents/${id}`),
  test: (id) => http.get(`/agents/${id}/test`).then(r => r.data),
}

export const chatApi = {
  chat: (data) => http.post('/chat', data).then(r => r.data),
  chatStream: (data, options) => streamChatFetch(data, options),
  agentChat: (data) => http.post('/agent-chat', data).then(r => r.data),
  sessions: () => http.get('/sessions').then(r => r.data.sessions),
  createSession: (data) => http.post('/sessions', data).then(r => r.data),
  sessionMessages: (id) => http.get(`/sessions/${id}/messages`).then(r => r.data),
  sessionDelete: (id) => http.delete(`/sessions/${id}`),
  sessionUpdate: (id, data) => http.put(`/sessions/${id}`, data).then(r => r.data),
  sessionRename: (id, title) => http.put(`/sessions/${id}`, { title }).then(r => r.data),
}

export const projectApi = {
  list: () => http.get('/projects').then(r => r.data.projects),
  create: (data) => http.post('/projects', data).then(r => r.data),
  get: (id) => http.get(`/projects/${id}`).then(r => r.data),
  delete: (id) => http.delete(`/projects/${id}`),
  rename: (id, name) => http.put(`/projects/${id}`, { name }).then(r => r.data),
  pin: (id, pinned) => http.put(`/projects/${id}/pin`, { pinned }).then(r => r.data),
  deleteCascade: (id) => http.delete(`/projects/${id}/cascade`).then(r => r.data),
}

// ========== SSE 流式聊天 ==========

/**
 * 流式聊天：发送 POST /v1/chat/stream，返回一个可消费的 SSE 流。
 * 返回 AsyncGenerator，yield 出 { type, data } 对象。
 * type: "tool_call" | "tool_result" | "done" | "error" | "keepalive"
 */
export async function* streamChatFetch(data, options = {}) {
  const url = isElectron ? `${baseURL}/chat/stream` : '/v1/chat/stream'
  const token = localStorage.getItem('openfox_token')

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal: options.signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload.detail || payload.message || ''
    } catch {
      // Keep the HTTP status when the server did not return JSON.
    }
    throw new Error(detail || `Chat stream failed: ${response.status}`)
  }

  if (!response.body) {
    throw new Error('聊天服务没有返回流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 解析 SSE 格式：event: xxx\ndata: xxx\n\n
    const parts = buffer.split('\n\n')
    buffer = parts.pop() // 最后一段可能不完整

    for (const part of parts) {
      if (!part.trim()) continue
      // SSE 注释行（以 `:` 开头，如 `: keepalive`），直接跳过
      if (part.trim().startsWith(':')) continue
      let eventType = 'message'
      let eventData = '{}'
      for (const line of part.split('\n')) {
        // 跳过行内注释（如 `: keepalive`）
        if (line.startsWith(':')) continue
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          eventData = line.slice(5).trim()
        }
      }
      try {
        const data = JSON.parse(eventData)
        yield { type: eventType, data }
      } catch {
        yield { type: eventType, data: {} }
      }
    }
  }
}

export const metaApi = {
  models: () => http.get('/models').then(r => r.data.data),
  tools: () => http.get('/tools').then(r => r.data.tools),
  skills: () => http.get('/skills').then(r => r.data),
}

export const modelApi = {
  list: () => http.get('/models/detail').then(r => r.data),
  create: (data) => http.post('/models', data).then(r => r.data),
  update: (name, data) => http.put(`/models/${name}`, data).then(r => r.data),
  remove: (name) => http.delete(`/models/${name}`),
  setActive: (name) => http.put(`/models/${name}/active`).then(r => r.data),
  test: (name) => http.post(`/models/${name}/test`).then(r => r.data),
  fetchAvailable: (data) => http.post('/models/fetch', data).then(r => r.data),
}

export const memoryApi = {
  list: () => http.get('/memory').then(r => r.data),
  create: (data) => http.post('/memory', data).then(r => r.data),
  update: (data) => http.put('/memory', data).then(r => r.data),
  remove: (data) => http.delete('/memory', { data }),
}

export const skillApi = {
  list: () => http.get('/skills/detail').then(r => r.data.skills),
  getContent: (name) => http.get(`/skills/${name}/content`).then(r => r.data),
  updateContent: (name, content) => http.put(`/skills/${name}/content`, { content }).then(r => r.data),
  create: (data) => http.post('/skills', data).then(r => r.data),
  remove: (name, mode = 'deprecate') => http.delete(`/skills/${name}`, { params: { mode } }),
  rollback: (name) => http.post(`/skills/${name}/rollback`).then(r => r.data),
  stats: (name) => http.get(`/skills/${name}/stats`).then(r => r.data),
  versions: (name) => http.get(`/skills/${name}/versions`).then(r => r.data.versions),
  import: (data) => http.post('/skills/import', data).then(r => r.data),
  upload: (data) => http.post('/skills/upload', data).then(r => r.data),
  installUrl: (data) => http.post('/skills/install-url', data).then(r => r.data),
  aiGenerate: (data) => http.post('/skills/ai-generate', data).then(r => r.data),
}

export const evolutionApi = {
  pending: () => http.get('/evolution/pending').then(r => r.data.pending),
  confirm: (id) => http.post(`/evolution/pending/${id}/confirm`).then(r => r.data),
  reject: (id) => http.post(`/evolution/pending/${id}/reject`).then(r => r.data),
}

export const mcpApi = {
  list: () => http.get('/mcps').then(r => r.data),
  detail: (name) => http.get(`/mcps/${name}/detail`).then(r => r.data),
  create: (data) => http.post('/mcps', data).then(r => r.data),
  update: (name, data) => http.put(`/mcps/${name}`, data).then(r => r.data),
  remove: (name) => http.delete(`/mcps/${name}`),
  toggle: (name) => http.post(`/mcps/${name}/toggle`).then(r => r.data),
  test: (name) => http.post(`/mcps/${name}/test`).then(r => r.data),
  tools: (name) => http.get(`/mcps/${name}/tools`).then(r => r.data),
  import: (data) => http.post('/mcps/import', data).then(r => r.data),
  reload: () => http.post('/reload').then(r => r.data),
}

export const usageApi = {
  records: (params) => http.get('/usage/records', { params }).then(r => r.data),
  summary: (params) => http.get('/usage/summary', { params }).then(r => r.data),
}

export const contextApi = {
  status: () => http.get('/context/status').then(r => r.data),
  compact: () => http.post('/context/compact').then(r => r.data),
}

export const toolsApi = {
  list: () => http.get('/tools').then(r => r.data),
  confirm: (confirmId, approved) => http.post('/tool/confirm', { confirm_id: confirmId, approved }).then(r => r.data),
}
