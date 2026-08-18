<template>
  <div class="model-manage">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-left">
        <h2 class="page-title">模型管理</h2>
        <span class="page-subtitle">{{ totalModels }} 个模型 / {{ providerGroups.length }} 个供应商</span>
      </div>
      <div class="page-header-right">
        <el-input
          v-model="keyword"
          placeholder="搜索模型名称或标识"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button class="btn-create" :icon="Plus" @click="openCreate">添加供应商</el-button>
      </div>
    </div>

    <!-- 供应商→模型 两层列表 -->
    <div v-loading="loading" class="provider-list">
      <div
        v-for="group in filteredGroups"
        :key="group.key"
        class="provider-section"
        :class="{ 'is-active-provider': groupIsActive(group) }"
      >
        <!-- 供应商行 -->
        <div
          class="provider-row"
          :class="{
            expanded: expandedProviders.has(group.key),
            active: groupIsActive(group)
          }"
          @click="toggleProvider(group.key)"
        >
          <div class="provider-left">
            <div class="provider-badge" :style="{ background: group.color }">
              {{ group.icon }}
            </div>
            <div class="provider-info">
              <div class="provider-name">
                {{ group.name }}
                <span v-if="groupIsActive(group)" class="active-label">当前选中</span>
              </div>
              <div class="provider-url">{{ group.baseUrl }}</div>
            </div>
          </div>
          <div class="provider-right">
            <el-button
              link
              size="small"
              class="provider-add-btn"
              :icon="Plus"
              @click.stop="quickAddModel(group)"
            >
              添加模型
            </el-button>
            <span class="provider-count">{{ group.models.length }} 个模型</span>
            <el-icon class="expand-arrow" :class="{ expanded: expandedProviders.has(group.key) }">
              <ArrowDown />
            </el-icon>
          </div>
        </div>

        <!-- 展开的模型列表 -->
        <transition name="slide">
          <div v-if="expandedProviders.has(group.key)" class="model-list">
            <div
              v-for="m in group.models"
              :key="m.name"
              class="model-row"
              :class="{ 'is-active': m.name === activeModel }"
            >
              <div class="model-left">
                <div class="model-dot" :class="{ active: m.name === activeModel }"></div>
                <div class="model-info">
                  <div class="model-name">
                    {{ m.model }}
                    <el-tag v-if="m.name === activeModel" class="default-tag" size="small" effect="dark" round>
                      默认
                    </el-tag>
                  </div>
                  <div class="model-config-name">{{ m.name }}</div>
                </div>
              </div>
              <div class="model-actions">
                <el-button link class="action-edit" size="small" @click="openEdit(m)">
                  <el-icon><Edit /></el-icon> 编辑
                </el-button>
                <el-button
                  v-if="m.name !== activeModel"
                  link
                  class="action-default"
                  size="small"
                  @click="setActive(m)"
                >
                  <el-icon><Star /></el-icon> 设为默认
                </el-button>
                <el-tooltip
                  v-if="testResult[m.name] && !testResult[m.name].ok"
                  :content="testResult[m.name].message || '测试失败'"
                  placement="left"
                >
                  <el-button
                    link
                    :class="testResult[m.name]?.ok ? 'action-test-ok' : 'action-test'"
                    size="small"
                    :loading="testingMap[m.name]"
                    @click="testModel(m)"
                  >
                    <el-icon v-if="!testingMap[m.name]">
                      <CircleCheck v-if="testResult[m.name]?.ok" />
                      <CircleClose v-else-if="testResult[m.name]" />
                      <Promotion v-else />
                    </el-icon>
                    {{ testingMap[m.name] ? '测试中' : testResult[m.name] ? (testResult[m.name].ok ? '正常' : '异常') : '测试' }}
                  </el-button>
                </el-tooltip>
                <el-button
                  v-else
                  link
                  :class="testResult[m.name]?.ok ? 'action-test-ok' : 'action-test'"
                  size="small"
                  :loading="testingMap[m.name]"
                  @click="testModel(m)"
                >
                  <el-icon v-if="!testingMap[m.name]">
                    <CircleCheck v-if="testResult[m.name]?.ok" />
                    <CircleClose v-else-if="testResult[m.name]" />
                    <Promotion v-else />
                  </el-icon>
                  {{ testingMap[m.name] ? '测试中' : testResult[m.name] ? (testResult[m.name].ok ? '正常' : '异常') : '测试' }}
                </el-button>
                <el-button link class="action-delete" size="small" @click="removeModel(m)">
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </div>
            </div>

            <!-- 供应商下无模型 -->
            <div v-if="!group.models.length" class="model-empty">
              暂无模型配置
            </div>
          </div>
        </transition>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && !providerGroups.length" class="empty-state">
        <el-empty
          :description="keyword ? '未搜索到匹配的模型' : '暂无供应商，点击右上角添加'"
          :image-size="100"
        />
      </div>
    </div>

    <!-- 新增/编辑对话框 -->
    <model-form-dialog
      v-model:visible="dialogVisible"
      :model="editingModel"
      @submit="saveModel"
      @batch-submit="batchSaveModels"
    />

    <!-- 快速添加模型对话框 -->
    <el-dialog v-model="quickAddVisible" title="快速添加模型" width="480px">
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="供应商">
          <el-input :model-value="quickAddProvider?.name" disabled />
        </el-form-item>
        <el-form-item label="API 地址">
          <el-input :model-value="quickBaseUrl" disabled />
        </el-form-item>
        <el-form-item label="模型标识" required>
          <el-input
            v-model="quickAddForm.model"
            placeholder="如 deepseek-chat"
            clearable
            @keyup.enter="submitQuickAdd"
          />
        </el-form-item>
        <el-form-item label="密钥">
          <el-input
            v-model="quickAddForm.api_key"
            type="password"
            show-password
            placeholder="该供应商密钥（如已配置可留空）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickAddVisible = false">取消</el-button>
        <el-button type="primary" :loading="quickAdding" @click="submitQuickAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Plus, Search, Edit, Delete, Star, ArrowDown,
  Promotion, CircleCheck, CircleClose,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelApi } from '../api'
