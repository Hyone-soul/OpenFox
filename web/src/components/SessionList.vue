<template>
  <div class="session-list">
    <div
      v-for="s in sessions"
      :key="s.id"
      :class="['session-item', { active: s.id === activeId }]"
      @click="emit('select', s.id)"
    >
      <div class="session-item-icon">
        <el-icon><ChatRound /></el-icon>
      </div>
      <div class="session-item-main">
        <div class="session-item-title">{{ s.title || '未命名会话' }}</div>
        <div class="session-item-time">{{ formatTime(s.created_at) }}</div>
      </div>
      <div class="session-item-actions" @click.stop>
        <button class="session-item-delete" @click="emit('remove', s.id)">
          <el-icon><Delete /></el-icon>
        </button>
      </div>
    </div>
    <div v-if="!sessions.length" class="session-empty">
      <el-icon class="empty-icon"><ChatLineSquare /></el-icon>
      <span>暂无历史对话</span>
    </div>
  </div>
</template>

<script setup>
import { Delete, ChatRound, ChatLineSquare } from '@element-plus/icons-vue'

defineProps({
  sessions: Array,
  activeId: String,
})
const emit = defineEmits(['select', 'remove'])

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = (now - d) / 1000

  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  const isSameYear = d.getFullYear() === now.getFullYear()
  const yy = String(d.getFullYear()).slice(-2)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return isSameYear ? `${mm}-${dd}` : `${yy}-${mm}-${dd}`
}
</script>

<style scoped>
.session-list {
  padding: 4px;
}

/* 会话条目 */
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.15s, color 0.15s;
  position: relative;
}
.session-item:hover {
  background: #f1f5f9;
}
/* 选中态：浅灰背景+近黑文字 */
.session-item.active {
  background: #e2e8f0;
}
.session-item.active .session-item-title {
  color: #1e293b;
  font-weight: 600;
}
.session-item.active .session-item-icon {
  background: #1e293b;
  color: #fff;
}

/* 左侧图标 */
.session-item-icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #94a3b8;
  background: #f1f5f9;
  flex-shrink: 0;
  transition: all 0.15s;
}

.session-item-main {
  flex: 1;
  min-width: 0;
}
.session-item-title {
  font-size: 13px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.15s;
}
.session-item-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

/* 操作按钮 */
.session-item-actions {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
}
.session-item:hover .session-item-actions {
  opacity: 1;
}
.session-item-delete {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: #94a3b8;
  font-size: 13px;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}
.session-item-delete:hover {
  color: #ef4444;
  background: #fef2f2;
}

/* 空状态 */
.session-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 40px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.empty-icon {
  font-size: 28px;
  opacity: 0.4;
}
</style>
