<template>
  <div class="mcp-manage">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">MCP 管理</h2>
        <span class="page-subtitle">{{ servers.length }} 个服务器 / {{ totalTools }} 个工具</span>
      </div>
      <div class="page-header-right">
        <el-button plain :icon="Refresh" @click="reloadAll" :loading="reloading">全部重载</el-button>
        <el-button plain :icon="Download" @click="importVisible = true">导入配置</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">添加服务器</el-button>
      </div>
    </div>

    <!-- 概览统计条 -->
    <div class="overview-bar" v-if="servers.length > 0">
      <div class="overview-item">
        <div class="overview-dot connected"></div>
        <span class="overview-label">已连接</span>
        <span class="overview-value">{{ connectedCount }}</span>
      </div>
      <div class="overview-item">
        <div class="overview-dot enabled"></div>
        <span class="overview-label">已启用</span>
        <span class="overview-value">{{ enabledCount }}</span>
      </div>
      <div class="overview-item">
        <div class="overview-dot disabled"></div>
        <span class="overview-label">已禁用</span>
        <span class="overview-value">{{ disabledCount }}</span>
      </div>
      <div class="overview-item">
        <div class="overview-dot failed"></div>
        <span class="overview-label">连接失败</span>
        <span class="overview-value">{{ failedCount }}</span>
      </div>
    </div>

    <!-- 服务器卡片网格 -->
    <div v-loading="loading" class="card-grid">
      <el-card
        v-for="s in servers"
        :key="s.name"
        shadow="hover"
        class="mcp-card"
        :class="{
          'is-disabled': !s.enabled,
          'is-failed': s.enabled && !s.connected,
        }"
      >
        <!-- 状态色条 -->
        <div class="card-stripe" :class="statusClass(s)"></div>

        <!-- 卡片头部 -->
        <div class="card-header">
          <div class="card-header-left">
            <div class="server-icon" :class="statusClass(s)">
              <el-icon><Connection /></el-icon>
            </div>
            <div class="card-title-area">
              <div class="card-title">
                <span class="server-name" @click="openDetail(s)">{{ s.name }}</span>
                <span class="status-badge" :class="statusClass(s)">
                  <span class="status-dot"></span>
                  {{ statusText(s) }}
                </span>
              </div>
              <div class="card-subtitle">
                <el-tag size="small" effect="plain" round class="transport-tag">
                  {{ transportLabel(s.transport) }}
                </el-tag>
                <span class="tool-count" v-if="s.tool_count > 0">
                  {{ s.tool_count }} 个工具
                </span>
                <span class="tool-count zero" v-else>无工具</span>
              </div>
            </div>
          </div>
          <!-- 操作按钮组 -->
          <div class="card-actions">
            <el-tooltip content="测试连接" placement="top">
              <el-button
                circle
                size="small"
                :icon="Monitor"
                :loading="testingName === s.name"
                @click="testServer(s)"
              />
            </el-tooltip>
            <el-tooltip :content="s.enabled ? '禁用' : '启用'" placement="top">
              <el-switch
                v-model="s.enabled"
                size="small"
                @change="toggleServer(s)"
                class="card-switch"
              />
            </el-tooltip>
            <el-dropdown trigger="click" @click.stop>
              <el-icon class="card-more"><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openDetail(s)">
                    <el-icon><View /></el-icon> 查看详情
                  </el-dropdown-item>
                  <el-dropdown-item @click="openEdit(s)">
                    <el-icon><Edit /></el-icon> 编辑配置
                  </el-dropdown-item>
                  <el-dropdown-item @click="testServer(s)">
                    <el-icon><Monitor /></el-icon> 测试连接
                  </el-dropdown-item>
                  <el-dropdown-item @click="toggleServer(s)">
                    <el-icon><Switch /></el-icon> {{ s.enabled ? '禁用' : '启用' }}
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="deleteServer(s)">
                    <el-icon><Delete /></el-icon> 删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <!-- 工具列表（可展开） -->
        <div class="card-tools" v-if="s.tools && s.tools.length > 0">
          <div class="tools-header" @click="toggleExpand(s.name)">
            <el-icon class="tools-icon"><Tools /></el-icon>
            <span>工具列表</span>
            <span class="tools-count-badge">{{ s.tools.length }}</span>
            <el-icon class="expand-icon" :class="{ expanded: expandedNames.has(s.name) }">
              <ArrowDown />
            </el-icon>
          </div>
          <transition name="tools-expand">
            <div v-if="expandedNames.has(s.name)" class="tools-list">
              <el-tag
                v-for="t in s.tools"
                :key="t"
                size="small"
                effect="plain"
                round
                class="tool-tag"
              >
                {{ t }}
              </el-tag>
            </div>
          </transition>
        </div>

        <!-- 连接信息 -->
        <div class="card-footer">
          <div class="footer-info">
            <el-icon class="footer-icon"><FolderOpened /></el-icon>
            <span class="source-file" :title="s.source_file">{{ shortPath(s.source_file) }}</span>
          </div>
          <el-button link size="small" type="primary" @click="openDetail(s)">
            详情 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </el-card>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && servers.length === 0"
        description="暂无 MCP 服务器，点击右上角添加"
        :image-size="100"
        class="empty-state"
      >
        <el-button type="primary" :icon="Plus" @click="openCreate">添加服务器</el-button>
        <el-button plain :icon="Download" @click="importVisible = true">导入配置</el-button>
      </el-empty>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentServer?.name || 'MCP 详情'"
      size="55%"
      direction="rtl"
    >
      <template v-if="currentServer">
        <!-- 详情头部 -->
        <div class="detail-header">
          <div class="detail-header-top">
            <div class="server-icon-lg" :class="statusClass(currentServer)">
              <el-icon><Connection /></el-icon>
            </div>
            <div class="detail-title-area">
              <div class="detail-title">
                {{ currentServer.name }}
                <span class="status-badge" :class="statusClass(currentServer)">
                  <span class="status-dot"></span>
                  {{ statusText(currentServer) }}
                </span>
              </div>
              <div class="detail-meta">
                <el-tag size="small" effect="plain" round>
                  {{ transportLabel(currentServer.transport) }}
                </el-tag>
                <el-tag v-if="currentServer.enabled" size="small" type="success" effect="plain" round>已启用</el-tag>
                <el-tag v-else size="small" type="info" effect="plain" round>已禁用</el-tag>
              </div>
            </div>
          </div>
          <div class="detail-source">
            <el-icon><FolderOpened /></el-icon>
            <span>{{ currentServer.source_file }}</span>
          </div>
        </div>

        <!-- 标签页 -->
        <el-tabs v-model="detailTab" class="detail-tabs">
          <!-- 工具列表 Tab -->
          <el-tab-pane name="tools">
            <template #label>
              <span>工具 <el-badge :value="detailTools.length" :hidden="detailTools.length === 0" type="primary" /></span>
            </template>
            <div v-if="!detailTools.length" class="tab-empty">
              <el-empty description="暂无工具（服务器未连接或已被过滤）" :image-size="80" />
            </div>
            <div v-else class="tools-detail-list">
              <el-card
                v-for="t in detailTools"
                :key="t.name"
                shadow="never"
                class="tool-detail-card"
              >
                <div class="tool-detail-header">
                  <el-icon class="tool-detail-icon"><Tools /></el-icon>
                  <span class="tool-detail-name">{{ t.name }}</span>
                  <span class="tool-detail-fullname">{{ t.full_name }}</span>
                </div>
                <div class="tool-detail-desc">{{ t.description || '无描述' }}</div>
                <div class="tool-detail-schema" v-if="t.parameters && t.parameters.properties">
                  <span class="schema-label">参数：</span>
                  <div class="schema-params">
                    <el-tag
                      v-for="(val, key) in t.parameters.properties"
                      :key="key"
                      size="small"
                      effect="plain"
                      class="schema-param-tag"
                    >
                      <span class="param-name">{{ key }}</span>
                      <span class="param-type">{{ val.type || 'any' }}</span>
                    </el-tag>
                  </div>
                </div>
              </el-card>
            </div>
          </el-tab-pane>

          <!-- 原始配置 Tab -->
          <el-tab-pane label="配置详情" name="config">
            <div v-if="!currentServerConfig" class="tab-empty">
              <el-empty description="无法加载配置" :image-size="80" />
            </div>
            <div v-else class="config-detail">
              <div class="config-row" v-for="(val, key) in currentServerConfig" :key="key">
                <span class="config-key">{{ key }}</span>
                <span class="config-value">{{ formatConfigValue(val) }}</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>

        <!-- 操作按钮 -->
        <div class="detail-actions">
          <el-button
            :type="currentServer.enabled ? 'warning' : 'success'"
            plain
            :icon="Switch"
            @click="toggleServer(currentServer)"
          >
            {{ currentServer.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button plain :icon="Monitor" :loading="testingName === currentServer.name" @click="testServer(currentServer)">
            测试连接
          </el-button>
          <el-button plain :icon="Edit" @click="openEdit(currentServer)">编辑配置</el-button>
          <el-button type="danger" plain :icon="Delete" @click="deleteServer(currentServer)">删除</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formMode === 'create' ? '添加 MCP 服务器' : `编辑 ${form.name}`"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="form.name"
            placeholder="字母数字下划线连字符，如 amap"
            :disabled="formMode === 'edit'"
          />
        </el-form-item>
        <!-- 快速模板（仅创建模式显示） -->
        <el-form-item v-if="formMode === 'create'" label="快速模板">
          <div class="preset-row">
            <el-tag
              v-for="p in presets"
              :key="p.name"
              class="preset-tag"
              effect="plain"
              @click="applyPreset(p)"
            >
              {{ p.label }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="传输方式" prop="transport">
          <el-radio-group v-model="form.transport">
            <el-radio-button value="streamable-http">Streamable HTTP</el-radio-button>
            <el-radio-button value="sse">SSE</el-radio-button>
            <el-radio-button value="stdio">Stdio</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- stdio 专属字段 -->
        <template v-if="form.transport === 'stdio'">
          <el-form-item label="启动命令" prop="command">
            <el-input
              v-model="form.command"
              placeholder="如 npx -y @modelcontextprotocol/server-filesystem /tmp"
            />
          </el-form-item>
        </template>

        <!-- HTTP/SSE 专属字段 -->
        <template v-if="form.transport !== 'stdio'">
          <el-form-item label="URL" prop="url">
            <el-input
              v-model="form.url"
              placeholder="如 https://mcp.amap.com/mcp?key=xxx"
            />
          </el-form-item>
          <el-form-item label="请求头">
            <el-input
              v-model="headersText"
              type="textarea"
              :rows="3"
              placeholder='JSON 格式，如 {"Authorization": "Bearer xxx"}'
            />
          </el-form-item>
        </template>

        <el-form-item label="超时(秒)">
          <el-input-number v-model="form.timeout" :min="5" :max="300" :step="5" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>

        <!-- 工具过滤 -->
        <el-collapse class="advanced-collapse">
          <el-collapse-item title="工具过滤（高级）" name="filters">
            <el-form-item label="白名单">
              <el-input
                v-model="allowlistText"
                type="textarea"
                :rows="2"
                placeholder="逗号分隔工具名，留空表示全部允许"
              />
            </el-form-item>
            <el-form-item label="黑名单">
              <el-input
                v-model="denylistText"
                type="textarea"
                :rows="2"
                placeholder="逗号分隔工具名"
              />
            </el-form-item>
        </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveServer">
          {{ formMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 测试结果对话框 -->
    <el-dialog v-model="testResultVisible" title="连接测试结果" width="460px">
      <div class="test-result" v-if="testResult">
        <div class="test-result-icon" :class="{ success: testResult.success, fail: !testResult.success }">
          <el-icon v-if="testResult.success"><CircleCheckFilled /></el-icon>
          <el-icon v-else><CircleCloseFilled /></el-icon>
        </div>
        <div class="test-result-msg">{{ testResult.message }}</div>
        <div class="test-result-tools" v-if="testResult.tools && testResult.tools.length > 0">
          <div class="test-tools-label">发现的工具：</div>
          <div class="test-tools-tags">
            <el-tag v-for="t in testResult.tools" :key="t" size="small" effect="plain" round>
              {{ t }}
            </el-tag>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="testResultVisible = false">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入配置对话框 -->
    <el-dialog v-model="importVisible" title="导入 MCP 配置" width="600px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        粘贴 YAML 格式的 MCP 配置，导入后将自动创建服务器并重载。
      </el-alert>
      <el-input
        v-model="importContent"
        type="textarea"
        :rows="12"
        placeholder="name: my-server&#10;transport: streamable-http&#10;url: https://example.com/mcp&#10;enabled: true&#10;timeout: 30"
        style="font-family: 'SF Mono', 'Fira Code', monospace; font-size: 13px"
      />
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Plus, Refresh, Edit, Delete, Connection, Monitor, Switch,
  MoreFilled, View, ArrowRight, ArrowDown, FolderOpened, Tools,
  CircleCheckFilled, CircleCloseFilled, Download,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { mcpApi } from '../api'

const loading = ref(false)
const servers = ref([])
const totalTools = ref(0)
const reloading = ref(false)
const expandedNames = reactive(new Set())

// 详情
const detailVisible = ref(false)
const currentServer = ref(null)
const currentServerConfig = ref(null)
const detailTools = ref([])
const detailTab = ref('tools')

// 创建/编辑
const formVisible = ref(false)
const formMode = ref('create')
const formRef = ref()
const saving = ref(false)
const form = ref({
  name: '',
  transport: 'streamable-http',
  command: '',
  url: '',
  enabled: true,
  timeout: 30,
  headers: {},
  tool_allowlist: [],
  tool_denylist: [],
})
const headersText = ref('')
const allowlistText = ref('')
const denylistText = ref('')
const formRules = {
  name: [
    { required: true, message: '请输入服务器名称', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符', trigger: 'blur' },
  ],
  transport: [{ required: true, message: '请选择传输方式', trigger: 'change' }],
  command: [
    {
      validator: (rule, val, callback) => {
        if (form.value.transport === 'stdio' && !val) {
          callback(new Error('stdio 必须指定启动命令'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  url: [
    {
      validator: (rule, val, callback) => {
        if (form.value.transport !== 'stdio' && !val) {
          callback(new Error(`${form.value.transport} 必须指定 URL`))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

// 预设模板
const presets = [
  { name: 'amap', label: '高德地图', transport: 'streamable-http', url: 'https://mcp.amap.com/mcp?key=YOUR_KEY', command: '' },
  { name: 'filesystem', label: '文件系统', transport: 'stdio', command: 'npx -y @modelcontextprotocol/server-filesystem /tmp', url: '' },
  { name: 'github', label: 'GitHub', transport: 'stdio', command: 'npx -y @modelcontextprotocol/server-github', url: '' },
  { name: 'sqlite', label: 'SQLite', transport: 'stdio', command: 'npx -y @modelcontextprotocol/server-sqlite --db-path /tmp/data.db', url: '' },
  { name: 'fetch', label: 'Fetch', transport: 'stdio', command: 'npx -y @modelcontextprotocol/server-fetch', url: '' },
  { name: 'puppeteer', label: 'Puppeteer', transport: 'stdio', command: 'npx -y @modelcontextprotocol/server-puppeteer', url: '' },
]

function applyPreset(p) {
  form.value.name = p.name
  form.value.transport = p.transport
  form.value.command = p.command
  form.value.url = p.url
}

// 导入配置
const importVisible = ref(false)
const importContent = ref('')
const importing = ref(false)

async function doImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴配置内容')
    return
  }
  importing.value = true
  try {
    const r = await mcpApi.import({ content: importContent.value, format: 'yaml' })
    ElMessage.success(r.message || '导入成功')
    importVisible.value = false
    importContent.value = ''
    await loadList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

// 测试
const testingName = ref('')
const testResultVisible = ref(false)
const testResult = ref(null)

// 统计
const connectedCount = computed(() => servers.value.filter(s => s.connected).length)
const enabledCount = computed(() => servers.value.filter(s => s.enabled).length)
const disabledCount = computed(() => servers.value.filter(s => !s.enabled).length)
const failedCount = computed(() => servers.value.filter(s => s.enabled && !s.connected).length)

// 状态辅助函数
function statusClass(s) {
  if (!s.enabled) return 'disabled'
  if (s.connected) return 'connected'
  return 'failed'
}

function statusText(s) {
  if (!s.enabled) return '已禁用'
  if (s.connected) return '已连接'
  return '连接失败'
}

function transportLabel(t) {
  const map = { 'streamable-http': 'Streamable HTTP', 'sse': 'SSE', 'stdio': 'Stdio' }
  return map[t] || t
}

function shortPath(path) {
  if (!path) return ''
  const parts = path.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
}

function formatConfigValue(val) {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'boolean') return val ? 'true' : 'false'
  if (Array.isArray(val)) return val.length ? val.join(', ') : '[]'
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function toggleExpand(name) {
  if (expandedNames.has(name)) {
    expandedNames.delete(name)
  } else {
    expandedNames.add(name)
  }
}

// 数据加载
async function loadList() {
  loading.value = true
  try {
    const r = await mcpApi.list()
    servers.value = r.servers || []
    totalTools.value = r.total_tools || 0
  } catch (e) {
    ElMessage.error('加载 MCP 列表失败')
  } finally {
    loading.value = false
  }
}

async function reloadAll() {
  reloading.value = true
  try {
    await mcpApi.reload()
    ElMessage.success('重载完成')
    await loadList()
  } catch (e) {
    ElMessage.error('重载失败')
  } finally {
    reloading.value = false
  }
}

// 详情
async function openDetail(s) {
  currentServer.value = s
  detailVisible.value = true
  detailTab.value = 'tools'
  detailTools.value = []
  currentServerConfig.value = null

  // 加载工具详情
  try {
    const r = await mcpApi.tools(s.name)
    detailTools.value = r.tools || []
  } catch {
    detailTools.value = []
  }

  // 加载配置文件详情
  try {
    const detail = await mcpApi.detail(s.name)
    currentServerConfig.value = detail
  } catch {
    currentServerConfig.value = null
  }
}

// 创建/编辑
function openCreate() {
  formMode.value = 'create'
  form.value = {
    name: '',
    transport: 'streamable-http',
    command: '',
    url: '',
    enabled: true,
    timeout: 30,
    headers: {},
    tool_allowlist: [],
    tool_denylist: [],
  }
  headersText.value = ''
  allowlistText.value = ''
  denylistText.value = ''
  formVisible.value = true
}

async function openEdit(s) {
  formMode.value = 'edit'
  form.value = {
    name: s.name,
    transport: s.transport,
    command: '',
    url: '',
    enabled: s.enabled,
    timeout: 30,
    headers: {},
    tool_allowlist: [],
    tool_denylist: [],
  }
  headersText.value = ''
  allowlistText.value = ''
  denylistText.value = ''

  // 从后端详情接口获取完整配置（含 command/url/headers 等）
  try {
    const detail = await mcpApi.detail(s.name)
    form.value.command = detail.command || ''
    form.value.url = detail.url || ''
    form.value.timeout = detail.timeout || 30
    form.value.headers = detail.headers || {}
    form.value.tool_allowlist = detail.tool_allowlist || []
    form.value.tool_denylist = detail.tool_denylist || []
    headersText.value = detail.headers && Object.keys(detail.headers).length
      ? JSON.stringify(detail.headers, null, 2)
      : ''
    allowlistText.value = (detail.tool_allowlist || []).join(', ')
    denylistText.value = (detail.tool_denylist || []).join(', ')
  } catch {
    // 静默失败，用户可以手动填写
  }
  formVisible.value = true
}

async function saveServer() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 解析 headers
  let headers = {}
  if (headersText.value.trim()) {
    try {
      headers = JSON.parse(headersText.value)
    } catch {
      ElMessage.error('请求头 JSON 格式错误')
      return
    }
  }

  // 解析白名单/黑名单
  const allowlist = allowlistText.value.trim()
    ? allowlistText.value.split(',').map(s => s.trim()).filter(Boolean)
    : []
  const denylist = denylistText.value.trim()
    ? denylistText.value.split(',').map(s => s.trim()).filter(Boolean)
    : []

  const payload = {
    ...form.value,
    headers,
    tool_allowlist: allowlist,
    tool_denylist: denylist,
  }

  saving.value = true
  try {
    if (formMode.value === 'create') {
      const r = await mcpApi.create(payload)
      ElMessage.success(r.message || '创建成功')
    } else {
      const r = await mcpApi.update(form.value.name, payload)
      ElMessage.success(r.message || '更新成功')
    }
    formVisible.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

// 启停
async function toggleServer(s) {
  try {
    const r = await mcpApi.toggle(s.name)
    ElMessage.success(r.message || '操作成功')
    await loadList()
    // 如果详情抽屉打开，更新当前对象
    if (currentServer.value?.name === s.name) {
      const updated = servers.value.find(x => x.name === s.name)
      if (updated) currentServer.value = updated
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
    // 恢复 switch 状态
    s.enabled = !s.enabled
  }
}

// 测试
async function testServer(s) {
  testingName.value = s.name
  try {
    const r = await mcpApi.test(s.name)
    testResult.value = r
    testResultVisible.value = true
    if (r.success) {
      ElMessage.success(r.message)
    } else {
      ElMessage.warning(r.message)
    }
  } catch (e) {
    testResult.value = {
      name: s.name,
      success: false,
      message: e.response?.data?.detail || '测试请求失败',
      tools: [],
    }
    testResultVisible.value = true
  } finally {
    testingName.value = ''
  }
}

// 删除
async function deleteServer(s) {
  try {
    await ElMessageBox.confirm(
      `确定删除 MCP 服务器「${s.name}」吗？配置文件将被永久删除。`,
      '删除确认',
      { type: 'error', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await mcpApi.remove(s.name)
    ElMessage.success('已删除')
    detailVisible.value = false
    await loadList()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadList)
</script>

<style scoped>
.mcp-manage {
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}
.page-subtitle {
  font-size: 13px;
  color: #9ca3af;
}
.page-header-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 概览统计条 */
.overview-bar {
  display: flex;
  gap: 24px;
  padding: 12px 20px;
  background: #f9fafb;
  border-radius: 10px;
  margin-bottom: 16px;
  border: 1px solid #f0f0f0;
}
.overview-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.overview-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.overview-dot.connected { background: #10b981; }
.overview-dot.enabled { background: #1e293b; }
.overview-dot.disabled { background: #d1d5db; }
.overview-dot.failed { background: #ef4444; }
.overview-label {
  font-size: 13px;
  color: #6b7280;
}
.overview-value {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  font-variant-numeric: tabular-nums;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  min-height: 200px;
}

/* MCP 卡片 */
.mcp-card {
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  transition: all 0.2s;
  overflow: hidden;
}
.mcp-card:hover {
  border-color: #cbd5e1;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
.mcp-card.is-disabled {
  opacity: 0.65;
}
.mcp-card.is-failed .server-icon {
  background: linear-gradient(135deg, #ef4444, #f87171) !important;
}
.mcp-card :deep(.el-card__body) {
  padding: 16px;
}

/* 状态色条 */
.card-stripe {
  height: 3px;
  margin: -16px -16px 12px -16px;
  border-radius: 10px 10px 0 0;
  background: #1e293b;
}
.card-stripe.connected { background: linear-gradient(90deg, #10b981, #34d399, #6ee7b7); }
.card-stripe.failed { background: linear-gradient(90deg, #ef4444, #f87171, #fca5a5); }
.card-stripe.disabled { background: linear-gradient(90deg, #d1d5db, #e5e7eb, #f3f4f6); }

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.card-header-left {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
  flex: 1;
}
.server-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #1e293b;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.server-icon.connected { background: linear-gradient(135deg, #10b981, #34d399); }
.server-icon.failed { background: linear-gradient(135deg, #ef4444, #f87171); }
.server-icon.disabled { background: linear-gradient(135deg, #9ca3af, #d1d5db); }
.card-title-area {
  min-width: 0;
  flex: 1;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.server-name {
  cursor: pointer;
}
.server-name:hover {
  color: #1e293b;
}

/* 状态徽章 */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.status-badge .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-badge.connected { color: #059669; background: #d1fae5; }
.status-badge.connected .status-dot { background: #10b981; }
.status-badge.failed { color: #dc2626; background: #fee2e2; }
.status-badge.failed .status-dot { background: #ef4444; }
.status-badge.disabled { color: #9ca3af; background: #f3f4f6; }
.status-badge.disabled .status-dot { background: #d1d5db; }

.card-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
}
.transport-tag {
  font-size: 11px;
}
.tool-count {
  color: #64748b;
  font-weight: 500;
}
.tool-count.zero {
  color: #d1d5db;
}

/* 卡片操作 */
.card-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.card-more {
  font-size: 16px;
  color: #d1d5db;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;
}
.card-more:hover {
  color: #1e293b;
  background: #f1f5f9;
}
.card-switch {
  margin: 0 2px;
}

/* 工具列表展开 */
.card-tools {
  margin-bottom: 10px;
}
.tools-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 6px 0;
  font-size: 13px;
  color: #6b7280;
  transition: color 0.2s;
}
.tools-header:hover {
  color: #1e293b;
}
.tools-icon {
  font-size: 14px;
}
.tools-count-badge {
  background: #e2e8f0;
  color: #1e293b;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.expand-icon {
  margin-left: auto;
  font-size: 12px;
  transition: transform 0.2s;
}
.expand-icon.expanded {
  transform: rotate(180deg);
}
.tools-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 0 4px;
}
.tool-tag {
  font-size: 12px;
}

/* 展开动画 */
.tools-expand-enter-active,
.tools-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.tools-expand-enter-from,
.tools-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.tools-expand-enter-to,
.tools-expand-leave-from {
  opacity: 1;
  max-height: 200px;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid #f5f5f5;
}
.footer-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #9ca3af;
  min-width: 0;
}
.footer-icon {
  flex-shrink: 0;
}
.source-file {
  font-family: 'SF Mono', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 空状态 */
.empty-state {
  grid-column: 1 / -1;
  padding: 60px 0;
}

/* 详情抽屉 */
.detail-header {
  margin-bottom: 20px;
}
.detail-header-top {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.server-icon-lg {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: #1e293b;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.server-icon-lg.connected { background: linear-gradient(135deg, #10b981, #34d399); }
.server-icon-lg.failed { background: linear-gradient(135deg, #ef4444, #f87171); }
.server-icon-lg.disabled { background: linear-gradient(135deg, #9ca3af, #d1d5db); }
.detail-title-area {
  flex: 1;
  min-width: 0;
}
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.detail-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}
.detail-source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
  font-family: 'SF Mono', 'Consolas', monospace;
  background: #f9fafb;
  padding: 6px 12px;
  border-radius: 6px;
}

/* 详情标签页 */
.detail-tabs {
  margin-top: 8px;
}

/* 工具详情列表 */
.tools-detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tool-detail-card {
  border-radius: 8px;
  border: 1px solid #f0f0f0;
}
.tool-detail-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.tool-detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.tool-detail-icon {
  color: #64748b;
  font-size: 14px;
}
.tool-detail-name {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}
.tool-detail-fullname {
  font-size: 12px;
  color: #9ca3af;
  font-family: 'SF Mono', 'Consolas', monospace;
  margin-left: auto;
}
.tool-detail-desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
  margin-bottom: 8px;
}
.tool-detail-schema {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
}
.schema-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
  flex-shrink: 0;
}
.schema-params {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.schema-param-tag {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
}
.param-name {
  font-weight: 600;
  color: #4b5563;
}
.param-type {
  color: #9ca3af;
  margin-left: 4px;
}

/* 配置详情 */
.config-detail {
  background: #f9fafb;
  border-radius: 8px;
  padding: 12px 16px;
}
.config-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
}
.config-row:last-child {
  border-bottom: none;
}
.config-key {
  font-weight: 600;
  color: #374151;
  min-width: 120px;
  flex-shrink: 0;
}
.config-value {
  color: #4b5563;
  font-family: 'SF Mono', 'Consolas', monospace;
  word-break: break-all;
}

/* Tab 空状态 */
.tab-empty {
  padding: 20px 0;
}

/* 详情操作 */
.detail-actions {
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  margin-top: 20px;
  flex-wrap: wrap;
}

/* 高级折叠面板 */
.advanced-collapse {
  margin-top: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
}
.advanced-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

/* 测试结果 */
.test-result {
  text-align: center;
  padding: 20px 0;
}
.test-result-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.test-result-icon.success {
  color: #10b981;
}
.test-result-icon.fail {
  color: #ef4444;
}
.test-result-msg {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 16px;
}
.test-result-tools {
  text-align: left;
  background: #f9fafb;
  border-radius: 8px;
  padding: 12px 16px;
}
.test-tools-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}
.test-tools-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 预设模板 */
.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.preset-tag {
  cursor: pointer;
  transition: all 0.15s;
}
.preset-tag:hover {
  border-color: #1e293b;
  color: #1e293b;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }
  .overview-bar {
    gap: 12px;
  }
  .card-actions {
    gap: 4px;
  }
  .detail-actions {
    flex-direction: column;
  }
  .detail-actions .el-button {
    width: 100%;
  }
}

@media (max-width: 480px) {
  .card-grid {
    grid-template-columns: 1fr;
  }
  .page-title {
    font-size: 18px;
  }
  .overview-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .mcp-card :deep(.el-card__body) {
    padding: 12px;
  }
  .card-stripe {
    margin: -12px -12px 10px -12px;
  }
  .card-actions .el-tooltip {
    display: none;
  }
}
</style>
