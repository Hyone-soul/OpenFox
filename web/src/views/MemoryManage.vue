<template>
  <div class="memory-manage">
    <!-- 顶部栏（嵌入模式下由 dialog-body 隐藏 page-header） -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">记忆管理</h2>
        <span class="page-subtitle">{{ totalCount }} 条记忆</span>
      </div>
      <div class="page-header-right">
        <el-input
          v-model="keyword"
          placeholder="搜索记忆内容"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button class="btn-create" :icon="Plus" @click="openCreate">新增</el-button>
      </div>
    </div>

    <!-- 显式记忆 -->
    <div class="mem-group">
      <div class="group-header" @click="toggleGroup('explicit')">
        <span class="group-band group-band--high"></span>
        <span class="group-title">用户显式记忆</span>
        <span class="group-count">{{ filteredExplicit.length }}</span>
        <span class="group-desc">用户明确要求记住的内容</span>
        <el-icon class="group-arrow" :class="{ expanded: expandedGroups.has('explicit') }"><ArrowDown /></el-icon>
      </div>
      <transition name="slide">
        <div v-if="expandedGroups.has('explicit')" class="group-body">
          <div v-for="row in filteredExplicit" :key="row.content" class="mem-item">
            <span class="mem-band mem-band--high"></span>
            <div class="mem-content" v-if="editingRow !== row" @click="startEdit(row, 'explicit')">{{ row.content }}</div>
            <div class="mem-edit-wrap" v-else>
              <el-input v-model="editText" size="small" :maxlength="500" show-word-limit @keydown.enter="saveEdit(row, 'explicit')" @keydown.escape="cancelEdit" />
              <el-button link type="primary" size="small" @click="saveEdit(row, 'explicit')">保存</el-button>
              <el-button link size="small" @click="cancelEdit">取消</el-button>
            </div>
            <span class="mem-meta">{{ row.meta }}</span>
            <div class="mem-actions">
              <el-button link size="small" @click="startEdit(row, 'explicit')">编辑</el-button>
              <el-button link size="small" class="action-delete" @click="removeMemory(row, true)">删除</el-button>
            </div>
          </div>
          <div v-if="!loading && !filteredExplicit.length" class="mem-empty">暂无显式记忆</div>
        </div>
      </transition>
    </div>

    <!-- 隐式记忆 -->
    <div class="mem-group">
      <div class="group-header" @click="toggleGroup('implicit')">
        <span class="group-band group-band--mid"></span>
        <span class="group-title">隐式抽取记忆</span>
        <span class="group-count">{{ implicitTotalCount }}</span>
        <span class="group-desc">AI 自动提炼的长期稳态结论</span>
        <el-icon class="group-arrow" :class="{ expanded: expandedGroups.has('implicit') }"><ArrowDown /></el-icon>
      </div>
      <transition name="slide">
        <div v-if="expandedGroups.has('implicit')" class="group-body">
          <div v-for="sec in filteredImplicit" :key="sec.name" class="mem-sub">
            <div class="sub-header">
              <span class="sub-band"></span>
              <span class="sub-title">{{ sec.name }}</span>
              <span class="sub-count">{{ sec.entries.length }}</span>
            </div>
            <div v-for="row in sec.entries" :key="row.content" class="mem-item mem-item--sub">
              <span class="mem-band" :class="confBandClass(row.confidence)"></span>
              <div class="mem-content" v-if="editingRow !== row" @click="startEdit(row, 'implicit', sec.name)">{{ row.content }}</div>
              <div class="mem-edit-wrap" v-else>
                <el-input v-model="editText" size="small" :maxlength="500" show-word-limit @keydown.enter="saveEdit(row, 'implicit', sec.name)" @keydown.escape="cancelEdit" />
                <el-button link type="primary" size="small" @click="saveEdit(row, 'implicit', sec.name)">保存</el-button>
                <el-button link size="small" @click="cancelEdit">取消</el-button>
              </div>
              <span v-if="row.confidence" class="mem-conf" :class="'mem-conf--' + row.confidence">{{ row.confidence }}</span>
              <span class="mem-meta">{{ row.meta }}</span>
              <div class="mem-actions">
                <el-button link size="small" @click="startEdit(row, 'implicit', sec.name)">编辑</el-button>
                <el-button link size="small" class="action-delete" @click="removeMemory(row, false)">删除</el-button>
              </div>
            </div>
            <div v-if="!sec.entries.length" class="mem-empty">暂无记忆</div>
          </div>
          <div v-if="!filteredImplicit.length" class="mem-empty">暂无隐式记忆</div>
        </div>
      </transition>
    </div>

    <!-- 归档记忆 -->
    <div class="mem-group">
      <div class="group-header" @click="toggleGroup('archive')">
        <span class="group-band group-band--low"></span>
        <span class="group-title">已废弃归档</span>
        <span class="group-count">{{ filteredArchive.length }}</span>
        <span class="group-desc">过期、推翻的历史记忆，仅归档不生效</span>
        <el-icon class="group-arrow" :class="{ expanded: expandedGroups.has('archive') }"><ArrowDown /></el-icon>
      </div>
      <transition name="slide">
        <div v-if="expandedGroups.has('archive')" class="group-body">
          <div v-for="row in filteredArchive" :key="row.content" class="mem-item mem-item--archive">
            <span class="mem-band mem-band--low"></span>
            <div class="mem-content mem-content--archive">{{ row.content }}</div>
            <span class="mem-meta">{{ row.meta }}</span>
          </div>
          <div v-if="!filteredArchive.length" class="mem-empty">暂无归档</div>
        </div>
      </transition>
    </div>

    <!-- 新增对话框 -->
    <el-dialog v-model="dialogVisible" title="新增记忆" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-width="80px" size="default">
        <el-form-item label="类型" required>
          <el-radio-group v-model="form.memory_type">
            <el-radio value="explicit">显式记忆</el-radio>
            <el-radio value="implicit">隐式记忆</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.memory_type === 'implicit'" label="分类" required>
          <el-select v-model="form.section" placeholder="选择板块" style="width:100%">
            <el-option v-for="s in sections" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.memory_type === 'implicit'" label="置信度">
          <el-radio-group v-model="form.confidence">
            <el-radio value="高">高</el-radio>
            <el-radio value="中">中</el-radio>
            <el-radio value="低">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="精简的记忆内容" :maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button class="btn-create" @click="saveMemory">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Plus, Search, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { memoryApi } from '../api'

