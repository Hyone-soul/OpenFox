<template>
  <div class="app-layout" :class="{ 'is-electron': isElectron }">
    <header v-if="isElectron" class="desktop-titlebar electron-drag">
      <div class="desktop-titlebar-brand">
        <img src="/OpenFox.png" class="desktop-titlebar-logo" alt="" />
        <span>OpenFox</span>
      </div>
      <div class="desktop-titlebar-actions electron-no-drag">
        <button class="window-action" title="最小化" aria-label="最小化" @click="minimizeWindow">
          <el-icon size="16"><Minus /></el-icon>
        </button>
        <button class="window-action" title="最大化或还原" aria-label="最大化或还原" @click="toggleMaximizeWindow">
          <el-icon size="14"><FullScreen /></el-icon>
        </button>
        <button class="window-action window-action-close" title="关闭" aria-label="关闭" @click="closeWindow">
          <el-icon size="15"><CloseBold /></el-icon>
        </button>
      </div>
    </header>
    <!-- 登录页和介绍页不显示侧栏 -->
    <template v-if="!isPublicPage">
      <!-- 桌面端：固定左侧栏 -->
      <aside v-if="!isMobile" class="sidebar" :class="{ 'electron-drag': isElectron }">
        <!-- 新建对话按钮 + 插件入口 -->
        <div class="sidebar-new-chat" :class="{ 'electron-no-drag': isElectron }">
          <button class="new-chat-btn" @click="handleNewChat">
            <el-icon size="16"><Plus /></el-icon>
            <span>新建对话</span>
          </button>
          <button class="plugin-btn" @click="pluginDialogVisible = true">
            <el-icon size="16"><Connection /></el-icon>
            <span>插件</span>
          </button>
        </div>

        <!-- 会话列表（按项目分组） -->
        <div class="sidebar-sessions" :class="{ 'electron-no-drag': isElectron }">
          <div class="sessions-header">
            <span class="sessions-label">项目</span>
            <span class="sessions-count">{{ chatSessions.length }}</span>
          </div>
          <div class="sessions-list">
            <template v-for="group in groupedSessions" :key="group.project ? group.project.id : '__unlinked'">
              <!-- 项目分组标题 -->
              <div
                v-if="group.project"
                :class="['project-group-header', { 'project-pinned': group.project.pinned }]"
                @click="toggleProjectCollapse(group.project.id)"
                @contextmenu.prevent="openProjectContextMenu($event, group.project)"
              >
                <el-icon size="12" class="project-collapse-icon" :class="{ collapsed: collapsedProjects.has(group.project.id) }">
                  <ArrowDown />
                </el-icon>
                <el-icon size="13" class="project-folder-icon"><FolderOpened /></el-icon>
                <span class="project-group-name">{{ group.project.name }}</span>
                <span class="project-group-count">{{ group.sessions.length }}</span>
              </div>
              <!-- 未关联会话标题 -->
              <div v-else class="project-group-header project-group-unlinked">
                <span class="project-group-name">未关联会话</span>
                <span class="project-group-count">{{ group.sessions.length }}</span>
              </div>
              <!-- 会话条目 -->
              <div v-show="!group.project || !collapsedProjects.has(group.project.id)">
                <div
                  v-for="s in group.sessions"
                  :key="s.id"
                  :class="['session-item', { active: s.id === chatSessions_active, 'session-pinned': s.pinned }]"
                  @click="handleSelectSession(s.id)"
                  @contextmenu.prevent="openSessionContextMenu($event, s, group.project)"
                >
                  <el-icon v-if="s.pinned" size="12" class="session-pin-icon"><Top /></el-icon>
                  <el-icon v-else class="session-item-icon" size="14"><ChatRound /></el-icon>
                  <!-- 重命名模式 -->
                  <input
                    v-if="renamingId === s.id"
                    ref="renameInput"
                    class="session-rename-input"
                    v-model="renameValue"
                    @keydown.enter="confirmRename(s.id)"
                    @keydown.escape="cancelRename"
                    @blur="confirmRename(s.id)"
                    @click.stop
                  />
                  <!-- 正常显示 -->
                  <span v-else class="session-item-title">{{ s.title || '未命名会话' }}</span>
                </div>
              </div>
            </template>
            <div v-if="!chatSessions.length" class="sessions-empty">暂无对话</div>
          </div>
        </div>

        <!-- 底部用户区 -->
        <div class="sidebar-bottom" :class="{ 'electron-no-drag': isElectron }">
          <div class="sidebar-footer">
            <div class="user-area" @click="toggleUserMenu">
              <el-icon size="16"><UserFilled /></el-icon>
              <span class="user-name-text">{{ currentUser }}</span>
              <el-icon class="user-arrow" size="12"><ArrowUp /></el-icon>
            </div>
            <!-- 用户下拉菜单 -->
            <transition name="user-menu">
              <div v-if="userMenuOpen" class="user-dropdown">
                <div class="user-dropdown-item" @click="openSettings">
                  <el-icon size="14"><Setting /></el-icon>
                  <span>设置</span>
                </div>
                <div class="user-dropdown-divider"></div>
                <div class="user-dropdown-item user-dropdown-item-danger" @click="handleLogout">
                  <el-icon size="14"><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </div>
                <div v-if="isElectron" class="user-dropdown-item user-dropdown-item-danger" @click="handleQuit">
                  <el-icon size="14"><CloseBold /></el-icon>
                  <span>退出应用</span>
                </div>
              </div>
            </transition>
          </div>
        </div>
      </aside>

      <!-- 移动端：汉堡按钮 + 抽屉 -->
      <div v-if="isMobile" class="mobile-header" :class="{ 'electron-drag': isElectron }">
        <button class="hamburger-btn" :class="{ 'electron-no-drag': isElectron }" @click="drawerOpen = true">
          <img src="/OpenFox.png" class="brand-logo-sm" alt="OpenFox" />
        </button>
        <span class="mobile-title">OpenFox</span>
      </div>
    </template>

    <!-- 移动端抽屉导航 -->
    <el-drawer
      v-if="isMobile && !isPublicPage"
      v-model="drawerOpen"
      direction="ltr"
      size="260px"
      :show-close="false"
      :with-header="false"
    >
      <div class="drawer-nav">
        <div class="drawer-brand">
          <img src="/OpenFox.png" class="brand-logo" alt="OpenFox" />
          <span>OpenFox</span>
        </div>
        <div class="drawer-new-chat">
          <button class="new-chat-btn" @click="handleNewChat(); drawerOpen = false">
            <el-icon size="16"><Plus /></el-icon>
            <span>新建对话</span>
          </button>
          <button class="plugin-btn" @click="pluginDialogVisible = true; drawerOpen = false">
            <el-icon size="16"><Connection /></el-icon>
            <span>插件</span>
          </button>
        </div>
        <!-- 移动端抽屉内也放会话列表（按项目分组） -->
        <div class="drawer-sessions">
          <div class="sessions-header">
            <span class="sessions-label">项目</span>
            <span class="sessions-count">{{ chatSessions.length }}</span>
          </div>
          <div class="sessions-list">
            <template v-for="group in groupedSessions" :key="group.project ? group.project.id : '__unlinked'">
              <div v-if="group.project" :class="['project-group-header', { 'project-pinned': group.project.pinned }]" @click="toggleProjectCollapse(group.project.id)" @contextmenu.prevent="openProjectContextMenu($event, group.project)">
                <el-icon size="12" class="project-collapse-icon" :class="{ collapsed: collapsedProjects.has(group.project.id) }"><ArrowDown /></el-icon>
                <el-icon size="13" class="project-folder-icon"><FolderOpened /></el-icon>
                <span class="project-group-name">{{ group.project.name }}</span>
                <span class="project-group-count">{{ group.sessions.length }}</span>
              </div>
              <div v-else class="project-group-header project-group-unlinked">
                <span class="project-group-name">未关联会话</span>
                <span class="project-group-count">{{ group.sessions.length }}</span>
              </div>
              <div v-show="!group.project || !collapsedProjects.has(group.project.id)">
                <div
                  v-for="s in group.sessions"
                  :key="s.id"
                  :class="['session-item', { active: s.id === chatSessions_active, 'session-pinned': s.pinned }]"
                  @click="handleSelectSession(s.id); drawerOpen = false"
                  @contextmenu.prevent="openSessionContextMenu($event, s, group.project)"
                >
                  <el-icon class="session-item-icon" size="14"><ChatRound /></el-icon>
                  <span class="session-item-title">{{ s.title || '未命名会话' }}</span>
                </div>
              </div>
            </template>
          </div>
        </div>
        <div class="drawer-footer">
          <div class="user-area" @click="toggleUserMenu">
            <el-icon size="16"><UserFilled /></el-icon>
            <span>{{ currentUser }}</span>
            <el-icon class="user-arrow" size="12"><ArrowUp /></el-icon>
          </div>
          <transition name="user-menu">
            <div v-if="userMenuOpen" class="user-dropdown">
              <div class="user-dropdown-item" @click="openSettings">
                <el-icon size="14"><Setting /></el-icon>
                <span>设置</span>
              </div>
              <div class="user-dropdown-divider"></div>
              <div class="user-dropdown-item user-dropdown-item-danger" @click="handleLogout">
                <el-icon size="14"><SwitchButton /></el-icon>
                <span>退出登录</span>
              </div>
              <div v-if="isElectron" class="user-dropdown-item user-dropdown-item-danger" @click="handleQuit">
                <el-icon size="14"><CloseBold /></el-icon>
                <span>退出应用</span>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </el-drawer>

    <!-- 插件弹窗：Skill + MCP -->
    <el-dialog
      v-model="pluginDialogVisible"
      title="插件管理"
      width="80%"
      :close-on-click-modal="false"
      class="plugin-dialog"
      destroy-on-close
    >
      <div class="dialog-split">
        <div class="dialog-tabs">
          <div
            :class="['dialog-tab', { active: pluginTab === 'skill' }]"
            @click="pluginTab = 'skill'"
          >
            <el-icon size="16"><MagicStick /></el-icon>
            <span>Skill 管理</span>
          </div>
          <div
            :class="['dialog-tab', { active: pluginTab === 'mcp' }]"
            @click="pluginTab = 'mcp'"
          >
            <el-icon size="16"><Connection /></el-icon>
            <span>MCP 管理</span>
          </div>
        </div>
        <div class="dialog-body">
          <SkillManage v-if="pluginTab === 'skill'" :embedded="true" />
          <MCPManage v-if="pluginTab === 'mcp'" :embedded="true" />
        </div>
      </div>
    </el-dialog>

    <!-- 设置弹窗：模型 + 记忆 + 用量 -->
    <el-dialog
      v-model="settingsDialogVisible"
      title="设置"
      width="80%"
      :close-on-click-modal="false"
      class="settings-dialog"
      destroy-on-close
    >
      <div class="dialog-split">
        <div class="dialog-tabs">
          <div
            :class="['dialog-tab', { active: settingsTab === 'models' }]"
            @click="settingsTab = 'models'"
          >
            <el-icon size="16"><Cpu /></el-icon>
            <span>模型管理</span>
          </div>
          <div
            :class="['dialog-tab', { active: settingsTab === 'memory' }]"
            @click="settingsTab = 'memory'"
          >
            <el-icon size="16"><Collection /></el-icon>
            <span>记忆管理</span>
          </div>
          <div
            :class="['dialog-tab', { active: settingsTab === 'usage' }]"
            @click="settingsTab = 'usage'"
          >
            <el-icon size="16"><DataAnalysis /></el-icon>
            <span>用量管理</span>
          </div>
          <div
            :class="['dialog-tab', { active: settingsTab === 'tools' }]"
            @click="settingsTab = 'tools'"
          >
            <el-icon size="16"><Tools /></el-icon>
            <span>工具管理</span>
          </div>
        </div>
        <div class="dialog-body">
          <ModelManage v-if="settingsTab === 'models'" :embedded="true" />
          <MemoryManage v-if="settingsTab === 'memory'" :embedded="true" />
          <UsageManage v-if="settingsTab === 'usage'" :embedded="true" />
          <ToolsManage v-if="settingsTab === 'tools'" :embedded="true" />
        </div>
      </div>
    </el-dialog>

    <!-- 主内容区 -->
    <main :class="[isPublicPage ? 'main-content-login' : 'main-content', { 'main-content-chat': isChatPage }]">
      <router-view />
    </main>

    <!-- 项目三点菜单浮层 -->
    <div
      v-if="projectMenu.visible"
      class="ctx-menu"
      :style="{ top: projectMenu.y + 'px', left: projectMenu.x + 'px' }"
      @click.stop
    >
      <div class="ctx-menu-item" @click="handleProjectMenuNewSession">
        <el-icon size="14"><Plus /></el-icon>
        <span>新增会话</span>
      </div>
      <div class="ctx-menu-item" @click="handleProjectMenuTogglePin">
        <el-icon size="14"><Top /></el-icon>
        <span>{{ projectMenu.project?.pinned ? '取消置顶' : '置顶文件夹' }}</span>
      </div>
      <div class="ctx-menu-divider"></div>
      <div class="ctx-menu-item ctx-menu-danger" @click="handleProjectMenuDelete">
        <el-icon size="14"><Delete /></el-icon>
        <span>删除文件夹</span>
      </div>
    </div>

    <!-- 会话右键菜单浮层 -->
    <div
      v-if="sessionMenu.visible"
      class="ctx-menu"
      :style="{ top: sessionMenu.y + 'px', left: sessionMenu.x + 'px' }"
      @click.stop
    >
      <div v-if="sessionMenu.canPin" class="ctx-menu-item" @click="handleSessionMenuTogglePin">
        <el-icon size="14"><Top /></el-icon>
        <span>{{ sessionMenu.session?.pinned ? '取消置顶' : '置顶会话' }}</span>
      </div>
      <div class="ctx-menu-item" @click="handleSessionMenuRename">
        <el-icon size="14"><EditPen /></el-icon>
        <span>重命名</span>
      </div>
      <div class="ctx-menu-divider"></div>
      <div class="ctx-menu-item ctx-menu-danger" @click="handleSessionMenuDelete">
        <el-icon size="14"><Delete /></el-icon>
        <span>删除会话</span>
      </div>
    </div>

    <!-- 删除文件夹二次确认弹窗 -->
    <el-dialog
      v-model="deleteConfirmVisible"
      title="确认删除"
      width="360px"
      :close-on-click-modal="false"
      class="delete-confirm-dialog"
    >
      <div class="delete-confirm-body">
        <p>确定要删除文件夹 <strong>{{ deleteConfirmName }}</strong> 吗？</p>
        <p class="delete-confirm-warn">该操作将删除文件夹及其下所有会话，且不可恢复。</p>
      </div>
      <template #footer>
        <button class="delete-confirm-cancel" @click="deleteConfirmVisible = false">取消</button>
        <button class="delete-confirm-ok" @click="confirmDeleteProject">删除</button>
      </template>
    </el-dialog>

    <!-- 删除会话二次确认弹窗 -->
    <el-dialog
      v-model="deleteSessionConfirmVisible"
      title="确认删除"
      width="360px"
      :close-on-click-modal="false"
      class="delete-confirm-dialog"
    >
      <div class="delete-confirm-body">
        <p>确定要删除会话 <strong>{{ deleteSessionName }}</strong> 吗？</p>
        <p class="delete-confirm-warn">该操作不可恢复。</p>
      </div>
      <template #footer>
        <button class="delete-confirm-cancel" @click="deleteSessionConfirmVisible = false">取消</button>
        <button class="delete-confirm-ok" @click="confirmDeleteSession">删除</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted, nextTick, provide } from 'vue'