import { useChatSessions } from '../composables/useChatSessions'
import ModelFormDialog from '../components/ModelFormDialog.vue'

// 获取会话共享状态，模型切换后同步刷新全局状态
const { loadModels: syncGlobalModels } = useChatSessions()

const models = ref([])
const activeModel = ref('')
const loading = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)
const editingModel = ref(null)

// 展开的供应商
const expandedProviders = ref(new Set())

// 当前选中的供应商（默认模型所属的供应商）
const activeProviderKey = computed(() => {
  if (!activeModel.value) return ''
  const m = models.value.find(m => m.name === activeModel.value)
  return m?.base_url || ''
})

// 判断供应商组是否为当前选中的
function groupIsActive(group) {
  return group.key === activeProviderKey.value
}

// 连通性测试状态
const testingMap = reactive({})
const testResult = reactive({})

// 供应商映射表（与 ModelFormDialog 保持一致）
const PROVIDERS = [
  { match: 'deepseek', name: 'DeepSeek', icon: 'DS', color: '#4D6BFE' },
  { match: 'openai', name: 'OpenAI', icon: 'AI', color: '#10A37F' },
  { match: 'minimax', name: 'MiniMax', icon: 'MM', color: '#FF4D4F' },
  { match: 'moonshot', name: 'Kimi', icon: '🌙', color: '#f97316' },
  { match: 'bigmodel', name: 'Zhipu', icon: 'Z', color: '#3469FF' },
  { match: 'dashscope', name: 'Qwen', icon: 'Q', color: '#615CED' },
  { match: 'volces', name: 'Doubao', icon: '豆', color: '#3B5BFF' },
  { match: 'baichuan', name: 'Baichuan', icon: 'B', color: '#FF8800' },
  { match: 'yi', name: '01.AI', icon: 'Y', color: '#00B4D8' },
  { match: 'siliconflow', name: 'SiliconFlow', icon: 'SF', color: '#6366F1' },
]

const DEFAULT_PROVIDER = { name: '自定义', icon: '⚙', color: '#6B7280' }

// 检测供应商
function detectProvider(model) {
  const url = (model.base_url || '').toLowerCase()
  for (const p of PROVIDERS) {
    if (url.includes(p.match)) return p
  }
  return DEFAULT_PROVIDER
}

