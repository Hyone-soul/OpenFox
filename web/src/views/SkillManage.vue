<template>
  <div class="skill-manage">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">Skill 管理</h2>
        <el-badge v-if="pendingCount > 0" :value="pendingCount" type="warning" class="pending-badge">
          <el-button size="small" round @click="showPending = true">
            <el-icon><MagicStick /></el-icon>
            进化候选
          </el-button>
        </el-badge>
      </div>
      <div class="page-header-right">
        <el-input
          v-model="keyword"
          placeholder="搜索 Skill 名称或描述"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button plain :icon="Link" @click="openInstallUrl">URL 安装</el-button>
        <el-button plain :icon="Upload" @click="openImport">导入 Skill</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建 Skill</el-button>
      </div>
    </div>

    <!-- 状态过滤栏 -->
    <div class="filter-bar">
      <div
        v-for="tab in filterTabs"
        :key="tab.key"
        class="filter-tab"
        :class="{ active: activeFilter === tab.key }"
        @click="activeFilter = tab.key"
      >
        <span class="filter-label">{{ tab.label }}</span>
        <span class="filter-count">{{ tab.count }}</span>
      </div>
    </div>

    <!-- 卡片网格 -->
    <div v-loading="loading" class="card-grid">
      <el-card
        v-for="s in filteredSkills"
        :key="s.name"
        shadow="hover"
        class="skill-card"
        :class="{ 'is-deprecated': s.deprecated }"
        @click="openDetail(s)"
      >
        <!-- 顶部色条 -->
        <div class="card-stripe" :class="{ deprecated: s.deprecated }"></div>

        <!-- 卡片头部 -->
        <div class="card-header">
          <div class="card-header-left">
            <div class="skill-icon" :class="{ deprecated: s.deprecated }">
              <el-icon><Lightning /></el-icon>
            </div>
            <div class="card-title-area">
              <div class="card-title">
                {{ s.name }}
                <el-tag v-if="s.version > 1" size="small" type="info" effect="plain" round>
                  v{{ s.version }}
                </el-tag>
                <el-tag v-if="s.deprecated" size="small" type="danger" effect="dark" round>
                  已废弃
                </el-tag>
              </div>
              <div class="card-subtitle">
                {{ s.tools.length ? s.tools.join(', ') : '无工具依赖' }}
              </div>
            </div>
          </div>
          <!-- 卡片快捷操作 -->
          <el-dropdown trigger="click" @click.stop>
            <el-icon class="card-more"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="openDetail(s)">
                  <el-icon><View /></el-icon> 查看详情
                </el-dropdown-item>
                <el-dropdown-item @click="quickEdit(s)">
                  <el-icon><Edit /></el-icon> 编辑内容
                </el-dropdown-item>
                <el-dropdown-item v-if="!s.deprecated" @click="quickDeprecate(s)">
                  <el-icon><Warning /></el-icon> 标记废弃
                </el-dropdown-item>
                <el-dropdown-item @click="quickDelete(s)">
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- 描述 -->
        <div class="card-desc">{{ truncate(s.description, 120) }}</div>

        <!-- 脚本标签 -->
        <div class="card-scripts" v-if="s.scripts.length">
          <el-tag v-for="sc in s.scripts" :key="sc.id" size="small" effect="plain" round>
            <el-icon style="margin-right: 2px"><Document /></el-icon>
            {{ sc.id }}
          </el-tag>
        </div>

        <!-- 底部信息 -->
        <div class="card-footer">
          <div class="footer-stats">
            <span class="stat-item" v-if="statsMap[s.name]">
              <el-icon><DataLine /></el-icon>
              {{ statsMap[s.name].invocations }} 次调用
            </span>
            <span class="stat-item trigger-item" v-if="s.trigger">
              <el-icon><Aim /></el-icon>
              {{ truncate(s.trigger, 24) }}
            </span>
          </div>
          <el-icon class="card-arrow"><ArrowRight /></el-icon>
        </div>
      </el-card>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && !filteredSkills.length"
        :description="emptyText"
        :image-size="100"
        class="empty-state"
      />
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentSkill?.name || 'Skill 详情'"
      size="60%"
      direction="rtl"
    >
      <template v-if="currentSkill">
        <!-- 详情头部 -->
        <div class="detail-header">
          <div class="detail-header-top">
            <div class="skill-icon-lg" :class="{ deprecated: currentSkill.deprecated }">
              <el-icon><Lightning /></el-icon>
            </div>
            <div class="detail-title-area">
              <div class="detail-title">
                {{ currentSkill.name }}
                <el-tag size="small" effect="plain" round>v{{ currentSkill.version }}</el-tag>
                <el-tag v-if="currentSkill.deprecated" size="small" type="danger" effect="dark" round>
                  已废弃
                </el-tag>
              </div>
              <div class="detail-tools" v-if="currentSkill.tools.length">
                <el-tag v-for="t in currentSkill.tools" :key="t" size="small" type="info" effect="plain" round>
                  {{ t }}
                </el-tag>
              </div>
            </div>
          </div>
          <div class="detail-desc">{{ currentSkill.description }}</div>
          <div class="detail-trigger" v-if="currentSkill.trigger">
            <el-icon><Aim /></el-icon>
            <span class="trigger-label">触发条件：</span>
            <span class="trigger-text">{{ currentSkill.trigger }}</span>
          </div>
        </div>

        <!-- 标签页 -->
        <el-tabs v-model="detailTab" class="detail-tabs">
          <!-- 概览 Tab -->
          <el-tab-pane label="概览" name="overview">
            <!-- 统计面板 -->
            <div class="stats-panel" v-if="statsMap[currentSkill.name]">
              <div class="stat-card">
                <div class="stat-icon invocations">
                  <el-icon><DataLine /></el-icon>
                </div>
                <div class="stat-body">
                  <div class="stat-value">{{ statsMap[currentSkill.name].invocations }}</div>
                  <div class="stat-label">总调用</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon failures" :class="{ active: statsMap[currentSkill.name].failures > 0 }">
                  <el-icon><Warning /></el-icon>
                </div>
                <div class="stat-body">
                  <div class="stat-value" :class="{ 'has-error': statsMap[currentSkill.name].failures > 0 }">
                    {{ statsMap[currentSkill.name].failures }}
                  </div>
                  <div class="stat-label">失败次数</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon success">
                  <el-icon><CircleCheck /></el-icon>
                </div>
                <div class="stat-body">
                  <div class="stat-value text">{{ statsMap[currentSkill.name].last_success_at || '-' }}</div>
                  <div class="stat-label">上次成功</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon failed">
                  <el-icon><CircleClose /></el-icon>
                </div>
                <div class="stat-body">
                  <div class="stat-value text">{{ statsMap[currentSkill.name].last_failed_at || '-' }}</div>
                  <div class="stat-label">上次失败</div>
                </div>
              </div>
            </div>

            <!-- 脚本列表 -->
            <div v-if="currentSkill.scripts.length" class="detail-section">
              <div class="section-title">
                <el-icon><Document /></el-icon> 脚本
              </div>
              <el-table :data="currentSkill.scripts" size="small" border>
                <el-table-column prop="id" label="ID" width="120" />
                <el-table-column prop="lang" label="语言" width="80" />
                <el-table-column prop="entry" label="入口" />
                <el-table-column prop="timeout" label="超时" width="70" />
              </el-table>
            </div>

            <!-- 源目录 -->
            <div class="detail-section">
              <div class="section-title">
                <el-icon><FolderOpened /></el-icon> 源目录
              </div>
              <div class="source-dir">{{ currentSkill.source_dir }}</div>
            </div>

            <!-- 操作按钮 -->
            <div class="detail-actions">
              <el-button
                v-if="!currentSkill.deprecated"
                type="warning"
                plain
                :icon="Warning"
                @click="deprecateSkill"
              >标记废弃</el-button>
              <el-button type="danger" plain :icon="Delete" @click="deleteSkill">物理删除</el-button>
            </div>
          </el-tab-pane>

          <!-- SKILL.md 内容 Tab -->
          <el-tab-pane label="SKILL.md" name="content">
            <div class="content-toolbar">
              <el-button link size="small" @click="copyContent">
                <el-icon><CopyDocument /></el-icon> 复制
              </el-button>
              <el-button v-if="!editMode" link size="small" @click="enterEditMode">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button v-else link size="small" type="primary" @click="saveContent" :loading="saving">
                <el-icon><Check /></el-icon> 保存
              </el-button>
              <el-button v-if="editMode" link size="small" @click="cancelEdit">
                <el-icon><Close /></el-icon> 取消
              </el-button>
            </div>
            <!-- 预览模式 -->
            <div v-if="!editMode" class="skill-preview markdown-body" v-html="renderedContent"></div>
            <!-- 编辑模式 -->
            <div v-else class="skill-edit">
              <el-input
                v-model="editingContent"
                type="textarea"
                :rows="22"
                :maxlength="50000"
                show-word-limit
                class="skill-editor"
              />
            </div>
          </el-tab-pane>

          <!-- 版本历史 Tab -->
          <el-tab-pane label="版本历史" name="versions">
            <div v-if="!versions.length" class="versions-empty">
              <el-empty description="暂无历史版本" :image-size="80" />
            </div>
            <div v-else>
              <el-button
                type="warning"
                plain
                size="small"
                :icon="RefreshLeft"
                @click="rollbackSkill"
                style="margin-bottom: 12px"
              >
                回滚到上一版本
              </el-button>
              <el-timeline>
                <el-timeline-item
                  v-for="v in versions"
                  :key="v.version"
                  :timestamp="v.version"
                  placement="top"
                >
                  <div class="version-item">
                    <span class="version-desc">{{ v.description }}</span>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

    <!-- 新建 Skill 对话框 -->
    <el-dialog v-model="createVisible" title="新建 Skill" width="560px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="小写字母+数字+连字符，如 my-skill"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="2"
            placeholder="一句话描述 Skill 的用途"
          />
        </el-form-item>
        <!-- AI 生成模板按钮（仅填了名称和描述后可用） -->
        <el-form-item v-if="createForm.name && createForm.description" label="模板">
          <div class="ai-gen-row">
            <el-button
              size="small"
              plain
              :icon="MagicStick"
              :loading="aiGenerating"
              @click="aiGenerate"
            >
              生成内容模板
            </el-button>
            <span v-if="aiGenerated" class="ai-gen-hint">
              已生成，可继续编辑下方内容
            </span>
          </div>
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="createForm.content"
            type="textarea"
            :rows="8"
            placeholder="留空将自动生成模板，或点击上方按钮 AI 生成"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createSkill">创建</el-button>
      </template>
    </el-dialog>

    <!-- URL 安装 Skill 对话框 -->
    <el-dialog v-model="installUrlVisible" title="从 URL 安装 Skill" width="560px">
      <el-alert
        title="安装说明"
        type="info"
        :closable="false"
        style="margin-bottom: 16px"
      >
        <template #default>
          支持从 GitHub 或其他直链下载 <strong>SKILL.md</strong> 文件并安装到本地。
          <br />例如：
          <code class="url-example">https://raw.githubusercontent.com/user/repo/main/skills/my-skill/SKILL.md</code>
        </template>
      </el-alert>
      <el-form label-width="90px">
        <el-form-item label="URL">
          <el-input
            v-model="installUrlForm.url"
            placeholder="https://raw.githubusercontent.com/..."
            clearable
          />
        </el-form-item>
        <el-form-item label="覆盖已有">
          <el-switch v-model="installUrlForm.overwrite" />
          <span class="import-hint">同名 Skill 已存在时是否覆盖</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="installUrlVisible = false">取消</el-button>
        <el-button type="primary" :loading="installingUrl" @click="doInstallUrl">安装</el-button>
      </template>
    </el-dialog>

    <!-- 导入 Skill 对话框 -->
    <el-dialog v-model="importVisible" title="导入本地 Skill" width="560px">
      <el-alert
        title="导入说明"
        type="info"
        :closable="false"
        style="margin-bottom: 16px"
      >
        <template #default>
          支持两种导入方式：
          <ul style="margin: 4px 0 0; padding-left: 16px">
            <li><strong>浏览上传</strong>：点击浏览按钮选择 SKILL.md 文件或整个 Skill 目录</li>
            <li><strong>路径导入</strong>：手动输入服务器本地路径（目录或 SKILL.md 文件）</li>
          </ul>
          导入后 version 重置为 1。node_modules / .versions / __pycache__ 会被自动排除。
        </template>
      </el-alert>

      <!-- 隐藏的文件选择 input -->
      <input
        ref="fileInputRef"
        type="file"
        accept=".md"
        style="display: none"
        @change="onFilePicked"
      />
      <input
        ref="dirInputRef"
        type="file"
        style="display: none"
        @change="onDirPicked"
      />

      <el-form :model="importForm" label-width="90px">
        <!-- 浏览上传区域 -->
        <el-form-item label="浏览上传">
          <div class="browse-area">
            <el-button-group>
              <el-button :icon="Document" @click="pickFile">选择文件</el-button>
              <el-button :icon="FolderOpened" @click="pickDir">选择目录</el-button>
            </el-button-group>
            <!-- 已选文件预览 -->
            <div v-if="uploadFiles.length > 0" class="picked-files">
              <div class="picked-summary">
                <el-tag size="small" type="success" effect="dark">
                  {{ uploadFiles.length }} 个文件
                </el-tag>
                <span class="picked-root">{{ uploadRootDir }}</span>
                <el-button link size="small" type="danger" @click="clearPicked">
                  <el-icon><Close /></el-icon> 清除
                </el-button>
              </div>
              <div class="picked-scroll">
                <div v-for="f in uploadPreview" :key="f.path" class="picked-file-item">
                  <el-icon class="picked-file-icon"><Document /></el-icon>
                  <span class="picked-file-path">{{ f.path }}</span>
                  <span class="picked-file-size">{{ formatSize(f.size) }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>

        <!-- 分隔线 -->
        <el-divider content-position="center">
          <span class="divider-text">或手动输入路径</span>
        </el-divider>

        <!-- 路径输入 -->
        <el-form-item label="本地路径">
          <el-input
            v-model="importForm.source_path"
            placeholder="例如：D:\my-skills\my-skill 或 C:\...\SKILL.md"
            clearable
            :disabled="uploadFiles.length > 0"
          />
        </el-form-item>
        <el-form-item label="覆盖已有">
          <el-switch v-model="importForm.overwrite" />
          <span class="import-hint">同名 Skill 已存在时是否覆盖</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入</el-button>
      </template>
    </el-dialog>

    <!-- 进化候选对话框 -->
    <el-dialog v-model="showPending" title="Skill 进化候选" width="700px" top="5vh">
      <div v-if="!pendingList.length" class="pending-empty">
        <el-empty description="暂无待确认的进化候选" :image-size="80" />
      </div>
      <div v-else class="pending-list">
        <el-card
          v-for="p in pendingList"
          :key="p.id"
          shadow="never"
          class="pending-card"
        >
          <div class="pending-header">
            <el-tag :type="p.action === 'fix' ? 'warning' : 'success'" size="small" effect="dark">
              {{ p.action === 'fix' ? '修复' : '新建' }}
            </el-tag>
            <span class="pending-skill">{{ p.skill_name }}</span>
            <span class="pending-time">{{ p.created_at }}</span>
          </div>
          <div class="pending-reason">{{ p.reason }}</div>
          <el-divider />
          <div class="pending-content-preview">
            <pre>{{ truncate(p.content, 500) }}</pre>
          </div>
          <div class="pending-actions">
            <el-button
              type="success"
              :loading="confirmingId === p.id"
              @click="confirmPending(p)"
            >
              <el-icon><Check /></el-icon> 确认采纳
            </el-button>
            <el-button
              type="danger"
              plain
              :loading="rejectingId === p.id"
              @click="rejectPending(p)"
            >
              <el-icon><Close /></el-icon> 拒绝
            </el-button>
          </div>
        </el-card>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Plus, Search, Edit, Delete, Document, CopyDocument,
  ArrowRight, Lightning, DataLine, Aim, Clock, RefreshLeft,
  MagicStick, Warning, Check, Close, Upload, MoreFilled,
  View, FolderOpened, CircleCheck, CircleClose, Link,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { skillApi, evolutionApi } from '../api'

const loading = ref(false)
const skills = ref([])
const keyword = ref('')
const statsMap = reactive({})
const detailVisible = ref(false)
const currentSkill = ref(null)
const skillContent = ref('')
const editMode = ref(false)
const editingContent = ref('')
const saving = ref(false)
const versions = ref([])
const detailTab = ref('overview')
const activeFilter = ref('all')

// 新建
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const createForm = ref({ name: '', description: '', content: '' })
const createRules = {
  name: [
    { required: true, message: '请输入 Skill 名称', trigger: 'blur' },
    { pattern: /^[a-z0-9][a-z0-9-]{0,31}$/, message: '小写字母+数字+连字符，2-32 字符', trigger: 'blur' },
  ],
  description: [{ required: true, message: '请输入描述', trigger: 'blur' }],
}

// AI 生成模板
const aiGenerating = ref(false)
const aiGenerated = ref(false)

async function aiGenerate() {
  if (!createForm.value.name || !createForm.value.description) return
  aiGenerating.value = true
  try {
    const r = await skillApi.aiGenerate({
      name: createForm.value.name,
      description: createForm.value.description,
    })
    createForm.value.content = r.content
    aiGenerated.value = true
    ElMessage.success('模板已生成，可继续编辑')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    aiGenerating.value = false
  }
}

// URL 安装
const installUrlVisible = ref(false)
const installingUrl = ref(false)
const installUrlForm = ref({ url: '', overwrite: false })

function openInstallUrl() {
  installUrlForm.value = { url: '', overwrite: false }
  installUrlVisible.value = true
}

async function doInstallUrl() {
  if (!installUrlForm.value.url.trim()) {
    ElMessage.warning('请输入 URL')
    return
  }
  installingUrl.value = true
  try {
    const r = await skillApi.installUrl(installUrlForm.value)
    ElMessage.success(r.message || '安装成功')
    installUrlVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '安装失败')
  } finally {
    installingUrl.value = false
  }
}