import { useRouter } from 'vue-router'
import {
  UserFilled, Plus, ChatRound, CloseBold, Minus, FullScreen,
  Cpu, Collection, MagicStick, Connection, DataAnalysis,
  SwitchButton, ArrowUp, ArrowDown, Setting,
  FolderOpened, Tools, Top, Delete, EditPen,
} from '@element-plus/icons-vue'
import SkillManage from './views/SkillManage.vue'
import MCPManage from './views/MCPManage.vue'
import ModelManage from './views/ModelManage.vue'
import MemoryManage from './views/MemoryManage.vue'
import ToolsManage from './views/ToolsManage.vue'
import UsageManage from './views/UsageManage.vue'
import { useChatSessions } from './composables/useChatSessions'

const router = useRouter()

const isElectron = typeof window !== 'undefined' && window.electronAPI?.isElectron

const currentUser = ref('Fox')
const drawerOpen = ref(false)
const userMenuOpen = ref(false)
const windowWidth = ref(window.innerWidth)

// 插件弹窗
const pluginDialogVisible = ref(false)
const pluginTab = ref('skill')

// 设置弹窗
const settingsDialogVisible = ref(false)
const settingsTab = ref('models')

const isMobile = computed(() => windowWidth.value < 900)

// 旧导航菜单项已收入插件弹窗和设置弹窗
// 插件弹窗包含：Skill 管理 + MCP 管理
// 设置弹窗包含：模型管理 + 记忆管理 + 用量管理

