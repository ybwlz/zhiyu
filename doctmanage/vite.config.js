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
      target: 'chrome120'
    }
  },
  build: {
    target: 'chrome120',
    rollupOptions: {
      output: {
        // 入口 chunk 若承载共享模块（vue/commonjs helpers），动态 chunk（MathJax/路由）反向
        // import 它，入口又动态 import 它们 → 模块图循环死锁/黑屏。
        // 解决：按 npm 包分组，所有 node_modules 依赖独立成 vendor chunk，入口只留应用代码；
        // MathJax 组件（含 xmldom）文件级独立（顶层 await 动态自加载需跨 chunk 避免 TDZ）。
        // 注：曾尝试按大类合并 vendor（减少请求数），但引发动态 import 循环加载失败，回滚按包分组。
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          // 用完整 id 判断（xmldom-sre 可能是嵌套依赖，包名正则取不到）
          const isMjx = id.includes('mathjax') || id.includes('tex-svg') || id.includes('xypic') ||
                        id.includes('wgxpath') || id.includes('lite-dom') || id.includes('xmldom')
          if (isMjx) {
            const fn = id.split(/[\\/]/).pop().replace(/[^a-zA-Z0-9]/g, '_')
            let h = 0
            for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0
            return 'mjx-' + h.toString(36) + '-' + fn.slice(0, 40)
          }
          const m = id.match(/node_modules[\\/]([^\\/]+)/)
          if (!m) return undefined
          return 'vendor-' + m[1].replace(/[^a-zA-Z0-9]/g, '_')
        }
      }
    }
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

