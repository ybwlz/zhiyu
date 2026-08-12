<template>
  <div class="settings-page">
    <h2 class="set-title">设置</h2>
    <div class="set-sub-row">
      <p class="set-sub">SETTINGS · 账户与偏好</p>
      <button class="page-back" @click="pageBack">← BACK</button>
    </div>

    <!-- 账号信息卡 -->
    <div class="set-card acct-card">
      <div class="acct-top">
        <div class="set-avatar big">
          <img v-if="account.avatar" :src="account.avatar" alt="avatar" />
          <span v-else>{{ (account.nickname || '?').slice(0, 1) }}</span>
        </div>
        <div class="acct-info">
          <div class="acct-name">{{ account.nickname || account.username }}<span class="role-badge" :class="{ admin: account.role === 'admin' }">{{ account.role === 'admin' ? '管理员' : '用户' }}</span></div>
          <div class="acct-username">ID：<b>@{{ account.username }}</b><button class="id-edit" data-tip="修改 ID（每月一次）" @click="openIdModal">✎</button></div>
          <div class="acct-email" v-if="currentEmail">📧 {{ currentEmail }}</div>
        </div>
      </div>
      <div class="acct-stats">
        <div class="stat"><b>{{ account.points ?? 0 }}</b><span>知屿币</span></div>
        <div class="stat"><b>{{ fmtSeconds(account.read_seconds) }}</b><span>阅读时长</span></div>
        <div class="stat"><b>{{ (account.created_at || '').slice(0, 10) }}</b><span>加入时间</span></div>
      </div>
    </div>

    <!-- 账号与安全 -->
    <div class="set-card">
      <h3>账号与安全</h3>
      <div class="set-row">
        <label>邮箱</label>
        <span v-if="currentEmail" class="set-static">已绑定 {{ currentEmail }}</span>
        <span v-else class="set-static dim">未绑定邮箱</span>
      </div>
      <div class="set-row">
        <label>新邮箱</label>
        <input v-model="email.value" class="set-input" placeholder="输入邮箱" />
        <button class="set-btn ghost" :disabled="sending" @click="sendEmailCode">{{ sending ? '发送中…' : '发验证码' }}</button>
      </div>
      <div class="set-row">
        <label>验证码</label>
        <input v-model="email.code" class="set-input" placeholder="邮箱收到的验证码" />
        <button class="set-btn primary" @click="saveEmail">绑定邮箱</button>
      </div>
      <div class="set-divider"></div>
      <div class="set-row"><label>当前密码</label><input v-model="pwd.old" type="password" class="set-input" placeholder="未设置过密码可留空" /></div>
      <div class="set-row"><label>新密码</label><input v-model="pwd.nw" type="password" class="set-input" placeholder="至少 6 位" /></div>
      <div class="set-row"><label>确认新密码</label><input v-model="pwd.confirm" type="password" class="set-input" /></div>
      <div class="set-actions"><button class="set-btn primary" @click="savePwd">修改密码</button></div>
    </div>

    <!-- 编辑资料 -->
    <div class="set-card">
      <h3>编辑资料</h3>
      <div class="avatar-row">
        <div class="set-avatar" :class="{ clickable: form.avatar }" @click="form.avatar && (viewAvatar = true)" data-tip="点击查看大图">
          <img v-if="form.avatar" :src="form.avatar" alt="avatar" />
          <span v-else>{{ (form.nickname || '?').slice(0, 1) }}</span>
        </div>
        <label class="set-btn ghost">更换头像<input type="file" accept="image/*" hidden @change="onAvatar" /></label>
      </div>
      <div class="set-row"><label>昵称</label><input v-model="form.nickname" class="set-input" placeholder="昵称" /></div>
      <div class="set-row"><label>简介</label><textarea v-model="form.bio" class="set-input" rows="2" placeholder="一句话介绍自己"></textarea></div>
      <div class="set-row"><label>兴趣</label><input v-model="form.interests" class="set-input" placeholder="如：408 考研、高等数学" /></div>
      <div class="set-actions"><button class="set-btn primary" @click="saveProfile">保存资料</button></div>
    </div>

    <!-- 隐私设置 -->
    <div class="set-card">
      <h3>隐私设置</h3>
      <div class="set-row">
        <label>点赞公开</label>
        <button class="set-switch" :class="{ on: privacy.likes_public }" @click="togglePriv('likes_public')"><span class="knob"></span></button>
        <span class="set-hint">关闭后别人看不到你点赞的笔记</span>
      </div>
      <div class="set-row">
        <label>收藏公开</label>
        <button class="set-switch" :class="{ on: privacy.favorites_public }" @click="togglePriv('favorites_public')"><span class="knob"></span></button>
        <span class="set-hint">关闭后别人看不到你收藏的笔记</span>
      </div>
    </div>

    <!-- 通用 -->
    <div class="set-card">
      <h3>通用</h3>
      <div class="set-actions"><button class="set-btn danger" @click="doLogout">🚪 退出登录</button></div>
    </div>

    <!-- 修改 ID 弹窗 -->
    <div v-if="idOpen" class="modal-mask" @click.self="idOpen = false">
      <div class="modal">
        <h3>修改 ID</h3>
        <p class="modal-tip">ID 是你在知屿的唯一标识（@用户名），会显示在个人主页。每月仅可修改一次。</p>
        <div class="modal-row"><label>新 ID</label><input v-model="idForm.username" class="set-input" placeholder="字母/数字/下划线，3-32 位" /></div>
        <div class="modal-actions">
          <button class="set-btn ghost" @click="idOpen = false">取消</button>
          <button class="set-btn primary" @click="saveId">确认修改</button>
        </div>
      </div>
    </div>
  </div>

  <!-- 查看大头像 -->
  <div v-if="viewAvatar && form.avatar" class="avatar-view" @click="viewAvatar = false">
    <img :src="form.avatar" alt="avatar" />
  </div>

  <!-- 头像裁剪 -->
  <AvatarCrop :visible="cropVisible" :file="cropFile" @done="onCropDone" @close="cropVisible = false" />