// 导入
const importVisible = ref(false)
const importing = ref(false)
const importForm = ref({ source_path: '', overwrite: false })

// 浏览上传
const fileInputRef = ref(null)
const dirInputRef = ref(null)
const uploadFiles = ref([])        // File 对象数组
const uploadPreview = ref([])      // [{path, size}, ...]
const uploadRootDir = ref('')      // 选中目录的名称

// 进化候选
const showPending = ref(false)
const pendingList = ref([])
const pendingCount = ref(0)
const confirmingId = ref('')
const rejectingId = ref('')

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

// 过滤标签
const filterTabs = computed(() => [
  { key: 'all', label: '全部', count: skills.value.length },
  { key: 'active', label: '活跃', count: skills.value.filter(s => !s.deprecated).length },
  { key: 'deprecated', label: '已废弃', count: skills.value.filter(s => s.deprecated).length },
])

const filteredSkills = computed(() => {
  let list = skills.value
  if (activeFilter.value === 'active') list = list.filter(s => !s.deprecated)
  else if (activeFilter.value === 'deprecated') list = list.filter(s => s.deprecated)
  if (!keyword.value) return list
  const kw = keyword.value.toLowerCase()
  return list.filter(
    (s) => s.name.toLowerCase().includes(kw) || s.description.toLowerCase().includes(kw),
  )
})