const loading = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)

// 分组展开状态
const expandedGroups = ref(new Set(['explicit', 'implicit']))

const explicit = ref([])
const implicit = ref([])
const archive = ref([])

const sections = ['用户编码与风格偏好', '项目约束与配置规范', '工具与系统使用偏好']

const totalCount = computed(() => {
  return explicit.value.length + implicit.value.reduce((sum, s) => sum + s.entries.length, 0)
})

const implicitTotalCount = computed(() => implicit.value.reduce((sum, s) => sum + s.entries.length, 0))

const form = ref({
  memory_type: 'explicit',
  section: '',
  content: '',
  confidence: '低',
})

// 内联编辑
const editingRow = ref(null)
const editText = ref('')
const editType = ref('')
const editSection = ref('')

function startEdit(row, type, sectionName) {
  editingRow.value = row
  editText.value = row.content
  editType.value = type
  editSection.value = sectionName || ''
}

function cancelEdit() {
  editingRow.value = null
  editText.value = ''
}

async function saveEdit(row, type, sectionName) {
  if (!editText.value.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  try {
    await memoryApi.update({
      target_content: row.content,
      new_content: editText.value,
      memory_type: type,
    })
    ElMessage.success('已更新')
    editingRow.value = null
    loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

const filteredExplicit = computed(() => {
  if (!keyword.value) return explicit.value
  const kw = keyword.value.toLowerCase()
  return explicit.value.filter(e => e.content.toLowerCase().includes(kw) || (e.meta || '').toLowerCase().includes(kw))
})

const filteredImplicit = computed(() => {
  const kw = keyword.value?.toLowerCase() || ''
  if (!kw) return implicit.value
  return implicit.value
    .map(s => ({ ...s, entries: s.entries.filter(e => e.content.toLowerCase().includes(kw) || (e.meta || '').toLowerCase().includes(kw)) }))
    .filter(s => s.entries.length > 0)
})

const filteredArchive = computed(() => {
  if (!keyword.value) return archive.value
  const kw = keyword.value.toLowerCase()
  return archive.value.filter(e => e.content.toLowerCase().includes(kw) || (e.meta || '').toLowerCase().includes(kw))
})

function toggleGroup(name) {
  if (expandedGroups.value.has(name)) {
    expandedGroups.value.delete(name)
  } else {
    expandedGroups.value.add(name)
  }
}

function confBandClass(conf) {
  if (conf === '高') return 'mem-band--high'
  if (conf === '中') return 'mem-band--mid'
  return 'mem-band--low'
}

async function loadAll() {
  loading.value = true
  try {
    const data = await memoryApi.list()
    explicit.value = data.explicit || []
    implicit.value = data.implicit || []
    archive.value = data.archive || []
  } catch (e) {
    ElMessage.error('加载记忆失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = { memory_type: 'explicit', section: '', content: '', confidence: '低' }
  dialogVisible.value = true
}

async function saveMemory() {
  if (!form.value.content.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  try {
    if (form.value.memory_type === 'implicit' && !form.value.section) {
      ElMessage.warning('隐式记忆需选择分类板块')
      return
    }
    await memoryApi.create({
      memory_type: form.value.memory_type,
      section: form.value.section,
      content: form.value.content,
      confidence: form.value.confidence,
    })
    ElMessage.success('已新增')
    dialogVisible.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function removeMemory(row, isExplicit) {
  try {
    await ElMessageBox.confirm('确定删除这条记忆吗？', '删除确认', { type: 'warning' })
    await memoryApi.remove({ target_content: row.content, archive: true })
    ElMessage.success('已删除')
    loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.memory-manage {
  max-width: 960px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
.page-subtitle {
  font-size: 13px;
  color: #94a3b8;
}
.page-header-right {
  display: flex;
  gap: 10px;
  align-items: center;
}
.search-input { width: 220px; }

/* 新增按钮 */
.btn-create {
  background: #1e293b !important;
  border-color: #1e293b !important;
  color: #fff !important;
  font-weight: 500;
}
.btn-create:hover {
  background: #334155 !important;
  border-color: #334155 !important;
}

/* 分组容器 */
.mem-group {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 10px;
  overflow: hidden;
}

/* 分组头 */
.group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.12s;
}
.group-header:hover {
  background: #f8fafc;
}
.group-band {
  width: 3px;
  height: 18px;
  border-radius: 2px;
  flex-shrink: 0;
}
.group-band--high { background: #1e293b; }
.group-band--mid  { background: #64748b; }
.group-band--low  { background: #cbd5e1; }
.group-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.group-count {
  font-size: 12px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 1px 8px;
  border-radius: 10px;
}
.group-desc {
  font-size: 12px;
  color: #94a3b8;
  flex: 1;
}
.group-arrow {
  font-size: 13px;
  color: #94a3b8;
  transition: transform 0.2s;
}
.group-arrow.expanded { transform: rotate(180deg); }

/* 分组内容 */
.group-body {
  border-top: 1px solid #e2e8f0;
  background: #fafbfc;
}

/* 记忆条目 */
.mem-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.12s;
}
.mem-item:hover { background: #fff; }
.mem-item--sub { padding-left: 28px; }
.mem-item--archive { opacity: 0.55; }
.mem-item:last-child { border-bottom: none; }

/* 左侧色带 */
.mem-band {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex-shrink: 0;
}
.mem-band--high { background: #1e293b; }
.mem-band--mid  { background: #64748b; }
.mem-band--low  { background: #cbd5e1; }

/* 内容 */
.mem-content {
  flex: 1;
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
  min-width: 0;
  cursor: pointer;
  word-break: break-word;
}
.mem-content--archive { color: #94a3b8; cursor: default; }

/* 编辑区域 */
.mem-edit-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 元信息 */
.mem-meta {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  flex-shrink: 0;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 置信度标签 */
.mem-conf {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.mem-conf--高 { background: #f1f5f9; color: #1e293b; }
.mem-conf--中 { background: #f1f5f9; color: #64748b; }
.mem-conf--低 { background: #f1f5f9; color: #94a3b8; }

/* 操作 */
.mem-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.12s;
  flex-shrink: 0;
}
.mem-item:hover .mem-actions { opacity: 1; }
.action-delete { color: #ef4444 !important; }

/* 空态 */
.mem-empty {
  padding: 16px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

/* 子分区 */
.mem-sub { margin-bottom: 2px; }
.sub-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px 4px 16px;
}
.sub-band {
  width: 2px;
  height: 12px;
  background: #cbd5e1;
  border-radius: 1px;
  flex-shrink: 0;
}
.sub-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}
.sub-count {
  font-size: 11px;
  color: #94a3b8;
}

/* 展开/收起动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.15s ease;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 1200px;
}

/* 响应式 */
@media (max-width: 768px) {
  .search-input { width: 100% !important; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 10px; }
  .group-desc { display: none; }
  .mem-meta { max-width: 100px; }
  .mem-actions { opacity: 1; }
}

@media (max-width: 480px) {
  .mem-item { flex-wrap: wrap; }
  .mem-meta { max-width: none; }
}
</style>
