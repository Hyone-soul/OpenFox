import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isElectron = mode === 'electron'

  return {
    plugins: [vue()],
    // Electron 模式使用相对路径（file:// 协议兼容）
    base: isElectron ? './' : '/',
    server: {
      port: 5173,
      proxy: {
        '/v1': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      // Electron 模式下使用相对路径加载资源
      assetsDir: isElectron ? 'assets' : 'assets',
    },
  }
})