const isPublicPage = computed(() => {
  const path = router.currentRoute.value.path
  return path === '/login'
})

const isChatPage = computed(() => router.currentRoute.value.path === '/chat')

// 使用会话共享状态
const {
  sessions: chatSessions,
  activeSession: chatSessions_active,
  projects: chatProjects,
  groupedSessions,
  createSession,
  createProject,
  deleteProject,
  deleteProjectCascade,
  pinProject,
  pinSession,
  removeSession,
  renameSession,
  selectSession,
  loadAll,
} = useChatSessions()

// 重命名状态
const renamingId = ref(null)
const renameValue = ref('')

// 项目折叠状态
const collapsedProjects = ref(new Set())

// 项目右键菜单状态
const projectMenu = ref({ visible: false, x: 0, y: 0, project: null })

// 会话右键菜单状态
const sessionMenu = ref({ visible: false, x: 0, y: 0, session: null, canPin: false })

// 删除文件夹确认弹窗
const deleteConfirmVisible = ref(false)
const deleteConfirmName = ref('')
const pendingDeleteProjectId = ref('')

// 删除会话确认弹窗
const deleteSessionConfirmVisible = ref(false)
const deleteSessionName = ref('')
const pendingDeleteSessionId = ref('')

function startRename(s) {
  renamingId.value = s.id
  renameValue.value = s.title || '未命名会话'
  // nextTick 聚焦输入框
  nextTick(() => {
    const inputs = document.querySelectorAll('.session-rename-input')
    const input = inputs[inputs.length - 1]
    if (input) { input.focus(); input.select() }
  })
}

