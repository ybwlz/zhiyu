import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/theme.css'
import './styles/docs-theme.css'
import './styles/custom-blocks.css'
import './styles/code-group.css'
import './styles/annotation.css'
import 'highlight.js/styles/github-dark.css' // Switched to github-dark for cleaner look
import App from './App.vue'
import router from "@/router/index.js";
import { initTheme } from '@/utils/theme.js'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { createPinia } from 'pinia';

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

const pinia = createPinia()

app.use(router)
app.use(ElementPlus)
app.use(pinia)
initTheme()

// Electron 桌面版：自定义深色标题栏适配（顶部 40px 拖拽区 + body 下移）
if (navigator.userAgent.includes('Electron')) {
  document.documentElement.classList.add('desktop-electron')
  const bar = document.createElement('div')
  bar.id = 'titlebar-drag'
  document.body.appendChild(bar)
}

app.mount('#app')
