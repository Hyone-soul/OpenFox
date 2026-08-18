<template>
  <div class="chat-workbench">
    <main class="chat-main">
      <!-- 主页态：无会话选中 -->
      <div v-if="!activeSession" class="chat-home">
        <img src="/OpenFox.png" class="home-logo" alt="OpenFox" />
        <h2 class="home-title">OpenFox</h2>
        <p class="home-text">在左侧选择对话，或新建对话开始你的会话</p>
        <div class="home-suggestions">
          <div
            v-for="(s, i) in suggestions"
            :key="i"
            class="suggestion-card"
            @click="quickStart(s.text)"
          >
            <el-icon class="suggestion-icon"><component :is="s.icon" /></el-icon>
            <div class="suggestion-body">
              <div class="suggestion-title">{{ s.title }}</div>
              <div class="suggestion-desc">{{ s.text }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 会话态：有会话选中 -->
      <template v-else>
        <!-- 顶部标题栏（极简单行） -->
        <header class="chat-header">
          <el-icon v-if="currentSessionProjectId" size="14" class="header-folder-icon"><FolderOpened /></el-icon>
          <h3 class="header-title">{{ activeMeta?.title || '对话' }}</h3>
        </header>

        <!-- 消息流 -->
        <chat-messages
          :messages="messages"
          :tool-events="toolEvents"
          :loading="sending"
          :streaming-content="streamingReply"
          :streaming-reasoning="streamingReasoning"
          :error-state="errorState"
          agent-name="OpenFox"
          @retry="retryLast"
          @open-settings="() => openSettingsDialog?.('models')"
        />

<!-- 输入区 -->
        <div class="chat-input-wrap">
          <chat-input
            :loading="sending"
            :model-details="modelDetails"
            v-model="selectedModel"
            :projects="projects"
            :current-project-id="currentSessionProjectId"
            :slash-commands="slashCommands"
            :current-value="currentSlashValue"
            :slash-disable-filter="expandedCmd !== null"
            @send="sendMessage"
            @stop="stopSending"
            @command="handleCommand"
            @slash-filter="onSlashFilter"
            @select-project="handleSelectProject"
            @create-project="handleCreateProject"
          />
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, inject } from 'vue'
import {
  MagicStick, Document, DataAnalysis, ChatLineRound,
  FolderOpened,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { chatApi, modelApi, skillApi, metaApi, mcpApi, contextApi } from '../api'
import { useChatSessions } from '../composables/useChatSessions'
import ChatMessages from '../components/ChatMessages.vue'
import ChatInput from '../components/ChatInput.vue'


// openSettingsDialog 由 App.vue 通过 provide/inject 暴露，用于 /memory 命令跳转
const openSettingsDialog = inject('openSettingsDialog', null)

const {
  activeSession,
  modelDetails,
  selectedModel,
  activeProvider,
  currentProviderModels,
  activeMeta,
  sessions,
  projects,
  loadAll,
  fetchContextStatus,
  createSession,
  createProject,
  selectSession,
  removeSession,
  renameSession,
  updateSessionTitle,
} = useChatSessions()

const messages = ref([])
const toolEvents = ref([])
const sending = ref(false)
const streamingReply = ref('')
const streamingReasoning = ref('')
const errorState = ref(null)
const requestController = ref(null)
const lastFailedPrompt = ref('')


// 当前会话关联的项目 ID
const currentSessionProjectId = computed(() => {
  if (!activeSession.value) return ''
  const s = sessions.value.find(s => s.id === activeSession.value)
  return s?.project_id || ''
})

// 切换当前会话的项目关联
async function handleSelectProject(projectId) {
  if (!activeSession.value) return
  try {
    await chatApi.sessionUpdate(activeSession.value, { project_id: projectId })
    // 本地同步更新
    const s = sessions.value.find(s => s.id === activeSession.value)
    if (s) s.project_id = projectId
  } catch {
    // 静默失败
  }
}

// 新建项目（调用 Electron 文件选择对话框）
async function handleCreateProject() {
  const isElectron = typeof window !== 'undefined' && window.electronAPI?.isElectron
  if (isElectron && window.electronAPI?.selectDirectory) {
    const result = await window.electronAPI.selectDirectory()
    if (result.canceled || !result.path) return
    try {
      const p = await createProject(result.path)
      // 自动将当前会话关联到新项目
      await handleSelectProject(p.id)
    } catch {
      // 路径不存在等错误
    }
  } else {
    const workdir = window.prompt('请输入工作目录路径：')
    if (!workdir) return
    try {
      const p = await createProject(workdir)
      await handleSelectProject(p.id)
    } catch {
      // 错误
    }
  }
}

// ========== 动态命令面板（Codex 风格） ==========

// 顶层命令：action='expand' 会展开为子列表，action='direct' 直接执行
const TOP_COMMANDS = [
  { name: 'model',   label: '/model',   desc: '切换模型',   action: 'expand' },
  { name: 'new',     label: '/new',      desc: '新建会话',   action: 'direct' },
  { name: 'compact', label: '/compact',  desc: '压缩上下文', action: 'direct' },
  { name: 'skill',   label: '/skill',    desc: '查看技能与工具', action: 'direct' },
  { name: 'memory',  label: '/memory',   desc: '打开记忆管理', action: 'direct' },
  { name: 'help',    label: '/help',     desc: '帮助',       action: 'direct' },
]

const expandedCmd = ref(null)

// 命令面板的内容：根据展开状态动态切换
const slashCommands = computed(() => {
  if (expandedCmd.value === 'model') {
    // 展开后：仅展示当前供应商下的模型（Codex 风格，与聊天窗模型标识一致）
    return currentProviderModels.value.map(m => ({
      name: 'model-select',
      label: m.model,
      desc: m.name,
      value: m.name,
      current: m.name === selectedModel.value,
      action: 'select-model',
    }))
  }
  return TOP_COMMANDS
})

// 对勾标识的当前值
const currentSlashValue = computed(() => {
  if (expandedCmd.value === 'model') return selectedModel.value
  return ''
})

// ========== /model 命令直接展开逻辑 ==========

// 监听输入框的 slash-filter 事件：输入 /model 后直接展开模型列表
function onSlashFilter(val) {
  const trimmed = (val || '').trim()
  // 输入是 /model（含逐步输入 /m /mo /mod /mode）→ 直接展开模型列表
  if (trimmed.startsWith('/model') || '/model'.startsWith(trimmed)) {
    expandedCmd.value = 'model'
  } else if (expandedCmd.value === 'model') {
    // 输入不再是 /model 的前缀 → 收起展开状态
    expandedCmd.value = null
  }
}

// 欢迎屏建议提示词
const suggestions = [
  { title: '日常对话', text: '帮我写一段关于人工智能未来发展的短文', icon: ChatLineRound },
  { title: '创意写作', text: '请给我讲一个关于时间旅行的故事', icon: MagicStick },
  { title: '文档分析', text: '帮我总结这段文字的核心要点', icon: Document },
  { title: '数据分析', text: '请用表格对比几种常用排序算法的复杂度', icon: DataAnalysis },
]

watch(activeSession, async (id) => {
  if (id) {
    toolEvents.value = []
    streamingReply.value = ''
    streamingReasoning.value = ''
    errorState.value = null
    const data = await chatApi.sessionMessages(id)
    messages.value = rebuildToolEvents(data.messages)
  } else {
    messages.value = []
    toolEvents.value = []
    streamingReply.value = ''
    streamingReasoning.value = ''
    errorState.value = null
  }
})

/**
 * 从后端消息列表重建 tool_events 卡片（支持"按步穿插"展示）。
 *
 * 后端存储的是标准 OpenAI 格式：
 *   - assistant 消息带 tool_calls 数组（function.arguments 是 JSON 字符串）
 *   - tool 消息带 tool_call_id + content（工具执行结果）
 *
 * 重建策略：保持消息原有顺序遍历，遇到 assistant(tool_calls) 时
 * 在原位置生成 tool_events 卡片（事件包含 step 分组），
 * 遇到含"已达到最大步数"的 system 消息时标记其前面的卡片为 interrupted。
 */
function rebuildToolEvents(msgs) {
  // 建立 tool_call_id → tool 结果的映射
  const toolResultMap = new Map()
  for (const m of msgs) {
    if (m.role === 'tool' && m.tool_call_id) {
      toolResultMap.set(m.tool_call_id, m)
    }
  }

  const result = []
  let currentStep = 0
  // 待处理的中断信息：遇到 system「已达到最大步数」时暂存，
  // 在下一条 tool_events 卡片渲染后立即标在那里。
  // 如果先遇到 user 消息（新一轮对话），则丢弃——中断只影响当轮。
  let pendingInterrupt = ''
  for (const m of msgs) {
    // 中断标记：后端会在 max_steps 用尽后追加一条 system 消息
    if (m.role === 'system' && (m.content || '').includes('已达到最大步数')) {
      pendingInterrupt = m.content
      continue
    }
    // 过滤系统提示词（注入给 LLM 的 role=system 消息，非用户可见内容）
    if (m.role === 'system') {
      continue
    }
    // 用户发新消息 = 新一轮对话开始，之前的待处理中断不再有意义
    if (m.role === 'user') {
      pendingInterrupt = ''
    }

    if (m.role === 'assistant' && m.tool_calls?.length) {
      // 如果 assistant 消息同时有文本内容，先保留为普通助手消息
      if (m.content && m.content.trim()) {
        result.push({ role: 'assistant', content: m.content, reasoning: m.reasoning || undefined })
      }
      // 将 tool_calls 转换为 tool_events 卡片（携带 step 分组）
      const events = m.tool_calls.map(tc => {
        const tr = toolResultMap.get(tc.id)
        const isError = tr?.content?.startsWith('ERROR:')
        return {
          id: tc.id || `h-${currentStep}-${Math.random().toString(36).slice(2, 7)}`,
          step: currentStep,
          name: tc.function?.name || tc.name || '',
          args: safeParseArgs(tc.function?.arguments),
          status: tr ? (isError ? 'error' : 'done') : 'error',
          result: tr?.content || '',
          elapsed: 0,
        }
      })
      const card = {
        role: 'tool_events',
        events,
        step: currentStep,
        collapsed: true,
      }
      // 如果此卡片前面有一条待处理中断，标记到这张卡片并清空
      if (pendingInterrupt) {
        card.interrupted = true
        card.interruptedReason = pendingInterrupt
        result.push(card)
        result.push({ role: 'interrupted_note', content: pendingInterrupt })
        pendingInterrupt = ''
      } else {
        result.push(card)
      }
      currentStep++
    } else if (m.role !== 'tool') {
      // tool 消息已折叠进 tool_events，跳过；其余消息正常保留
      if (m.role === 'assistant') {
        result.push({ role: 'assistant', content: m.content, reasoning: m.reasoning || undefined })
      } else {
        result.push(m)
      }
    }
  }

  // 尾部兜底：中断消息在最后、后面没有更多工具卡片
  if (pendingInterrupt) {
    result.push({ role: 'interrupted_note', content: pendingInterrupt })
  }
  return result
}

function safeParseArgs(argsStr) {
  if (!argsStr) return {}
  try { return JSON.parse(argsStr) } catch { return {} }
}

async function quickStart(text) {
  const s = await createSession('新会话')
  selectSession(s.id)
  sendMessage(text)
}

async function sendMessage(text) {
  const prompt = String(text || '').trim()
  if (!prompt || sending.value) return
  if (!activeSession.value) {
    const s = await createSession('新会话')
    selectSession(s.id)
  }
  messages.value.push({ role: 'user', content: prompt })
  sending.value = true
  toolEvents.value = []
  streamingReply.value = ''
  streamingReasoning.value = ''
  errorState.value = null
  lastFailedPrompt.value = ''
  const controller = new AbortController()
  requestController.value = controller

  try {
    const stream = chatApi.chatStream({
      session_id: activeSession.value,
      message: prompt,
      model: selectedModel.value || undefined,
    }, { signal: controller.signal })

    for await (const { type, data } of stream) {
      if (type === 'tool_call') {
        // 先把已积累的流式文本刷入 messages（工具调用前的思考文本）
        flushStreamingReply()
        const stepIdx = data.step ?? 0
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'tool_events' && lastMsg.step === stepIdx) {
          // 同一步骤的后续工具调用，追加到同一张卡片
          lastMsg.events.push({
            id: data.id || `${stepIdx}-${lastMsg.events.length}`,
            step: stepIdx,
            name: data.name,
            args: data.args,
            status: 'running',
            result: '',
            elapsed: 0,
          })
        } else {
          // 新步骤：创建新的工具卡片，直接推入消息流
          messages.value.push({
            role: 'tool_events',
            step: stepIdx,
            events: [{
              id: data.id || `${stepIdx}-0`,
              step: stepIdx,
              name: data.name,
              args: data.args,
              status: 'running',
              result: '',
              elapsed: 0,
            }],
            collapsed: false,
            interrupted: false,
          })
        }
      } else if (type === 'tool_result') {
        const stepIdx = data.step ?? 0
        for (let i = messages.value.length - 1; i >= 0; i--) {
          const m = messages.value[i]
          if (m.role === 'tool_events' && m.step === stepIdx) {
            const evt = m.events.find(e =>
              (data.id && e.id === data.id) || (e.status === 'running' && e.name === data.name)
            )
            if (evt) {
              evt.status = data.success ? 'done' : 'error'
              evt.result = data.result
              evt.elapsed = data.elapsed || 0
            }
            break
          }
        }
      } else if (type === 'assistant_delta') {
        // 文本增量直接累积到 streamingReply，reasoning 累积到 streamingReasoning
        streamingReply.value += data.content || ''
        streamingReasoning.value += data.reasoning || ''
      } else if (type === 'done') {
        const streamText = streamingReply.value.trim()
        const reasoningText = streamingReasoning.value.trim()
        const replyText = data.reply ? String(data.reply).trim() : ''
        if (replyText && streamText && replyText.startsWith(streamText)) {
          messages.value.push({ role: 'assistant', content: data.reply, reasoning: reasoningText || undefined })
        } else if (streamText) {
          messages.value.push({ role: 'assistant', content: streamingReply.value, reasoning: reasoningText || undefined })
        } else if (replyText) {
          messages.value.push({ role: 'assistant', content: data.reply, reasoning: reasoningText || undefined })
        }
        streamingReply.value = ''
        streamingReasoning.value = ''
        lastFailedPrompt.value = ''
        if (data.auto_title) {
          updateSessionTitle(activeSession.value, data.auto_title)
        }
      } else if (type === 'cancelled') {
        markLastToolEventsInterrupted('任务已停止。')
        flushStreamingReply()
        addSystemMsg(data.message || '任务已停止')
      } else if (type === 'error') {
        markLastToolEventsInterrupted(data.message || '对话出错。')
        flushStreamingReply()
        setChatError(data.message || '对话出错', prompt)
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      markLastToolEventsInterrupted('任务已停止。')
      flushStreamingReply()
      addSystemMsg('任务已停止')
    } else {
      markLastToolEventsInterrupted(e.message || '连接异常。')
      flushStreamingReply()
      setChatError(e.message || '发送失败', prompt)
    }
  } finally {
    sending.value = false
    if (requestController.value === controller) requestController.value = null
    fetchContextStatus()
  }
}

function stopSending() {
  if (!sending.value) return
  requestController.value?.abort()
}

function flushStreamingReply() {
  // 把当前积累的流式文本刷入 messages 作为 assistant 消息
  if (streamingReply.value.trim()) {
    messages.value.push({ role: 'assistant', content: streamingReply.value, reasoning: streamingReasoning.value.trim() || undefined })
  }
  streamingReply.value = ''
  streamingReasoning.value = ''
}

function markLastToolEventsInterrupted(reason = '操作已中断。') {
  // 标记所有仍在运行的工具卡片为中断状态
  for (const m of messages.value) {
    if (m.role === 'tool_events' && m.events?.some(e => e.status === 'running')) {
      m.interrupted = true
      m.interruptedReason = reason
      for (const e of m.events) {
        if (e.status === 'running') {
          e.status = 'error'
          e.result = '操作被中断'
        }
      }
    }
  }
}

function setChatError(message, prompt) {
  errorState.value = { message, prompt }
  lastFailedPrompt.value = prompt
}

async function retryLast() {
  const prompt = lastFailedPrompt.value
  if (!prompt || sending.value) return
  const lastMessage = messages.value[messages.value.length - 1]
  if (lastMessage?.role === 'user' && lastMessage.content === prompt) {
    messages.value.pop()
  }
  await sendMessage(prompt)
}

// ========== 命令执行（Codex 风格） ==========

async function handleCommand(cmd) {
  const { name, action, value } = cmd

  // 选择类命令：点击子项直接切换
  if (action === 'select-model') {
    try {
      await modelApi.setActive(value)
      ElMessage.success(`已切换到: ${cmd.label}`)
      await loadAll()
    } catch {
      ElMessage.error('切换失败')
    }
    expandedCmd.value = null
    return
  }

  // 展开类命令：面板切换为子列表（ChatInput 已回填 /model 文本保持面板可见）
  if (action === 'expand') {
    expandedCmd.value = name
    return
  }

  // 直接执行类命令
  expandedCmd.value = null

  switch (name) {
    case 'new':     return await cmdNew()
    case 'compact': return await cmdCompact()
    case 'skill':   return await cmdSkill()
    case 'memory':  return await cmdMemory()
    case 'help':    return cmdHelp()
    default:        ElMessage.warning(`未知命令: /${name}`)
  }
}

// /new — 新建会话（合并原 /clear 语义：旧会话保留侧栏）
async function cmdNew() {
  const s = await createSession('新会话')
  selectSession(s.id)
  messages.value = []
  toolEvents.value = []
  ElMessage.success('已新建会话')
}

// /compact — 压缩上下文，结果内联展示到聊天流
async function cmdCompact() {
  try {
    addSystemMsg('正在压缩上下文...')
    const result = await contextApi.compact()
    if (result.success) {
      const lines = [
        `✓ 压缩完成`,
        `  原始: ${result.original_tokens} tokens → 压缩后: ${result.compressed_tokens} tokens`,
        `  节省: ${result.savings_percent}%  |  消息: ${result.messages_before} → ${result.messages_after}`,
      ]
      addSystemMsg(lines.join('\n'))
    } else if (result.skipped) {
      addSystemMsg(`上下文未达到压缩阈值（当前 ${result.current_tokens} tokens）`)
    } else {
      addSystemMsg(`压缩失败: ${result.error || '未知错误'}`)
    }
    fetchContextStatus()
  } catch (e) {
    addSystemMsg(`压缩请求失败: ${e.message || ''}`)
  }
}

// /skill — 统一展示技能、工具、MCP 三类信息
async function cmdSkill() {
  let skillLines = []
  let toolLines = []
  let mcpLines = []

  // 并行获取三类信息
  const [skillsRes, toolsRes, mcpRes] = await Promise.allSettled([
    skillApi.list(),
    metaApi.tools(),
    mcpApi.list(),
  ])

  if (skillsRes.status === 'fulfilled' && skillsRes.value?.length) {
    skillLines = skillsRes.value.map((s, i) => `  ${i + 1}. ${s.name}${s.description ? ' — ' + s.description : ''}`)
  }
  if (toolsRes.status === 'fulfilled' && toolsRes.value?.length) {
    toolLines = toolsRes.value.map((t, i) => `  ${i + 1}. ${t.name || t.function?.name || t}`)
  }
  if (mcpRes.status === 'fulfilled') {
    const mcps = mcpRes.value.servers || mcpRes.value.mcps || mcpRes.value || []
    if (mcps.length) {
      mcpLines = mcps.map((m, i) => {
        const status = m.connected ? '已连接' : (m.enabled ? '连接失败' : '已禁用')
        return `  ${i + 1}. ${m.name} (${status}, ${m.tool_count || 0} 工具)`
      })
    }
  }

  if (!skillLines.length && !toolLines.length && !mcpLines.length) {
    addSystemMsg('暂无技能、工具或 MCP 服务')
    return
  }

  let output = ''
  if (skillLines.length) {
    output += `技能 (${skillLines.length}):
${skillLines.join('\n')}`
  }
  if (toolLines.length) {
    output += `${output ? '\n\n' : ''}工具 (${toolLines.length}):
${toolLines.join('\n')}`
  }
  if (mcpLines.length) {
    output += `${output ? '\n\n' : ''}MCP 服务 (${mcpLines.length}):
${mcpLines.join('\n')}`
  }
  addSystemMsg(output)
}

// /memory — 跳转到侧栏设置面板中的记忆管理
async function cmdMemory() {
  if (openSettingsDialog) {
    openSettingsDialog('memory')
    ElMessage.success('已打开记忆管理')
  } else {
    addSystemMsg('记忆管理面板不可用，请通过侧栏底部 设置 → 记忆管理 访问')
  }
}

// /help
function cmdHelp() {
  addSystemMsg(
    `可用命令:\n` +
    `  /model    切换模型\n` +
    `  /new      新建会话\n` +
    `  /compact  压缩上下文\n` +
    `  /skill    查看技能与工具\n` +
    `  /memory   打开记忆管理\n` +
    `  /help     显示帮助`
  )
}

function addSystemMsg(content) {
  messages.value.push({ role: 'system', content })
}

onMounted(() => {
  loadAll()
})

onUnmounted(() => requestController.value?.abort())
</script>

<style scoped>
.chat-workbench {
  display: flex;
  height: 100%;
  background: #fff;
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  min-width: 0;
}

.chat-home {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow-y: auto;
}

.home-logo { width: 56px; height: 56px; border-radius: 12px; margin-bottom: 16px; opacity: 0.85; }
.home-title { font-size: 22px; font-weight: 700; color: #1e293b; margin: 0 0 6px; }
.home-text { font-size: 14px; color: #94a3b8; margin: 0 0 28px; text-align: center; max-width: 400px; }

.home-suggestions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px; width: 100%; max-width: 640px;
}
.suggestion-card {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 16px; border: 1px solid #e2e8f0; border-radius: 8px;
  cursor: pointer; transition: all 0.15s; background: #fff;
}
.suggestion-card:hover { border-color: #cbd5e1; background: #f8fafc; }
.suggestion-icon { font-size: 18px; color: #f97316; flex-shrink: 0; margin-top: 2px; }
.suggestion-body { min-width: 0; }
.suggestion-title { font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 2px; }
.suggestion-desc { font-size: 12px; color: #94a3b8; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.chat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 24px; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;
}
.header-folder-icon { color: #94a3b8; flex-shrink: 0; }
.header-title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.chat-input-wrap {
  padding: 14px 24px 20px; border-top: 1px solid #e2e8f0;
  background: #fff; flex-shrink: 0;
}

@media (max-width: 768px) {
  .chat-home { padding: 32px 16px; }
  .home-logo { width: 48px; height: 48px; }
  .home-title { font-size: 20px; }
  .home-text { font-size: 13px; }
  .home-suggestions { grid-template-columns: 1fr; max-width: 100%; gap: 8px; }
  .chat-header { padding: 8px 12px; }
  .header-title { font-size: 13px; }
  .chat-input-wrap { padding: 10px 12px 12px; }
}
</style>