async function confirmRename(id) {
  if (renamingId.value !== id) return
  const newTitle = renameValue.value.trim()
  if (newTitle) {
    await renameSession(id, newTitle)
  }
  renamingId.value = null
}

function cancelRename() {
  renamingId.value = null
}

function onResize() {
  windowWidth.value = window.innerWidth
  if (windowWidth.value >= 900) drawerOpen.value = false
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  // 非公开页面才加载会话
  if (!isPublicPage.value) loadAll()
})

onUnmounted(() => window.removeEventListener('resize', onResize))

// 登录后加载会话
watch(isPublicPage, (v) => {
  if (!v) loadAll()
})

// goHome removed — sidebar brand no longer exists

function minimizeWindow() {
  window.electronAPI?.minimize()
}

function toggleMaximizeWindow() {
  window.electronAPI?.toggleMaximize()
}

function closeWindow() {
  window.electronAPI?.close()
}

async function handleNewChat() {
  router.push('/chat')
  const s = await createSession('新会话')
  selectSession(s.id)
}

async function handleNewChatInProject(projectId) {
  router.push('/chat')
  const s = await createSession('新会话', projectId)
  selectSession(s.id)
}

async function handleCreateProject() {
  newChatMenuOpen.value = false
  // 调用 Electron 文件选择对话框
  if (isElectron && window.electronAPI?.selectDirectory) {
    const result = await window.electronAPI.selectDirectory()
    if (result.canceled || !result.path) return
    const p = await createProject(result.path)
    // 选中新项目并创建会话
    await handleNewChatInProject(p.id)
  } else {
    // 非桌面端：用 prompt 输入路径
    const workdir = window.prompt('请输入工作目录路径：')
    if (!workdir) return
    try {
      const p = await createProject(workdir)
      await handleNewChatInProject(p.id)
    } catch {
      // 路径不存在等错误
    }
  }
}

