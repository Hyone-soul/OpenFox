/**
 * useChatSessions — 聊天会话共享状态
 *
 * 提供全局唯一的会话列表、当前活跃会话、模型列表等状态，
 * 供 App.vue（侧栏）和 ChatWorkbench.vue（聊天页）共同使用。
 */
import { ref, computed } from 'vue'
import { chatApi, metaApi, modelApi, contextApi, projectApi } from '../api'

// ========== 单例状态（模块级，跨组件共享） ==========

const sessions = ref([])
const activeSession = ref(null)
const projects = ref([]) // 项目列表
const modelDetails = ref([]) // 完整模型详情 [{ name, model, base_url, ... }]
const selectedModel = ref('') // 当前选中的模型配置名
const activeProvider = ref('') // 当前选中的供应商 key (base_url)
const contextInfo = ref(null)
const DEFAULT_AGENT_ID = 'default'

// ========== 供应商映射表 ==========

const PROVIDERS = [
  { match: 'deepseek', name: 'DeepSeek', icon: 'DS', color: '#4D6BFE' },
  { match: 'openai', name: 'OpenAI', icon: 'AI', color: '#10A37F' },
  { match: 'minimax', name: 'MiniMax', icon: 'MM', color: '#FF4D4F' },
  { match: 'moonshot', name: 'Kimi', icon: '🌙', color: '#f97316' },
  { match: 'bigmodel', name: 'Zhipu', icon: 'Z', color: '#3469FF' },
  { match: 'dashscope', name: 'Qwen', icon: 'Q', color: '#615CED' },
  { match: 'volces', name: 'Doubao', icon: '豆', color: '#3B5BFF' },
  { match: 'baichuan', name: 'Baichuan', icon: 'B', color: '#FF8800' },
  { match: 'yi', name: '01.AI', icon: 'Y', color: '#00B4D8' },
  { match: 'siliconflow', name: 'SiliconFlow', icon: 'SF', color: '#6366F1' },
]

const DEFAULT_PROVIDER = { name: '自定义', icon: '⚙', color: '#6B7280' }

function detectProvider(model) {
  const url = (model.base_url || '').toLowerCase()
  for (const p of PROVIDERS) {
    if (url.includes(p.match)) return p
  }
  return DEFAULT_PROVIDER
}

// ========== 计算属性 ==========

const activeMeta = computed(() => {
  const s = sessions.value.find((x) => x.id === activeSession.value)
  if (!s) return null
  return {
    title: s.title,
    agentId: s.agent_id || DEFAULT_AGENT_ID,
    agentName: s.agent_name || 'OpenFox',
  }
})

// 模型名列表（向后兼容）
const modelNames = computed(() => modelDetails.value.map(m => m.name))

// 按供应商分组的模型（供 ChatInput 分组选择用）
const providerModelGroups = computed(() => {
  const groupMap = new Map()
  for (const m of modelDetails.value) {
    const provider = detectProvider(m)
    const groupKey = m.base_url || 'unknown'
    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, {
        key: groupKey,
        name: provider.name,
        icon: provider.icon,
        color: provider.color,
        models: [],
      })
    }
    groupMap.get(groupKey).models.push(m)
  }
  return Array.from(groupMap.values())
})

// 当前供应商下的可用模型
const currentProviderModels = computed(() => {
  if (!activeProvider.value) return modelDetails.value
  return modelDetails.value.filter(m => m.base_url === activeProvider.value)
})

// ========== 操作方法 ==========

async function loadSessions() {
  const loaded = await chatApi.sessions()
  sessions.value = loaded.map((session) => ({
    ...session,
    agent_id: session.agent_id || DEFAULT_AGENT_ID,
    agent_name: session.agent_name || 'OpenFox',
    project_id: session.project_id || '',
    pinned: session.pinned || false,
  }))
}

