<template>
  <div class="chat-messages" ref="scrollRef" @scroll="handleScroll">
    <!-- 空状态：提示发消息 -->
    <div v-if="!messages.length && !loading" class="chat-empty">
      <el-icon class="empty-icon"><ChatLineRound /></el-icon>
      <div class="empty-text">在下方输入框开始对话</div>
    </div>

    <!-- 消息列表 -->
    <template v-for="(m, i) in messages" :key="i">
      <!-- 用户消息：浅灰圆角卡片 -->
      <div v-if="m.role === 'user'" class="msg-row user">
        <div class="msg-body">
          <div class="msg-bubble user-bubble">
            <div class="msg-content plain">{{ m.content }}</div>
          </div>
          <div class="msg-meta">
            <span class="msg-time">{{ formatTime(m.timestamp) }}</span>
          </div>
        </div>
      </div>

      <!-- 助手消息：无卡片纯文本 -->
      <div v-else-if="m.role === 'assistant'" class="msg-row assistant">
        <div v-if="messageShowAvatar[i]" class="msg-avatar ai-avatar">
          <img src="/OpenFox.png" class="avatar-img" alt="OpenFox" />
        </div>
        <div v-else class="msg-avatar-spacer"></div>
        <div class="msg-body">
          <div class="msg-meta" v-if="messageShowAvatar[i]">
            <span class="msg-name">{{ agentName || 'OpenFox' }}</span>
            <span class="msg-time" v-if="m.timestamp">{{ formatTime(m.timestamp) }}</span>
            <div class="msg-actions">
              <button class="msg-action-btn" @click="copyMessage(m.content)" title="复制">
                <el-icon><CopyDocument /></el-icon>
              </button>
            </div>
          </div>
          <!-- 思考过程（可折叠） -->
          <div v-if="m.reasoning" class="reasoning-block" :class="{ collapsed: isReasoningCollapsed('msg-' + i) }">
            <div class="reasoning-header" @click="toggleReasoning('msg-' + i)">
              <span class="reasoning-toggle">{{ isReasoningCollapsed('msg-' + i) ? '+' : '-' }}</span>
              <span class="reasoning-label">思考过程</span>
            </div>
            <div v-if="!isReasoningCollapsed('msg-' + i)" class="reasoning-content">
              <div class="msg-content markdown" v-html="renderMarkdown(m.reasoning)"></div>
            </div>
          </div>
          <div class="msg-bubble ai-bubble">
            <div class="msg-content markdown" v-html="renderMarkdown(m.content)"></div>
          </div>
        </div>
      </div>

      <!-- 历史工具调用消息（已持久化的工具调用记录） -->
      <div v-else-if="m.role === 'tool_events'" class="msg-row assistant">
        <div v-if="messageShowAvatar[i]" class="msg-avatar ai-avatar">
          <img src="/OpenFox.png" class="avatar-img" alt="OpenFox" />
        </div>
        <div v-else class="msg-avatar-spacer"></div>
        <div class="msg-body">
          <div class="msg-meta" v-if="messageShowAvatar[i]">
            <span class="msg-name">{{ agentName || 'OpenFox' }}</span>
          </div>
          <ToolCallCard :events="m.events" :collapsed="m.collapsed !== false" :interrupted="m.interrupted" :interrupted-reason="m.interruptedReason || ''" />
        </div>
      </div>

      <!-- 系统消息（命令结果，灰色内联样式） -->
      <div v-else-if="m.role === 'system'" class="msg-row system">
        <div class="msg-body">
          <div class="msg-bubble system-bubble">
            <div class="msg-content plain system-content">{{ m.content }}</div>
          </div>
        </div>
      </div>

      <!-- 中断原因提示（最大步数被强制结束） -->
      <div v-else-if="m.role === 'interrupted_note'" class="msg-row system">
        <div class="msg-body">
          <div class="msg-bubble system-bubble interrupted-bubble">
            <div class="msg-content plain system-content">{{ m.content }}</div>
          </div>
        </div>
      </div>

      <!-- 危险命令确认卡片 -->
      <div v-else-if="m.role === 'tool_confirm'" class="msg-row assistant">
        <div v-if="messageShowAvatar[i]" class="msg-avatar ai-avatar">
          <img src="/OpenFox.png" class="avatar-img" alt="OpenFox" />
        </div>
        <div v-else class="msg-avatar-spacer"></div>
        <div class="msg-body">
          <div class="confirm-card" :class="{ 'confirm-resolved': m.confirmed }">
            <div class="confirm-header">
              <span class="confirm-icon">!</span>
              <span class="confirm-title">危险操作确认</span>
            </div>
            <div class="confirm-cmd">{{ m.cmd }}</div>
            <div v-if="m.confirmed" class="confirm-result">
              {{ m.approved ? '已允许执行' : '已拒绝' }}
            </div>
            <div v-else class="confirm-actions">
              <button class="confirm-btn confirm-allow" @click="$emit('toolConfirm', m.id, true)">允许</button>
              <button class="confirm-btn confirm-deny" @click="$emit('toolConfirm', m.id, false)">拒绝</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 请求失败：错误与重试操作直接留在消息流中 -->
    <div v-if="errorState" class="chat-error-row" role="alert">
      <el-icon><WarningFilled /></el-icon>
      <span class="chat-error-message">{{ errorState.message }}</span>
      <button
        v-if="isApiKeyError"
        class="chat-retry-btn chat-settings-btn"
        type="button"
        @click="emit('openSettings')"
      >
        去设置
      </button>
      <button class="chat-retry-btn" type="button" @click="emit('retry')">
        <el-icon><Refresh /></el-icon>
        重试
      </button>
    </div>

    <!-- 当前助手回复的增量内容 -->
    <div v-if="streamingContent || streamingReasoningVisible" class="msg-row assistant streaming-row">
      <div v-if="dynamicAvatar.streaming" class="msg-avatar ai-avatar">
        <img src="/OpenFox.png" class="avatar-img" alt="OpenFox" />
      </div>
      <div v-else class="msg-avatar-spacer"></div>
      <div class="msg-body">
        <div class="msg-meta" v-if="dynamicAvatar.streaming">
          <span class="msg-name">{{ agentName || 'OpenFox' }}</span>
          <span class="msg-status">{{ isThinkingOnly ? '思考中...' : '生成中...' }}</span>
        </div>
        <!-- 流式思考过程 -->
        <div v-if="streamingReasoningVisible" class="reasoning-block streaming-reasoning">
          <div class="reasoning-header" @click="toggleReasoning('streaming')">
            <span class="reasoning-toggle">{{ isReasoningCollapsed('streaming') ? '+' : '-' }}</span>
            <span class="reasoning-label">思考过程</span>
            <span class="reasoning-status" v-if="isThinkingOnly">{{ isReasoningCollapsed('streaming') ? '' : '' }}</span>
          </div>
          <div v-if="!isReasoningCollapsed('streaming')" class="reasoning-content">
            <div class="msg-content markdown" v-html="renderMarkdown(streamingReasoning)"></div>
          </div>
        </div>
        <div v-if="streamingContent" class="msg-bubble ai-bubble">
          <div class="msg-content markdown" v-html="renderMarkdown(streamingContent)"></div>
        </div>
      </div>
    </div>

    <!-- 加载中：工具运行时或正在思考时不显示打字指示器 -->
    <div v-if="loading && !hasRunningTools && !streamingReasoningVisible" class="msg-row assistant">
      <div v-if="dynamicAvatar.loading" class="msg-avatar ai-avatar">
        <img src="/OpenFox.png" class="avatar-img" alt="OpenFox" />
      </div>
      <div v-else class="msg-avatar-spacer"></div>
      <div class="msg-body">
        <div class="msg-meta" v-if="dynamicAvatar.loading">
          <span class="msg-name">{{ agentName || 'OpenFox' }}</span>
          <span class="msg-status">思考中...</span>
        </div>
        <div class="msg-bubble ai-bubble">
          <div class="typing-indicator">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { CopyDocument, ChatLineRound, WarningFilled, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps({
  messages: Array,
  toolEvents: Array,
  loading: Boolean,
  agentName: String,
  streamingContent: { type: String, default: '' },
  streamingReasoning: { type: String, default: '' },
  errorState: { type: Object, default: null },
})

const emit = defineEmits(['retry', 'openSettings', 'toolConfirm'])

// 思考过程折叠状态
const reasoningCollapsed = ref({})

// 判断是否为 API 密钥未配置的错误（用于显示"去设置"按钮）
const isApiKeyError = computed(() => {
  const msg = props.errorState?.message || ''
  return msg.includes('密钥') || msg.includes('API') || msg.includes('key')
})

// 流式思考内容（实时阶段）
const streamingReasoningVisible = computed(() => props.streamingReasoning && props.streamingReasoning.trim())

// 是否正在思考（无 streamingContent 但有 streamingReasoning = 纯思考阶段）
const isThinkingOnly = computed(() => !!streamingReasoningVisible.value && !props.streamingContent)

// AI 侧消息角色集合
const AI_ROLES = new Set(['assistant', 'tool_events'])

// 历史消息：只有连续 AI 消息块的第一个显示头像
const messageShowAvatar = computed(() => {
  return props.messages.map((m, i) => {
    if (!AI_ROLES.has(m.role)) return false
    const prev = i > 0 ? props.messages[i - 1] : null
    return !prev || !AI_ROLES.has(prev.role)
  })
})

// 是否有正在运行的工具卡片（实时阶段）
const hasRunningTools = computed(() => {
  const last = props.messages[props.messages.length - 1]
  return last?.role === 'tool_events' && last.events?.some(e => e.status === 'running')
})

// 动态区域（streaming / loading）：仅最后一条历史消息非 AI 侧时，
// 第一个可见动态块才显示头像
const dynamicAvatar = computed(() => {
  // 工具运行中时，卡片自身已展示状态，不需要动态区域头像
  if (hasRunningTools.value) return { streaming: false, loading: false }
  const lastIsAi = props.messages.length > 0
    && AI_ROLES.has(props.messages[props.messages.length - 1].role)
  if (lastIsAi) return { streaming: false, loading: false }
  const streamVisible = !!props.streamingContent || !!streamingReasoningVisible.value
  const loadVisible = props.loading
  if (streamVisible) return { streaming: true, loading: false }
  if (loadVisible) return { streaming: false, loading: true }
  return { streaming: false, loading: false }
})

const scrollRef = ref(null)
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

// ── 滚动控制 ──
// 用户是否停留在底部附近（距底 80px 内）；上滑后停止自动拉底
const isAtBottom = ref(true)
const SCROLL_BOTTOM_THRESHOLD = 80

function handleScroll() {
  const el = scrollRef.value
  if (!el) return
  isAtBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_BOTTOM_THRESHOLD
}

function scrollToBottom() {
  if (scrollRef.value) {
    isAtBottom.value = true
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}

async function copyMessage(content) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败')
  }
}

