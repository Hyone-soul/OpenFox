<template>
  <div class="login-page">
    <!-- 左侧品牌展示区 -->
    <div class="login-brand">
      <div class="brand-bg-grid"></div>
      <div class="brand-content">
        <div class="brand-mascot">
          <img src="/OpenFox.png" class="mascot-img" alt="OpenFox" />
        </div>
        <h1 class="brand-title">OpenFox</h1>
        <p class="brand-tagline">Agent Skills Framework</p>
      </div>
      <!-- 底部版本信息 -->
      <div class="brand-footer">OpenFox v0.1.0</div>
    </div>

    <!-- 右侧登录/注册表单区 -->
    <div class="login-form-area">
      <div class="form-container">
        <!-- 顶部 Logo（移动端可见） -->
        <div class="mobile-brand">
          <img src="/OpenFox.png" class="mobile-logo" alt="OpenFox" />
          <span class="mobile-name">OpenFox</span>
        </div>

        <!-- 模式标签 -->
        <div class="mode-tabs">
          <button
            :class="['mode-tab', { active: mode === 'login' }]"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            :class="['mode-tab', { active: mode === 'register' }]"
            @click="switchMode('register')"
          >
            注册
          </button>
          <div class="mode-indicator" :class="{ right: mode === 'register' }"></div>
        </div>

        <!-- 欢迎语 -->
        <div class="welcome-text">
          <h2 v-if="mode === 'login'">欢迎回来</h2>
          <h2 v-else>创建账号</h2>
          <p v-if="mode === 'login'">登录以继续使用 OpenFox</p>
          <p v-else>注册一个新的 OpenFox 账号</p>
        </div>

        <!-- 登录表单 -->
        <transition name="form-fade" mode="out-in">
          <el-form
            v-if="mode === 'login'"
            key="login"
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            class="auth-form"
            @submit.prevent="handleLogin"
          >
            <el-form-item prop="username">
              <div class="input-wrapper">
                <label class="input-label">用户名</label>
                <el-input
                  v-model="loginForm.username"
                  placeholder="请输入用户名"
                  size="large"
                  :prefix-icon="User"
                  @keyup.enter="handleLogin"
                />
              </div>
            </el-form-item>

            <el-form-item prop="password">
              <div class="input-wrapper">
                <label class="input-label">密码</label>
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  placeholder="请输入密码"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                  @keyup.enter="handleLogin"
                />
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                class="submit-btn"
                :loading="loading"
                @click="handleLogin"
              >
                <span v-if="!loading">登 录</span>
                <span v-else>登录中...</span>
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 注册表单 -->
          <el-form
            v-else
            key="register"
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            class="auth-form"
            @submit.prevent="handleRegister"
          >
            <el-form-item prop="username">
              <div class="input-wrapper">
                <label class="input-label">用户名</label>
                <el-input
                  v-model="registerForm.username"
                  placeholder="字母、数字、下划线、连字符"
                  size="large"
                  :prefix-icon="User"
                />
              </div>
            </el-form-item>

            <el-form-item prop="displayName">
              <div class="input-wrapper">
                <label class="input-label">显示名称</label>
                <el-input
                  v-model="registerForm.displayName"
                  placeholder="选填，其他用户看到的名字"
                  size="large"
                  :prefix-icon="UserFilled"
                />
              </div>
            </el-form-item>

            <el-form-item prop="password">
              <div class="input-wrapper">
                <label class="input-label">密码</label>
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  placeholder="至少 6 位"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                />
              </div>
            </el-form-item>

            <el-form-item prop="confirmPassword">
              <div class="input-wrapper">
                <label class="input-label">确认密码</label>
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  placeholder="再次输入密码"
                  size="large"
                  :prefix-icon="Lock"
                  show-password
                  @keyup.enter="handleRegister"
                />
              </div>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                size="large"
                class="submit-btn"
                :loading="loading"
                @click="handleRegister"
              >
                <span v-if="!loading">注 册</span>
                <span v-else>注册中...</span>
              </el-button>
            </el-form-item>
          </el-form>
        </transition>

        <!-- 提示消息 -->
        <transition name="msg-slide">
          <div v-if="errorMsg" class="msg msg-error">
            <span class="msg-icon">&#10060;</span>
            {{ errorMsg }}
          </div>
        </transition>
        <transition name="msg-slide">
          <div v-if="successMsg" class="msg msg-success">
            <span class="msg-icon">&#9989;</span>
            {{ successMsg }}
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, UserFilled } from '@element-plus/icons-vue'
import { authApi } from '../api/index.js'

const router = useRouter()

// ---- 模式切换 ----
const mode = ref('login')

function switchMode(m) {
  mode.value = m
  errorMsg.value = ''
  successMsg.value = ''
}

// ---- 通用状态 ----
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

