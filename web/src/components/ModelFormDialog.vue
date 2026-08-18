<template>
  <el-dialog
    :model-value="visible"
    :title="model ? '编辑模型' : '添加供应商'"
    width="600px"
    @update:model-value="emit('update:visible', $event)"
  >
    <!-- ===== 编辑模式 ===== -->
    <el-form v-if="model" ref="editFormRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="模型标识" prop="model">
        <el-input v-model="form.model" placeholder="上游 API 的模型名" />
      </el-form-item>
      <el-form-item label="API 地址" prop="base_url">
        <el-input v-model="form.base_url" placeholder="如 https://api.deepseek.com" />
      </el-form-item>
      <el-form-item label="密钥" prop="api_key">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          placeholder="如 sk-xxxxxxxx"
        />
      </el-form-item>

      <el-divider content-position="left">
        <span class="advanced-toggle" @click="showAdvanced = !showAdvanced">
          高级参数
          <el-icon class="toggle-icon" :class="{ rotated: showAdvanced }">
            <ArrowDown />
          </el-icon>
        </span>
      </el-divider>

      <div v-show="showAdvanced">
        <el-form-item label="温度">
          <div class="param-row">
            <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" :show-tooltip="false" class="param-slider" />
            <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="2" size="small" class="param-number" />
          </div>
          <div class="param-hint">留空使用上游默认值</div>
        </el-form-item>
        <el-form-item label="上下文限制">
          <el-input-number v-model="form.max_tokens" :min="1" :max="200000" :step="100" placeholder="留空不限制" class="full-width" />
          <div class="param-hint">单次回复最大 token 数</div>
        </el-form-item>
        <el-form-item label="失败重试">
          <el-input-number v-model="form.retry_count" :min="0" :max="10" :step="1" placeholder="留空默认 3 次" class="full-width" />
          <div class="param-hint">API 调用失败时的自动重试次数</div>
        </el-form-item>
      </div>
    </el-form>

    <!-- ===== 新建模式：三步式 ===== -->
    <div v-else class="create-flow">
      <!-- 步骤指示器 -->
      <div class="steps-bar">
        <div class="step-item" :class="{ active: step >= 1, done: step > 1 }">
          <span class="step-num">1</span>
          <span class="step-text">选择供应商</span>
        </div>
        <div class="step-line" :class="{ filled: step > 1 }"></div>
        <div class="step-item" :class="{ active: step >= 2, done: step > 2 }">
          <span class="step-num">2</span>
          <span class="step-text">配置连接</span>
        </div>
        <div class="step-line" :class="{ filled: step > 2 }"></div>
        <div class="step-item" :class="{ active: step >= 3 }">
          <span class="step-num">3</span>
          <span class="step-text">选择模型</span>
        </div>
      </div>

      <!-- Step 1：选择供应商（行式列表） -->
      <div v-if="step === 1" class="step-content">
        <div class="step-title">选择模型供应商</div>
        <div class="step-desc">选择供应商后将自动填充 API 地址和模型列表</div>
        <div class="provider-list">
          <div
            v-for="p in PROVIDER_TEMPLATES"
            :key="p.name"
            class="provider-row"
            :class="{ selected: selectedProvider === p.name }"
            @click="selectProvider(p)"
          >
            <div class="provider-row-left">
              <span class="provider-row-icon" :style="{ background: p.color }">{{ p.icon }}</span>
              <div class="provider-row-info">
                <div class="provider-row-name">{{ p.name }}</div>
                <div class="provider-row-url">{{ p.base_url }}</div>
              </div>
            </div>
            <el-icon v-if="selectedProvider === p.name" class="check-icon"><CircleCheckFilled /></el-icon>
          </div>
          <!-- 自定义 -->
          <div
            class="provider-row"
            :class="{ selected: selectedProvider === 'custom' }"
            @click="selectProvider({ name: 'custom', icon: '⚙', color: '#6B7280', base_url: '' })"
          >
            <div class="provider-row-left">
              <span class="provider-row-icon" style="background: #6B7280">⚙</span>
              <div class="provider-row-info">
                <div class="provider-row-name">自定义</div>
                <div class="provider-row-url">手动填写 API 地址</div>
              </div>
            </div>
            <el-icon v-if="selectedProvider === 'custom'" class="check-icon"><CircleCheckFilled /></el-icon>
          </div>
        </div>
      </div>

      <!-- Step 2：配置连接参数 -->
      <div v-if="step === 2" class="step-content">
        <div class="step-title">配置连接参数</div>
        <div class="step-desc">填写 API 地址和密钥后拉取可用模型</div>
        <el-form ref="configFormRef" :model="form" :rules="step2Rules" label-width="100px">
          <el-form-item label="API 地址" prop="base_url">
            <el-input v-model="form.base_url" placeholder="如 https://api.deepseek.com" />
          </el-form-item>
          <el-form-item label="密钥" prop="api_key">
            <el-input
              v-model="form.api_key"
              type="password"
              show-password
              placeholder="如 sk-xxxxxxxx"
            />
          </el-form-item>
        </el-form>
        <div v-if="fetchError" class="fetch-error">{{ fetchError }}</div>
      </div>

      <!-- Step 3：选择模型 -->
      <div v-if="step === 3" class="step-content">
        <div class="step-title">选择要添加的模型</div>
        <div class="step-desc">
          已从 <strong>{{ selectedProviderName }}</strong> 获取到
          <strong>{{ fetchedModels.length }}</strong> 个可用模型（可多选）
        </div>
        <div v-if="fetchedModels.length" class="model-select-list">
          <el-checkbox-group v-model="selectedModels">
            <div
              v-for="m in fetchedModels"
              :key="m"
              class="model-option"
              :class="{ checked: selectedModels.includes(m) }"
            >
              <el-checkbox :label="m" :value="m">
                <span class="model-id">{{ m }}</span>
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </div>
        <div v-else class="no-models">
          <el-empty description="未获取到可用模型" :image-size="60" />
        </div>
      </div>
    </div>

    <!-- 底部按钮 -->
    <template #footer>
      <div class="dialog-footer">
        <el-button v-if="step > 1 && !model" @click="prevStep">上一步</el-button>
        <div class="footer-spacer"></div>
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <!-- 编辑模式 -->
        <el-button v-if="model" class="btn-save" @click="submitEdit">保存</el-button>
        <!-- 新建 Step 1 -->
        <el-button
          v-if="!model && step === 1"
          class="btn-next"
          :disabled="!selectedProvider"
          @click="goStep2"
        >下一步</el-button>
        <!-- 新建 Step 2 -->
        <el-button
          v-if="!model && step === 2"
          class="btn-fetch"
          :loading="fetching"
          @click="fetchModels"
        >{{ fetching ? '拉取中...' : '拉取模型' }}</el-button>
        <!-- 新建 Step 3 -->
        <el-button
          v-if="!model && step === 3"
          class="btn-save"
          :disabled="!selectedModels.length"
          @click="submitCreate"
        >添加 {{ selectedModels.length ? `(${selectedModels.length})` : '' }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown, CircleCheckFilled } from '@element-plus/icons-vue'
