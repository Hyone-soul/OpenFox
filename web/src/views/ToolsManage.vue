<template>
  <div class="tools-manage">
    <!-- 顶部栏 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">工具管理</h2>
      </div>
      <div class="page-header-right">
        <el-input
          v-model="searchQuery"
          placeholder="搜索工具名称或描述"
          size="small"
          clearable
          style="width: 220px"
          :prefix-icon="Search"
        />
      </div>
    </div>

    <!-- 汇总数字 -->
    <div class="summary-row" v-loading="loading">
      <div
        class="stat-item"
        v-for="cat in categoryStats"
        :key="cat.label"
        :class="{ active: activeFilter === cat.label }"
        @click="toggleFilter(cat.label)"
      >
        <span class="stat-value">{{ cat.count }}</span>
        <span class="stat-label">{{ cat.label }}</span>
      </div>
    </div>

    <!-- 工具列表 -->
    <div class="tools-list" v-loading="loading">
      <template v-for="cat in groupedTools" :key="cat.category">
        <div v-if="cat.tools.length" class="category-group">
          <div class="category-header" @click="toggleCollapse(cat.category)">
            <span class="category-title">{{ cat.category }}</span>
            <span class="category-count">{{ cat.tools.length }}</span>
            <el-icon class="collapse-icon" :class="{ collapsed: collapsedSet.has(cat.category) }">
              <ArrowDown />
            </el-icon>
          </div>
          <div class="category-body" v-show="!collapsedSet.has(cat.category)">
            <div
              class="tool-card"
              v-for="tool in cat.tools"
              :key="tool.name"
              @click="selectTool(tool)"
            >
              <div class="tool-card-header">
                <span class="tool-name">{{ tool.name }}</span>
                <span class="tool-source" :class="'source-' + tool.sourceClass">{{ tool.sourceLabel }}</span>
              </div>
              <p class="tool-desc">{{ tool.description || '暂无描述' }}</p>
            </div>
          </div>
        </div>
      </template>
      <div v-if="!loading && filteredTools.length === 0" class="tools-empty">
        暂无工具数据
      </div>
    </div>

    <!-- 工具详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedTool?.name || '工具详情'"
      direction="rtl"
      size="420px"
      append-to-body
    >
      <template #header>
        <div class="drawer-header">
          <span class="drawer-title">{{ selectedTool?.name }}</span>
          <span class="tool-source" :class="'source-' + selectedTool?.sourceClass">{{ selectedTool?.sourceLabel }}</span>
        </div>
      </template>
      <div class="drawer-body" v-if="selectedTool">
        <div class="detail-section">
          <div class="detail-label">描述</div>
          <p class="detail-text">{{ selectedTool.description || '暂无描述' }}</p>
        </div>
        <div class="detail-section">
          <div class="detail-label">分类</div>
          <p class="detail-text">{{ selectedTool.category }}</p>
        </div>
        <div class="detail-section">
          <div class="detail-label">来源</div>
          <p class="detail-text">{{ selectedTool.source }}</p>
        </div>
        <div class="detail-section" v-if="selectedTool.parameters && selectedTool.parameters.properties">
          <div class="detail-label">参数</div>
          <div class="param-list">
            <div
              class="param-item"
              v-for="(param, key) in selectedTool.parameters.properties"
              :key="key"
            >
              <div class="param-top">
                <span class="param-name">{{ key }}</span>
                <span class="param-type">{{ param.type || 'any' }}</span>
                <span class="param-required" v-if="isRequired(key)">必填</span>
              </div>
              <p class="param-desc">{{ param.description || '—' }}</p>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import { toolsApi } from '../api'

const props = defineProps({
  embedded: { type: Boolean, default: false },
})

// ---- 数据状态 ----
const loading = ref(false)
const tools = ref([])
const searchQuery = ref('')
const activeFilter = ref('')
const collapsedSet = ref(new Set())
const drawerVisible = ref(false)
const selectedTool = ref(null)

// ---- 来源标签映射 ----
const sourceMap = {
  builtin: { label: '内置', class: 'builtin' },
  memory: { label: '记忆', class: 'memory' },
  custom: { label: '自定义', class: 'custom' },
  custom_python: { label: '自定义', class: 'custom' }, // 兼容旧后端
}
const mcpPrefix = 'mcp:'

function enrichTool(tool) {
  let sourceLabel, sourceClass
  if (tool.source && tool.source.startsWith(mcpPrefix)) {
    sourceLabel = tool.source.slice(mcpPrefix.length)
    sourceClass = 'mcp'
  } else {
    const s = sourceMap[tool.source] || { label: tool.source || '其他', class: 'other' }
    sourceLabel = s.label
    sourceClass = s.class
  }
  // category 兜底：后端未返回或为 null 时归为「其他」
  const category = tool.category || '其他'
  return { ...tool, category, sourceLabel, sourceClass }
}