// 模型总数
const totalModels = computed(() => models.value.length)

// 按 base_url 分组（同一个 base_url 视为同一供应商）
const providerGroups = computed(() => {
  const groupMap = new Map()
  for (const m of models.value) {
    const provider = detectProvider(m)
    // 用 base_url 作为分组 key（同一供应商可能配不同 key）
    const groupKey = m.base_url || 'unknown'
    if (!groupMap.has(groupKey)) {
      groupMap.set(groupKey, {
        key: groupKey,
        name: provider.name,
        icon: provider.icon,
        color: provider.color,
        baseUrl: m.base_url,
        models: [],
      })
    }
    groupMap.get(groupKey).models.push(m)
  }
  return Array.from(groupMap.values())
})

// 搜索过滤
const filteredGroups = computed(() => {
  if (!keyword.value) return providerGroups.value
  const kw = keyword.value.toLowerCase()
  return providerGroups.value
    .map(g => ({
      ...g,
      models: g.models.filter(m =>
        m.name.toLowerCase().includes(kw) ||
        (m.model || '').toLowerCase().includes(kw)
      ),
    }))
    .filter(g => g.models.length > 0 || g.name.toLowerCase().includes(kw))
})

// 展开/收起供应商
function toggleProvider(key) {
  if (expandedProviders.value.has(key)) {
    expandedProviders.value.delete(key)
  } else {
    expandedProviders.value.add(key)
  }
}

