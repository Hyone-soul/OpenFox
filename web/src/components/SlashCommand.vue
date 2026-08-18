<template>
  <!-- 命令面板：紧贴输入框上方，与输入框同宽同圆角，Codex 风格 -->
  <div
    v-if="visible"
    ref="panelRef"
    class="slash-panel"
    :style="panelStyle"
  >
    <div class="slash-list" ref="listRef">
      <div
        v-for="(cmd, i) in filteredCommands"
        :key="cmd.name + (cmd.value || '')"
        class="slash-item"
        :class="{ active: i === activeIndex }"
        @click="execute(cmd)"
        @mouseenter="activeIndex = i"
      >
        <span class="slash-item-name">{{ cmd.label }}</span>
        <span class="slash-item-desc">{{ cmd.desc }}</span>
        <span v-if="cmd.current" class="slash-item-check">&#10003;</span>
      </div>
      <div v-if="filteredCommands.length === 0" class="slash-empty">
        无匹配结果
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: Boolean,
  filterText: { type: String, default: '' },
  anchorRect: { type: Object, default: () => null },
  commands: { type: Array, default: () => [] },
  /** 当前选中值（用于显示对勾），如当前模型名、当前会话id等 */
  currentValue: { type: String, default: '' },
  /** 展开为子列表时禁用 filterText 过滤（如 /model 展开模型列表时不按拼写过滤） */
  disableFilter: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'execute'])

const activeIndex = ref(0)
const listRef = ref(null)
const panelRef = ref(null)

// 根据过滤文本筛选
const filteredCommands = computed(() => {
  if (props.disableFilter) return props.commands
  const q = props.filterText.toLowerCase().replace(/^\//, '')
  if (!q) return props.commands
  return props.commands.filter(c =>
    (c.name || '').includes(q) || (c.desc || '').includes(q) || (c.label || '').includes(q)
  )
})

// 面板定位：紧贴输入框上方，与输入框同宽
const panelStyle = computed(() => {
  const rect = props.anchorRect
  if (!rect) return { display: 'none' }
  return {
    position: 'fixed',
    left: `${rect.left}px`,
    bottom: `${window.innerHeight - rect.top + 2}px`,
    width: `${rect.width}px`,
  }
})

watch(filteredCommands, () => {
  activeIndex.value = 0
})

function handleKeydown(e) {
  if (!props.visible) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % filteredCommands.value.length
    scrollToActive()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value =
      (activeIndex.value - 1 + filteredCommands.value.length) % filteredCommands.value.length
    scrollToActive()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const cmd = filteredCommands.value[activeIndex.value]
    if (cmd) execute(cmd)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    close()
  }
}

function scrollToActive() {
  nextTick(() => {
    const list = listRef.value
    if (!list) return
    const active = list.children[activeIndex.value]
    if (active) active.scrollIntoView({ block: 'nearest' })
  })
}

function execute(cmd) {
  emit('execute', cmd)
  // expand 类命令不关闭面板（由父组件控制面板内容切换为子列表）
  if (cmd.action !== 'expand') {
    close()
  }
}

function close() {
  emit('close')
}

function onClickOutside(e) {
  if (!props.visible) return
  if (panelRef.value && !panelRef.value.contains(e.target)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown, true)
  document.addEventListener('mousedown', onClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, true)
  document.removeEventListener('mousedown', onClickOutside)
})
</script>

<style scoped>
.slash-panel {
  z-index: 9999;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
  max-height: 320px;
  overflow: hidden;
  animation: slash-slide-up 0.1s ease-out;
}

@keyframes slash-slide-up {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.slash-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}

.slash-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.08s;
}
.slash-item:hover,
.slash-item.active {
  background: #f1f5f9;
}

.slash-item-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Consolas', 'Menlo', monospace;
  flex-shrink: 0;
}
.slash-item-desc {
  font-size: 12px;
  color: #94a3b8;
  flex: 1;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.slash-item-check {
  color: #1e293b;
  font-size: 13px;
  flex-shrink: 0;
  font-weight: 600;
}

.slash-empty {
  padding: 16px 12px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
</style>