import { modelApi } from '../api'

const props = defineProps({
  visible: Boolean,
  model: Object,
})
const emit = defineEmits(['submit', 'batch-submit', 'update:visible'])

const editFormRef = ref()
const configFormRef = ref()
const showAdvanced = ref(false)

// 新建流程状态
const step = ref(1)
const selectedProvider = ref('')
const fetching = ref(false)
const fetchError = ref('')
const fetchedModels = ref([])
const selectedModels = ref([])

// 供应商模板
const PROVIDER_TEMPLATES = [
  { name: 'DeepSeek', icon: 'DS', color: '#4D6BFE', base_url: 'https://api.deepseek.com', defaultModel: 'deepseek-chat' },
  { name: 'OpenAI', icon: 'AI', color: '#10A37F', base_url: 'https://api.openai.com/v1', defaultModel: 'gpt-4o' },
  { name: 'MiniMax', icon: 'MM', color: '#FF4D4F', base_url: 'https://api.minimaxi.com/v1', defaultModel: 'MiniMax-M3' },
  { name: 'Kimi', icon: '🌙', color: '#f97316', base_url: 'https://api.moonshot.cn/v1', defaultModel: 'moonshot-v1-8k' },
  { name: 'Zhipu', icon: 'Z', color: '#3469FF', base_url: 'https://open.bigmodel.cn/api/paas/v4', defaultModel: 'glm-4' },
  { name: 'Qwen', icon: 'Q', color: '#615CED', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModel: 'qwen-plus' },
  { name: 'Doubao', icon: '豆', color: '#3B5BFF', base_url: 'https://ark.cn-beijing.volces.com/api/v3', defaultModel: 'doubao-pro-32k' },
  { name: 'SiliconFlow', icon: 'SF', color: '#6366F1', base_url: 'https://api.siliconflow.cn/v1', defaultModel: 'Qwen/Qwen2.5-72B-Instruct' },
]

const selectedProviderName = computed(() => {
  if (selectedProvider.value === 'custom') return '自定义'
  const p = PROVIDER_TEMPLATES.find(t => t.name === selectedProvider.value)
  return p ? p.name : ''
})

const defaultForm = () => ({
  name: '',
  model: '',
  base_url: '',
  api_key: '',
  temperature: null,
  max_tokens: null,
  retry_count: null,
})

const form = ref(defaultForm())

const rules = {
  model: [{ required: true, message: '请输入模型标识', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入密钥', trigger: 'blur' }],
}

const step2Rules = {
  base_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入密钥', trigger: 'blur' }],
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      if (props.model) {
        form.value = { ...defaultForm(), ...props.model }
        showAdvanced.value =
          props.model.temperature != null ||
          props.model.max_tokens != null ||
          props.model.retry_count != null
      } else {
        form.value = defaultForm()
        step.value = 1
        selectedProvider.value = ''
        fetching.value = false
        fetchError.value = ''
        fetchedModels.value = []
        selectedModels.value = []
        showAdvanced.value = false
      }
      editFormRef.value?.clearValidate()
      configFormRef.value?.clearValidate()
    }
  },
)