// ---- 登录 ----
const loginFormRef = ref(null)
const loginForm = reactive({ username: '', password: '' })
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!loginFormRef.value) return
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const res = await authApi.login({
      username: loginForm.username,
      password: loginForm.password,
    })
    localStorage.setItem('openfox_token', res.token)
    localStorage.setItem('openfox_user', JSON.stringify(res.user))
    const redirect = router.currentRoute.value.query.redirect || '/chat'
    router.replace(redirect)
  } catch (e) {
    const detail = e.response?.data?.detail
    errorMsg.value = detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}

// ---- 注册 ----
const registerFormRef = ref(null)
const registerForm = reactive({
  username: '',
  displayName: '',
  password: '',
  confirmPassword: '',
})

const validateConfirmPassword = (_rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_-]+$/, message: '只能包含字母、数字、下划线和连字符', trigger: 'blur' },
    { max: 32, message: '不能超过 32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleRegister() {
  if (!registerFormRef.value) return
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''
  successMsg.value = ''

  try {
    const res = await authApi.register({
      username: registerForm.username,
      password: registerForm.password,
      display_name: registerForm.displayName || registerForm.username,
    })
    // 注册成功，自动登录
    localStorage.setItem('openfox_token', res.token)
    localStorage.setItem('openfox_user', JSON.stringify(res.user))
    successMsg.value = '注册成功，正在跳转...'
    setTimeout(() => {
      const redirect = router.currentRoute.value.query.redirect || '/chat'
      router.replace(redirect)
    }, 800)
  } catch (e) {
    const detail = e.response?.data?.detail
    errorMsg.value = detail || '注册失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ========== 页面布局 ========== */
.login-page {
  min-height: 100vh;
  display: flex;
  background: #fff;
}

/* ========== 左侧品牌区：黑白极简 ========== */
.login-brand {
  flex: 0 0 440px;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 48px 40px;
}

/* 网格背景 */
.brand-bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 100%);
}

.brand-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

/* 吉祥物 */
.brand-mascot {
  position: relative;
  display: inline-block;
  margin-bottom: 24px;
}

.mascot-img {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  object-fit: cover;
  position: relative;
  z-index: 1;
}

.brand-title {
  font-size: 36px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -1px;
  margin: 0 0 4px;
  line-height: 1.2;
}

.brand-tagline {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.4);
  margin: 0;
  font-weight: 400;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.brand-footer {
  position: absolute;
  bottom: 24px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.15);
}

/* ========== 右侧表单区 ========== */
.login-form-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  position: relative;
}

.form-container {
  width: 100%;
  max-width: 400px;
  position: relative;
  z-index: 1;
}

/* 移动端品牌（桌面端隐藏） */
.mobile-brand {
  display: none;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}

.mobile-logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: cover;
}

.mobile-name {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
}

/* ========== 模式标签切换 ========== */
.mode-tabs {
  display: flex;
  position: relative;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 28px;
}

.mode-tab {
  flex: 1;
  padding: 10px 0;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  background: none;
  border: none;
  cursor: pointer;
  position: relative;
  z-index: 1;
  transition: color 0.25s ease;
  border-radius: 6px;
}

.mode-tab.active {
  color: #1e293b;
}

.mode-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 0;
}

.mode-indicator.right {
  transform: translateX(100%);
}

/* ========== 欢迎语 ========== */
.welcome-text {
  margin-bottom: 28px;
}

.welcome-text h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.welcome-text p {
  font-size: 14px;
  color: #94a3b8;
  margin: 0;
}

/* ========== 表单 ========== */
.auth-form {
  margin: 0;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.input-wrapper {
  width: 100%;
}

.input-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}

.auth-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  padding: 4px 14px;
  box-shadow: 0 0 0 1px #e2e8f0;
  transition: all 0.15s ease;
  background: #fff;
}

.auth-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #cbd5e1;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #1e293b, 0 0 0 3px rgba(30, 41, 59, 0.06);
}

.auth-form :deep(.el-input__prefix) {
  color: #94a3b8;
}

/* 提交按钮：纯黑 */
.submit-btn {
  width: 100%;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  height: 46px;
  background: #1e293b;
  border: none;
  transition: background 0.15s;
  letter-spacing: 0.5px;
  margin-top: 4px;
}

.submit-btn:hover {
  background: #334155;
}

.submit-btn:active {
  background: #0f172a;
}

/* ========== 消息提示 ========== */
.msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-top: 16px;
}

.msg-error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.msg-success {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}

.msg-icon {
  font-size: 14px;
  flex-shrink: 0;
}

/* 过渡动画 */
.msg-slide-enter-active,
.msg-slide-leave-active {
  transition: all 0.3s ease;
}
.msg-slide-enter-from,
.msg-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.form-fade-enter-active,
.form-fade-leave-active {
  transition: all 0.25s ease;
}
.form-fade-enter-from,
.form-fade-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .login-brand {
    display: none;
  }

  .mobile-brand {
    display: flex;
  }

  .login-form-area {
    background: #fff;
  }
}

@media (max-width: 480px) {
  .login-form-area {
    padding: 24px 20px;
  }

  .welcome-text h2 {
    font-size: 20px;
  }
}
</style>
