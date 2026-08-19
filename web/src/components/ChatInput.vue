<template>
  <div class="chat-input" ref="inputWrapRef">
    <!-- 文本域 + 工具栏 一体式容器 -->
    <div class="input-container" :class="{ disabled: loading, focused: isFocused }">
      <!-- 文本域 -->
      <textarea
        ref="textareaRef"
        v-model="text"
        class="input-textarea"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        :disabled="loading"
        rows="1"
        @keydown="handleKeydown"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
        @focus="isFocused = true"
        @blur="onBlur"
        @input="onInput"
      ></textarea>

      <!-- 底部工具栏 -->
      <div class="input-toolbar">
        <!-- 左侧：项目选择器 + Plan 模式开关 -->
        <div class="toolbar-left">
          <div class="project-selector">
            <button class="project-tag" @click="projectMenuOpen = !projectMenuOpen">
              <el-icon size="13"><FolderOpened /></el-icon>
              <span class="project-tag-name">{{ currentProjectLabel }}</span>
              <svg class="project-tag-arrow" width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 4l3 3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <!-- 项目下拉菜单 -->
            <div v-if="projectMenuOpen" class="project-dropdown" @click.stop>
              <div class="project-dropdown-item" @click="selectProject('')">
                <span>不关联项目</span>
                <el-icon v-if="!currentProjectId" size="14" color="#1e293b"><Select /></el-icon>
              </div>
              <div v-for="p in projects" :key="p.id" class="project-dropdown-item" @click="selectProject(p.id)">
                <el-icon size="13"><FolderOpened /></el-icon>
                <span class="project-dropdown-name">{{ p.name }}</span>
                <el-icon v-if="p.id === currentProjectId" size="14" color="#1e293b"><Select /></el-icon>
              </div>
              <div class="project-dropdown-divider"></div>
              <div class="project-dropdown-item project-dropdown-action" @click="handleCreateProject">
                <el-icon size="13"><FolderAdd /></el-icon>
                <span>新建项目</span>
              </div>
            </div>
          </div>
          <!-- Plan 模式切换 -->
          <button
            class="mode-toggle-btn"
            :class="{ active: planMode }"
            @click="$emit('toggle-plan-mode')"
            :title="planMode ? '计划模式已开启：点击关闭' : '开启计划模式：先提问再规划，确认后执行'"
          >
            <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
              <path d="M3 3.5L5 5.5L11 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M3 7.5h8M3 10.5h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <span v-if="planMode" class="mode-label">计划</span>
          </button>
        </div>

        <!-- 右侧：模型标识 + 字数 + 发送 -->
        <div class="toolbar-right">
          <button
            class="model-tag"
            @click="openModelPanel"
            :title="`当前模型: ${currentModelLabel}`"
          >
            <el-icon size="13"><Cpu /></el-icon>
            <span class="model-tag-name">{{ currentModelLabel }}</span>
            <svg class="model-tag-arrow" width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 4l3 3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <span v-if="text.length > 0" class="char-count">{{ text.length }} 字</span>
          <button
            v-if="!loading"
            class="send-btn"
            :disabled="!text.trim()"
            @click="handleSend"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <button v-else class="stop-btn" @click="emit('stop')">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <rect x="1" y="1" width="12" height="12" rx="2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 快捷键提示 -->
    <div class="input-hint">
      <span><kbd>Enter</kbd> 发送</span>
      <span class="dot-sep">·</span>
      <span><kbd>Shift</kbd> + <kbd>Enter</kbd> 换行</span>
      <span class="dot-sep">·</span>
      <span><kbd>/</kbd> 命令</span>
    </div>

    <!-- 命令面板：紧贴输入框上方 -->
    <SlashCommand
      :visible="slashVisible"
      :filterText="slashFilter"
      :anchorRect="anchorRect"
      :commands="slashCommands"
      :currentValue="currentValue"
      :disableFilter="slashDisableFilter"
      @close="closeSlash"
      @execute="onCommandExecute"
    />
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Cpu, FolderOpened, FolderAdd, Select } from '@element-plus/icons-vue'
import SlashCommand from './SlashCommand.vue'