</template>

<script>
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'
import { ElMessage } from 'element-plus'
import AvatarCrop from '@/components/AvatarCrop.vue'

export default {
  name: 'Settings',
  components: { AvatarCrop },
  data() {
    const u = JSON.parse(localStorage.getItem('kb_user') || 'null') || {}
    return {
      auth: null,
      account: {},
      currentEmail: u.email || '',
      form: { nickname: u.nickname || '', bio: u.bio || '', interests: u.interests || '', avatar: u.avatar || '' },
      email: { value: '', code: '' },
      sending: false,
      cropVisible: false,
      cropFile: null,
      viewAvatar: false,
      idOpen: false,
      idForm: { username: '' },
      pwd: { old: '', nw: '', confirm: '' },
      privacy: { likes_public: u.likes_public !== 0, favorites_public: u.favorites_public !== 0 },
    }
  },
  created() {
    this.auth = useAuthStore()
    // 拉最新账号信息 + 隐私值
    api.get('/auth/me').then((res) => {
      const u = res.data || {}
      this.currentEmail = u.email || ''
      this.privacy.likes_public = u.likes_public !== 0
      this.privacy.favorites_public = u.favorites_public !== 0
    }).catch(() => { /* 忽略 */ })
    if (this.auth.user) {
      api.get('/users/' + this.auth.user.id).then((res) => {
        this.account = res.data || {}
        this.form.nickname = this.account.nickname || ''
        this.form.bio = this.account.bio || ''
        this.form.interests = this.account.interests || ''
        this.form.avatar = this.account.avatar || ''
      }).catch(() => { /* 忽略 */ })
    }
  },
  methods: {
    pageBack() {
      if (window.history.length > 1) this.$router.back()
      else this.$router.push('/')
    },
    fmtSeconds(s) {
      s = Number(s) || 0
      if (s < 60) return s + ' 秒'
      if (s < 3600) return Math.floor(s / 60) + ' 分'
      return (s / 3600).toFixed(1) + ' 时'
    },
    async onAvatar(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.cropFile = file
      this.cropVisible = true
      e.target.value = ''
    },
    async onCropDone(file) {
      this.cropVisible = false
      try {
        const res = await this.auth.uploadAvatar(file)
        this.form.avatar = res.avatar
        this.account.avatar = res.avatar
        ElMessage.success('头像已更换')
      } catch (err) { ElMessage.error('头像上传失败') }
    },
    async saveProfile() {
      try {
        await this.auth.updateProfile({ nickname: this.form.nickname, bio: this.form.bio, interests: this.form.interests, avatar: this.form.avatar })
        this.account.nickname = this.form.nickname
        ElMessage.success('资料已保存')
      } catch (e) { ElMessage.error('保存失败') }
    },
    async sendEmailCode() {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.email.value)) { ElMessage.warning('邮箱格式不正确'); return }
      this.sending = true
      try {
        const r = await api.post('/auth/send-code', { email: this.email.value })
        if (r.data.dev_code) { this.email.code = r.data.dev_code; ElMessage.success('开发模式：验证码已自动填入') }
        else ElMessage.success('验证码已发送到邮箱')
      } catch (e) { ElMessage.error(e.response?.data?.error || '发送失败') }
      this.sending = false
    },
    async saveEmail() {
      if (!this.email.value || !this.email.code) { ElMessage.warning('请填写邮箱和验证码'); return }
      try {
        const r = await api.post('/auth/update-email', { email: this.email.value, code: this.email.code })
        this.currentEmail = r.data.email
        if (this.auth.user) {
          this.auth.user.email = r.data.email
          localStorage.setItem('kb_user', JSON.stringify(this.auth.user))
        }
        this.email = { value: '', code: '' }
        ElMessage.success('邮箱已绑定')
      } catch (e) { ElMessage.error(e.response?.data?.error || '绑定失败') }
    },
    openIdModal() { this.idForm.username = this.account.username || ''; this.idOpen = true },
    async saveId() {
      const v = this.idForm.username.trim()
      if (!v) { ElMessage.warning('请输入新 ID'); return }
      try {
        const r = await api.post('/auth/update-username', { username: v })
        this.account.username = r.data.username
        if (this.auth.user) {
          this.auth.user.username = r.data.username
          localStorage.setItem('kb_user', JSON.stringify(this.auth.user))
        }
        this.idOpen = false
        ElMessage.success('ID 已修改，下次修改需等 30 天')
      } catch (e) { ElMessage.error(e.response?.data?.error || '修改失败') }
    },
    async togglePriv(key) {
      this.privacy[key] = !this.privacy[key]
      try {
        await this.auth.updateProfile({ [key]: this.privacy[key] ? 1 : 0 })
        ElMessage.success(key === 'likes_public' ? '点赞可见性已更新' : '收藏可见性已更新')
      } catch (e) {
        this.privacy[key] = !this.privacy[key]
        ElMessage.error('保存失败')
      }
    },
    async savePwd() {
      if (this.pwd.nw.length < 6) { ElMessage.warning('新密码至少 6 位'); return }
      if (this.pwd.nw !== this.pwd.confirm) { ElMessage.warning('两次输入的新密码不一致'); return }
      // 未设置过密码（邮箱验证码注册）可留空旧密码直接设置；已设置密码则后端校验旧密码
      try {
        await api.post('/auth/change-password', { old_password: this.pwd.old, new_password: this.pwd.nw })
        ElMessage.success('密码已修改')
        this.pwd = { old: '', nw: '', confirm: '' }
      } catch (e) { ElMessage.error(e.response?.data?.error || '修改失败') }
    },
    async doLogout() {
      await this.auth.logout()
      this.$router.push('/login')
    },
  },
}
</script>

