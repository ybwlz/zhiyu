<template>
  <div class="admin-panel">
    <aside class="ap-side">
      <div class="ap-brand">⚙️ 知屿管理后台</div>
      <nav class="ap-nav">
        <button v-for="m in menus" :key="m.id" class="ap-nav-item" :class="{ on: mod === m.id }" @click="mod = m.id">
          {{ m.icon }} {{ m.label }}
        </button>
      </nav>
      <div class="ap-foot">
        <button class="ap-back" @click="goBack">← 返回网站</button>
      </div>
    </aside>

    <main class="ap-main">
      <!-- ── 仪表盘 ── -->
      <section v-if="mod === 'dash'">
        <h2 class="ap-title">📊 仪表盘</h2>
        <div class="stat-grid">
          <div class="stat-card"><b>{{ stats.users ?? '-' }}</b><span>用户总数</span></div>
          <div class="stat-card"><b>{{ stats.docs ?? '-' }}</b><span>笔记总数</span></div>
          <div class="stat-card"><b>{{ stats.docs_public ?? '-' }}</b><span>公开笔记</span></div>
          <div class="stat-card"><b>{{ stats.ai_usage ?? '-' }}</b><span>AI 使用次数</span></div>
          <div class="stat-card warn" @click="mod = 'audits'"><b>{{ stats.audit_pending ?? '-' }}</b><span>待审笔记</span></div>
        </div>
        <div class="trend-card">
          <h3>近 7 天增长</h3>
          <table class="ap-table">
            <thead><tr><th>日期</th><th>新增用户</th><th>新增笔记</th></tr></thead>
            <tbody>
              <tr v-for="d in trendDays" :key="d">
                <td>{{ d }}</td>
                <td>{{ dayCount(stats.users_7, d) }}</td>
                <td>{{ dayCount(stats.docs_7, d) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ── 用户管理 ── -->
      <section v-else-if="mod === 'users'">
        <h2 class="ap-title">👥 用户管理</h2>
        <div class="toolbar">
          <input v-model="uQuery" class="ap-input" placeholder="搜索用户名/昵称/邮箱" @keyup.enter="loadUsers(1)" />
          <button class="ap-btn" @click="loadUsers(1)">搜索</button>
        </div>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>用户名</th><th>昵称</th><th>角色</th><th>积分</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="u in userList" :key="u.id">
              <td>{{ u.id }}</td>
              <td>{{ u.username }}</td>
              <td>{{ u.nickname || '-' }}</td>
              <td><span class="role-tag" :class="u.role">{{ roleLabel(u.role) }}</span></td>
              <td>{{ u.points }}</td>
              <td>{{ u.banned ? '❌ 已封禁' : '✅ 正常' }}</td>
              <td>{{ u.created_at }}</td>
              <td class="ops">
                <button v-if="!u.banned && u.role !== 'admin'" class="ap-btn sm danger" @click="banUser(u)">封禁</button>
                <button v-if="u.banned" class="ap-btn sm" @click="unbanUser(u)">解封</button>
                <button v-if="u.role !== 'admin'" class="ap-btn sm danger" @click="delUser(u)">删除</button>
                <button v-if="u.role !== 'admin'" class="ap-btn sm" @click="openManager(u)">设管理员</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="userTotal > 20">
          <button class="ap-btn sm" :disabled="uPage <= 1" @click="loadUsers(uPage - 1)">上一页</button>
          <span>{{ uPage }} / {{ Math.ceil(userTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="uPage >= Math.ceil(userTotal / 20)" @click="loadUsers(uPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 笔记管理 ── -->
      <section v-else-if="mod === 'docs'">
        <h2 class="ap-title">📄 笔记管理</h2>
        <div class="toolbar">
          <input v-model="dQuery" class="ap-input" placeholder="搜索标题/作者" @keyup.enter="loadDocs(1)" />
          <div class="filter-seg">
            <button :class="{ on: dVis === '' }" @click="dVis = ''; loadDocs(1)">全部</button>
            <button :class="{ on: dVis === 'public' }" @click="dVis = 'public'; loadDocs(1)">公开</button>
            <button :class="{ on: dVis === 'private' }" @click="dVis = 'private'; loadDocs(1)">私密</button>
          </div>
          <div class="filter-seg">
            <button :class="{ on: dAudit === '' }" @click="dAudit = ''; loadDocs(1)">全部审核</button>
            <button :class="{ on: dAudit === 'pending' }" @click="dAudit = 'pending'; loadDocs(1)">待审</button>
            <button :class="{ on: dAudit === 'approved' }" @click="dAudit = 'approved'; loadDocs(1)">通过</button>
            <button :class="{ on: dAudit === 'blocked' }" @click="dAudit = 'blocked'; loadDocs(1)">拒绝</button>
          </div>
          <button class="ap-btn" @click="loadDocs(1)">搜索</button>
        </div>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>标题</th><th>作者</th><th>可见性</th><th>审核</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="d in docList" :key="d.id">
              <td>{{ d.id }}</td>
              <td class="ellipsis">{{ d.title }}</td>
              <td>{{ d.nickname || d.username || '系统' }}</td>
              <td>{{ d.visibility === 'public' ? '公开' : '私密' }}</td>
              <td><span class="audit-tag" :class="d.audit_status">{{ auditLabel(d.audit_status) }}</span></td>
              <td>{{ d.updated_at }}</td>
              <td class="ops">
                <button class="ap-btn sm" @click="previewDoc(d)">预览</button>
                <button v-if="d.visibility === 'public'" class="ap-btn sm" @click="unpublishDoc(d)">下架</button>
                <button class="ap-btn sm danger" @click="delDoc(d)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="docTotal > 20">
          <button class="ap-btn sm" :disabled="dPage <= 1" @click="loadDocs(dPage - 1)">上一页</button>
          <span>{{ dPage }} / {{ Math.ceil(docTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="dPage >= Math.ceil(docTotal / 20)" @click="loadDocs(dPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 审核队列 ── -->
      <section v-else-if="mod === 'audits'">
        <h2 class="ap-title">🔍 审核队列 <span class="ap-sub">（AI 不可用时先上架的笔记，人工复核）</span></h2>
        <div v-if="!auditList.length" class="empty-tip">✅ 暂无待审笔记</div>
        <div v-for="a in auditList" :key="a.id" class="audit-card">
          <div class="audit-head">
            <b>{{ a.title }}</b>
            <span class="ap-meta">{{ a.nickname || a.username || '系统' }} · {{ a.updated_at }}</span>
          </div>
          <p class="audit-content">{{ a.content }}</p>
          <div class="audit-ops">
            <button class="ap-btn sm" @click="approveAudit(a)">✅ 通过</button>
            <button class="ap-btn sm danger" @click="rejectAudit(a)">⛔ 拒绝</button>
            <button class="ap-btn sm ghost" @click="previewDoc(a)">预览全文</button>
          </div>
        </div>
        <div class="page-bar" v-if="auditTotal > 20">
          <button class="ap-btn sm" :disabled="aPage <= 1" @click="loadAudits(aPage - 1)">上一页</button>
          <span>{{ aPage }} / {{ Math.ceil(auditTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="aPage >= Math.ceil(auditTotal / 20)" @click="loadAudits(aPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 评论管理 ── -->
      <section v-else-if="mod === 'comments'">
        <h2 class="ap-title">💬 评论管理</h2>
        <div class="toolbar">
          <input v-model="cQuery" class="ap-input" placeholder="搜索评论内容" @keyup.enter="loadComments(1)" />
          <button class="ap-btn" @click="loadComments(1)">搜索</button>
        </div>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>评论内容</th><th>用户</th><th>所属笔记</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="c in commentList" :key="c.id">
              <td>{{ c.id }}</td>
              <td class="ellipsis">{{ c.content }}</td>
              <td>{{ c.nickname || c.username || '—' }}</td>
              <td class="ellipsis">{{ c.doc_title || '—' }}</td>
              <td>{{ c.created_at }}</td>
              <td class="ops"><button class="ap-btn sm danger" @click="delComment(c)">删除</button></td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="commentTotal > 20">
          <button class="ap-btn sm" :disabled="cPage <= 1" @click="loadComments(cPage - 1)">上一页</button>
          <span>{{ cPage }} / {{ Math.ceil(commentTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="cPage >= Math.ceil(commentTotal / 20)" @click="loadComments(cPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 知屿币 ── -->
      <section v-else-if="mod === 'coins'">
        <h2 class="ap-title">🪙 知屿币</h2>
        <div class="form-card">
          <h3>给用户发放知屿币</h3>
          <div class="form-row">
            <input v-model="coinUid" class="ap-input" placeholder="用户 ID 或用户名" />
            <input v-model.number="coinAmount" class="ap-input" type="number" placeholder="数量（≥1）" />
            <input v-model="coinNote" class="ap-input" placeholder="备注（可选）" />
            <button class="ap-btn" @click="grantCoins">发放</button>
          </div>
        </div>
        <h3 class="ap-sec">发放记录</h3>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>用户</th><th>数量</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="l in coinLogs" :key="l.id">
              <td>{{ l.id }}</td>
              <td>{{ l.nickname || l.username || l.user_id }}</td>
              <td style="color:#22c55e">+{{ l.delta }}</td>
              <td>{{ l.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="coinTotal > 20">
          <button class="ap-btn sm" :disabled="coinPage <= 1" @click="loadCoins(coinPage - 1)">上一页</button>
          <span>{{ coinPage }} / {{ Math.ceil(coinTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="coinPage >= Math.ceil(coinTotal / 20)" @click="loadCoins(coinPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 兑换码 ── -->
      <section v-else-if="mod === 'codes'">
        <h2 class="ap-title">🎫 兑换码</h2>
        <div class="form-card">
          <h3>批量生成兑换码</h3>
          <div class="form-row">
            <input v-model.number="codeAmount" class="ap-input" type="number" placeholder="面值（知屿币）" />
            <input v-model.number="codeCount" class="ap-input" type="number" placeholder="数量（1-200）" />
            <input v-model.number="codeDays" class="ap-input" type="number" placeholder="有效期天数（0=永久）" />
            <button class="ap-btn" @click="genCodes">生成</button>
          </div>
          <div v-if="newCodes.length" class="code-box">
            <div class="code-box-head">新生成的兑换码（用户可在商城页兑换）</div>
            <div class="code-list">
              <span v-for="c in newCodes" :key="c" class="code-chip" @click="copyCode(c)">{{ c }}</span>
            </div>
            <button class="ap-btn sm ghost" @click="copyAllCodes">复制全部</button>
          </div>
        </div>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>兑换码</th><th>面值</th><th>状态</th><th>使用者</th><th>生成时间</th></tr></thead>
          <tbody>
            <tr v-for="cd in codeList" :key="cd.id">
              <td>{{ cd.id }}</td>
              <td class="mono">{{ cd.code }}</td>
              <td>{{ cd.amount }}</td>
              <td>{{ cd.used_by ? '✅ 已使用' : '待使用' }}</td>
              <td>{{ cd.used_username || '—' }}</td>
              <td>{{ cd.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="codeTotal > 20">
          <button class="ap-btn sm" :disabled="codePage <= 1" @click="loadCodes(codePage - 1)">上一页</button>
          <span>{{ codePage }} / {{ Math.ceil(codeTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="codePage >= Math.ceil(codeTotal / 20)" @click="loadCodes(codePage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 通知 ── -->
      <section v-else-if="mod === 'notices'">
        <h2 class="ap-title">📢 发送通知</h2>
        <div class="form-card">
          <div class="form-row">
            <select v-model="noticeTarget" class="ap-input sel">
              <option value="all">全站用户</option>
              <option value="one">指定用户</option>
            </select>
            <input v-if="noticeTarget === 'one'" v-model="noticeUid" class="ap-input" placeholder="用户 ID" />
          </div>
          <div class="form-row">
            <input v-model="noticeTitle" class="ap-input" placeholder="标题（默认：系统通知）" />
          </div>
          <div class="form-row">
            <textarea v-model="noticeContent" class="ap-input ta" placeholder="通知内容"></textarea>
          </div>
          <button class="ap-btn" @click="sendNotice">发送通知</button>
        </div>
      </section>

      <!-- ── 管理员管理 ── -->
      <section v-else-if="mod === 'admins'">
        <h2 class="ap-title">🛡️ 管理员管理 <span class="ap-sub">（在「用户管理」里设置辅助管理员，这里调整权限/取消）</span></h2>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>权限点</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="m in mgrList" :key="m.id">
              <td>{{ m.id }}</td>
              <td>{{ m.nickname || m.username }}</td>
              <td><span class="role-tag" :class="m.role">{{ roleLabel(m.role) }}</span></td>
              <td class="perm-cell">
                <template v-if="m.role === 'admin'"><span class="ap-meta">全部权限</span></template>
                <template v-else>
                  <label v-for="p in permKeys" :key="p" class="perm-item">
                    <input type="checkbox" :checked="m.perms?.includes(p)" @change="togglePerm(m, p)" />
                    {{ permLabels[p] }}
                  </label>
                </template>
              </td>
              <td class="ops">
                <button v-if="m.role === 'moderator'" class="ap-btn sm ghost" @click="setManager('user', m.id)">取消</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- ── AI 日志 ── -->
      <section v-else-if="mod === 'ailogs'">
        <h2 class="ap-title">🤖 AI 使用日志</h2>
        <table class="ap-table">
          <thead><tr><th>ID</th><th>用户</th><th>页面</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="l in aiLogs" :key="l.id">
              <td>{{ l.id }}</td>
              <td>{{ l.nickname || l.username || l.user_id }}</td>
              <td>{{ l.page || '—' }}</td>
              <td>{{ l.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <div class="page-bar" v-if="aiLogTotal > 20">
          <button class="ap-btn sm" :disabled="aiPage <= 1" @click="loadAiLogs(aiPage - 1)">上一页</button>
          <span>{{ aiPage }} / {{ Math.ceil(aiLogTotal / 20) }}</span>
          <button class="ap-btn sm" :disabled="aiPage >= Math.ceil(aiLogTotal / 20)" @click="loadAiLogs(aiPage + 1)">下一页</button>
        </div>
      </section>

      <!-- ── 占位模块 ── -->
      <section v-else>
        <h2 class="ap-title">{{ currentMenu?.icon }} {{ currentMenu?.label }}</h2>
        <div class="empty-tip">该模块开发中，即将上线。</div>
      </section>

      <!-- 预览弹窗 -->
      <div v-if="previewDocData" class="modal-mask" @click.self="previewDocData = null">
        <div class="modal">
          <div class="modal-head">
            <b>{{ previewDocData.title }}</b>
            <button class="modal-close" @click="previewDocData = null">✕</button>
          </div>
          <div class="modal-body">
            <pre class="preview-raw">{{ previewDocData.content }}</pre>
          </div>
          <div class="modal-foot">
            <button class="ap-btn sm ghost" @click="previewDocData = null">关闭</button>
          </div>
        </div>
      </div>

      <!-- 自研确认弹窗 -->
      <div v-if="confirmState" class="modal-mask" @click.self="confirmCancel">
        <div class="modal small">
          <div class="modal-head"><b>{{ confirmState.title }}</b><button class="modal-close" @click="confirmCancel">✕</button></div>
          <div class="modal-body">{{ confirmState.msg }}</div>
          <div class="modal-foot">
            <button class="ap-btn ghost" @click="confirmCancel">取消</button>
            <button class="ap-btn" :class="{ danger: confirmState.danger }" @click="confirmOk">确定</button>
          </div>
        </div>
      </div>

      <!-- 自研输入弹窗 -->
      <div v-if="promptState" class="modal-mask" @click.self="promptCancel">
        <div class="modal small">
          <div class="modal-head"><b>{{ promptState.title }}</b><button class="modal-close" @click="promptCancel">✕</button></div>
          <div class="modal-body">
            <input v-model="promptState.value" class="ap-input w100" :placeholder="promptState.placeholder" @keyup.enter="promptOk" />
          </div>
          <div class="modal-foot">
            <button class="ap-btn ghost" @click="promptCancel">取消</button>
            <button class="ap-btn" @click="promptOk">确定</button>
          </div>
        </div>
      </div>

      <!-- 主题 toast -->
      <div class="ap-toasts">
        <TransitionGroup name="toast">
          <div v-for="t in toasts" :key="t.id" class="ap-toast" :class="t.type">{{ t.msg }}</div>
        </TransitionGroup>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const menus = [
  { id: 'dash', icon: '📊', label: '仪表盘' },
  { id: 'users', icon: '👥', label: '用户管理' },
  { id: 'docs', icon: '📄', label: '笔记管理' },
  { id: 'audits', icon: '🔍', label: '审核队列' },
  { id: 'comments', icon: '💬', label: '评论管理' },
  { id: 'coins', icon: '🪙', label: '知屿币' },
  { id: 'codes', icon: '🎫', label: '兑换码' },
  { id: 'notices', icon: '📢', label: '通知' },
  { id: 'admins', icon: '🛡️', label: '管理员' },
  { id: 'ailogs', icon: '🤖', label: 'AI 日志' },
]
const mod = ref('dash')
const currentMenu = computed(() => menus.find(m => m.id === mod.value))
// 切到管理员模块时刷新列表（在用户管理里设置后能看到）
watch(mod, (v) => {
  if (v === 'admins') loadManagers()
  if (v === 'comments') loadComments(1)
  if (v === 'coins') loadCoins(1)
  if (v === 'codes') loadCodes(1)
  if (v === 'ailogs') loadAiLogs(1)
})

// ── 自研弹窗/提示（替换默认 alert/confirm/prompt） ──
const toasts = ref([])
let toastId = 0
const toast = (msg, type = 'ok') => {
  const id = ++toastId
  toasts.value.push({ id, msg, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 2600)
}
const confirmState = ref(null)
const confirmResolve = ref(null)
const askConfirm = ({ title, msg, danger = false }) => new Promise(res => {
  confirmResolve.value = res
  confirmState.value = { title, msg, danger }
})
const confirmOk = () => { const r = confirmResolve.value; confirmState.value = null; confirmResolve.value = null; r?.(true) }
const confirmCancel = () => { const r = confirmResolve.value; confirmState.value = null; confirmResolve.value = null; r?.(false) }
const promptState = ref(null)
const promptResolve = ref(null)
const askPrompt = ({ title, placeholder = '' }) => new Promise(res => {
  promptResolve.value = res
  promptState.value = { title, placeholder, value: '' }
})
const promptOk = () => { const r = promptResolve.value; const v = promptState.value?.value ?? ''; promptState.value = null; promptResolve.value = null; r?.(v) }
const promptCancel = () => { const r = promptResolve.value; promptState.value = null; promptResolve.value = null; r?.(null) }

const goBack = () => router.push('/')

// ── 仪表盘 ──
const stats = ref({})
const trendDays = computed(() => {
  const days = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
})
const dayCount = (arr, d) => (arr || []).find(x => String(x.date).startsWith(d))?.count || 0

// ── 用户 ──
const uQuery = ref('')
const userList = ref([])
const userTotal = ref(0)
const uPage = ref(1)

// ── 笔记 ──
const dQuery = ref('')
const dVis = ref('public')
const dAudit = ref('')
const docList = ref([])
const docTotal = ref(0)
const dPage = ref(1)
const previewDocData = ref(null)

// ── 审核 ──
const auditList = ref([])
const auditTotal = ref(0)
const aPage = ref(1)

const roleLabel = r => ({ admin: '站长', moderator: '管理员', user: '用户' }[r] || r)
const auditLabel = s => ({ approved: '✅ 通过', pending: '⏳ 待审', blocked: '⛔ 拒绝' }[s] || '—')

async function loadStats() {
  try { stats.value = (await api.get('/admin/stats')).data } catch (e) { /* 权限不足 */ }
}
async function loadUsers(page) {
  uPage.value = page || 1
  try {
    const r = (await api.get('/admin/users', { params: { q: uQuery.value, page: uPage.value, size: 20 } })).data
    userList.value = r.items || []
    userTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}
async function loadDocs(page) {
  dPage.value = page || 1
  try {
    const r = (await api.get('/admin/docs', { params: { q: dQuery.value, vis: dVis.value, audit: dAudit.value, page: dPage.value, size: 20 } })).data
    docList.value = r.items || []
    docTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}
async function loadAudits(page) {
  aPage.value = page || 1
  try {
    const r = (await api.get('/admin/audits', { params: { page: aPage.value, size: 20 } })).data
    auditList.value = r.items || []
    auditTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}

async function previewDoc(d) {
  try {
    const r = (await api.get('/docs/' + d.id)).data
    previewDocData.value = { ...d, ...r }
  } catch (e) {
    previewDocData.value = d
  }
}

async function banUser(u) { if (!(await askConfirm({ title: '封禁用户', msg: `确认封禁 ${u.username}？封禁后其公开笔记会隐藏。`, danger: true }))) return; try { await api.post(`/admin/users/${u.id}/ban`); toast('已封禁 ' + u.username); loadUsers(uPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }
async function unbanUser(u) { try { await api.post(`/admin/users/${u.id}/unban`); toast('已解封 ' + u.username); loadUsers(uPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }
async function delUser(u) { if (!(await askConfirm({ title: '删除用户', msg: `确认删除用户 ${u.username}？其全部笔记/评论/数据将被清除，不可恢复！`, danger: true }))) return; try { await api.delete(`/admin/users/${u.id}`); toast('已删除用户'); loadUsers(uPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }
async function openManager(u) {
  // 用户列表一键设为辅助管理员（默认：审核/笔记/评论），精细权限在「管理员」模块调整
  if (!(await askConfirm({ title: '设为辅助管理员', msg: `确认将 ${u.username} 设为辅助管理员？（默认权限：审核/笔记/评论）` }))) return
  try {
    await api.post('/admin/managers', { user_id: u.id, role: 'moderator', perms: ['audit', 'notes', 'comments'] })
    toast('已设为辅助管理员，可在「管理员」模块调整权限')
    loadUsers(uPage.value)
  } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}

async function unpublishDoc(d) { if (!(await askConfirm({ title: '下架笔记', msg: `确认下架「${d.title}」？（转为私密）`, danger: true }))) return; try { await api.post(`/admin/docs/${d.id}/unpublish`); toast('已下架'); loadDocs(dPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }
async function delDoc(d) { if (!(await askConfirm({ title: '删除笔记', msg: `确认删除笔记「${d.title}」？不可恢复！`, danger: true }))) return; try { await api.delete(`/admin/docs/${d.id}`); toast('已删除笔记'); loadDocs(dPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }

async function approveAudit(a) { try { await api.post(`/admin/audits/${a.id}/approve`); toast('已通过审核'); loadAudits(aPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') } }
async function rejectAudit(a) {
  const reason = await askPrompt({ title: '拒绝原因', placeholder: '违规内容（将记录并通知）' })
  if (reason === null || !reason.trim()) return
  try { await api.post(`/admin/audits/${a.id}/reject`, { reason }); toast('已拒绝并下架'); loadAudits(aPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}

// ── 评论管理 ──
const cQuery = ref('')
const commentList = ref([])
const commentTotal = ref(0)
const cPage = ref(1)
async function loadComments(page) {
  cPage.value = page || 1
  try {
    const r = (await api.get('/admin/comments', { params: { q: cQuery.value, page: cPage.value, size: 20 } })).data
    commentList.value = r.items || []
    commentTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}
async function delComment(c) {
  if (!(await askConfirm({ title: '删除评论', msg: '确认删除该评论？', danger: true }))) return
  try { await api.delete(`/admin/comments/${c.id}`); toast('已删除评论'); loadComments(cPage.value) } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}

// ── 知屿币 ──
const coinUid = ref('')
const coinAmount = ref(100)
const coinNote = ref('')
const coinLogs = ref([])
const coinTotal = ref(0)
const coinPage = ref(1)
async function grantCoins() {
  if (!coinUid.value || !coinAmount.value || coinAmount.value <= 0) { toast('请填写用户和数量', 'err'); return }
  try {
    await api.post('/admin/coins/grant', { user_id: Number(coinUid.value) || coinUid.value, amount: coinAmount.value, note: coinNote.value })
    toast(`已给用户发放 ${coinAmount.value} 知屿币`)
    coinNote.value = ''
    loadCoins(1)
  } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}
async function loadCoins(page) {
  coinPage.value = page || 1
  try {
    const r = (await api.get('/admin/coins/logs', { params: { page: coinPage.value, size: 20 } })).data
    coinLogs.value = r.items || []
    coinTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}

// ── 兑换码 ──
const codeAmount = ref(100)
const codeCount = ref(10)
const codeDays = ref(0)
const newCodes = ref([])
const codeList = ref([])
const codeTotal = ref(0)
const codePage = ref(1)
async function genCodes() {
  if (!codeAmount.value || codeAmount.value <= 0) { toast('请填写面值', 'err'); return }
  try {
    const r = (await api.post('/admin/codes/generate', { amount: codeAmount.value, count: codeCount.value, days: codeDays.value })).data
    newCodes.value = r.codes || []
    toast(`已生成 ${newCodes.value.length} 个兑换码`)
    loadCodes(1)
  } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}
async function loadCodes(page) {
  codePage.value = page || 1
  try {
    const r = (await api.get('/admin/codes', { params: { page: codePage.value, size: 20 } })).data
    codeList.value = r.items || []
    codeTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}
function copyCode(c) { navigator.clipboard?.writeText(c).then(() => toast('已复制：' + c)) }
function copyAllCodes() {
  const all = newCodes.value.join('\n')
  navigator.clipboard?.writeText(all).then(() => toast(`已复制全部 ${newCodes.value.length} 个兑换码`))
}

// ── 通知 ──
const noticeTarget = ref('all')
const noticeUid = ref('')
const noticeTitle = ref('')
const noticeContent = ref('')
async function sendNotice() {
  if (!noticeContent.value.trim()) { toast('通知内容不能为空', 'err'); return }
  try {
    const target = noticeTarget.value === 'all' ? 'all' : [Number(noticeUid.value)]
    const r = (await api.post('/admin/notices', { target, title: noticeTitle.value, content: noticeContent.value })).data
    toast(`已发送给 ${r.sent} 位用户`)
    noticeContent.value = ''
  } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}

// ── 管理员管理 ──
const permKeys = ['audit', 'notes', 'comments', 'coins', 'codes', 'users', 'notices', 'admins']
const permLabels = { audit: '审核', notes: '笔记', comments: '评论', coins: '知屿币', codes: '兑换码', users: '用户', notices: '通知', admins: '管理员' }
const mgrUid = ref('')
const mgrList = ref([])
async function loadManagers() {
  try { mgrList.value = ((await api.get('/admin/managers')).data?.items) || [] } catch (e) { /* 权限不足 */ }
}
async function setManager(role, uid) {
  const target = uid || Number(mgrUid.value)
  if (!target) { toast('请填写用户 ID 或用户名', 'err'); return }
  const perms = role === 'moderator' ? ['audit', 'notes', 'comments'] : []
  try {
    await api.post('/admin/managers', { user_id: target, role, perms })
    toast(role === 'moderator' ? '已设为辅助管理员（默认：审核/笔记/评论）' : '已取消管理员')
    loadManagers()
  } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}
async function togglePerm(m, p) {
  const perms = new Set(m.perms || [])
  perms.has(p) ? perms.delete(p) : perms.add(p)
  try { await api.post('/admin/managers', { user_id: m.id, role: 'moderator', perms: [...perms] }); toast('权限已更新'); loadManagers() } catch (e) { toast(e.response?.data?.error || '操作失败', 'err') }
}

// ── AI 日志 ──
const aiLogs = ref([])
const aiLogTotal = ref(0)
const aiPage = ref(1)
async function loadAiLogs(page) {
  aiPage.value = page || 1
  try {
    const r = (await api.get('/admin/ai-logs', { params: { page: aiPage.value, size: 20 } })).data
    aiLogs.value = r.items || []
    aiLogTotal.value = r.total || 0
  } catch (e) { /* 权限不足 */ }
}

onMounted(async () => {
  // 非管理员/辅助管理员禁止进入
  if (!auth.isLogin || !['admin', 'moderator'].includes(auth.user?.role)) {
    toast('无权限访问管理后台', 'err')
    router.replace('/')
    return
  }
  // 支持 /admin-panel?mod=xxx 直达模块
  const qm = route.query.mod
  if (qm && menus.some(m => m.id === qm)) mod.value = qm
  loadStats()
  loadUsers(1)
  loadDocs(1)
  loadAudits(1)
  loadComments(1)
  loadCoins(1)
  loadCodes(1)
  loadManagers()
  loadAiLogs(1)
})
</script>

<style scoped>
.admin-panel { display: flex; min-height: calc(100vh - 60px); max-width: 1680px; margin: 0 auto; padding: 20px 24px 40px; gap: 20px; }
.ap-side {
  width: 220px; flex-shrink: 0;
  position: fixed; left: 0; top: 60px; bottom: 0;
  overflow-y: auto;
  background: color-mix(in srgb, var(--btn-bg) 55%, transparent);
  padding: 14px 10px;
  z-index: 50;
  border-radius: 0;
  border: none;
  backdrop-filter: blur(6px);
}
.ap-brand { font-weight: 700; font-size: 14px; padding: 6px 10px 14px; color: var(--text1); border-bottom: 1px solid var(--border); margin-bottom: 8px; }
.ap-nav { display: flex; flex-direction: column; gap: 2px; }
.ap-nav-item { display: flex; align-items: center; gap: 8px; padding: 9px 12px; border: none; background: transparent; color: var(--text2); font-size: 13.5px; cursor: pointer; border-radius: 9px; text-align: left; }
.ap-nav-item:hover { background: var(--btn-bg-hover); color: var(--text1); }
.ap-nav-item.on { background: color-mix(in srgb, var(--brand-1) 18%, transparent); color: var(--brand-1); font-weight: 600; }
.ap-foot { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
.ap-back { width: 100%; padding: 8px; border: 1px solid var(--border); background: transparent; color: var(--text2); border-radius: 9px; cursor: pointer; font-size: 12.5px; }
.ap-back:hover { color: var(--text1); }
.ap-main { flex: 1; min-width: 0; margin-top: 0; margin-left: 240px; }
.ap-title { font-size: 18px; font-weight: 700; color: var(--text1); margin: 4px 0 16px; }
.ap-sub { font-size: 12.5px; color: var(--text2); font-weight: 400; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }
.stat-card { padding: 18px; border-radius: 14px; border: 1px solid var(--border); background: var(--btn-bg); }
.stat-card b { display: block; font-size: 26px; color: var(--text1); margin-bottom: 4px; }
.stat-card span { font-size: 12.5px; color: var(--text2); }
.stat-card.warn { cursor: pointer; }
.stat-card.warn b { color: #f59e0b; }
.trend-card, .audit-card { border: 1px solid var(--border); border-radius: 14px; background: var(--btn-bg); padding: 16px; margin-bottom: 12px; }
.trend-card h3 { font-size: 14px; margin: 0 0 10px; color: var(--text1); }
.toolbar { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }
/* 主题风格分段筛选（替代原生 select） */
.filter-seg { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--btn-bg); border: 1px solid var(--border); }
.filter-seg button { border: none; background: transparent; color: var(--text2); font-size: 12.5px; padding: 5px 12px; border-radius: 999px; cursor: pointer; transition: background .2s, color .2s; }
.filter-seg button:hover { color: var(--text1); background: color-mix(in srgb, var(--text2) 10%, transparent); }
.filter-seg button.on { background: color-mix(in srgb, var(--brand-1) 16%, transparent); color: var(--brand-1); font-weight: 600; }
.ap-input { padding: 8px 12px; border-radius: 9px; border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1); font-size: 13px; outline: none; min-width: 180px; }
.ap-input.sel { min-width: 120px; }
.ap-btn { padding: 8px 16px; border: none; border-radius: 9px; cursor: pointer; font-size: 13px; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); color: #fff; font-weight: 600; }
.ap-btn.sm { padding: 5px 10px; font-size: 12px; }
.ap-btn.danger { background: #e5484d; }
.ap-btn.ghost { background: transparent; border: 1px solid var(--border); color: var(--text2); }
.ap-btn:disabled { opacity: .5; cursor: not-allowed; }
.ap-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ap-table th { text-align: left; padding: 9px 10px; color: var(--text2); font-weight: 600; border-bottom: 1px solid var(--border); white-space: nowrap; }
.ap-table td { padding: 9px 10px; color: var(--text1); border-bottom: 1px solid color-mix(in srgb, var(--border) 60%, transparent); }
.ap-table .ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ops { display: flex; gap: 6px; flex-wrap: wrap; }
.role-tag { padding: 2px 8px; border-radius: 999px; font-size: 11.5px; }
.role-tag.admin { background: color-mix(in srgb, #f59e0b 20%, transparent); color: #f59e0b; }
.role-tag.moderator { background: color-mix(in srgb, var(--brand-1) 20%, transparent); color: var(--brand-1); }
.role-tag.user { background: color-mix(in srgb, var(--text2) 16%, transparent); color: var(--text2); }
.audit-tag { padding: 2px 8px; border-radius: 999px; font-size: 11.5px; }
.audit-tag.approved { background: color-mix(in srgb, #22c55e 18%, transparent); color: #22c55e; }
.audit-tag.pending { background: color-mix(in srgb, #f59e0b 18%, transparent); color: #f59e0b; }
.audit-tag.blocked { background: color-mix(in srgb, #e5484d 18%, transparent); color: #e5484d; }
.page-bar { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; color: var(--text2); font-size: 13px; }
.form-card { border: 1px solid var(--border); border-radius: 14px; background: var(--btn-bg); padding: 16px; margin-bottom: 18px; }
.form-card h3 { font-size: 14px; margin: 0 0 12px; color: var(--text1); }
.form-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.form-row .ap-input { flex: 1; min-width: 140px; }
.ap-input.ta { min-height: 90px; resize: vertical; width: 100%; }
.ap-sec { font-size: 14px; margin: 16px 0 10px; color: var(--text1); }
.mono { font-family: Consolas, monospace; letter-spacing: .5px; }
.code-box { margin-top: 12px; padding: 12px; border-radius: 10px; background: color-mix(in srgb, var(--brand-1) 8%, transparent); border: 1px dashed color-mix(in srgb, var(--brand-1) 40%, transparent); }
.code-box-head { font-size: 12.5px; color: var(--text2); margin-bottom: 8px; }
.code-list { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.code-chip { padding: 4px 10px; border-radius: 8px; background: var(--bg); border: 1px solid var(--border); font-family: Consolas, monospace; font-size: 12.5px; color: var(--text1); cursor: pointer; }
.code-chip:hover { border-color: var(--brand-1); color: var(--brand-1); }
.perm-cell { display: flex; flex-wrap: wrap; gap: 4px 10px; }
.perm-item { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; color: var(--text2); cursor: pointer; }
.perm-item input { accent-color: var(--brand-1); }
.empty-tip { color: var(--text2); font-size: 13.5px; padding: 30px; text-align: center; }
.audit-head { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
.audit-head b { color: var(--text1); }
.ap-meta { color: var(--text2); font-size: 12px; white-space: nowrap; }
.audit-content { color: var(--text2); font-size: 13px; margin: 0 0 10px; max-height: 90px; overflow: hidden; white-space: pre-line; }
.audit-ops { display: flex; gap: 8px; }
.modal-mask { position: fixed; inset: 0; z-index: 300; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; padding: 20px; }
.modal { width: min(680px, 94vw); max-height: 86vh; display: flex; flex-direction: column; border-radius: 14px; background: var(--bg); border: 1px solid var(--border); overflow: hidden; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border); color: var(--text1); }
.modal-close { border: none; background: transparent; color: var(--text2); font-size: 16px; cursor: pointer; }
.modal-body { padding: 16px 18px; overflow-y: auto; color: var(--text1); font-size: 13.5px; line-height: 1.7; }
.preview-raw { margin: 0; white-space: pre-wrap; word-break: break-word; font-family: inherit; color: var(--text1); }
.modal-foot { padding: 12px 18px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 8px; }
.modal.small { width: min(420px, 92vw); }
.ap-input.w100 { width: 100%; box-sizing: border-box; }
/* 主题 toast */
.ap-toasts { position: fixed; top: 74px; right: 20px; z-index: 400; display: flex; flex-direction: column; gap: 8px; }
.ap-toast {
  padding: 10px 18px; border-radius: 12px; font-size: 13px; font-weight: 600;
  background: var(--bg); border: 1px solid var(--border); color: var(--text1);
  box-shadow: 0 8px 30px rgba(0, 0, 0, .3);
  max-width: 360px;
}
.ap-toast.err { border-color: #e5484d; color: #e5484d; }
.toast-enter-active, .toast-leave-active { transition: opacity .25s, transform .25s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(16px); }

@media (max-width: 900px) {
  .admin-panel { flex-direction: column; padding: 0 12px 30px; }
  .ap-side { width: 100%; position: static; margin-top: 10px; max-height: none; overflow-y: visible; }
  .ap-nav { flex-direction: row; flex-wrap: wrap; }
  .ap-main { margin-top: 10px; margin-left: 0; }
  .ap-table { font-size: 12px; }
  .ops { flex-direction: column; }
}
</style>
