<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth.js'
import { TERMS_SECTIONS, PRIVACY_SECTIONS } from '@/constants/legal.js'

const router = useRouter()
const auth = useAuthStore()

// 登录方式：email = 邮箱登录（验证码，首次自动建号）/ pwd = 密码登录
const tab = ref('email')
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)

const emailForm = ref({ email: '', code: '' })
const pwdForm = ref({ account: '', password: '' })

// 验证码倒计时定时器（组件卸载时清理）
let codeTimer = null
onBeforeUnmount(() => { if (codeTimer) clearInterval(codeTimer) })

// 条款：默认不勾选，首次登录（自动建号）必须勾选
const agree = ref(false)
const legalOpen = ref(false)
const legalType = ref('terms')
const legalSections = computed(() => (legalType.value === 'terms' ? TERMS_SECTIONS : PRIVACY_SECTIONS))
const openLegal = (type) => {
  legalType.value = type
  // 移动端弹窗；PC 端跳独立页面（文字更多）
  if (window.innerWidth <= 720) legalOpen.value = true
  else router.push(type === 'terms' ? '/terms' : '/privacy')
}

const emailRule = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

// 发送验证码：60s 倒计时；开发模式（后端未配 SMTP）自动填充 dev_code 方便本地调试
const sendCode = async () => {
  const email = emailForm.value.email.trim()
  if (!email || !emailRule.test(email)) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }
  sending.value = true
  try {
    const res = await auth.sendCode(email)
    if (res.dev_code) {
      emailForm.value.code = res.dev_code
      ElMessage.success('开发模式：验证码已自动填入（' + res.dev_code + '）')
    } else {
      ElMessage.success('验证码已发送到 ' + email + '，10 分钟内有效')
    }
    countdown.value = 60
    if (codeTimer) clearInterval(codeTimer)
    codeTimer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) { clearInterval(codeTimer); codeTimer = null }
    }, 1000)
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '发送失败')
  } finally {
    sending.value = false
  }
}

// 邮箱登录（首次自动建号）
const doEmailLogin = () => {
  if (!agree.value) {
    ElMessage.warning('请先阅读并同意《服务条款》和《隐私协议》')
    return
  }
  const email = emailForm.value.email.trim()
  if (!email || !emailRule.test(email)) {
    ElMessage.warning('请输入正确的邮箱')
    return
  }
  if (!emailForm.value.code) {
    ElMessage.warning('请输入验证码')
    return
  }
  loading.value = true
  try {
    auth.codeLogin({ email, code: emailForm.value.code, agree: agree.value }).then((u) => {
      ElMessage.success(`欢迎来到知屿，${u.nickname || u.username}`)
      router.replace('/admin')
    }).catch((e) => {
      ElMessage.error(e?.response?.data?.error || '登录失败')
    }).finally(() => { loading.value = false })
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '登录失败')
    loading.value = false
  }
}

// 密码登录（邮箱或用户名）
const doPwdLogin = () => {
  const account = pwdForm.value.account.trim()
  if (!account) {
    ElMessage.warning('请输入邮箱或用户名')
    return
  }
  if (!pwdForm.value.password) {
    ElMessage.warning('请输入密码')
    return
  }
  loading.value = true
  try {
    auth.login(account, pwdForm.value.password).then((u) => {
      ElMessage.success(`欢迎回来，${u.nickname || u.username}`)
      router.replace('/admin')
    }).catch((e) => {
      ElMessage.error(e?.response?.data?.error || '登录失败')
    }).finally(() => { loading.value = false })
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '登录失败')
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="brand-mark">✦</span>
        <h1 class="brand-name">知屿</h1>
        <p class="brand-tagline">把散落的笔记，汇成一座知识岛</p>
      </div>

      <div class="login-tabs">
        <button class="tab-btn" :class="{ on: tab === 'email' }" @click="tab = 'email'">邮箱登录</button>
        <button class="tab-btn" :class="{ on: tab === 'pwd' }" @click="tab = 'pwd'">密码登录</button>
      </div>

      <!-- 邮箱登录（首次自动建号） -->
      <div v-if="tab === 'email'" class="login-fields">
        <div class="field">
          <label class="field-label">邮箱</label>
          <el-input v-model="emailForm.email" placeholder="用于接收验证码" clearable @keyup.enter="doEmailLogin" />
        </div>
        <div class="field">
          <label class="field-label">验证码</label>
          <div class="code-row">
            <el-input v-model="emailForm.code" placeholder="6 位验证码" clearable @keyup.enter="doEmailLogin" />
            <el-button class="code-btn" :disabled="countdown > 0 || sending" @click="sendCode">
              {{ countdown > 0 ? countdown + 's 后重发' : (sending ? '发送中…' : '获取验证码') }}
            </el-button>
          </div>
        </div>
        <label class="agree-row">
          <input v-model="agree" type="checkbox" class="agree-check" />
          <span class="agree-text">我已阅读并同意
            <a class="agree-link" @click.prevent="openLegal('terms')">《服务条款》</a> 和
            <a class="agree-link" @click.prevent="openLegal('privacy')">《隐私协议》</a>
          </span>
        </label>
        <el-button class="submit-btn" type="primary" :loading="loading" @click="doEmailLogin">登录 / 注册</el-button>
      </div>

      <!-- 密码登录 -->
      <div v-else class="login-fields">
        <div class="field">
          <label class="field-label">邮箱或用户名</label>
          <el-input v-model="pwdForm.account" placeholder="邮箱（老用户也可用原用户名）" clearable @keyup.enter="doPwdLogin" />
        </div>
        <div class="field">
          <label class="field-label">密码</label>
          <el-input v-model="pwdForm.password" type="password" placeholder="密码" show-password @keyup.enter="doPwdLogin" />
        </div>
        <el-button class="submit-btn" type="primary" :loading="loading" @click="doPwdLogin">登 录</el-button>
        <p class="login-hint">没有密码？<a class="hint-link" @click="tab = 'email'">用邮箱验证码登录</a></p>
      </div>
    </div>

    <!-- 条款 / 协议弹窗（移动端） -->
    <Teleport to="body">
      <Transition name="legal-fade">
        <div v-if="legalOpen" class="legal-mask" @click.self="legalOpen = false">
          <div class="legal-modal">
            <div class="legal-modal-head">
              <h3>{{ legalType === 'terms' ? '知屿 · 服务条款' : '知屿 · 隐私协议' }}</h3>
              <button class="legal-close" type="button" aria-label="关闭" @click="legalOpen = false">✕</button>
            </div>
            <div class="legal-modal-body">
              <section v-for="sec in legalSections" :key="sec.title" class="lm-sec">
                <h4 class="lm-sec-title">{{ sec.title }}</h4>
                <p v-for="(p, i) in sec.paras" :key="i" class="lm-para">{{ p }}</p>
              </section>
            </div>
            <div class="legal-modal-foot">
              <button class="legal-ok" type="button" @click="legalOpen = false">我知道了</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 90px 20px 40px;
  box-sizing: border-box;
  background: transparent;
}
.login-card {
  width: 400px;
  max-width: 100%;
  padding: 34px 34px 26px;
  border-radius: 22px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(16px);
}
.login-brand { text-align: center; margin-bottom: 22px; }
.brand-mark {
  display: inline-flex;
  width: 46px; height: 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow: 0 8px 22px color-mix(in srgb, var(--brand-1) 45%, transparent);
}
.brand-name { font-size: 22px; font-weight: 800; margin: 12px 0 4px; color: var(--text1); }
.brand-tagline { font-size: 13px; color: var(--text2); margin: 0; }