function toggleProjectCollapse(projectId) {
  if (collapsedProjects.value.has(projectId)) {
    collapsedProjects.value.delete(projectId)
  } else {
    collapsedProjects.value.add(projectId)
  }
  // 触发响应式更新
  collapsedProjects.value = new Set(collapsedProjects.value)
}

// ── 项目右键菜单 ──

function openProjectContextMenu(e, project) {
  projectMenu.value = {
    visible: true,
    x: e.clientX,
    y: e.clientY,
    project,
  }
}

function closeProjectMenu() {
  projectMenu.value = { visible: false, x: 0, y: 0, project: null }
}

async function handleProjectMenuNewSession() {
  const pid = projectMenu.value.project?.id
  closeProjectMenu()
  if (pid) await handleNewChatInProject(pid)
}

async function handleProjectMenuTogglePin() {
  const p = projectMenu.value.project
  closeProjectMenu()
  if (p) await pinProject(p.id, !p.pinned)
}

function handleProjectMenuDelete() {
  const p = projectMenu.value.project
  closeProjectMenu()
  if (p) {
    pendingDeleteProjectId.value = p.id
    deleteConfirmName.value = p.name
    deleteConfirmVisible.value = true
  }
}

async function confirmDeleteProject() {
  const id = pendingDeleteProjectId.value
  deleteConfirmVisible.value = false
  if (id) await deleteProjectCascade(id)
}

