<template>
  <div class="agent-manage">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">智能体管理</h2>
        <span class="page-subtitle">{{ agents.length }} 个智能体</span>
      </div>
      <div class="page-header-right">
        <el-input
          v-model="keyword"
          placeholder="搜索智能体名称或描述"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button type="primary" :icon="Plus" @click="openCreate">新建智能体</el-button>
      </div>
    </div>

    <!-- 卡片网格 -->
    <div v-loading="loading" class="card-grid">
      <el-card
        v-for="a in filteredAgents"
        :key="a.id"
        shadow="hover"
        class="agent-card"
      >
        <!-- 卡片头部：图标 + 名称 + 模型标签 -->
        <div class="card-header">
          <div class="card-header-left">
            <div class="agent-badge">
              <el-icon :size="20"><Monitor /></el-icon>
            </div>
            <div class="card-title-area">
              <div class="card-title">{{ a.name }}</div>
              <div class="card-subtitle">{{ a.id }}</div>
            </div>
          </div>
          <el-tag size="small" effect="plain" round type="primary" v-if="a.model">
            {{ a.model }}
          </el-tag>
          <el-tag size="small" effect="plain" round type="info" v-else>
            默认模型
          </el-tag>
        </div>

        <!-- 描述 -->
        <div class="card-desc" v-if="a.description">
          {{ a.description }}
        </div>
        <div class="card-desc dim" v-else>
          暂无描述
        </div>

        <!-- 工具 / 技能标签 -->
        <div class="card-tags">
          <template v-if="a.tools && a.tools.length">
            <el-tag
              v-for="t in a.tools.slice(0, 4)"
              :key="t"
              size="small"
              effect="plain"
              round
              class="tag-item"
            >
              {{ t }}
            </el-tag>
            <el-tag v-if="a.tools.length > 4" size="small" effect="plain" round class="tag-item">
              +{{ a.tools.length - 4 }}
            </el-tag>
          </template>
          <template v-if="a.skills && a.skills.length">
            <el-tag
              v-for="s in a.skills.slice(0, 3)"
              :key="s"
              size="small"
              type="success"
              effect="plain"
              round
              class="tag-item"
            >
              {{ s }}
            </el-tag>
            <el-tag v-if="a.skills.length > 3" size="small" type="success" effect="plain" round class="tag-item">
              +{{ a.skills.length - 3 }}
            </el-tag>
          </template>
          <span v-if="(!a.tools || !a.tools.length) && (!a.skills || !a.skills.length)" class="dim tag-placeholder">
            全部工具 & 技能
          </span>
        </div>

        <!-- 参数指标 -->
        <div class="card-params">
          <el-tag size="small" type="info" effect="plain" round>
            🌡️ {{ a.temperature != null ? a.temperature : 0.7 }}
          </el-tag>
          <el-tag size="small" type="info" effect="plain" round>
            🔄 {{ a.max_steps || 20 }} 步
          </el-tag>
        </div>

        <!-- 操作按钮 -->
        <div class="card-actions">
          <el-button link type="primary" :icon="Edit" @click="openEdit(a)">编辑</el-button>
          <el-button
            link
            :type="testResult[a.id]?.ok ? 'success' : 'warning'"
            :loading="testingMap[a.id]"
            @click="testAgent(a)"
          >
            <el-icon v-if="!testingMap[a.id]">
              <Promotion v-if="!testResult[a.id]" />
              <CircleCheck v-else-if="testResult[a.id].ok" />
              <CircleClose v-else />
            </el-icon>
            {{ testingMap[a.id] ? '测试中' : testResult[a.id] ? (testResult[a.id].ok ? '正常' : '异常') : '测试' }}
          </el-button>
          <el-button link type="danger" :icon="Delete" @click="removeAgent(a)">删除</el-button>
        </div>
      </el-card>

      <!-- 空状态 -->
      <el-empty
        v-if="!loading && !filteredAgents.length"
        :description="keyword ? '未搜索到匹配的智能体' : '暂无智能体，点击右上角新建'"
        :image-size="100"
        class="empty-state"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <agent-form-dialog
      v-model:visible="dialogVisible"
      :agent="editingAgent"
      :models="models"
      :tools="tools"
      :skills="skills"
      @submit="saveAgent"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus, Search, Edit, Delete, Monitor, Promotion, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, metaApi } from '../api'
