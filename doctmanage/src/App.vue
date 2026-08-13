<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import NavBar from '@/components/NavBar.vue'
import { themeState } from '@/utils/theme.js'
import StarfieldBackground from '@/components/StarfieldBackground.vue'
import SkyBackground from '@/components/SkyBackground.vue'
import MinimalBackground from '@/components/MinimalBackground.vue'
import AIAssistant from '@/components/AIAssistant.vue'
import ToolBall from '@/components/ToolBall.vue'
import WindowControls from '@/components/WindowControls.vue'
import UpdateNotice from '@/components/UpdateNotice.vue'

const auth = useAuthStore()
// 启动时用最新 /auth/me 刷新登录用户信息（后端字段有更新时，localStorage 旧缓存也能补上 public_id 等新字段）
onMounted(() => { auth.fetchMe() })

// ── 卸载模式（双击 知屿卸载.exe / --uninstall 启动）：弹出卸载确认 ──
const showUninstall = ref(false)
onMounted(async () => {
  if (window.desktop?.isUninstallMode) {
    try {
      if (await window.desktop.isUninstallMode()) showUninstall.value = true
    } catch (e) { /* 忽略 */ }
  }
})
const confirmUninstall = () => { window.desktop?.uninstallApp?.() }
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
  <WindowControls />
  <UpdateNotice />

  <!-- 卸载确认弹窗（卸载模式启动时，站内 modal 风格） -->
  <div v-if="showUninstall" class="uninstall-mask" @click.self="showUninstall = false">
    <div class="uninstall-modal">
      <div class="um-head">
        <b>卸载知屿？</b>
        <button class="um-close" @click="showUninstall = false">✕</button>
      </div>
      <div class="um-body">
        <p>将删除安装目录下的程序文件、桌面快捷方式与开机自启项。<br>你的云端笔记数据不受影响（保存在服务器）。</p>
      </div>
      <div class="um-foot">
        <button class="um-btn ghost" @click="showUninstall = false">取消</button>
        <button class="um-btn danger" @click="confirmUninstall">确认卸载</button>
      </div>
    </div>
  </div>
</template>

<style>
/* 卸载确认弹窗（覆盖层，桌面版卸载模式，站内 modal 风格） */
.uninstall-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .62);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
}
.uninstall-modal {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 14px;
  width: 360px;
  max-width: 92vw;
  box-shadow: 0 24px 64px rgba(0, 0, 0, .4);
  overflow: hidden;
}
html[data-theme="starlight"] .uninstall-modal { background: #0d1220; }
html[data-theme="sky"] .uninstall-modal,
html[data-theme="minimal"] .uninstall-modal { background: #ffffff; }
.um-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 0;
  font-size: 15px;
  color: var(--text1);
}
.um-close {
  background: none;
  border: none;
  color: var(--text2);
  font-size: 14px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
}
.um-close:hover { background: rgba(255,255,255,.08); color: var(--text1); }
.um-body { padding: 12px 18px 4px; font-size: 13px; color: var(--text2); line-height: 1.7; }
.um-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 18px 16px; }
.um-btn {
  padding: 7px 18px;
  border-radius: 8px;
  border: none;
  font-size: 13.5px;
  cursor: pointer;
  background: var(--brand-1);
  color: #fff;
  transition: filter .15s;
}
.um-btn:hover { filter: brightness(1.08); }
.um-btn.ghost { background: transparent; border: 1px solid var(--border); color: var(--text2); }
.um-btn.danger { background: #e11d48; }
.um-btn.danger:hover { filter: brightness(1.1); }

/* 沉浸式阅读：隐藏全局导航 */
body.immersive .kb-navbar {
  display: none !important;
}
body.immersive .ai-assistant,
body.immersive .tball {
  display: none !important;
}
/* 沉浸时隐藏选中文字的「引用」定位浮层（Teleport 到 body，需全局规则） */
body.immersive .sel-tip {
  display: none !important;
}
/* 沉浸时：导航栏隐藏，Menu/大纲 浮空按钮移到顶部导航栏位置，内容占位相应减小（docs / 笔记阅读 / 笔记广场 全部向上补齐） */
body.immersive .mobile-header-sub {
  top: 10px;
}
body.immersive .docs-layout,
body.immersive .reader-page,
body.immersive .square-page {
  padding-top: 52px !important;
}
/* 移动端聊天页：进入具体会话时隐藏顶部导航栏，全屏聊天（QQ 式） */
@media (max-width: 900px) {
  body.chatting .kb-navbar {
    display: none !important;
  }
}
/* 移动端编辑页：页面自带「← 返回」，隐藏顶部导航栏，顶部更精简 */
@media (max-width: 860px) {
  body.editing .kb-navbar {
    display: none !important;
  }
}
/* 移动端 docs 菜单抽屉 + 大纲浮层：毛玻璃半透明（两者都 teleport 到 body，需全局规则） */
@media (max-width: 860px) {
  body .el-drawer.mobile-menu-drawer {
    --el-drawer-bg-color: color-mix(in srgb, var(--bg-soft) 80%, transparent) !important;
    background: color-mix(in srgb, var(--bg-soft) 80%, transparent) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
  }
  .outline-popover {
    background: color-mix(in srgb, var(--bg-soft) 82%, transparent) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
  }
}
body.immersive {
  background: var(--bg);
}
/* 沉浸按钮：无背景纯图标（⛶），hover 提示用站内统一 data-tip 气泡（0.5s 向下浮现）；位置由各页面 scoped 指定：阅览室左侧、笔记页右侧 */
.immersive-btn {
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: none; color: var(--text2);
  font-size: 18px; line-height: 1; cursor: pointer; padding: 6px;
  transition: color .2s;
}
.immersive-btn:hover { color: var(--brand-1); }

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