// ── 会话右键菜单 ──

function openSessionContextMenu(e, session, project) {
  // 文件夹内会话不支持置顶
  const canPin = !project
  sessionMenu.value = {
    visible: true,
    x: e.clientX,
    y: e.clientY,
    session,
    canPin,
  }
}

function closeSessionMenu() {
  sessionMenu.value = { visible: false, x: 0, y: 0, session: null, canPin: false }
}

async function handleSessionMenuTogglePin() {
  const s = sessionMenu.value.session
  closeSessionMenu()
  if (s) await pinSession(s.id, !s.pinned)
}

function handleSessionMenuRename() {
  const s = sessionMenu.value.session
  closeSessionMenu()
  if (s) startRename(s)
}

function handleSessionMenuDelete() {
  const s = sessionMenu.value.session
  closeSessionMenu()
  if (s) {
    pendingDeleteSessionId.value = s.id
    deleteSessionName.value = s.title || '未命名会话'
    deleteSessionConfirmVisible.value = true
  }
}

async function confirmDeleteSession() {
  const id = pendingDeleteSessionId.value
  deleteSessionConfirmVisible.value = false
  if (id) await removeSession(id)
}

function handleSelectSession(id) {
  selectSession(id)
  // 确保在聊天页
  if (router.currentRoute.value.path !== '/chat') {
    router.push('/chat')
  }
}

async function handleRemoveSession(id) {
  pendingDeleteSessionId.value = id
  const s = chatSessions.value.find((x) => x.id === id)
  deleteSessionName.value = s?.title || '未命名会话'
  deleteSessionConfirmVisible.value = true
}

function refreshUser() {
  try {
    const user = JSON.parse(localStorage.getItem('openfox_user') || '{}')
    currentUser.value = user.display_name || user.username || 'Fox'
  } catch {
    currentUser.value = 'Fox'
  }
}

watch(() => router.currentRoute.value.path, refreshUser, { immediate: true })

function openSettings() {
  userMenuOpen.value = false
  settingsDialogVisible.value = true
}

// 暴露给子组件（如 ChatWorkbench 的 /memory 命令）打开设置弹窗并定位到指定 tab
function openSettingsDialog(tab = 'models') {
  settingsTab.value = tab
  settingsDialogVisible.value = true
}
provide('openSettingsDialog', openSettingsDialog)

function handleUserCommand(command) {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'quit') {
    handleQuit()
  }
}

// 用户菜单：切换下拉
function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

// 退出登录
function handleLogout() {
  userMenuOpen.value = false
  localStorage.removeItem('openfox_token')
  localStorage.removeItem('openfox_user')
  currentUser.value = 'Fox'
  router.replace('/login')
}

// 退出应用（桌面端）
function handleQuit() {
  userMenuOpen.value = false
  if (isElectron && window.electronAPI) {
    window.electronAPI.close()
  }
}