import AgentFormDialog from '../components/AgentFormDialog.vue'

const agents = ref([])
const models = ref([])
const tools = ref([])
const skills = ref([])
const loading = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)
const editingAgent = ref(null)

// 测试状态
const testingMap = reactive({})
const testResult = reactive({})

const filteredAgents = computed(() => {
  if (!keyword.value) return agents.value
  const kw = keyword.value.toLowerCase()
  return agents.value.filter(
    (a) =>
      a.name.toLowerCase().includes(kw) ||
      (a.id || '').toLowerCase().includes(kw) ||
      (a.description || '').toLowerCase().includes(kw),
  )
})

async function loadAll() {
  loading.value = true
  try {
    agents.value = await agentApi.list()
    const [m, t, s] = await Promise.all([metaApi.models(), metaApi.tools(), metaApi.skills()])
    models.value = m
    tools.value = t
    skills.value = Object.keys(s)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingAgent.value = null
  dialogVisible.value = true
}

function openEdit(agent) {
  editingAgent.value = { ...agent }
  dialogVisible.value = true
}

async function saveAgent(formData) {
  try {
    if (editingAgent.value) {
      await agentApi.update(editingAgent.value.id, formData)
    } else {
      await agentApi.create(formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function removeAgent(agent) {
  try {
    await ElMessageBox.confirm(
      `确定删除智能体「${agent.name}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await agentApi.remove(agent.id)
    ElMessage.success('已删除')
    loadAll()
  } catch (e) {
    if (e === 'cancel') return
  }
}

async function testAgent(agent) {
  testingMap[agent.id] = true
  try {
    const r = await agentApi.test(agent.id)
    testResult[agent.id] = r
    if (r.ok) {
      ElMessage.success(`「${agent.name}」连接正常`)
    } else {
      ElMessage.warning(`「${agent.name}」${r.message}`)
    }
  } catch (e) {
    testResult[agent.id] = { ok: false, message: '请求失败' }
    ElMessage.error(e.response?.data?.detail || '测试失败')
  } finally {
    testingMap[agent.id] = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.agent-manage {
  max-width: 1400px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}
.page-subtitle {
  font-size: 13px;
  color: #9ca3af;
}
.page-header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}
.search-input {
  width: 260px;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  min-height: 200px;
}

/* 单个卡片 */
.agent-card {
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.agent-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
.agent-card :deep(.el-card__body) {
  padding: 18px;
}

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.card-header-left {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
  flex: 1;
}
.agent-badge {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  background: #1e293b;
}
.card-title-area {
  min-width: 0;
  flex: 1;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
.card-subtitle {
  font-size: 12px;
  color: #9ca3af;
  font-family: 'SF Mono', 'Consolas', monospace;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

/* 描述 */
.card-desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-desc.dim {
  color: #c0c4cc;
  font-style: italic;
}

/* 工具 / 技能标签 */
.card-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  min-height: 24px;
  align-items: center;
}
.tag-item {
  font-size: 11px;
}
.tag-placeholder {
  font-size: 12px;
}

/* 参数标签 */
.card-params {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

/* 操作按钮 */
.card-actions {
  display: flex;
  gap: 4px;
  padding-top: 12px;
  border-top: 1px solid #f5f5f5;
}

/* 空状态 */
.empty-state {
  grid-column: 1 / -1;
  padding: 60px 0;
}

/* 通用辅助 */
.dim {
  color: #9ca3af;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px;
  }
  .card-title {
    max-width: 160px;
  }
  .card-subtitle {
    max-width: 160px;
  }
}

@media (max-width: 480px) {
  .card-grid {
    grid-template-columns: 1fr;
  }
  .page-title {
    font-size: 18px;
  }
  .agent-card :deep(.el-card__body) {
    padding: 14px;
  }
  .card-title {
    max-width: 180px;
  }
  .card-subtitle {
    max-width: 180px;
  }
  .card-actions {
    flex-wrap: wrap;
  }
}
</style>
