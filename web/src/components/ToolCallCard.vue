<template>
  <div class="tool-card">
    <!-- 卡片顶部：状态汇总行 -->
    <div class="tool-card-header" @click="toggleCard">
      <div class="tool-card-header-left">
        <!-- 运行中：脉冲环动画 -->
        <span v-if="hasRunning" class="tool-pulse-ring">
          <span class="pulse-core"></span>
        </span>
        <!-- 全部完成：橙色扳手图标 -->
        <span v-else-if="allDone" class="tool-wrench">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M11.1 1.4a3.5 3.5 0 0 0-4.95 4.95L2.05 10.45a2 2 0 1 0 2.83 2.83l5.1-5.1a3.5 3.5 0 0 0 1.12-6.78zM10 4.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z" fill="#f97316"/>
          </svg>
        </span>
        <!-- 有失败：红色警告 -->
        <span v-else-if="hasError" class="tool-warn">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="#ef4444" stroke-width="1.5" fill="none"/>
            <path d="M8 4.5v4M8 11v1" stroke="#ef4444" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </span>

        <span class="tool-card-title">
          <template v-if="hasRunning">正在进行思考与执行</template>
          <template v-else-if="interrupted">操作执行 · {{ doneCount }}/{{ events.length }} 完成</template>
          <template v-else-if="allDone">操作执行 · {{ doneCount }} 个操作已完成</template>
          <template v-else>操作执行 · {{ doneCount }}/{{ events.length }} 完成</template>
        </span>
      </div>
      <div class="tool-card-header-right">
        <span v-if="!hasRunning && totalElapsed" class="tool-card-time">{{ totalElapsed }}s</span>
        <span v-if="allDone" class="tool-success-check">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" fill="#10b981"/>
            <path d="M5.5 8.5l2 2 3-3.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <!-- 折叠箭头 -->
        <span class="tool-card-arrow" :class="{ expanded: isExpanded }">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
      </div>
    </div>

    <!-- 卡片内容：工具调用列表（可折叠） -->
    <transition name="tool-collapse">
      <div v-if="isExpanded" class="tool-card-body">
        <div
          v-for="(evt, i) in events"
          :key="i"
          class="tool-item"
          :class="evt.status"
        >
          <!-- 工具项头部 -->
          <div class="tool-item-header" @click="toggleItem(i)">
            <div class="tool-item-left">
              <!-- 状态图标 -->
              <span class="tool-item-icon">
                <span v-if="evt.status === 'running'" class="tool-spinner"></span>
                <span v-else-if="evt.status === 'done'" class="tool-check-mark">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                    <path d="M3.5 8.5l3 3 6-6.5" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
                <span v-else class="tool-cross-mark">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                    <path d="M4 4l8 8M12 4l-8 8" stroke="#ef4444" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </span>
              </span>
              <span class="tool-item-label">{{ formatToolLabel(evt.name) }}</span>
              <span class="tool-item-args">{{ formatArgs(evt.name, evt.args) }}</span>
            </div>
            <div class="tool-item-right">
              <span v-if="evt.elapsed" class="tool-item-elapsed">{{ evt.elapsed }}s</span>
              <span v-if="evt.status === 'running'" class="tool-item-status running">运行中...</span>
              <span v-if="evt.status === 'done'" class="tool-item-status done">完成</span>
              <span v-if="evt.status === 'error'" class="tool-item-status error">失败</span>
              <!-- 详情展开箭头（完成/失败状态才有） -->
              <span v-if="evt.status !== 'running' && evt.result" class="tool-item-detail-arrow" :class="{ expanded: expandedItems[i] }">
                <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
                  <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </span>
            </div>
          </div>
          <!-- 详情内容（可展开） -->
          <transition name="tool-detail">
            <div v-if="expandedItems[i] && evt.result" class="tool-item-detail">
              <pre class="tool-detail-content">{{ truncate(evt.result, 500) }}</pre>
            </div>
          </transition>
        </div>
      </div>
    </transition>

    <!-- 卡片底部折叠按钮 -->
    <div v-if="isExpanded && !hasRunning" class="tool-card-footer" @click="isExpanded = false">
      <span class="tool-card-footer-arrow">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
          <path d="M4 10l4-4 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
      <span>收起</span>
    </div>

    <!-- 中断提示：未展开时也能看到被中断的原因 -->
    <div v-if="!isExpanded && interrupted" class="tool-card-interrupted">
      {{ interruptedReasonText }}
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  collapsed: { type: Boolean, default: false },
  interrupted: { type: Boolean, default: false },
  interruptedReason: { type: String, default: '' },
})

