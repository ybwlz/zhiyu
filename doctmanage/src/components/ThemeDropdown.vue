<!-- 全局主题下拉：右上角按钮 + 三套主题选择（含缩略预览），全站共用。
     原生实现：点击按钮开合、选中即收、点击外部关闭 -->
<template>
  <div ref="wrapRef" class="kb-theme-wrap">
    <button class="kb-theme-trigger" type="button" :data-tip="'主题：' + current.label" data-tip-align="right" @click.stop="toggle">
      <span class="kb-trigger-icon">{{ current.icon }}</span>
      <span class="kb-trigger-label">{{ current.short }}</span>
      <span class="kb-trigger-caret" :class="{ open: visible }">▾</span>
    </button>

    <Transition name="kb-drop">
      <div v-if="visible" ref="menuRef" class="kb-theme-menu" :style="{ left: menuLeft + 'px', top: menuTop + 'px' }">
        <div
          v-for="t in THEMES"
          :key="t.id"
          class="kb-theme-item"
          :class="{ active: themeState.id === t.id }"
          @click="pick(t.id)"
        >
          <span class="kb-theme-swatch" :class="'swatch-' + t.id">
            <span class="swatch-icon">{{ t.icon }}</span>
          </span>
          <span class="kb-theme-info">
            <span class="kb-theme-name">{{ t.label }}</span>
            <span class="kb-theme-desc">{{ t.desc }}</span>
          </span>
          <span class="kb-theme-check" v-if="themeState.id === t.id">✓</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { THEMES, themeState, applyTheme } from '@/utils/theme.js'

const wrapRef = ref(null)
const menuRef = ref(null)
const visible = ref(false)
const menuLeft = ref(0)
const menuTop = ref(0)
const current = computed(() => THEMES.find((t) => t.id === themeState.id) || THEMES[0])

const toggle = () => {
  visible.value = !visible.value
  if (visible.value) nextTick(positionMenu)
}

// 菜单相对触发按钮水平居中，并保证不超出视口
const positionMenu = () => {
  const wrap = wrapRef.value
  const menu = menuRef.value
  if (!wrap || !menu) return
  const r = wrap.getBoundingClientRect()
  const w = menu.offsetWidth
  menuLeft.value = Math.min(Math.max(r.left + r.width / 2 - w / 2, 10), window.innerWidth - w - 10)
  menuTop.value = r.bottom + 10
}

const pick = (id) => {
  if (id !== themeState.id) applyTheme(id)
  visible.value = false // 选中后自动收回
}

// 点击外部关闭
const onClickOutside = (e) => {
  if (wrapRef.value && !wrapRef.value.contains(e.target)) {
    visible.value = false
  }
}
// 滚动（含鼠标滚轮）时也收回
const onWheel = () => { visible.value = false }
onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.addEventListener('wheel', onWheel, { passive: true })
})
onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  document.removeEventListener('wheel', onWheel)
})
</script>

<style scoped>
.kb-theme-wrap {
  position: relative;
  display: inline-block;
}
.kb-theme-trigger {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--btn-bg);
  color: var(--text1);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all .2s;
}
.kb-theme-trigger:hover {
  border-color: var(--btn-border-hover);
  background: var(--btn-bg-hover);
}
.kb-trigger-icon { font-size: 15px; line-height: 1; }
.kb-trigger-caret {
  font-size: 10px;
  color: var(--text2);
  transition: transform .25s;
  display: inline-block;
}
.kb-trigger-caret.open { transform: rotate(180deg); }

/* ── 下拉面板 ── */
.kb-theme-menu {
  position: fixed;
  width: 232px;
  padding: 8px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-soft) 90%, transparent);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  box-shadow: 0 20px 55px rgba(0, 0, 0, 0.32);
  z-index: 3000;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kb-theme-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 10px;
  border-radius: 12px;
  cursor: pointer;
  transition: background .2s;
}
.kb-theme-item:hover { background: var(--btn-bg); }
.kb-theme-item.active { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }

.kb-theme-swatch {
  position: relative;
  width: 46px;
  height: 34px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  border: 1px solid rgba(128, 128, 128, 0.25);
}
/* 三套主题缩略预览 */
.swatch-starlight {
  background: linear-gradient(180deg, #0b1224 0%, #151b31 60%, #0a0f1e 100%);
}
.swatch-starlight::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 72% 28%, rgba(0, 198, 255, 0.5), transparent 42%),
    radial-gradient(circle at 26% 70%, rgba(227, 5, 247, 0.35), transparent 45%);
}
.swatch-starlight::after {
  content: '';
  position: absolute;
  left: 8px; right: 8px; top: 4px; bottom: 4px;
  background-image: radial-gradient(circle, #fff 0.8px, transparent 0.8px);
  background-size: 7px 7px;
  opacity: 0.5;
}
.swatch-sky {
  background: linear-gradient(180deg, #9fd4ff 0%, #cdeaff 55%, #f0f8ff 100%);
}
.swatch-sky::before {
  content: '';
  position: absolute;
  right: 5px; top: -6px;
  width: 20px; height: 20px;
  border-radius: 50%;
  background: radial-gradient(circle, #fff6d8, #ffdf8e);
  box-shadow: 0 0 10px 3px rgba(255, 224, 140, 0.6);
}
.swatch-sky::after {
  content: '';
  position: absolute;
  left: 4px; top: 12px;
  width: 26px; height: 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 8px 0 -2px rgba(255, 255, 255, 0.5);
}
.swatch-minimal {
  background: linear-gradient(180deg, #ffffff 0%, #f2f2f3 100%);
}
.swatch-minimal::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, rgba(0, 0, 0, 0.08) 1px, transparent 1px);
  background-size: 9px 9px;
  opacity: 0.6;
}
.swatch-icon {
  position: absolute;
  right: 3px;
  bottom: 1px;
  font-size: 12px;
  font-style: normal;
  line-height: 1;
}

.kb-theme-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kb-theme-name { font-size: 14px; font-weight: 600; color: var(--text1); }
.kb-theme-desc { font-size: 12px; color: var(--text2); }
.kb-theme-check { color: var(--brand-1); font-weight: 700; font-size: 14px; }

.kb-drop-enter-active, .kb-drop-leave-active { transition: opacity .22s ease, transform .22s ease; }
.kb-drop-enter-from, .kb-drop-leave-to { opacity: 0; transform: translateY(-8px); }
</style>