async function loadModels() {
  try {
    const detail = await modelApi.list()
    modelDetails.value = detail.models || []
    // 始终以后端 active_model 为准，确保全局状态与后端一致
    const backendActive = detail.active_model || (modelDetails.value[0]?.name || '')
    if (backendActive) selectedModel.value = backendActive
    // 同步当前供应商为活跃模型所属的供应商
    const m = modelDetails.value.find(x => x.name === selectedModel.value)
    if (m) activeProvider.value = m.base_url || ''
  } catch {
    const models = await metaApi.models()
    modelDetails.value = models.map(m => ({ name: m.id, model: m.id, base_url: '' }))
    if (!selectedModel.value && modelDetails.value.length) {
      selectedModel.value = modelDetails.value[0].name
    }
  }
}

async function loadAll() {
  await Promise.all([loadSessions(), loadModels(), loadProjects()])
  fetchContextStatus()
}

async function fetchContextStatus() {
  try {
    contextInfo.value = await contextApi.status()
  } catch {
    // 静默失败
  }
}

async function createSession(title = '新会话', projectId = '') {
  const s = await chatApi.createSession({ title, agent_id: DEFAULT_AGENT_ID, project_id: projectId })
  await loadSessions()
  return s
}

async function removeSession(id) {
  await chatApi.sessionDelete(id)
  if (activeSession.value === id) {
    activeSession.value = null
  }
  await loadSessions()
}

async function renameSession(id, title) {
  await chatApi.sessionRename(id, title)
  // 本地同步更新，避免重新拉取全量
  const s = sessions.value.find((x) => x.id === id)
  if (s) s.title = title
}

function updateSessionTitle(id, title) {
  const s = sessions.value.find((x) => x.id === id)
  if (s) s.title = title
}

function selectSession(id) {
  activeSession.value = id
}

function clearActiveSession() {
  activeSession.value = null
}

// 切换供应商
function setActiveProvider(providerKey) {
  activeProvider.value = providerKey
  // 如果当前选中的模型不在新供应商下，自动切换到该供应商的第一个模型
  const currentModel = modelDetails.value.find(m => m.name === selectedModel.value)
  if (currentModel && currentModel.base_url !== providerKey) {
    const firstModel = modelDetails.value.find(m => m.base_url === providerKey)
    if (firstModel) selectedModel.value = firstModel.name
  }
}

async function createProject(workdir, name = '') {
  const p = await projectApi.create({ workdir, name })
  await loadProjects()
  return p
}

async function deleteProject(id) {
  await projectApi.delete(id)
  await loadProjects()
  await loadSessions() // 会话的 project_id 可能需要更新
}

async function deleteProjectCascade(id) {
  await projectApi.deleteCascade(id)
  await loadProjects()
  await loadSessions()
}

async function pinProject(id, pinned) {
  await projectApi.pin(id, pinned)
  await loadProjects()
}

async function pinSession(id, pinned) {
  await chatApi.sessionUpdate(id, { pinned })
  const s = sessions.value.find((x) => x.id === id)
  if (s) s.pinned = pinned
}

async function renameProject(id, name) {
  const p = await projectApi.rename(id, name)
  await loadProjects()
  return p
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {
    projects.value = []
  }
}

// 按项目分组的会话列表（置顶优先排序）
const groupedSessions = computed(() => {
  const groups = []
  // 按项目分组（projects 已按 pinned→created_at 排序）
  for (const p of projects.value) {
    const projSessions = sessions.value
      .filter(s => s.project_id === p.id)
      .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
    if (projSessions.length > 0) {
      groups.push({ project: p, sessions: projSessions })
    }
  }
  // 未关联会话（置顶优先）
  const unlinked = sessions.value
    .filter(s => !s.project_id)
    .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0))
  if (unlinked.length > 0) {
    groups.push({ project: null, sessions: unlinked })
  }
  return groups
})

// ========== 导出 ==========

export function useChatSessions() {
  return {
    // 状态
    sessions,
    activeSession,
    projects,
    groupedSessions,
    modelNames,
    modelDetails,
    selectedModel,
    activeProvider,
    providerModelGroups,
    currentProviderModels,
    contextInfo,
    activeMeta,
    // 方法
    loadAll,
    loadSessions,
    loadModels,
    loadProjects,
    fetchContextStatus,
    createSession,
    createProject,
    deleteProject,
    deleteProjectCascade,
    pinProject,
    pinSession,
    renameProject,
    removeSession,
    renameSession,
    updateSessionTitle,
    selectSession,
    clearActiveSession,
    setActiveProvider,
  }
}
