<!-- 通用单选下拉：外观与原生 <select> 一致，选项列表自绘（选中高亮用主题蓝，跨浏览器统一）。
     替代原生 select——原生展开列表的高亮色由浏览器/系统决定，无法用 CSS 改成主题色。 -->
<template>
  <div ref="wrapRef" class="vs-wrap" :class="{ open }">
    <button type="button" class="vs-trigger" @click="toggle">
      <span class="vs-label">{{ currentLabel }}</span>
      <span class="vs-caret" :class="{ open }">▾</span>
    </button>
    <Transition name="vs-drop">
      <div v-if="open" ref="menuRef" class="vs-menu" :style="{ left: menuLeft + 'px', top: menuTop + 'px', width: menuWidth + 'px' }">
        <div
          v-for="opt in options" :key="opt.value"
          class="vs-item" :class="{ on: modelValue === opt.value }"
          @click="pick(opt.value)"
        >
          <span>{{ opt.label }}</span>
          <span v-if="modelValue === opt.value" class="vs-check">✓</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] }, // [{ value, label }]
})
const emit = defineEmits(['update:modelValue'])

const wrapRef = ref(null)
const menuRef = ref(null)
const open = ref(false)
const menuLeft = ref(0)
const menuTop = ref(0)
const menuWidth = ref(0)

const currentLabel = computed(() => {
  const o = props.options.find(x => x.value === props.modelValue)
  return o ? o.label : ''
})

const toggle = () => {
  open.value = !open.value
  if (open.value) nextTick(positionMenu)
}

// 菜单相对 trigger 定位（fixed，随窗口滚动时自动关闭由 scroll 监听处理）
const positionMenu = () => {
  const t = wrapRef.value
  if (!t) return
  const r = t.getBoundingClientRect()
  menuLeft.value = r.left
  menuTop.value = r.bottom + 6
  menuWidth.value = r.width
}

const pick = (v) => {
  if (v !== props.modelValue) emit('update:modelValue', v)
  open.value = false
}

const onClickOutside = (e) => {
  if (wrapRef.value && !wrapRef.value.contains(e.target)) open.value = false
}
const onScrollOrWheel = () => { open.value = false }

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.addEventListener('wheel', onScrollOrWheel, { passive: true })
  window.addEventListener('scroll', onScrollOrWheel, true)
})
onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  document.removeEventListener('wheel', onScrollOrWheel)
  window.removeEventListener('scroll', onScrollOrWheel, true)
})
</script>

<style scoped>
.vs-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}
/* 触发器：与弹窗 input（modal-input）同款外观 */
.vs-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--btn-bg);
  color: var(--text1);
  font-size: 13.5px;
  cursor: pointer;
  transition: border-color .2s;
}
.vs-trigger:hover { border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.vs-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.vs-caret {
  font-size: 10px;
  color: var(--text2);
  transition: transform .2s;
  flex-shrink: 0;
}
.vs-caret.open { transform: rotate(180deg); }
/* 选项面板：毛玻璃，选中项主题蓝高亮（豆包式） */
.vs-menu {
  position: fixed;
  z-index: 4000;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-soft) 92%, transparent);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.vs-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13.5px;
  color: var(--text1);
  cursor: pointer;
  transition: background .15s;
}
.vs-item:hover { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.vs-item.on {
  color: var(--brand-1);
  font-weight: 600;
  background: color-mix(in srgb, var(--brand-1) 14%, transparent);
}
.vs-check { color: var(--brand-1); font-weight: 700; }
.vs-drop-enter-active, .vs-drop-leave-active { transition: opacity .16s ease, transform .16s ease; }
.vs-drop-enter-from, .vs-drop-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
