<template>
  <div class="usage-manage">
    <!-- 顶部栏 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">用量管理</h2>
      </div>
      <div class="page-header-right">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="-"
          start-placeholder="开始"
          end-placeholder="结束"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          :clearable="true"
          size="small"
          @change="onDateChange"
        />
      </div>
    </div>

    <!-- 汇总数字 -->
    <div class="summary-row">
      <div class="stat-item" v-for="item in summaryItems" :key="item.label">
        <span class="stat-value">{{ item.value }}</span>
        <span class="stat-label">{{ item.label }}</span>
      </div>
    </div>

    <!-- 模型用量排行 -->
    <div class="rank-section">
      <div class="section-header">
        <span class="section-title">模型用量排行</span>
        <span class="section-sub">按 Total Tokens 降序</span>
      </div>
      <div class="rank-list">
        <div v-for="(item, i) in modelRankList" :key="item.name" class="rank-item">
          <span class="rank-index">{{ i + 1 }}</span>
          <div class="rank-body">
            <div class="rank-top">
              <span class="rank-name">{{ item.name }}</span>
              <span class="rank-value">{{ formatNum(item.totalTokens) }}</span>
            </div>
            <div class="rank-bar-bg">
              <div class="rank-bar-fill" :style="{ width: item.percent + '%' }"></div>
            </div>
          </div>
        </div>
        <div v-if="!modelRankList.length" class="rank-empty">暂无模型用量数据</div>
      </div>
    </div>

    <!-- 详细记录表格 -->
    <div class="table-section">
      <div class="section-header">
        <span class="section-title">用量记录</span>
        <el-select v-model="modelFilter" placeholder="筛选模型" clearable size="small" style="width:160px">
          <el-option v-for="m in modelList" :key="m" :label="m" :value="m" />
        </el-select>
      </div>
      <el-table :data="records" size="small" v-loading="loading" empty-text="暂无用量数据" :header-cell-style="{ background: '#f8fafc', color: '#64748b', fontWeight: 500 }">
        <el-table-column prop="created_at" label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="模型" min-width="160" />
        <el-table-column prop="total_tokens" label="Total Tokens" width="130" align="right">
          <template #default="{ row }"><span class="num-highlight">{{ formatNum(row.total_tokens) }}</span></template>
        </el-table-column>
        <el-table-column prop="cache_hit_tokens" label="缓存命中" width="110" align="right">
          <template #default="{ row }">{{ formatNum(row.cache_hit_tokens) }}</template>
        </el-table-column>
        <el-table-column prop="agent_id" label="智能体" width="120">
          <template #default="{ row }">{{ row.agent_id || '—' }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="onPageChange"
          size="small"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { usageApi } from '../api'

// ---- 数据状态 ----
const loading = ref(false)
const summary = ref({})
const records = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const modelFilter = ref('')
const dateRange = ref(null)

// ---- 汇总数字 ----
const summaryItems = computed(() => {
  const s = summary.value
  return [
    { label: 'Total Tokens', value: formatNum(s.total_tokens || 0) },
    { label: 'Prompt Tokens', value: formatNum(s.total_prompt_tokens || 0) },
    { label: 'Completion Tokens', value: formatNum(s.total_completion_tokens || 0) },
    { label: '总请求数', value: formatNum(s.total_requests || 0) },
    { label: '缓存命中 Tokens', value: formatNum(s.total_cache_hit_tokens || 0) },
  ]
})

// ---- 模型排行 ----
const modelList = computed(() => Object.keys(summary.value.by_model || {}))

const modelRankList = computed(() => {
  const byModel = summary.value.by_model || {}
  const entries = Object.entries(byModel).map(([name, v]) => ({
    name,
    totalTokens: v.total_tokens || 0,
  }))
  entries.sort((a, b) => b.totalTokens - a.totalTokens)
  const maxVal = entries.length ? entries[0].totalTokens : 1
  return entries.map(e => ({
    ...e,
    percent: maxVal > 0 ? Math.max((e.totalTokens / maxVal) * 100, 1) : 0,
  }))
})

// ---- 数据加载 ----
async function fetchSummary() {
  try {
    const params = buildDateParams()
    summary.value = await usageApi.summary(params)
  } catch {
    summary.value = {}
  }
}

async function fetchRecords() {
  loading.value = true
  try {
    const params = {
      ...buildDateParams(),
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
    }
    if (modelFilter.value) params.model = modelFilter.value
    const data = await usageApi.records(params)
    records.value = data.records || []
    total.value = data.total || 0
  } catch {
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function buildDateParams() {
  const params = {}
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
  return params
}

function refresh() {
  fetchSummary()
  currentPage.value = 1
  fetchRecords()
}

function onDateChange() { refresh() }
function onPageChange(page) { currentPage.value = page; fetchRecords() }

watch(modelFilter, () => { currentPage.value = 1; fetchRecords() })

function formatNum(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString()
}

function formatTime(iso) {
  if (!iso) return ''
  return iso.replace('T', ' ').slice(0, 16)
}

onMounted(refresh)
</script>

<style scoped>
.usage-manage {
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
  gap: 2px;
  margin-bottom: 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.stat-item {
  flex: 1;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-right: 1px solid #e2e8f0;
}
.stat-item:last-child { border-right: none; }
.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

/* 排行区 */
.rank-section {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 12px;
  overflow: hidden;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.section-sub {
  font-size: 12px;
  color: #94a3b8;
}

.rank-list { padding: 8px 0; }

.rank-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
}
.rank-item:hover { background: #f8fafc; }

.rank-index {
  font-size: 12px;
  color: #94a3b8;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.rank-body {
  flex: 1;
  min-width: 0;
}

.rank-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}
.rank-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 12px;
}
.rank-value {
  font-size: 12px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.rank-bar-bg {
  width: 100%;
  height: 4px;
  background: #f1f5f9;
  border-radius: 2px;
  overflow: hidden;
}
.rank-bar-fill {
  height: 100%;
  background: #1e293b;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.rank-empty {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

/* 表格区 */
.table-section {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.num-highlight {
  font-weight: 600;
  color: #1e293b;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
}

/* 响应式 */
@media (max-width: 768px) {
  .summary-row {
    flex-wrap: wrap;
  }
  .stat-item {
    flex: 1 1 45%;
    border-right: none;
    border-bottom: 1px solid #e2e8f0;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