// ---- 分类统计 ----
const categoryStats = computed(() => {
  const counts = {}
  for (const t of tools.value) {
    const cat = t.category || '其他'
    counts[cat] = (counts[cat] || 0) + 1
  }
  // 按固定顺序排列
  const order = ['文件操作', 'Shell', '代码搜索', 'Git', '浏览器', '代码分析', '任务管理', '记忆', '自定义工具', 'MCP', '其他']
  const sorted = []
  for (const cat of order) {
    if (counts[cat]) {
      sorted.push({ label: cat, count: counts[cat] })
    }
  }
  // 未列出的分类
  for (const cat of Object.keys(counts)) {
    if (!order.includes(cat)) {
      sorted.push({ label: cat, count: counts[cat] })
    }
  }
  return sorted
})

// ---- 过滤 + 搜索 ----
const filteredTools = computed(() => {
  let result = tools.value
  if (activeFilter.value) {
    result = result.filter(t => t.category === activeFilter.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    result = result.filter(t =>
      t.name.toLowerCase().includes(q) ||
      (t.description || '').toLowerCase().includes(q)
    )
  }
  return result
})

// ---- 分组 ----
const groupedTools = computed(() => {
  const groups = {}
  for (const t of filteredTools.value) {
    const cat = t.category || '其他'
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(t)
  }
  const order = ['文件操作', 'Shell', '代码搜索', 'Git', '浏览器', '代码分析', '任务管理', '记忆', '自定义工具', 'MCP', '其他']
  const result = []
  for (const cat of order) {
    if (groups[cat]) result.push({ category: cat, tools: groups[cat] })
  }
  for (const cat of Object.keys(groups)) {
    if (!order.includes(cat)) result.push({ category: cat, tools: groups[cat] })
  }
  return result
})

// ---- 交互 ----
function toggleFilter(label) {
  activeFilter.value = activeFilter.value === label ? '' : label
}

function toggleCollapse(category) {
  const s = new Set(collapsedSet.value)
  if (s.has(category)) s.delete(category)
  else s.add(category)
  collapsedSet.value = s
}

function selectTool(tool) {
  selectedTool.value = tool
  drawerVisible.value = true
}

function isRequired(key) {
  return (selectedTool.value?.parameters?.required || []).includes(key)
}

// ---- 数据加载 ----
async function fetchTools() {
  loading.value = true
  try {
    const data = await toolsApi.list()
    tools.value = (data.tools || []).map(enrichTool)
  } catch {
    tools.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchTools)

// 暴露刷新方法
defineExpose({ refresh: fetchTools })
</script>

<style scoped>
.tools-manage {
  max-width: 960px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}
.page-header-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* 汇总数字行 */
.summary-row {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  flex-wrap: wrap;
}
.stat-item {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: background 0.15s;
  border-right: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  min-width: 80px;
}
.stat-item:hover { background: #f1f5f9; }
.stat-item.active { background: #e2e8f0; }
.stat-item.active .stat-value { color: #1e293b; }
.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #334155;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

/* 工具列表 */
.tools-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-group {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}
.category-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #f8fafc;
  cursor: pointer;
  user-select: none;
}
.category-header:hover { background: #f1f5f9; }
.category-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.category-count {
  font-size: 12px;
  color: #94a3b8;
  background: #e2e8f0;
  padding: 1px 8px;
  border-radius: 10px;
}
.collapse-icon {
  margin-left: auto;
  transition: transform 0.2s;
  color: #94a3b8;
}
.collapse-icon.collapsed { transform: rotate(-90deg); }

.category-body {
  padding: 8px 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

.tool-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}
.tool-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.tool-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.tool-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-source {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 4px;
  flex-shrink: 0;
  font-weight: 500;
}
.source-builtin { background: #e2e8f0; color: #475569; }
.source-memory { background: #fef3c7; color: #92400e; }
.source-custom { background: #d1fae5; color: #065f46; }
.source-mcp { background: #dbeafe; color: #1e40af; }
.source-other { background: #f1f5f9; color: #64748b; }

.tool-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tools-empty {
  padding: 48px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

/* 抽屉详情 */
.drawer-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.drawer-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}
.drawer-body {
  padding: 0 4px;
}
.detail-section {
  margin-bottom: 20px;
}
.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.detail-text {
  font-size: 14px;
  color: #334155;
  line-height: 1.6;
  margin: 0;
}
.param-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.param-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f8fafc;
}
.param-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.param-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}
.param-type {
  font-size: 11px;
  color: #64748b;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
}
.param-required {
  font-size: 10px;
  color: #ef4444;
  background: #fef2f2;
  padding: 1px 6px;
  border-radius: 4px;
}
.param-desc {
  font-size: 12px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

/* 响应式 */
@media (max-width: 768px) {
  .summary-row {
    flex-direction: column;
  }
  .stat-item {
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }
  .category-body {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