<style scoped>
.settings-page { max-width: 640px; margin: 0 auto; padding: 84px 20px 60px; }
.set-sub-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.page-back {
  background: transparent; border: none;
  color: var(--text2); font-size: 14px; font-weight: 700; letter-spacing: 2px;
  padding: 12px 10px; line-height: 1.6;
  cursor: pointer; transition: color .15s;
}
.page-back:hover { color: var(--brand-1); }
.set-title {
  font-size: 26px; font-weight: 800; margin: 0 0 4px;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.set-sub { font-size: 11.5px; letter-spacing: 4px; color: var(--text2); text-transform: uppercase; margin: 0; }
.set-card {
  position: relative;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 16px; padding: 22px 24px; margin-bottom: 18px;
  box-shadow: var(--shadow-1);
}
.set-card h3 { margin: 0 0 16px; font-size: 15px; font-weight: 700; color: var(--text1); }
.set-divider { height: 1px; background: var(--border); margin: 16px 0; }
.acct-top { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.set-avatar {
  width: 56px; height: 56px; border-radius: 50%; overflow: hidden;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 22px; font-weight: 700; flex-shrink: 0;
}
.set-avatar.big { width: 68px; height: 68px; font-size: 28px; }
.set-avatar img { width: 100%; height: 100%; object-fit: cover; }
.set-avatar.clickable { cursor: zoom-in; }
.avatar-view { position: fixed; inset: 0; z-index: 300; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; cursor: zoom-out; }
.avatar-view img { width: 220px; height: 220px; border-radius: 50%; object-fit: cover; border: 3px solid #fff; box-shadow: 0 8px 40px rgba(0,0,0,.5); }
.acct-info { min-width: 0; }
.acct-name { font-size: 17px; font-weight: 800; color: var(--text1); display: flex; align-items: center; gap: 8px; }
.role-badge {
  font-size: 10.5px; padding: 1px 8px; border-radius: 999px;
  color: #7c3aed; background: #ede9fe; white-space: nowrap;
}
.role-badge.admin { color: #b45309; background: #fde68a; }
.acct-username { font-size: 13px; color: var(--text2); margin-top: 2px; display: flex; align-items: center; gap: 6px; }
.id-edit {
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 11px; width: 22px; height: 22px;
  border-radius: 6px; cursor: pointer; display: inline-flex;
  align-items: center; justify-content: center; transition: all .15s;
}
.id-edit:hover { color: var(--brand-1); border-color: color-mix(in srgb, var(--brand-1) 45%, transparent); }
.acct-email { font-size: 12.5px; color: var(--text2); margin-top: 4px; }
.acct-stats { display: flex; gap: 10px; }
.acct-stats .stat {
  flex: 1; text-align: center; padding: 10px 6px;
  background: var(--btn-bg); border: 1px solid var(--border);
  border-radius: 12px;
}
.acct-stats .stat b { display: block; font-size: 15px; color: var(--text1); }
.acct-stats .stat span { font-size: 11px; color: var(--text2); }
.avatar-row { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.set-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.set-row label { width: 86px; flex-shrink: 0; font-size: 13.5px; color: var(--text2); }
.set-static { font-size: 13.5px; color: var(--text1); }
.set-static.dim { color: var(--text2); }
.set-input {
  flex: 1; padding: 9px 12px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text1); font-size: 13.5px; font-family: inherit;
  resize: vertical; min-width: 0;
}
.set-input:focus { outline: none; border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.set-hint { font-size: 11.5px; color: var(--text2); }
.set-actions { display: flex; justify-content: flex-end; margin-top: 6px; }
.set-btn {
  padding: 9px 20px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--border); background: var(--btn-bg);
  color: var(--text2); font-size: 13.5px; transition: all .2s;
  white-space: nowrap;
}
.set-btn.primary {
  color: #fff; border-color: transparent;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
}
.set-btn.ghost { padding: 8px 14px; font-size: 12.5px; }
.set-btn.danger { color: #fff; border-color: transparent; background: linear-gradient(120deg, #ef4444, #f97316); }
.set-btn:hover { transform: translateY(-1px); opacity: .92; }
.set-btn:disabled { opacity: .5; cursor: not-allowed; transform: none; }
.set-switch {
  width: 44px; height: 24px; border-radius: 999px; cursor: pointer;
  border: none; background: #cbd5e1; position: relative;
  transition: background .2s; flex-shrink: 0; padding: 0;
}
.set-switch.on { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); }
.set-switch .knob {
  position: absolute; top: 3px; left: 3px; width: 18px; height: 18px;
  border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.25);
  transition: left .2s;
}
.set-switch.on .knob { left: 23px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); backdrop-filter: blur(4px); z-index: 200; display: flex; align-items: center; justify-content: center; }
.modal {
  width: 440px; max-width: 92vw; background: var(--bg-soft);
  border: 1px solid var(--border); border-radius: 16px; padding: 24px 26px;
  box-shadow: var(--shadow-1);
}
.modal h3 { margin: 0 0 8px; font-size: 16px; color: var(--text1); }
.modal-tip { font-size: 12.5px; color: var(--text2); margin: 0 0 16px; line-height: 1.7; }
.modal-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.modal-row label { width: 60px; flex-shrink: 0; font-size: 13.5px; color: var(--text2); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
@media (max-width: 560px) {
  .set-row { flex-wrap: wrap; }
  .set-row label { width: 100%; }
  .modal { max-width: 86vw; padding: 18px 16px; }
}
</style>
