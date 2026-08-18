<template>
  <div class="tool-call-panel">
    <el-collapse v-model="activeNames">
      <el-collapse-item name="trace">
        <template #title>
          <div class="panel-title">
            <el-icon class="panel-icon"><Tools /></el-icon>
            <span>工具调用轨迹</span>
            <el-tag size="small" round effect="plain" class="panel-count">{{ trace.length }} 步</el-tag>
          </div>
        </template>
        <div class="trace-list">
          <div v-for="(t, i) in trace" :key="i" class="trace-item">
            <!-- 步骤头 -->
            <div class="trace-header">
              <span class="trace-badge">{{ i + 1 }}</span>
              <span class="trace-tool-name">{{ t.name }}</span>
              <span class="trace-line"></span>
            </div>
            <!-- 步骤详情 -->
            <div class="trace-detail">
              <div v-if="t.args && Object.keys(t.args).length" class="trace-section">
                <div class="trace-section-title">参数</div>
                <pre class="trace-json">{{ formatJson(t.args) }}</pre>
              </div>
              <div class="trace-section">
                <div class="trace-section-title">结果</div>
                <div class="trace-result">{{ truncate(t.result, 300) }}</div>
              </div>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Tools } from '@element-plus/icons-vue'

const props = defineProps({
  trace: Array,
})

const activeNames = ref(['trace'])

function formatJson(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

function truncate(text, max) {
  const s = String(text || '')
  return s.length > max ? s.slice(0, max) + '…' : s
}
</script>

<style scoped>
.tool-call-panel {
  margin: 8px 0 16px;
  max-width: 85%;
}
.tool-call-panel :deep(.el-collapse) {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
.tool-call-panel :deep(.el-collapse-item__header) {
  padding: 0 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  height: 42px;
}
.tool-call-panel :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.tool-call-panel :deep(.el-collapse-item__content) {
  padding: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.panel-icon {
  color: #1e293b;
}
.panel-count {
  margin-left: 4px;
}

/* 步骤列表 */
.trace-list {
  padding: 4px 16px 12px;
}

.trace-item {
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
}
.trace-item:last-child {
  border-bottom: none;
}

.trace-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.trace-badge {
  background: #1e293b;
  color: #fff;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.trace-tool-name {
  font-weight: 600;
  font-size: 13px;
  color: #111827;
  font-family: 'SF Mono', 'Consolas', monospace;
}
.trace-line {
  flex: 1;
  height: 1px;
  background: #f0f0f0;
}

.trace-section {
  margin-bottom: 8px;
}
.trace-section:last-child {
  margin-bottom: 0;
}
.trace-section-title {
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 4px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.trace-json {
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  max-height: 160px;
  overflow: auto;
  margin: 0;
  line-height: 1.5;
}
.trace-result {
  font-size: 12px;
  color: #4b5563;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #f0f0f0;
}
</style>