// 选择供应商
function selectProvider(p) {
  selectedProvider.value = p.name
  form.value.base_url = p.base_url || ''
}

// Step 1 → Step 2
function goStep2() {
  step.value = 2
}

// Step 2：拉取模型
async function fetchModels() {
  try {
    await configFormRef.value.validate()
  } catch {
    return
  }
  fetching.value = true
  fetchError.value = ''
  try {
    const result = await modelApi.fetchAvailable({
      base_url: form.value.base_url,
      api_key: form.value.api_key,
    })
    if (result.ok) {
      fetchedModels.value = result.models || []
      step.value = 3
    } else {
      fetchError.value = result.message || '拉取失败'
    }
  } catch (e) {
    fetchError.value = e.response?.data?.detail || '拉取失败，请检查网络'
  } finally {
    fetching.value = false
  }
}

// 上一步
function prevStep() {
  if (step.value === 3) {
    step.value = 2
    fetchedModels.value = []
    selectedModels.value = []
  } else if (step.value === 2) {
    step.value = 1
  }
}

// 编辑模式提交
async function submitEdit() {
  try {
    await editFormRef.value.validate()
    emit('submit', { ...form.value })
  } catch {
    // 校验失败
  }
}

// 新建模式提交
async function submitCreate() {
  if (!selectedModels.value.length) return
  const providerName = selectedProvider.value === 'custom' ? 'custom' : selectedProvider.value.toLowerCase()
  const results = []
  for (const modelId of selectedModels.value) {
    const data = {
      ...form.value,
      name: `${providerName}-${modelId.replace(/[\/]/g, '-')}`,
      model: modelId,
    }
    results.push(data)
  }
  if (results.length === 1) {
    emit('submit', results[0])
  } else {
    emit('batch-submit', results)
  }
}
</script>

<style scoped>
/* 创建流程 */
.create-flow {
  min-height: 200px;
}

/* 步骤指示器 */
.steps-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.4;
  transition: opacity 0.2s;
}
.step-item.active {
  opacity: 1;
}
.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  background: #e2e8f0;
  color: #64748b;
  transition: all 0.2s;
}
.step-item.active .step-num {
  background: #1e293b;
  color: #fff;
}
.step-text {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
}
.step-line {
  width: 48px;
  height: 2px;
  background: #e2e8f0;
  margin: 0 12px;
  transition: background 0.2s;
}
.step-line.filled {
  background: #1e293b;
}

/* 步骤内容 */
.step-content {
  animation: fadeIn 0.2s ease;
}
.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}
.step-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 20px;
}

/* 供应商行式列表 */
.provider-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
  padding: 4px 0;
}
.provider-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.provider-row:hover {
  border-color: #94a3b8;
  background: #f8fafc;
}
.provider-row.selected {
  border-color: #1e293b;
  background: #f0fdf4;
}
.provider-row-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.provider-row-icon {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.provider-row-info {
  min-width: 0;
}
.provider-row-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.provider-row-url {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}
.check-icon {
  font-size: 18px;
  color: #1e293b;
}

/* 拉取错误 */
.fetch-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  font-size: 13px;
  color: #dc2626;
}

/* 模型选择列表 */
.model-select-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 4px;
}
.model-option {
  padding: 8px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}
.model-option:hover {
  background: #f8fafc;
}
.model-option.checked {
  background: #f1f5f9;
}
.model-id {
  font-size: 13px;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: #1e293b;
}
.no-models {
  padding: 20px 0;
}

/* 底部按钮 */
.dialog-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-spacer {
  flex: 1;
}
.btn-next,
.btn-fetch {
  background: #1e293b !important;
  border-color: #1e293b !important;
  color: #fff !important;
  font-weight: 500;
}
.btn-next:hover,
.btn-fetch:hover {
  background: #334155 !important;
  border-color: #334155 !important;
}
.btn-save {
  background: #1e293b !important;
  border-color: #1e293b !important;
  color: #fff !important;
  font-weight: 500;
}
.btn-save:hover {
  background: #334155 !important;
  border-color: #334155 !important;
}

/* 高级参数折叠 */
.advanced-toggle {
  cursor: pointer;
  font-size: 14px;
  color: #6b7280;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  user-select: none;
}
.advanced-toggle:hover {
  color: #1e293b;
}
.toggle-icon {
  transition: transform 0.2s;
}
.toggle-icon.rotated {
  transform: rotate(180deg);
}
.param-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.param-slider {
  flex: 1;
}
.param-number {
  width: 100px;
}
.param-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
.full-width {
  width: 100%;
}
:deep(.el-divider--horizontal) {
  margin: 8px 0 20px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