// 点击外部关闭用户菜单
function handleClickOutside(e) {
  const userArea = document.querySelector('.user-area')
  const dropdown = document.querySelector('.user-dropdown')
  if (userMenuOpen.value && !userArea?.contains(e.target) && !dropdown?.contains(e.target)) {
    userMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  // 点击外部关闭浮动菜单
  document.addEventListener('click', () => {
    if (projectMenu.value.visible) closeProjectMenu()
    if (sessionMenu.value.visible) closeSessionMenu()
  })
  if (isElectron && window.electronAPI) {
    window.electronAPI.onMenuAction?.((action) => {
      if (action === 'new-chat') {
        handleNewChat()
      } else if (action === 'find') {
        window.document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
      }
    })
    window.electronAPI.onMenuNavigate?.((path) => {
      router.push(path)
    })
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style>
/* 全局 box-sizing 修复 */
*, *::before, *::after {
  box-sizing: border-box;
}

/* 锁死 body 滚动，只保留主内容区滚动 */
html, body {
  margin: 0;
  padding: 0;
  height: 100vh;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
}

/* ===== 整体布局：侧栏 + 主内容 ===== */
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Electron uses one application-owned title bar instead of Windows chrome. */
.app-layout.is-electron {
  position: relative;
  padding-top: 42px;
}

.desktop-titlebar {
  position: absolute;
  z-index: 20;
  top: 0;
  right: 0;
  left: 0;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  user-select: none;
}

.desktop-titlebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 13px;
  font-weight: 650;
}

.desktop-titlebar-logo {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  object-fit: cover;
}

.desktop-titlebar-actions {
  align-self: stretch;
  display: flex;
}

.window-action {
  display: grid;
  width: 46px;
  border: 0;
  place-items: center;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}

.window-action:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.window-action-close:hover {
  background: #dc2626;
  color: #fff;
}

.app-layout.is-electron .sidebar {
  height: calc(100vh - 42px);
}

/* ===== 左侧固定侧栏（桌面端） ===== */
.sidebar {
  width: 240px;
  min-width: 240px;
  height: 100vh;
  background: #f1f5f9;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;
  overflow: hidden;
}

/* 新建对话按钮 + 插件入口 */
.sidebar-new-chat {
  padding: 12px 16px 10px;
  flex-shrink: 0;
  display: flex;
  gap: 8px;
}
.new-chat-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: #e2e8f0;
  color: #1e293b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.new-chat-btn:hover {
  background: #cbd5e1;
}
.plugin-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.plugin-btn:hover {
  background: #e2e8f0;
  color: #1e293b;
}

/* ===== 会话列表区域（Codex 风格） ===== */
.sidebar-sessions {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 12px;
}
.sessions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 6px;
  flex-shrink: 0;
}
.sessions-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.sessions-count {
  font-size: 11px;
  color: #94a3b8;
  background: #e2e8f0;
  padding: 0 6px;
  border-radius: 10px;
  line-height: 18px;
}
.sessions-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* 未关联会话标题：与“项目”标题样式一致 */
.project-group-unlinked .project-group-name {
  font-style: normal;
  color: #94a3b8;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 会话条目 */
.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px 7px 28px; /* 左侧内缩形成结构感 */
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  margin-bottom: 1px;
}
.session-item:hover {
  background: #e2e8f0;
}
.session-item.active {
  background: #e2e8f0;
}
.session-item.active .session-item-title {
  font-weight: 600;
  color: #1e293b;
}
.session-item.active .session-item-icon {
  color: #1e293b;
}
.session-item-icon {
  color: #94a3b8;
  flex-shrink: 0;
}
.session-item-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-rename-input {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #1e293b;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 2px 6px;
  outline: none;
  background: #fff;
}
.session-rename-input:focus {
  border-color: #1e293b;
}
.session-item-delete {
  flex-shrink: 0;
  opacity: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}
.session-item:hover .session-item-delete {
  opacity: 1;
}
.session-item-delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

/* 置顶高亮：浅蓝背景 */
.session-pinned {
  background: #e8eef5;
}
.session-pinned:hover {
  background: #dce5f0;
}
.session-pinned.active {
  background: #d5dfeb;
}

.sessions-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
  padding: 24px 0;
}

/* ===== 项目分组 ===== */
.project-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px 4px;
  cursor: pointer;
  user-select: none;
  position: relative;
}
.project-group-header:hover {
  background: rgba(226, 232, 240, 0.5);
  border-radius: 6px;
}
.project-collapse-icon {
  color: #94a3b8;
  transition: transform 0.15s;
}
.project-collapse-icon.collapsed {
  transform: rotate(-90deg);
}
.project-folder-icon {
  color: #64748b;
  flex-shrink: 0;
}
.project-group-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.project-group-count {
  font-size: 10px;
  color: #94a3b8;
  background: #e2e8f0;
  padding: 0 5px;
  border-radius: 8px;
  line-height: 16px;
  flex-shrink: 0;
}
.project-group-unlinked {
  cursor: default;
  padding-top: 10px;
}
.project-group-unlinked .project-group-name {
  font-style: normal;
  color: #94a3b8;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 项目置顶高亮 */
.project-pinned {
  background: #e8eef5;
  border-radius: 6px;
}
.project-pinned:hover {
  background: #dce5f0;
}

/* ===== 右键菜单浮层 ===== */
.ctx-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 4px;
}
.ctx-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.ctx-menu-item:hover {
  background: #f1f5f9;
  color: #1e293b;
}
.ctx-menu-danger:hover {
  background: #fef2f2;
  color: #ef4444;
}
.ctx-menu-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 4px 0;
}

/* 删除确认弹窗 */
.delete-confirm-body {
  text-align: center;
  padding: 8px 0 16px;
}
.delete-confirm-body p {
  margin: 0 0 8px;
  font-size: 14px;
  color: #1e293b;
}
.delete-confirm-warn {
  font-size: 13px;
  color: #ef4444;
}
.delete-confirm-cancel,
.delete-confirm-ok {
  padding: 7px 20px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid #e2e8f0;
}
.delete-confirm-cancel {
  background: #fff;
  color: #64748b;
  margin-right: 8px;
}
.delete-confirm-cancel:hover {
  background: #f1f5f9;
}
.delete-confirm-ok {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}
.delete-confirm-ok:hover {
  background: #dc2626;
}

