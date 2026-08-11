<script setup>
import NavBar from '@/components/NavBar.vue'
import { themeState } from '@/utils/theme.js'
import StarfieldBackground from '@/components/StarfieldBackground.vue'
import SkyBackground from '@/components/SkyBackground.vue'
import MinimalBackground from '@/components/MinimalBackground.vue'
import AIAssistant from '@/components/AIAssistant.vue'
import ToolBall from '@/components/ToolBall.vue'


</script>

<template>
  <!-- 全局主题背景：所有页面统一（首页/文档/日志/记录/引导/登录/书房） -->
  <Transition name="bg-fade" mode="out-in">
    <StarfieldBackground v-if="themeState.id === 'starlight'" />
    <SkyBackground v-else-if="themeState.id === 'sky'" />
    <MinimalBackground v-else />
  </Transition>

  <NavBar />
  <div class="page-shell">
    <router-view />
  </div>
  <AIAssistant />
  <ToolBall />
</template>

<style>
/* 沉浸式阅读：隐藏全局导航 */
body.immersive .kb-navbar {
  display: none !important;
}
body.immersive {
  background: var(--bg);
}

/* 手绘删除确认弹窗（DoodleBall） */
.el-message-box.zhy-doodle-confirm {
  border-radius: 16px;
  padding: 24px;
  width: 390px;
  border: 1px solid var(--border);
  background: var(--bg-soft);
  box-shadow: 0 18px 50px rgba(0, 0, 0, .18);
}
.zhy-doodle-confirm .el-message-box__title {
  font-size: 15.5px;
  font-weight: 700;
  color: var(--text1);
  display: flex;
  align-items: center;
  gap: 8px;
}
.zhy-doodle-confirm .el-message-box__title::before { content: '🗑️'; font-size: 17px; }
.zhy-doodle-confirm .el-message-box__content {
  color: var(--text2);
  font-size: 13.5px;
  line-height: 1.75;
  margin-top: 8px;
}
.zhy-doodle-confirm .el-message-box__btns {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.zhy-doodle-confirm .el-message-box__btns .el-button--primary {
  background: linear-gradient(120deg, #ef4444, #dc2626);
  border: none;
  border-radius: 999px;
  padding: 9px 24px;
  font-weight: 600;
}
.zhy-doodle-confirm .el-message-box__btns .el-button--primary:hover { filter: brightness(1.1); }
.zhy-doodle-confirm .el-message-box__btns .el-button--default {
  border-radius: 999px;
  padding: 9px 24px;
  border: 1px solid var(--border);
  background: var(--btn-bg);
  color: var(--text2);
}


/* ═══ 全局自定义 Tooltip（替代原生 title 黑框）═══
   用法：元素加 data-tip="提示文字"，悬停显示毛玻璃风格提示框 */
[data-tip] {
  position: relative;
  z-index: 0;
}
[data-tip]:hover, [data-tip]:focus-visible {
  z-index: 99999 !important;
}
[data-tip]::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 9px);
  left: 50%;
  transform: translateX(-50%) translateY(3px);
  padding: 5px 9px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--bg-soft) 90%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
  color: var(--text1);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity .16s ease, transform .16s ease, visibility .16s;
  transition-delay: 0s;
  z-index: 99999;
}
[data-tip]::before {
  content: '';
  position: absolute;
  top: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-bottom-color: var(--border);
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity .16s ease, visibility .16s;
  transition-delay: 0s;
  z-index: 99999;
}
[data-tip]:hover::after,
[data-tip]:focus-visible::after,
[data-tip]:hover::before,
[data-tip]:focus-visible::before {
  opacity: 1;
  visibility: visible;
  transition-delay: .5s;
}
[data-tip]:hover::after,
[data-tip]:focus-visible::after {
  transform: translateX(-50%) translateY(0);
  transition-delay: .5s;
}
/* 靠右边缘的按钮：提示框右对齐，避免溢出视口 */
[data-tip][data-tip-align="right"]::after {
  left: auto;
  right: 0;
  transform: translateY(3px);
}
[data-tip][data-tip-align="right"]:hover::after,
[data-tip][data-tip-align="right"]:focus-visible::after {
  transform: translateY(0);
}
[data-tip][data-tip-align="right"]::before {
  left: auto;
  right: 12px;
  transform: none;
}
/* 靠左边缘的按钮：提示框左对齐 */
[data-tip][data-tip-align="left"]::after {
  left: 0;
  transform: translateY(3px);
}
[data-tip][data-tip-align="left"]:hover::after,
[data-tip][data-tip-align="left"]:focus-visible::after {
  transform: translateY(0);
}
[data-tip][data-tip-align="left"]::before {
  left: 12px;
  transform: none;
}
</style>

<style scoped>
.page-shell {
  position: relative;
  z-index: 1;
}
.bg-fade-enter-active,
.bg-fade-leave-active {
  transition: opacity .45s ease;
}
.bg-fade-enter-from,
.bg-fade-leave-to {
  opacity: 0;
}
</style>