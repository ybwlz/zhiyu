<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const tab = ref('login') // login | register
const formRef = ref()
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)

const loginForm = ref({ email: '', password: '' })
const regForm = ref({ email: '', code: '', password: '', password2: '', nickname: '' })

const emailRule = { pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/, message: '邮箱格式不正确', trigger: 'blur' }
// 登录账号：邮箱或老用户名均可
const accountRule = {
  validator: (rule, value, cb) => {
    if (!value) return cb(new Error('请输入邮箱或用户名'))
    if (emailRule.pattern.test(value) || /^[A-Za-z0-9_\u4e00-\u9fa5]{2,20}$/.test(value)) cb()
    else cb(new Error('邮箱格式不正确或用户名无效'))
  },
  trigger: 'blur',
}

const loginRules = {
  email: [
    { required: true, message: '请输入邮箱或用户名', trigger: 'blur' },
    accountRule,
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
}
const regRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    emailRule,
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '6 位数字验证码', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  password2: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, cb) => {
        if (value !== regForm.value.password) cb(new Error('两次密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

// 发送验证码：60s 倒计时；开发模式（后端未配 SMTP）自动填充 dev_code 方便本地调试
const sendCode = async () => {
  const email = tab.value === 'register' ? regForm.value.email : loginForm.value.email
  if (!email || !emailRule.pattern.test(email)) {
    ElMessage.warning('请先输入正确的邮箱')
    return
  }
  sending.value = true
  try {
    const res = await auth.sendCode(email)
    if (res.dev_code) {
      regForm.value.code = res.dev_code
      ElMessage.success('开发模式：验证码已自动填入（' + res.dev_code + '）')
    } else {
      ElMessage.success('验证码已发送到 ' + email + '，10 分钟内有效')
    }
    countdown.value = 60
    const t = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(t)
    }, 1000)
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '发送失败')
  } finally {
    sending.value = false
  }
}

const doLogin = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const u = await auth.login(loginForm.value.email, loginForm.value.password)
      ElMessage.success(`欢迎回来，${u.nickname || u.username}`)
      router.replace('/admin')
    } catch (e) {
      ElMessage.error(e?.response?.data?.error || '登录失败')
    } finally {
      loading.value = false
    }
  })
}

const doRegister = () => {
  formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await auth.register({
        email: regForm.value.email,
        code: regForm.value.code,
        password: regForm.value.password,
        nickname: regForm.value.nickname,
      })
      ElMessage.success(res.role === 'admin' ? '注册成功，你已成为知识库管理员' : '注册成功，请登录')
      tab.value = 'login'
      loginForm.value.email = regForm.value.email
      regForm.value = { email: '', code: '', password: '', password2: '', nickname: '' }
    } catch (e) {
      ElMessage.error(e?.response?.data?.error || '注册失败')
    } finally {
      loading.value = false
    }
  })
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
        <button class="tab-btn" :class="{ on: tab === 'login' }" @click="tab = 'login'">登录</button>
        <button class="tab-btn" :class="{ on: tab === 'register' }" @click="tab = 'register'">注册</button>
      </div>

      <el-form ref="formRef" :model="tab === 'login' ? loginForm : regForm" :rules="tab === 'login' ? loginRules : regRules" label-position="top" size="large">
        <!-- 登录 -->
        <template v-if="tab === 'login'">
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="loginForm.email" placeholder="邮箱（老用户也可用原用户名）" clearable @keyup.enter="doLogin" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="loginForm.password" type="password" placeholder="密码" show-password @keyup.enter="doLogin" />
          </el-form-item>
          <el-button class="submit-btn" type="primary" :loading="loading" @click="doLogin">登 录</el-button>
        </template>

        <!-- 注册 -->
        <template v-else>
          <el-form-item label="昵称（可选）" prop="nickname">
            <el-input v-model="regForm.nickname" placeholder="大家怎么称呼你" clearable />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="regForm.email" placeholder="用于登录与接收验证码" clearable />
          </el-form-item>
          <el-form-item label="验证码" prop="code">
            <div class="code-row">
              <el-input v-model="regForm.code" placeholder="6 位验证码" clearable />
              <el-button class="code-btn" :disabled="countdown > 0 || sending" @click="sendCode">
                {{ countdown > 0 ? countdown + 's 后重发' : (sending ? '发送中…' : '发送验证码') }}
              </el-button>
            </div>
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="regForm.password" type="password" placeholder="至少 6 位" show-password />
          </el-form-item>
          <el-form-item label="确认密码" prop="password2">
            <el-input v-model="regForm.password2" type="password" placeholder="再次输入密码" show-password @keyup.enter="doRegister" />
          </el-form-item>
          <el-button class="submit-btn" type="primary" :loading="loading" @click="doRegister">注 册</el-button>
        </template>
      </el-form>

    </div>
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
  /* 背景透明：透出全局主题背景 */
  background: transparent;
}
.login-card {
  width: 380px;
  max-width: 100%;
  padding: 34px 34px 26px;
  border-radius: 22px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(16px);
}
.login-brand { text-align: center; margin-bottom: 20px; }
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

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.code-row .el-input {
  flex: 1;
}
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

.login-tip { text-align: center; font-size: 12px; color: var(--text2); margin: 14px 0 0; }

:deep(.el-form-item__label) { color: var(--text2); font-size: 13px; }
</style>