.login-tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  background: var(--btn-bg);
  border: 1px solid var(--border);
  margin-bottom: 20px;
}
.tab-btn {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text2);
  font-size: 14px;
  font-weight: 500;
  padding: 8px 0;
  border-radius: 999px;
  cursor: pointer;
  transition: all .2s;
}
.tab-btn.on {
  background: var(--card-bg);
  color: var(--text1);
  box-shadow: var(--shadow-1);
  font-weight: 600;
}

.login-fields { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; color: var(--text2); }

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.code-row .el-input { flex: 1; }
.code-btn {
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text2);
  background: var(--btn-bg);
}
.code-btn:hover:not(:disabled) {
  color: var(--brand-1);
  border-color: color-mix(in srgb, var(--brand-1) 45%, transparent);
}

.submit-btn {
  width: 100%;
  margin-top: 6px;
  border: none;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 600;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
}
.submit-btn:hover { opacity: .92; }

.login-hint { text-align: center; font-size: 12.5px; color: var(--text2); margin: 14px 0 0; }
.hint-link {
  color: var(--brand-1);
  font-weight: 600;
  cursor: pointer;
}
.hint-link:hover { text-decoration: underline; }

/* ── 条款勾选 ── */
.agree-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 4px 0 14px;
  cursor: pointer;
  user-select: none;
}
.agree-check {
  flex-shrink: 0;
  margin-top: 3px;
  width: 15px;
  height: 15px;
  accent-color: var(--brand-1);
  cursor: pointer;
}
.agree-text {
  font-size: 12.5px;
  color: var(--text2);
  line-height: 1.7;
}
.agree-link {
  font-weight: 700;
  color: var(--brand-1);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, var(--brand-1) 45%, transparent);
}
.agree-link:active { opacity: .8; }

/* ── 条款弹窗（移动端全屏） ── */
.legal-mask {
  position: fixed;
  inset: 0;
  z-index: 500;
  background: color-mix(in srgb, var(--bg) 78%, transparent);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.legal-modal {
  width: 92vw;
  max-width: 560px;
  height: 84vh;
  max-height: 720px;
  display: flex;
  flex-direction: column;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: var(--shadow-1);
  overflow: hidden;
}
.legal-modal-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.legal-modal-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text1);
}
.legal-close {
  border: none;
  background: var(--btn-bg);
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: var(--text2);
  font-size: 13px;
  cursor: pointer;
  transition: all .2s;
}
.legal-close:hover { color: var(--brand-1); }
.legal-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px 24px;
  -webkit-overflow-scrolling: touch;
}
.lm-sec { margin-bottom: 22px; }
.lm-sec-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text1);
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.lm-para {
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text2);
  margin: 0 0 10px;
}
.lm-para:last-child { margin-bottom: 0; }
.legal-modal-foot {
  flex-shrink: 0;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  text-align: center;
}
.legal-ok {
  width: 100%;
  padding: 11px 0;
  border: none;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
}
.legal-fade-enter-active, .legal-fade-leave-active { transition: opacity .2s ease; }
.legal-fade-enter-from, .legal-fade-leave-to { opacity: 0; }
</style>
