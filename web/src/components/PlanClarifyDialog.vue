<template>
  <Transition name="clarify-slide">
    <div v-if="visible" class="clarify-overlay">
      <div class="clarify-dialog">
        <!-- 头部 -->
        <div class="clarify-header">
          <div class="clarify-header-left">
            <span class="clarify-icon">?</span>
            <span class="clarify-title">请回答以下问题以帮助我更好地理解任务</span>
          </div>
          <button class="clarify-close-btn" @click="$emit('close')">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <!-- 问题进度指示 -->
        <div class="clarify-round-bar">
          <span class="clarify-round-text">共 {{ questions.length }} 个问题</span>
          <div class="clarify-round-dots">
            <span v-for="(q, i) in questions" :key="q.id || i"
              class="clarify-dot"
              :class="{ answered: !!answers[i] }">
            </span>
          </div>
        </div>

        <!-- 问题列表 -->
        <div class="clarify-body">
          <div v-for="(q, qi) in questions" :key="q.id || qi" class="clarify-question">
            <div class="clarify-q-text">
              <span class="clarify-q-num">{{ qi + 1 }}.</span>
              <span>{{ q.question }}</span>
            </div>
            <div class="clarify-options">
              <label
                v-for="(opt, oi) in q.options || []"
                :key="oi"
                class="clarify-option"
                :class="{ selected: isSelected(qi, opt.label) }"
              >
                <input
                  type="radio"
                  :name="'q-' + (q.id || qi)"
                  :value="opt.label"
                  v-model="answers[qi]"
                />
                <span class="clarify-option-label">{{ opt.label }}</span>
                <span v-if="opt.description" class="clarify-option-desc">{{ opt.description }}</span>
              </label>
              <!-- 自定义输入 -->
              <label
                v-if="q.allow_custom"
                class="clarify-option clarify-option-custom"
                :class="{ selected: isSelected(qi, '__custom__') }"
              >
                <input
                  type="radio"
                  :name="'q-' + (q.id || qi)"
                  value="__custom__"
                  v-model="answers[qi]"
                />
                <span class="clarify-option-label">自定义</span>
                <input
                  v-if="isSelected(qi, '__custom__')"
                  type="text"
                  class="clarify-custom-input"
                  v-model="customTexts[qi]"
                  placeholder="请输入..."
                  @click.stop
                />
              </label>
            </div>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="clarify-footer">
          <span class="clarify-skip-hint">未选择的题目将自动跳过</span>
          <div class="clarify-footer-btns">
            <button class="clarify-btn clarify-skip-btn" @click="$emit('close')">跳过全部</button>
            <button class="clarify-btn clarify-submit-btn" @click="submitAnswers">提交回答</button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  questions: { type: Array, default: () => [] },
  round: { type: Number, default: 0 },
  totalRounds: { type: Number, default: 3 },
})
const emit = defineEmits(['answer', 'close'])

// 答案数组：answers[qi] = 选中值 或 "__custom__"
const answers = ref([])
const customTexts = ref([])

// 当问题列表变化时重置
watch(() => props.questions, (qs) => {
  answers.value = new Array(qs.length).fill('')
  customTexts.value = new Array(qs.length).fill('')
}, { immediate: true })

watch(() => props.visible, (v) => {
  if (v) {
    answers.value = new Array(props.questions.length).fill('')
    customTexts.value = new Array(props.questions.length).fill('')
  }
})

function isSelected(qi, label) {
  return answers.value[qi] === label
}

function submitAnswers() {
  const result = props.questions.map((q, qi) => {
    const selected = answers.value[qi]
    let answer = ''
    let skipped = false
    if (!selected) {
      skipped = true
    } else if (selected === '__custom__') {
      answer = (customTexts.value[qi] || '').trim()
      if (!answer) skipped = true
    } else {
      answer = selected
    }
    return {
      question_id: q.id || `q${qi + 1}`,
      question: q.question,
      answer,
      skipped,
    }
  })
  emit('answer', result)
}
</script>

<style scoped>
.clarify-overlay {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: transparent;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 2000;
  pointer-events: none;
}

.clarify-overlay > .clarify-dialog {
  pointer-events: auto;
}

.clarify-dialog {
  width: 100%;
  max-width: 720px;
  max-height: 80vh;
  background: #fff;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.clarify-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.clarify-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.clarify-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #1e293b;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.clarify-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.clarify-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.clarify-close-btn:hover {
  background: #f1f5f9;
  color: #475569;
}

.clarify-round-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.clarify-round-text {
  font-size: 12px;
  color: #94a3b8;
}

.clarify-round-dots {
  display: flex;
  gap: 4px;
}

.clarify-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e2e8f0;
  transition: all 0.15s;
}

.clarify-dot.answered {
  background: #1e293b;
}

.clarify-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.clarify-question {
  margin-bottom: 20px;
}

.clarify-question:last-child {
  margin-bottom: 0;
}

.clarify-q-text {
  display: flex;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 10px;
}

.clarify-q-num {
  color: #64748b;
  flex-shrink: 0;
}

.clarify-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.clarify-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  background: #fff;
}

.clarify-option:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.clarify-option.selected {
  border-color: #1e293b;
  background: #f1f5f9;
}

.clarify-option input[type="radio"] {
  width: 14px;
  height: 14px;
  accent-color: #1e293b;
  cursor: pointer;
  flex-shrink: 0;
}

.clarify-option-label {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
}

.clarify-option-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 4px;
}

.clarify-option-custom {
  flex-wrap: wrap;
}

.clarify-custom-input {
  width: 100%;
  margin-top: 6px;
  padding: 6px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
}

.clarify-custom-input:focus {
  border-color: #1e293b;
}

.clarify-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.clarify-skip-hint {
  font-size: 12px;
  color: #94a3b8;
}

.clarify-footer-btns {
  display: flex;
  gap: 8px;
}

.clarify-btn {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.clarify-skip-btn {
  background: transparent;
  color: #64748b;
  border-color: #e2e8f0;
}

.clarify-skip-btn:hover {
  background: #f8fafc;
  color: #475569;
}

.clarify-submit-btn {
  background: #1e293b;
  color: #fff;
}

.clarify-submit-btn:hover {
  background: #334155;
}

/* 弹出动画 */
.clarify-slide-enter-active,
.clarify-slide-leave-active {
  transition: opacity 0.2s;
}

.clarify-slide-enter-active .clarify-dialog,
.clarify-slide-leave-active .clarify-dialog {
  transition: transform 0.25s ease-out;
}

.clarify-slide-enter-from,
.clarify-slide-leave-to {
  opacity: 0;
}

.clarify-slide-enter-from .clarify-dialog,
.clarify-slide-leave-to .clarify-dialog {
  transform: translateY(100%);
}
</style>