/* ===== 侧栏底部：用户区 ===== */
.sidebar-bottom {
  flex-shrink: 0;
  border-top: 1px solid #e2e8f0;
}

/* 侧栏底部用户区域 */
.sidebar-footer {
  padding: 8px 16px 12px;
  position: relative;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.user-area:hover {
  background: #e2e8f0;
  color: #1e293b;
}
.user-arrow {
  margin-left: auto;
  transition: transform 0.2s;
}
.user-area .user-arrow {
  transform: rotate(180deg);
}

/* 用户下拉菜单 */
.user-dropdown {
  position: absolute;
  bottom: 100%;
  left: 16px;
  right: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 4px;
  margin-bottom: 4px;
  z-index: 100;
}
.user-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.user-dropdown-item:hover {
  background: #f1f5f9;
  color: #1e293b;
}
.user-dropdown-item-danger:hover {
  background: #fef2f2;
  color: #ef4444;
}
.user-dropdown-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 4px 0;
}

/* 下拉动画 */
.user-menu-enter-active,
.user-menu-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.user-menu-enter-from,
.user-menu-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* ===== 移动端顶部栏 ===== */
.mobile-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.brand-logo-sm {
  width: 24px;
  height: 24px;
  border-radius: 4px;
}
.mobile-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}
.hamburger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  color: #64748b;
  transition: background 0.15s;
}
.hamburger-btn:hover {
  background: #f1f5f9;
}

/* ===== 抽屉导航（移动端） ===== */
.drawer-nav {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding-top: 8px;
}
.drawer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 16px;
  font-weight: 700;
  font-size: 17px;
  color: #1e293b;
  border-bottom: 1px solid #e2e8f0;
  margin-bottom: 8px;
}
.drawer-new-chat {
  padding: 0 16px 12px;
  display: flex;
  gap: 8px;
}
.drawer-sessions {
  flex: 1;
  min-height: 0;
  padding: 0 8px;
  overflow-y: auto;
}
.drawer-footer {
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
}

/* ===== 主内容区 ===== */
.main-content {
  flex: 1;
  min-width: 0;
  background: #ffffff;
  padding: 16px;
  overflow-y: auto;
}
.main-content-chat {
  overflow: hidden !important;
  padding: 0;
}
.main-content-login {
  flex: 1;
  min-width: 0;
  padding: 0;
  overflow: hidden !important;
}

/* ===== 插件 & 设置弹窗：左右分栏 ===== */
.dialog-split {
  display: flex;
  min-height: 480px;
  max-height: 70vh;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.dialog-tabs {
  width: 160px;
  min-width: 160px;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dialog-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.dialog-tab:hover {
  background: #e2e8f0;
  color: #1e293b;
}
.dialog-tab.active {
  background: #e2e8f0;
  color: #1e293b;
  font-weight: 600;
}
.dialog-body {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 16px;
}

/* 嵌入模式下：隐藏管理页面的标题（左侧 tab 已有），保留操作按钮区 */
.dialog-body .page-header .page-header-left {
  display: none;
}

/* ===== Electron 拖拽区域 ===== */
.electron-drag {
  -webkit-app-region: drag;
}
.electron-no-drag {
  -webkit-app-region: no-drag;
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .app-layout {
    flex-direction: column;
  }
  .main-content {
    padding: 8px;
  }
  .user-name-text {
    display: none;
  }
}

@media (max-width: 480px) {
  .main-content {
    padding: 4px;
  }
}

/* ===== 全局响应式：Element Plus 对话框 ===== */
@media (max-width: 768px) {
  .el-dialog {
    width: 92% !important;
    margin: 16px auto !important;
  }
  .el-drawer:not(.is-fullscreen) {
    max-width: 90%;
  }
}

/* ===== 全局响应式：通用页面头部 ===== */
@media (max-width: 768px) {
  .page-header,
  .toolbar,
  .overview-bar,
  .section-header {
    flex-wrap: wrap;
    gap: 10px;
  }
  .page-header-right {
    flex-wrap: wrap;
    gap: 8px;
  }
  .search-input {
    width: 100% !important;
    max-width: 100% !important;
  }
}
</style>
