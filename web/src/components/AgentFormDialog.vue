<template>
  <el-dialog
    :model-value="visible"
    :title="agent ? '编辑智能体' : '新建智能体'"
    width="680px"
    class="agent-dialog"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form :model="form" label-width="90px" label-position="top" class="agent-form">
      <!-- 基本信息 -->
      <div class="form-section">
        <div class="section-title">
          <el-icon><User /></el-icon>
          基本信息
        </div>
        <div class="form-row">
          <el-form-item label="名称" required class="form-col">
            <el-input v-model="form.name" placeholder="智能体名称，如：研究助手" />
          </el-form-item>
          <el-form-item label="ID" required class="form-col">
            <el-input v-model="form.id" :disabled="!!agent" placeholder="唯一标识，如 research-assistant" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述智能体的用途和能力" />
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="form.model" clearable placeholder="留空则使用全局默认模型" style="width: 100%">
            <el-option v-for="m in models" :key="m.id" :label="m.id" :value="m.id" />
          </el-select>
        </el-form-item>
      </div>

      <!-- 系统提示词 -->
      <div class="form-section">
        <div class="section-title">
          <el-icon><ChatLineRound /></el-icon>
          系统提示词
        </div>
        <el-form-item label="">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="5"
            placeholder="智能体专属指令，会附加到系统提示词中"
          />
        </el-form-item>
      </div>

      <!-- 能力配置 -->
      <div class="form-section">
        <div class="section-title">
          <el-icon><SetUp /></el-icon>
          能力配置
        </div>
        <el-form-item label="工具">
          <el-checkbox-group v-model="form.tools" class="checkbox-grid">
            <el-checkbox v-for="t in tools" :key="t.name" :label="t.name" :value="t.name" class="checkbox-item" />
          </el-checkbox-group>
          <div class="dim-hint" v-if="!tools.length">无可用工具</div>
          <div class="dim-hint" v-else>不勾选则默认拥有全部工具</div>
        </el-form-item>
        <el-form-item label="技能">
          <el-checkbox-group v-model="form.skills" class="checkbox-grid">
            <el-checkbox v-for="s in skills" :key="s" :label="s" :value="s" class="checkbox-item" />
          </el-checkbox-group>
          <div class="dim-hint" v-if="!skills.length">无可用技能</div>
          <div class="dim-hint" v-else>不勾选则默认拥有全部技能</div>
        </el-form-item>
      </div>

      <!-- 运行参数 -->
      <div class="form-section">
        <div class="section-title">
          <el-icon><Setting /></el-icon>
          运行参数
        </div>
        <div class="form-row">
          <el-form-item label="温度" class="form-col">
            <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input />
          </el-form-item>
          <el-form-item label="最大步数" class="form-col">
            <el-input-number v-model="form.max_steps" :min="1" :max="100" style="width: 100%" />
          </el-form-item>
        </div>
      </div>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('update:visible', false)">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { User, ChatLineRound, SetUp, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean,
  agent: Object,
  models: Array,
  tools: Array,
  skills: Array,
})
const emit = defineEmits(['submit', 'update:visible'])

const form = ref({ name: '', id: '', description: '', model: '',
                    system_prompt: '', tools: [], skills: [],
                    temperature: 0.7, max_steps: 20 })

watch(() => props.visible, (v) => {
  if (v) {
    form.value = props.agent
      ? { ...props.agent, tools: [...(props.agent.tools || [])], skills: [...(props.agent.skills || [])] }
      : { name: '', id: '', description: '', model: '', system_prompt: '',
          tools: [], skills: [], temperature: 0.7, max_steps: 20 }
  }
})

function submit() {
  if (!form.value.name || !form.value.id) {
    ElMessage.warning('名称和 ID 为必填项')
    return
  }
  emit('submit', form.value)
}
</script>

<style scoped>
.agent-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 16px;
}

.agent-form {
  max-height: 65vh;
  overflow-y: auto;
  padding-right: 4px;
}

/* 分区 */
.form-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #fafafa;
}
.form-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.section-title .el-icon {
  color: #1e293b;
}

/* 双列表单行 */
.form-row {
  display: flex;
  gap: 16px;
}
.form-col {
  flex: 1;
  min-width: 0;
}

/* 工具/技能 checkbox 网格 */
.checkbox-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.checkbox-item {
  margin-right: 0 !important;
}

.dim-hint {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

/* 底部按钮 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
