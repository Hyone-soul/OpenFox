import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'

import ChatWorkbench from '../views/ChatWorkbench.vue'
import ModelManage from '../views/ModelManage.vue'
import MemoryManage from '../views/MemoryManage.vue'
import SkillManage from '../views/SkillManage.vue'
import MCPManage from '../views/MCPManage.vue'
import UsageManage from '../views/UsageManage.vue'
import Login from '../views/Login.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  { path: '/models', name: 'models', component: ModelManage },
  { path: '/memory', name: 'memory', component: MemoryManage },
  { path: '/skills', name: 'skills', component: SkillManage },
  { path: '/mcps', name: 'mcps', component: MCPManage },
  { path: '/usage', name: 'usage', component: UsageManage },
  { path: '/chat', name: 'chat', component: ChatWorkbench },
]

// Electron 模式使用 hash 路由（兼容 file:// 协议）
// Web 模式使用 history 路由（URL 更美观）
const isElectron = import.meta.env.VITE_ELECTRON === 'true'
  || (typeof window !== 'undefined' && window.electronAPI?.isElectron)

const router = createRouter({
  history: isElectron ? createWebHashHistory() : createWebHistory(),
  routes,
})

// 路由守卫：未登录则跳转到 /login
router.beforeEach((to, from, next) => {
  const isPublic = to.matched.some(record => record.meta.public)
  const token = localStorage.getItem('openfox_token')
  if (!isPublic && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else if (isPublic && token && to.path === '/login') {
    // 已登录再访问 /login → 跳转首页
    next('/chat')
  } else {
    next()
  }
})

export default router
