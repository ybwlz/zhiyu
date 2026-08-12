import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/utils/api.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('kb_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('kb_user') || 'null'))
  const isLogin = ref(!!token.value)

  const setAuth = (t, u) => {
    token.value = t
    user.value = u
    isLogin.value = !!t
    localStorage.setItem('kb_token', t)
    localStorage.setItem('kb_user', JSON.stringify(u))
  }

  const clearAuth = () => {
    token.value = ''
    user.value = null
    isLogin.value = false
    localStorage.removeItem('kb_token')
    localStorage.removeItem('kb_user')
  }

  const login = async (account, password) => {
    const res = await api.post('/auth/login', { email: account, password })
    setAuth(res.data.token, res.data.user)
    return res.data.user
  }

  // 验证码登录即注册：首次使用自动建号（须同意条款）
  const codeLogin = async ({ email, code, agree }) => {
    const res = await api.post('/auth/code-login', { email, code, agree })
    setAuth(res.data.token, res.data.user)
    return res.data.user
  }

  const sendCode = async (email) => {
    const res = await api.post('/auth/send-code', { email })
    return res.data
  }

  const register = async ({ email, code, password, nickname }) => {
    const res = await api.post('/auth/register', { email, code, password, nickname })
    return res.data
  }

  const logout = async () => {
    try { await api.post('/auth/logout') } catch (e) { /* 忽略 */ }
    clearAuth()
  }

  const updateProfile = async (payload) => {
    const res = await api.put('/user/profile', payload)
    if (user.value) {
      for (const k of ['nickname', 'bio', 'interests', 'avatar', 'likes_public', 'favorites_public']) {
        if (payload[k] !== undefined) user.value[k] = payload[k]
      }
      localStorage.setItem('kb_user', JSON.stringify(user.value))
    }
    return res.data
  }

  const uploadAvatar = async (file) => {
    const fd = new FormData()
    fd.append('avatar', file)
    const res = await api.post('/user/avatar', fd)
    if (user.value) {
      user.value.avatar = res.data.avatar
      localStorage.setItem('kb_user', JSON.stringify(user.value))
    }
    return res.data
  }

  // 启动时校验 token 是否仍有效
  const fetchMe = async () => {
    if (!token.value) return null
    try {
      const res = await api.get('/auth/me')
      user.value = res.data
      localStorage.setItem('kb_user', JSON.stringify(res.data))
      return res.data
    } catch (e) {
      clearAuth()
      return null
    }
  }

  return { token, user, isLogin, login, codeLogin, register, sendCode, logout, fetchMe, updateProfile, uploadAvatar, setAuth, clearAuth }
})