const isExpanded = ref(!props.collapsed)
const expandedItems = reactive({})

// 计算属性
const hasRunning = computed(() => props.events.some(e => e.status === 'running'))
const allDone = computed(() => props.events.length > 0 && props.events.every(e => e.status === 'done'))
const hasError   = computed(() => props.events.some(e => e.status === 'error'))
const doneCount  = computed(() => props.events.filter(e => e.status === 'done').length)
const interruptedReasonText = computed(() => props.interruptedReason || '操作已中断。')
const totalElapsed = computed(() => {
  let total = 0
  for (const evt of props.events) {
    if (evt.elapsed) total += evt.elapsed
  }
  return total > 0 ? total.toFixed(1) : ''
})

function toggleCard() {
  isExpanded.value = !isExpanded.value
}

function toggleItem(i) {
  expandedItems[i] = !expandedItems[i]
}

// 历史卡片默认折叠，实时卡片默认展开
watch(() => props.collapsed, (v) => {
  isExpanded.value = !v
})

// 实时卡片：有新事件到达时自动展开
watch(() => props.events.length, () => {
  if (!props.collapsed) {
    isExpanded.value = true
  }
})

// 工具名称 → 友好标签映射
const TOOL_LABELS = {
  web_search: '搜索',
  web_fetch: '抓取网页',
  run_shell: '执行命令',
  read_file: '读取文件',
  write_file: '写入文件',
  edit_file: '编辑文件',
  grep_search: '搜索代码',
  glob_find: '查找文件',
  git_status: 'Git 状态',
  git_diff: 'Git 差异',
  git_commit: 'Git 提交',
  git_log: 'Git 日志',
  list_dir: '列出目录',
  make_dir: '创建目录',
  copy_file: '复制文件',
  move_file: '移动文件',
  ast_parse: '解析代码',
  todo_read: '读取待办',
  todo_write: '写入待办',
  memory_add: '添加记忆',
  memory_query: '查询记忆',
  memory_update: '更新记忆',
  memory_delete: '删除记忆',
  get_current_datetime: '获取时间',
}

function formatToolLabel(name) {
  return TOOL_LABELS[name] || name
}

// 格式化工具参数为简短展示
function formatArgs(name, args) {
  if (!args || typeof args !== 'object') return ''
  if (name === 'run_shell' && args.cmd) return truncate(args.cmd, 60)
  if (name === 'web_search' && args.query) return truncate(args.query, 40)
  if (name === 'web_fetch' && args.url) return truncate(args.url, 50)
  if (name === 'read_file' && args.path) return truncate(args.path, 40)
  if (name === 'write_file' && args.path) return truncate(args.path, 40)
  if (name === 'edit_file' && args.path) return truncate(args.path, 40)
  if (name === 'grep_search' && args.pattern) return truncate(args.pattern, 30)
  if (name === 'glob_find' && args.pattern) return truncate(args.pattern, 30)
  if (name === 'git_commit' && args.message) return truncate(args.message, 30)
  const firstVal = Object.values(args).find(v => typeof v === 'string' && v)
  if (firstVal) return truncate(firstVal, 40)
  return ''
}

function truncate(str, max) {
  const s = String(str || '')
  return s.length > max ? s.slice(0, max) + '…' : s
}
</script>