function toggleReasoning(key) {
  reasoningCollapsed.value[key] = !reasoningCollapsed.value[key]
}

function isReasoningCollapsed(key) {
  // 默认折叠
  return reasoningCollapsed.value[key] !== false
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

// 自动滚动：仅在用户停留在底部时拉底，上滑后不强制滚动
watch(
  () => [props.messages.length, props.streamingContent, props.streamingReasoning, hasRunningTools.value],
  async () => {
    await nextTick()
    if (scrollRef.value && isAtBottom.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  },
)

// 新消息发送 / loading 切换时强制拉底（用户主动操作，应跟到底）
watch(
  () => [props.messages.length, props.loading, props.errorState],
  async () => {
    await nextTick()
    scrollToBottom()
  },
)
</script>

<style scoped>
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 12px;
}

/* 空状态 */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #94a3b8;
}
.empty-icon { font-size: 32px; margin-bottom: 8px; opacity: 0.5; }
.empty-text { font-size: 14px; }

/* 消息行 */
.msg-row {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
  max-width: 85%;
}
.msg-row.user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.msg-row.assistant {
  margin-right: auto;
}

/* 头像 */
.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}
.ai-avatar { background: #f1f5f9; border: 1px solid #e2e8f0; overflow: hidden; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.msg-avatar-spacer { width: 32px; flex-shrink: 0; }

/* 消息体 */
.msg-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.msg-row.user .msg-body { align-items: flex-end; }
.msg-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.msg-name { font-size: 12px; font-weight: 600; color: #64748b; }
.msg-time { font-size: 11px; color: #94a3b8; }
.msg-status { font-size: 11px; color: #64748b; font-style: italic; }
.chat-error-row {
  display: flex; align-items: center; gap: 8px; max-width: 85%;
  margin: 0 auto 18px; padding: 10px 12px;
  color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px;
  font-size: 13px;
}
.chat-error-message { min-width: 0; overflow-wrap: anywhere; }
.chat-retry-btn {
  display: inline-flex; align-items: center; gap: 5px; min-height: 32px;
  margin-left: auto; padding: 5px 10px; border: 1px solid #fca5a5; border-radius: 5px;
  background: #fff; color: #b91c1c; cursor: pointer; flex-shrink: 0;
}
.chat-retry-btn:hover { background: #fff7f7; }

.msg-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.15s; }
.msg-row.assistant:hover .msg-actions { opacity: 1; }
.msg-action-btn {
  border: none; background: transparent; cursor: pointer;
  padding: 2px 4px; border-radius: 4px; color: #94a3b8;
  font-size: 13px; display: flex; align-items: center; transition: all 0.15s;
}
.msg-action-btn:hover { color: #1e293b; background: #f1f5f9; }

/* 气泡 */
.msg-bubble {
  padding: 12px 16px; border-radius: 8px; line-height: 1.7;
  font-size: 14px; word-break: break-word;
}
.user-bubble { background: #f1f5f9; color: #1e293b; border-bottom-right-radius: 4px; }
.ai-bubble { background: transparent; color: #1e293b; border: none; padding-left: 0; padding-right: 0; border-bottom-left-radius: 4px; }

/* 系统消息 */
.msg-row.system { margin-right: auto; margin-left: 0; max-width: 90%; }
.system-bubble {
  background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0;
  border-radius: 8px; padding: 10px 14px;
  font-family: 'SF Mono', 'Consolas', 'Menlo', monospace; font-size: 13px; line-height: 1.6;
}
.interrupted-bubble {
  background: #fff7f7; color: #b91c1c; border-color: #fecaca;
}
.system-content { white-space: pre-wrap; }

/* 纯文本 */
.msg-content.plain { white-space: pre-wrap; }

/* Markdown */
.msg-content.markdown :deep(p) { margin: 0 0 8px; }
.msg-content.markdown :deep(p:last-child) { margin-bottom: 0; }
.msg-content.markdown :deep(pre) {
  background: #1e293b; color: #e2e8f0; padding: 12px 16px;
  border-radius: 6px; overflow-x: auto; font-size: 13px; line-height: 1.5; margin: 8px 0;
}
.msg-content.markdown :deep(code) { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #be185d; }
.msg-content.markdown :deep(pre code) { background: transparent; padding: 0; color: inherit; }
.msg-content.markdown :deep(ul), .msg-content.markdown :deep(ol) { padding-left: 20px; margin: 0 0 8px; }
.msg-content.markdown :deep(blockquote) { border-left: 3px solid #e2e8f0; padding-left: 12px; margin: 8px 0; color: #64748b; }
.msg-content.markdown :deep(a) { color: #1e293b; text-decoration: underline; text-decoration-color: #cbd5e1; }
.msg-content.markdown :deep(a:hover) { color: #f97316; }
.msg-content.markdown :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 13px; }
.msg-content.markdown :deep(th), .msg-content.markdown :deep(td) { border: 1px solid #e2e8f0; padding: 6px 12px; }
.msg-content.markdown :deep(th) { background: #f8fafc; font-weight: 600; }

/* 思考过程 */
.reasoning-block {
  margin-bottom: 6px;
  border-left: 2px solid #e2e8f0;
  border-radius: 4px;
  background: #f8fafc;
}
.reasoning-block.streaming-reasoning {
  margin-bottom: 8px;
}
.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  color: #94a3b8;
  transition: color 0.15s;
}
.reasoning-header:hover { color: #64748b; }
.reasoning-toggle {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 11px;
  font-weight: 700;
  width: 14px;
  text-align: center;
  flex-shrink: 0;
}
.reasoning-label { font-weight: 500; }
.reasoning-status { font-style: italic; }
.reasoning-content {
  padding: 0 10px 8px 10px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.6;
}
.reasoning-content :deep(p) { margin: 0 0 6px; }
.reasoning-content :deep(p:last-child) { margin-bottom: 0; }

/* 打字指示器 */
.typing-indicator { display: flex; gap: 4px; padding: 4px 0; }
.typing-indicator .dot {
  width: 8px; height: 8px; border-radius: 50%; background: #cbd5e1;
  animation: typing-bounce 1.4s infinite ease-in-out;
}
.typing-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 危险命令确认卡片 */
.confirm-card {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 12px 16px;
  max-width: 560px;
}
.confirm-card.confirm-resolved {
  opacity: 0.7;
  background: #f8fafc;
  border-color: #e2e8f0;
}
.confirm-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.confirm-icon {
  width: 20px; height: 20px; border-radius: 50%;
  background: #f59e0b; color: #fff; font-size: 12px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.confirm-title {
  font-size: 13px; font-weight: 600; color: #92400e;
}
.confirm-card.confirm-resolved .confirm-title { color: #64748b; }
.confirm-cmd {
  background: #1e293b; color: #e2e8f0; padding: 8px 12px; border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  line-height: 1.5; white-space: pre-wrap; word-break: break-all;
  margin-bottom: 10px;
}
.confirm-result {
  font-size: 12px; color: #64748b;
}
.confirm-actions {
  display: flex; gap: 8px;
}
.confirm-btn {
  padding: 6px 16px; border-radius: 6px; font-size: 13px;
  cursor: pointer; border: 1px solid; font-weight: 500;
  transition: all 0.15s;
}
.confirm-allow {
  background: #fff; color: #92400e; border-color: #f59e0b;
}
.confirm-allow:hover { background: #fffbeb; }
.confirm-deny {
  background: #fff; color: #64748b; border-color: #e2e8f0;
}
.confirm-deny:hover { background: #f8fafc; }
</style>
