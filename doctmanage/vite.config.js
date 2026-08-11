import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // vueDevTools() 会往页面元素注入调试标记（左上角小蓝三角/检查按钮），
    // 还会在 script setup 下引发响应式失效问题，故关闭
  ],
  optimizeDeps: {
    esbuildOptions: {
      target: 'esnext'
    }
  },
  build: {
    target: 'esnext'
  },
  base: '/zhiyu/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    host: true, // 监听 0.0.0.0：局域网内平板/手机可访问 http://<本机IP>:5173/zhiyu/
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // 头像/上传文件静态资源也走后端（否则 5173 上 /uploads/... 直接 404）
      '/uploads': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})