<style scoped>
.tool-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.tool-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.tool-card-header:hover { background: #f8fafc; }

.tool-card-header-left { display: flex; align-items: center; gap: 10px; }
.tool-card-header-right { display: flex; align-items: center; gap: 8px; }

/* 脉冲环动画（运行中） */
.tool-pulse-ring {
  position: relative; width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
}
.pulse-core {
  width: 10px; height: 10px; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  animation: pulse-glow 1.5s ease-in-out infinite;
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); transform: scale(1); }
  50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); transform: scale(1.1); }
}

.tool-card-title { font-size: 13px; font-weight: 500; color: #1f2937; }
.tool-card-time { font-size: 12px; color: #9ca3af; font-variant-numeric: tabular-nums; }

.tool-card-arrow { display: flex; color: #9ca3af; transition: transform 0.2s; }
.tool-card-arrow.expanded { transform: rotate(180deg); }

/* 卡片内容区 */
.tool-card-body { border-top: 1px solid #f0f0f0; padding: 4px 0; }

/* 单个工具项 */
.tool-item { border-bottom: 1px solid #f5f5f5; }
.tool-item:last-child { border-bottom: none; }

.tool-item-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; cursor: pointer; transition: background 0.1s;
}
.tool-item-header:hover { background: #fafbfc; }

.tool-item-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.tool-item-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.tool-item-icon { width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }

/* 运行中：旋转小圆圈 */
.tool-spinner {
  width: 12px; height: 12px; border: 2px solid #e2e8f0;
  border-top-color: #3b82f6; border-radius: 50%;
  animation: tool-spin 0.8s linear infinite;
}
@keyframes tool-spin { to { transform: rotate(360deg); } }

.tool-item-label { font-size: 13px; font-weight: 500; color: #374151; white-space: nowrap; }
.tool-item-args {
  font-size: 12px; color: #9ca3af; min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-family: 'SF Mono', 'Consolas', 'Menlo', monospace;
}

.tool-item-status { font-size: 11px; font-variant-numeric: tabular-nums; }
.tool-item-elapsed { font-size: 11px; color: #9ca3af; font-variant-numeric: tabular-nums; }
.tool-item-status.running { color: #3b82f6; }
.tool-item-status.done { color: #10b981; }
.tool-item-status.error { color: #ef4444; }

.tool-item-detail-arrow { display: flex; color: #d1d5db; transition: transform 0.2s; }
.tool-item-detail-arrow.expanded { transform: rotate(180deg); }

/* 工具详情展开区 */
.tool-item-detail { padding: 0 16px 12px; }
.tool-detail-content {
  background: #f9fafb; border: 1px solid #f0f0f0; border-radius: 6px;
  padding: 10px 12px; font-size: 12px; line-height: 1.5; color: #4b5563;
  white-space: pre-wrap; word-break: break-word; margin: 0;
  max-height: 200px; overflow-y: auto;
  font-family: 'SF Mono', 'Consolas', 'Menlo', monospace;
}

/* 卡片底部 */
.tool-card-footer {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 8px; font-size: 12px; color: #9ca3af;
  cursor: pointer; border-top: 1px solid #f0f0f0; transition: all 0.15s;
}
.tool-card-footer:hover { background: #f8fafc; color: #6b7280; }
.tool-card-footer-arrow { display: flex; }

/* 中断提示（超出最大步数被强制结束） */
.tool-card-interrupted {
  border-top: 1px solid #fef2f2;
  background: #fff7f7;
  padding: 8px 16px;
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.5;
}

/* 折叠/展开动画 */
.tool-collapse-enter-active, .tool-collapse-leave-active { transition: all 0.2s ease; overflow: hidden; }
.tool-collapse-enter-from, .tool-collapse-leave-to { opacity: 0; max-height: 0; }
.tool-collapse-enter-to, .tool-collapse-leave-from { opacity: 1; max-height: 1000px; }

.tool-detail-enter-active, .tool-detail-leave-active { transition: all 0.15s ease; overflow: hidden; }
.tool-detail-enter-from, .tool-detail-leave-to { opacity: 0; max-height: 0; }
.tool-detail-enter-to, .tool-detail-leave-from { opacity: 1; max-height: 300px; }
</style>