const emptyText = computed(() => {
  if (keyword.value) return '未搜索到匹配的 Skill'
  if (activeFilter.value === 'active') return '暂无活跃 Skill'
  if (activeFilter.value === 'deprecated') return '暂无废弃 Skill'
  return '暂无 Skill，点击右上角新建或导入'
})

const renderedContent = computed(() => {
  if (!skillContent.value) return '<p style="color:#ccc">加载中...</p>'
  const text = skillContent.value
  const match = text.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/)
  const body = match ? match[1] : text
  return md.render(body)
})

async function loadAll() {
  loading.value = true
  try {
    skills.value = await skillApi.list()
    loadStats()
    loadPending()
  } catch (e) {
    ElMessage.error('加载 Skill 列表失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  for (const s of skills.value) {
    try {
      const st = await skillApi.stats(s.name)
      statsMap[s.name] = st
    } catch {
      // 统计不存在时静默
    }
  }
}

async function loadPending() {
  try {
    pendingList.value = await evolutionApi.pending()
    pendingCount.value = pendingList.value.length
  } catch {
    pendingList.value = []
    pendingCount.value = 0
  }
}

async function openDetail(skill) {
  currentSkill.value = skill
  detailVisible.value = true
  detailTab.value = 'overview'
  editMode.value = false
  versions.value = []
  try {
    const r = await skillApi.getContent(skill.name)
    skillContent.value = r.content
  } catch (e) {
    skillContent.value = ''
    ElMessage.error('加载 SKILL.md 失败')
  }
  try {
    versions.value = await skillApi.versions(skill.name)
  } catch {
    versions.value = []
  }
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '…' : text
}

function enterEditMode() {
  editingContent.value = skillContent.value
  editMode.value = true
}

function cancelEdit() {
  editMode.value = false
  editingContent.value = ''
}

async function saveContent() {
  if (!currentSkill.value) return
  saving.value = true
  try {
    const r = await skillApi.updateContent(currentSkill.value.name, editingContent.value)
    ElMessage.success(r.message || '保存成功')
    editMode.value = false
    skillContent.value = editingContent.value
    skills.value = await skillApi.list()
    versions.value = await skillApi.versions(currentSkill.value.name)
    const updated = skills.value.find((s) => s.name === currentSkill.value.name)
    if (updated) currentSkill.value = updated
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(skillContent.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败')
  }
}

function openCreate() {
  createForm.value = { name: '', description: '', content: '' }
  aiGenerated.value = false
  createVisible.value = true
}

async function createSkill() {
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  creating.value = true
  try {
    const r = await skillApi.create(createForm.value)
    ElMessage.success(r.message || '创建成功')
    createVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

// 导入功能
function openImport() {
  importForm.value = { source_path: '', overwrite: false }
  clearPicked()
  importVisible.value = true
}

// --- 浏览上传 ---
function pickFile() {
  fileInputRef.value?.click()
}

function pickDir() {
  // 设置 webkitdirectory 属性（Vue 不原生支持，需手动设置）
  if (dirInputRef.value) {
    dirInputRef.value.setAttribute('webkitdirectory', '')
    dirInputRef.value.setAttribute('directory', '')
  }
  dirInputRef.value?.click()
}

function onFilePicked(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  uploadFiles.value = files
  uploadPreview.value = files.map(f => ({ path: f.name, size: f.size }))
  uploadRootDir.value = ''
  // 禁用路径输入
  importForm.value.source_path = ''
  e.target.value = ''  // 重置以便可重复选择
}

function onDirPicked(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  uploadFiles.value = files
  uploadPreview.value = files.map(f => ({
    path: f.webkitRelativePath || f.name,
    size: f.size,
  }))
  // 提取根目录名
  const first = files[0]?.webkitRelativePath || ''
  uploadRootDir.value = first.split('/')[0] || ''
  importForm.value.source_path = ''
  e.target.value = ''
}

function clearPicked() {
  uploadFiles.value = []
  uploadPreview.value = []
  uploadRootDir.value = ''
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      // 去掉 data:...;base64, 前缀
      resolve(result.split(',')[1] || '')
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function doImport() {
  // 上传模式
  if (uploadFiles.value.length > 0) {
    importing.value = true
    try {
      // 检查是否包含 SKILL.md
      const hasSkillMd = uploadPreview.value.some(
        f => f.path.split('/').pop().toUpperCase() === 'SKILL.MD'
      )
      if (!hasSkillMd) {
        ElMessage.warning('所选文件中未找到 SKILL.md')
        importing.value = false
        return
      }
      // 构建 base64 文件列表
      const filesData = []
      for (let i = 0; i < uploadFiles.value.length; i++) {
        const f = uploadFiles.value[i]
        const path = f.webkitRelativePath || f.name
        // 排除不需要的文件/目录
        const parts = path.split('/')
        if (parts.some(p => ['node_modules', '.versions', '__pycache__', '.git', 'dist'].includes(p))) {
          continue
        }
        const content = await fileToBase64(f)
        filesData.push({ path, content })
      }
      if (!filesData.length) {
        ElMessage.warning('过滤后无可导入的文件')
        importing.value = false
        return
      }
      const r = await skillApi.upload({ files: filesData, overwrite: importForm.value.overwrite })
      ElMessage.success(r.message || '上传导入成功')
      importVisible.value = false
      clearPicked()
      await loadAll()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '上传导入失败')
    } finally {
      importing.value = false
    }
    return
  }

  // 路径模式（原有逻辑）
  if (!importForm.value.source_path.trim()) {
    ElMessage.warning('请浏览选择文件或输入本地路径')
    return
  }
  importing.value = true
  try {
    const r = await skillApi.import(importForm.value)
    ElMessage.success(r.message || '导入成功')
    importVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

// 快捷操作
function quickEdit(s) {
  openDetail(s)
  detailTab.value = 'content'
  setTimeout(() => enterEditMode(), 300)
}

async function quickDeprecate(s) {
  try {
    await ElMessageBox.confirm(
      `确定将「${s.name}」标记为废弃吗？废弃后不会被注入 Agent，但文件保留。`,
      '废弃确认',
      { type: 'warning' },
    )
    await skillApi.remove(s.name, 'deprecate')
    ElMessage.success('已标记废弃')
    await loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function quickDelete(s) {
  try {
    await ElMessageBox.confirm(
      `确定物理删除「${s.name}」吗？此操作不可恢复！`,
      '删除确认',
      { type: 'error', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await skillApi.remove(s.name, 'delete')
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function deprecateSkill() {
  if (!currentSkill.value) return
  try {
    await ElMessageBox.confirm(
      `确定将「${currentSkill.value.name}」标记为废弃吗？废弃后不会被注入 Agent，但文件保留。`,
      '废弃确认',
      { type: 'warning' },
    )
    await skillApi.remove(currentSkill.value.name, 'deprecate')
    ElMessage.success('已标记废弃')
    detailVisible.value = false
    await loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function deleteSkill() {
  if (!currentSkill.value) return
  try {
    await ElMessageBox.confirm(
      `确定物理删除「${currentSkill.value.name}」吗？此操作不可恢复！`,
      '删除确认',
      { type: 'error', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await skillApi.remove(currentSkill.value.name, 'delete')
    ElMessage.success('已删除')
    detailVisible.value = false
    await loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function rollbackSkill() {
  if (!currentSkill.value) return
  try {
    await ElMessageBox.confirm(
      `确定将「${currentSkill.value.name}」回滚到上一版本吗？`,
      '回滚确认',
      { type: 'warning' },
    )
    const r = await skillApi.rollback(currentSkill.value.name)
    ElMessage.success(r.message || '回滚成功')
    await loadAll()
    const updated = skills.value.find((s) => s.name === currentSkill.value.name)
    if (updated) openDetail(updated)
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '回滚失败')
  }
}

async function confirmPending(p) {
  confirmingId.value = p.id
  try {
    await evolutionApi.confirm(p.id)
    ElMessage.success('已采纳')
    pendingList.value = pendingList.value.filter((x) => x.id !== p.id)
    pendingCount.value = pendingList.value.length
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '确认失败')
  } finally {
    confirmingId.value = ''
  }
}

async function rejectPending(p) {
  rejectingId.value = p.id
  try {
    await evolutionApi.reject(p.id)
    ElMessage.success('已拒绝')
    pendingList.value = pendingList.value.filter((x) => x.id !== p.id)
    pendingCount.value = pendingList.value.length
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    rejectingId.value = ''
  }
}

onMounted(loadAll)
</script>

<style scoped>
.skill-manage {
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
.pending-badge {
  margin-left: 4px;
}
.page-header-right {
  display: flex;
  gap: 8px;
  align-items: center;
}
.search-input {
  width: 260px;
}

/* 过滤栏 */
.filter-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 0;
}
.filter-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  font-size: 13px;
  color: #6b7280;
}
.filter-tab:hover {
  color: #1e293b;
}
.filter-tab.active {
  color: #1e293b;
  border-bottom-color: #1e293b;
  font-weight: 600;
}
.filter-count {
  font-size: 11px;
  background: #f3f4f6;
  color: #6b7280;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.filter-tab.active .filter-count {
  background: #e2e8f0;
  color: #1e293b;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  min-height: 200px;
}

/* Skill 卡片 */
.skill-card {
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  cursor: pointer;
  transition: all 0.2s;
  overflow: hidden;
  position: relative;
}
.skill-card:hover {
  border-color: #cbd5e1;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
.skill-card.is-deprecated {
  opacity: 0.6;
}
.skill-card :deep(.el-card__body) {
  padding: 16px;
}

/* 顶部色条 */
.card-stripe {
  height: 3px;
  background: #1e293b;
  margin: -16px -16px 12px -16px;
  border-radius: 10px 10px 0 0;
}
.card-stripe.deprecated {
  background: linear-gradient(90deg, #9ca3af, #d1d5db);
}

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
.skill-icon {
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
.skill-icon.deprecated {
  background: linear-gradient(135deg, #9ca3af, #d1d5db);
}
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
  gap: 6px;
  flex-wrap: wrap;
}
.card-subtitle {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
  font-family: 'SF Mono', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-more {
  font-size: 16px;
  color: #d1d5db;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;
  flex-shrink: 0;
}
.card-more:hover {
  color: #1e293b;
  background: #f1f5f9;
}

/* 描述 */
.card-desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 脚本标签 */
.card-scripts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

/* 底部 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid #f5f5f5;
}
.footer-stats {
  display: flex;
  gap: 12px;
}
.stat-item {
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 3px;
}
.trigger-item {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-arrow {
  color: #d1d5db;
  font-size: 14px;
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
  margin-bottom: 12px;
}
.skill-icon-lg {
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
.skill-icon-lg.deprecated {
  background: linear-gradient(135deg, #9ca3af, #d1d5db);
}
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
  gap: 6px;
  flex-wrap: wrap;
}
.detail-tools {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}
.detail-desc {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  background: #f9fafb;
  padding: 12px 16px;
  border-radius: 8px;
}
.detail-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 13px;
  color: #6b7280;
}
.detail-trigger .el-icon {
  color: #64748b;
}
.trigger-label {
  font-weight: 600;
}
.trigger-text {
  font-family: 'SF Mono', 'Consolas', monospace;
}

/* 详情标签页 */
.detail-tabs {
  margin-top: 8px;
}

/* 统计面板 */
.stats-panel {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: #f9fafb;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  transition: all 0.2s;
}
.stat-card:hover {
  border-color: #e2e8f0;
}
.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.stat-icon.invocations {
  background: #f1f5f9;
  color: #1e293b;
}
.stat-icon.failures {
  background: #fef3c7;
  color: #d97706;
}
.stat-icon.failures.active {
  background: #fee2e2;
  color: #ef4444;
}
.stat-icon.success {
  background: #d1fae5;
  color: #059669;
}
.stat-icon.failed {
  background: #fee2e2;
  color: #ef4444;
}
.stat-body {
  flex: 1;
  min-width: 0;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-value.text {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stat-value.has-error {
  color: #ef4444;
}
.stat-label {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}

/* 详情分区 */
.detail-section {
  margin-bottom: 24px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 10px;
}
.source-dir {
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: #6b7280;
  background: #f9fafb;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
  word-break: break-all;
}

/* 内容工具栏 */
.content-toolbar {
  display: flex;
  gap: 4px;
  margin-bottom: 10px;
}

/* Markdown 预览 */
.skill-preview {
  background: #f9fafb;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px;
  font-size: 13px;
  line-height: 1.7;
  max-height: 500px;
  overflow-y: auto;
}
.skill-preview :deep(p) {
  margin: 0 0 8px;
}
.skill-preview :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.skill-preview :deep(code) {
  background: #f3f4f6;
  padding: 2px 5px;
  border-radius: 3px;
  font-size: 12px;
}
.skill-preview :deep(pre code) {
  background: transparent;
  padding: 0;
}
.skill-preview :deep(table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
  margin: 8px 0;
}
.skill-preview :deep(th),
.skill-preview :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 5px 10px;
}
.skill-preview :deep(th) {
  background: #f3f4f6;
  font-weight: 600;
}
.skill-preview :deep(ul),
.skill-preview :deep(ol) {
  padding-left: 20px;
  margin: 0 0 8px;
}

/* 编辑模式 */
.skill-edit {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.skill-editor :deep(.el-textarea__inner) {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
}

/* 版本历史 */
.versions-empty {
  padding: 20px 0;
}
.version-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-desc {
  font-size: 13px;
  color: #4b5563;
}

/* 详情操作按钮 */
.detail-actions {
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  margin-top: 20px;
}

/* 导入对话框 */
.import-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #9ca3af;
}
.divider-text {
  font-size: 12px;
  color: #9ca3af;
}

/* AI 生成模板 */
.ai-gen-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ai-gen-hint {
  font-size: 12px;
  color: #10b981;
}

/* URL 安装 */
.url-example {
  font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  color: #1e293b;
  word-break: break-all;
}

/* 浏览上传区域 */
.browse-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.picked-files {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}
.picked-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
}
.picked-root {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Consolas', monospace;
}
.picked-summary .el-button {
  margin-left: auto;
}
.picked-scroll {
  max-height: 200px;
  overflow-y: auto;
  padding: 6px 12px;
}
.picked-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}
.picked-file-icon {
  color: #64748b;
  flex-shrink: 0;
}
.picked-file-path {
  color: #4b5563;
  font-family: 'SF Mono', 'Consolas', monospace;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.picked-file-size {
  color: #9ca3af;
  flex-shrink: 0;
}

/* 进化候选 */
.pending-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pending-card {
  border-radius: 8px;
}
.pending-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.pending-skill {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
}
.pending-time {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}
.pending-reason {
  font-size: 13px;
  color: #6b7280;
  background: #fefce8;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #fef3c7;
}
.pending-content-preview {
  max-height: 200px;
  overflow: auto;
}
.pending-content-preview pre {
  font-size: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  white-space: pre-wrap;
  color: #4b5563;
  margin: 0;
}
.pending-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.pending-empty {
  padding: 40px 0;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }
  .filter-bar {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .filter-tab {
    white-space: nowrap;
    padding: 8px 12px;
  }
  .stats-panel {
    grid-template-columns: 1fr;
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
  .skill-card :deep(.el-card__body) {
    padding: 12px;
  }
  .card-stripe {
    margin: -12px -12px 10px -12px;
  }
  .filter-tab {
    padding: 6px 10px;
    font-size: 12px;
  }
}
</style>