async function loadAll() {
  loading.value = true
  try {
    const data = await modelApi.list()
    models.value = data.models || []
    activeModel.value = data.active_model || ''
    // 默认展开所有供应商
    expandedProviders.value = new Set(providerGroups.value.map(g => g.key))
  } catch (e) {
    ElMessage.error('加载模型列表失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingModel.value = null
  dialogVisible.value = true
}

function openEdit(model) {
  editingModel.value = { ...model }
  dialogVisible.value = true
}

// 快速添加模型（在当前供应商下直接填模型名）
const quickAddVisible = ref(false)
const quickAdding = ref(false)
const quickAddProvider = ref(null)
const quickAddForm = ref({ model: '', api_key: '' })

const quickBaseUrl = computed(() => quickAddProvider.value?.baseUrl || '')

function quickAddModel(group) {
  quickAddProvider.value = group
  quickAddForm.value = { model: '', api_key: '' }
  // 复用该供应商下第一个模型的密钥（如果已有配置）
  const first = group.models[0]
  if (first?.api_key) quickAddForm.value.api_key = first.api_key
  quickAddVisible.value = true
}

async function submitQuickAdd() {
  const modelId = quickAddForm.value.model.trim()
  if (!modelId) {
    ElMessage.warning('请输入模型标识')
    return
  }
  quickAdding.value = true
  try {
    const providerName = quickAddProvider.value.name.toLowerCase()
    const data = {
      name: `${providerName}-${modelId.replace(/[\/]/g, '-')}`,
      model: modelId,
      base_url: quickBaseUrl.value,
      api_key: quickAddForm.value.api_key,
    }
    await modelApi.create(data)
    ElMessage.success(`模型「${modelId}」添加成功`)
    quickAddVisible.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  } finally {
    quickAdding.value = false
  }
}

async function saveModel(formData) {
  try {
    if (editingModel.value) {
      await modelApi.update(editingModel.value.name, formData)
      ElMessage.success('保存成功')
    } else {
      await modelApi.create(formData)
      ElMessage.success(`模型「${formData.name}」添加成功`)
    }
    dialogVisible.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function batchSaveModels(modelsData) {
  let successCount = 0
  let failCount = 0
  for (const data of modelsData) {
    try {
      await modelApi.create(data)
      successCount++
    } catch (e) {
      failCount++
      ElMessage.error(`模型「${data.name}」添加失败：${e.response?.data?.detail || '未知错误'}`)
    }
  }
  if (successCount > 0) {
    ElMessage.success(`成功添加 ${successCount} 个模型${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    dialogVisible.value = false
    loadAll()
  }
}

async function removeModel(model) {
  try {
    await ElMessageBox.confirm(
      `确定删除模型「${model.name}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await modelApi.remove(model.name)
    ElMessage.success('已删除')
    loadAll()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function setActive(model) {
  try {
    const r = await modelApi.setActive(model.name)
    activeModel.value = r.active_model
    ElMessage.success(`已将「${model.name}」设为默认模型`)
    // 同步刷新全局会话状态，使聊天框模型标识同步更新
    syncGlobalModels()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '设置失败')
  }
}

async function testModel(model) {
  testingMap[model.name] = true
  try {
    const r = await modelApi.test(model.name)
    testResult[model.name] = r
    if (r.ok) {
      ElMessage.success(`「${model.name}」连接正常`)
    } else {
      ElMessage.warning(`「${model.name}」${r.message}`)
    }
  } catch (e) {
    const detail = e.response?.data?.detail || '请求失败'
    // 展示诊断信息
    let diag = detail
    if (typeof detail === 'object') {
      diag = detail.message || JSON.stringify(detail)
    }
    testResult[model.name] = { ok: false, message: diag }
    ElMessage.error(`「${model.name}」${diag}`)
  } finally {
    testingMap[model.name] = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.model-manage {
  max-width: 960px;
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
  width: 240px;
}

/* 新建按钮 */
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

/* 供应商列表 */
.provider-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.provider-section {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.provider-section:hover {
  border-color: #cbd5e1;
}
.provider-section.is-active-provider {
  border-color: #86efac;
}

/* 供应商行 */
.provider-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  user-select: none;
}
.provider-row:hover {
  background: #f8fafc;
}
.provider-row.expanded {
  background: #f8fafc;
}
.provider-row.active {
  background: #f0fdf4;
}
.provider-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.provider-badge {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.provider-info {
  min-width: 0;
}
.provider-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
}
.active-label {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 8px;
  border-radius: 10px;
  background: #dcfce7;
  color: #166534;
}
.provider-url {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 400px;
}
.provider-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.provider-count {
  font-size: 13px;
  color: #94a3b8;
}
.provider-add-btn {
  color: #64748b;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.provider-row:hover .provider-add-btn {
  opacity: 1;
}
.provider-add-btn:hover {
  color: #1e293b;
}
.expand-arrow {
  font-size: 14px;
  color: #94a3b8;
  transition: transform 0.2s;
}
.expand-arrow.expanded {
  transform: rotate(180deg);
}

/* 模型列表（展开） */
.model-list {
  border-top: 1px solid #e2e8f0;
  background: #fafbfc;
}
.model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px 10px 70px;
  transition: background 0.15s;
}
.model-row:hover {
  background: #f1f5f9;
}
.model-row.is-active {
  background: #f0fdf4;
}
.model-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.model-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d1d5db;
  flex-shrink: 0;
}
.model-dot.active {
  background: #1e293b;
}
.model-info {
  min-width: 0;
}
.model-name {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'SF Mono', 'Consolas', monospace;
}
.model-config-name {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 1px;
}

/* 默认标签 */
.default-tag {
  background: #1e293b !important;
  border-color: #1e293b !important;
  color: #fff !important;
}

/* 模型操作按钮 */
.model-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.model-row:hover .model-actions {
  opacity: 1;
}
.action-edit {
  color: #1e293b !important;
}
.action-default {
  color: #f97316 !important;
}
.action-test {
  color: #64748b !important;
}
.action-test-ok {
  color: #16a34a !important;
}
.action-delete {
  color: #ef4444 !important;
}

/* 模型空态 */
.model-empty {
  padding: 20px 18px 20px 70px;
  font-size: 13px;
  color: #94a3b8;
}

/* 全局空态 */
.empty-state {
  padding: 80px 0;
}

/* 展开/收起动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
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
  max-height: 800px;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  .search-input {
    width: 100%;
  }
  .provider-url {
    max-width: 260px;
  }
  .model-row {
    padding-left: 50px;
  }
  .model-actions {
    opacity: 1;
  }
}

@media (max-width: 480px) {
  .provider-row {
    padding: 12px 14px;
  }
  .model-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding-left: 14px;
  }
}
</style>