const props = defineProps({
  loading: Boolean,
  modelDetails: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  /** 项目列表 */
  projects: { type: Array, default: () => [] },
  /** 当前会话关联的项目 ID */
  currentProjectId: { type: String, default: '' },
  /** 命令面板的命令列表（由父组件动态提供） */
  slashCommands: { type: Array, default: () => [] },
  /** 当前选中值（用于面板对勾标识） */
  currentValue: { type: String, default: '' },
  /** 命令面板是否禁用 filterText 过滤（展开子列表时为 true） */
  slashDisableFilter: { type: Boolean, default: false },
  /** Plan 模式是否激活 */
  planMode: { type: Boolean, default: false },
})
const emit = defineEmits(['send', 'stop', 'update:modelValue', 'command', 'slash-filter', 'select-project', 'create-project', 'toggle-plan-mode'])

const text = ref('')
const isFocused = ref(false)
const textareaRef = ref(null)
const inputWrapRef = ref(null)
const isComposing = ref(false)

// 当前模型显示名
const currentModelLabel = computed(() => {
  const m = props.modelDetails.find(m => m.name === props.modelValue)
  return m?.model || m?.name || props.modelValue || '未选择'
})

// 项目选择器状态
const projectMenuOpen = ref(false)
const currentProjectLabel = computed(() => {
  if (!props.currentProjectId) return '选择项目'
  const p = props.projects.find(p => p.id === props.currentProjectId)
  return p?.name || '选择项目'
})

function selectProject(projectId) {
  projectMenuOpen.value = false
  emit('select-project', projectId)
}

function handleCreateProject() {
  projectMenuOpen.value = false
  emit('create-project')
}

// Slash 命令状态
const slashVisible = ref(false)
const slashFilter = ref('')
const anchorRect = ref(null)

// 点击模型标签 → 在输入框填入 /model 触发命令面板展开模型列表
function openModelPanel() {
  text.value = '/model'
  nextTick(() => {
    autoResize()
    updateSlashState()
    textareaRef.value?.focus()
  })
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function onInput() {
  autoResize()
  updateSlashState()
}

// ========== Slash 命令检测 ==========
function updateSlashState() {
  const val = text.value
  if (val.startsWith('/')) {
    slashFilter.value = val
    emit('slash-filter', val)
    const container = textareaRef.value?.closest('.input-container')
    if (container) {
      anchorRect.value = container.getBoundingClientRect()
    }
    slashVisible.value = true
  } else {
    slashVisible.value = false
    slashFilter.value = ''
    emit('slash-filter', '')
  }
}

function closeSlash() {
  slashVisible.value = false
  slashFilter.value = ''
  if (text.value.startsWith('/') && !text.value.includes(' ')) {
    text.value = ''
    nextTick(() => autoResize())
  }
}

function onCommandExecute(cmd) {
  // expand 类命令：保持面板可见，输入框回填命令文本（如 /model）
  if (cmd.action === 'expand') {
    text.value = cmd.label  // e.g. '/model'
    nextTick(() => {
      autoResize()
      updateSlashState()  // 重新打开面板并触发 slash-filter
      textareaRef.value?.focus()
    })
    emit('command', cmd)
    return
  }
  // 其他命令：清空输入框并关闭面板
  slashVisible.value = false
  slashFilter.value = ''
  text.value = ''
  nextTick(() => autoResize())
  // 通知父组件：命令对象整体传出
  emit('command', cmd)
}

// ========== 键盘事件 ==========
function handleKeydown(e) {
  if (slashVisible.value && ['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(e.key)) {
    if (e.key === 'Enter') e.preventDefault()
    if (e.key === 'Escape') {
      e.preventDefault()
      closeSlash()
    }
    return
  }

  if (e.key === 'Enter') {
    if (e.isComposing || isComposing.value) return
    if (e.shiftKey) return
    e.preventDefault()
    handleSend()
  }
}

function onBlur() {
  isFocused.value = false
  setTimeout(() => {
    if (slashVisible.value) closeSlash()
  }, 200)
}

// 点击外部关闭项目菜单
function onDocumentClick(e) {
  if (projectMenuOpen.value) {
    const selector = inputWrapRef.value?.querySelector('.project-selector')
    if (selector && !selector.contains(e.target)) {
      projectMenuOpen.value = false
    }
  }
}

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed) return

  if (trimmed.startsWith('/')) {
    // 未知命令文本直接作为消息发送
    emit('send', trimmed)
    text.value = ''
    slashVisible.value = false
    nextTick(() => autoResize())
    return
  }

  emit('send', trimmed)
  text.value = ''
  slashVisible.value = false
  nextTick(() => autoResize())
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<style scoped>
.chat-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
}

.input-container {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.input-container.focused {
  border-color: #cbd5e1;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 0 0 3px rgba(30, 41, 59, 0.04);
}
.input-container.disabled {
  background: #f8fafc;
}

.input-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  padding: 14px 16px 4px;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  background: transparent;
  color: #1e293b;
  max-height: 200px;
  overflow-y: auto;
  box-sizing: border-box;
  border-radius: 12px 12px 0 0;
}
.input-textarea::placeholder {
  color: #94a3b8;
}
.input-textarea:disabled {
  cursor: not-allowed;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px 10px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 项目选择器（底部左侧，Codex 风格） */
.project-selector {
  position: relative;
}
.project-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}
.project-tag:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #1e293b;
}
.project-tag-name {
  font-weight: 500;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.project-tag-arrow {
  color: #94a3b8;
  flex-shrink: 0;
}
.project-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 6px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  z-index: 100;
  min-width: 200px;
  max-height: 280px;
  overflow-y: auto;
}
.project-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #1e293b;
  cursor: pointer;
  transition: background 0.15s;
}
.project-dropdown-item:hover {
  background: #f1f5f9;
}
.project-dropdown-name {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.project-dropdown-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 4px 0;
}
.project-dropdown-action {
  color: #475569;
  font-weight: 500;
}
.project-dropdown-action:hover {
  background: #1e293b;
  color: #fff;
}
.project-dropdown-action:hover .el-icon {
  color: #fff;
}

/* Plan 模式切换按钮 */
.mode-toggle-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}
.mode-toggle-btn:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #64748b;
}
.mode-toggle-btn.active {
  background: #1e293b;
  color: #fff;
  border-color: #1e293b;
}
.mode-toggle-btn.active:hover {
  background: #334155;
  color: #fff;
}
.mode-label {
  font-weight: 500;
  font-size: 11px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 模型文字按钮（底部右侧，Codex 风格） */
.model-tag {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}
.model-tag:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #1e293b;
}
.model-tag-name {
  font-weight: 500;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-tag-arrow {
  color: #94a3b8;
  flex-shrink: 0;
}

.char-count {
  font-size: 12px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.send-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: #000;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) { background: #1e293b; }
.send-btn:disabled { background: #cbd5e1; cursor: not-allowed; }

.stop-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: #ef4444;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stop-btn:hover { background: #dc2626; }

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #94a3b8;
  padding: 0 4px;
}
.input-hint kbd {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 10px;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: #64748b;
}
.dot-sep { color: #e2e8f0; }

@media (max-width: 768px) {
  .input-textarea { padding: 12px 14px 4px; font-size: 15px; }
  .input-toolbar { padding: 6px 10px 8px; }
  .toolbar-right { gap: 8px; }
  .model-tag-name { max-width: 100px; }
  .input-hint { display: none; }
}

@media (max-width: 480px) {
  .model-tag-name { max-width: 80px; }
  .char-count { display: none; }
}
</style>
