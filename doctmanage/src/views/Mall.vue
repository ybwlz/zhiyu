<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api.js'
import { useAuthStore } from '@/stores/auth.js'

const auth = useAuthStore()
const points = ref(0)
const logs = ref([])
const loading = ref(true)
const redeemCode = ref('')

const redeem = async () => {
  if (!auth.isLogin) { ElMessage.warning('请先登录'); return }
  if (!redeemCode.value.trim()) { ElMessage.warning('请输入兑换码'); return }
  try {
    const res = await api.post('/mall/redeem', { code: redeemCode.value })
    ElMessage.success(`兑换成功！获得 ${res.data.amount} 知屿币`)
    redeemCode.value = ''
    load()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '兑换失败')
  }
}

const GOODS = [
  { id: 1, name: 'AI 助手额度 ×5', desc: '额外 5 次 DeepSeek 智能问答额度', cost: 100, icon: '🤖' },
  { id: 2, name: '笔记广场置顶 24h', desc: '让你的公开笔记在广场顶部展示一天', cost: 200, icon: '📌' },
  { id: 3, name: '专属徽章·学霸', desc: '个人主页永久展示「学霸」金色徽章', cost: 500, icon: '🏅' },
]

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/user/points')
    points.value = res.data.points
    logs.value = res.data.logs
  } catch (e) { /* 忽略 */ }
  loading.value = false
}

const pickGoods = ref(null)
const myNotes = ref([])
const loadingNotes = ref(false)

const exchange = async (g) => {
  if (!auth.isLogin) { ElMessage.warning('请先登录'); return }
  if (g.id === 2) {
    // 置顶商品：选择笔记弹窗
    pickGoods.value = g
    loadingNotes.value = true
    try {
      const res = await api.get('/docs?scope=mine')
      myNotes.value = res.data.filter(n => n.visibility === 'public')
    } catch (e) { myNotes.value = [] }
    loadingNotes.value = false
    return
  }
  try {
    const res = await api.post('/mall/exchange', { goods_id: g.id })
    points.value = res.data.points_left
    if (res.data.badge) ElMessage.success(`兑换成功！🏅「学霸」徽章已佩戴到你的主页`)
    else ElMessage.success(`兑换成功！「${g.name}」已到账（AI 额度 +${res.data.bonus} 次）`)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '兑换失败')
  }
}

const confirmPin = async (note) => {
  if (points.value < pickGoods.value.cost) { ElMessage.warning('知屿币不足（需 ' + pickGoods.value.cost + ' 知屿币）'); return }
  try {
    const res = await api.post('/mall/exchange', { goods_id: pickGoods.value.id, doc_id: note.id })
    points.value = res.data.points_left
    pickGoods.value = null
    ElMessage.success(`「${note.title}」已置顶 24 小时，快去广场看看！`)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '兑换失败')
  }
}

const reasonText = (r) => ({
  read: '阅读笔记', note_commented: '发表评论', note_liked: '笔记被点赞',
  note_favorited: '笔记被收藏', note_shared: '笔记被转发',
  note_received_comment: '笔记收到评论', note_published: '发布公开笔记',
}[r] || r)

onMounted(load)
</script>

<template>
  <div class="mall-page">
    <h1 class="page-title">知屿币商城</h1>
    <div class="balance-card">
      <div class="balance-num">{{ points }}</div>
      <div class="balance-label">我的知屿币</div>
      <p class="balance-tip">阅读笔记、发表评论、笔记被点赞/收藏/转发都能获得知屿币</p>
    </div>

    <h3 class="section-title">兑换好物</h3>
    <div class="goods-grid">
      <div v-for="g in GOODS" :key="g.id" class="goods-card">
        <div class="goods-icon">{{ g.icon }}</div>
        <h4>{{ g.name }}</h4>
        <p>{{ g.desc }}</p>

        <button class="exchange-btn" @click="exchange(g)">兑换 · {{ g.cost }} 知屿币</button>
      </div>
    </div>

    <!-- 兑换码兑换 -->
    <div class="redeem-card">
      <h3 class="section-title">🎫 兑换码</h3>
      <p class="redeem-tip">输入兑换码领取知屿币（兑换码由管理员发放）</p>
      <div class="redeem-row">
        <input v-model="redeemCode" class="redeem-input" placeholder="请输入兑换码" @keyup.enter="redeem" />
        <button class="exchange-btn" @click="redeem">兑换</button>
      </div>
    </div>

    <!-- 置顶选笔记弹窗 -->
    <div v-if="pickGoods" class="modal-mask" @click.self="pickGoods = null">
      <div class="modal">
        <h3>📌 选择要置顶的笔记（24h）</h3>
        <p class="modal-tip">仅公开笔记可置顶 · 消耗 {{ pickGoods.cost }} 知屿币</p>
        <div v-if="loadingNotes" class="center">加载中…</div>
        <div v-else-if="myNotes.length === 0" class="center empty">你还没有公开笔记，先去发布一篇吧</div>
        <div v-else class="note-pick-list">
          <div v-for="n in myNotes" :key="n.id" class="note-pick" @click="confirmPin(n)">
            <span class="np-title">{{ n.title }}</span>
            <span class="np-stats">👍{{ n.likes_count }} ⭐{{ n.favorites_count }}</span>
          </div>
        </div>
        <div class="modal-actions">
          <button class="cancel" @click="pickGoods = null">取消</button>
        </div>
      </div>
    </div>

    <h3 class="section-title">知屿币明细</h3>
    <div v-if="loading" class="center">加载中…</div>
    <div v-else-if="logs.length === 0" class="center empty">暂无知屿币记录</div>
    <div v-else class="log-list">
      <div v-for="(l, i) in logs" :key="i" class="log-row">
        <span class="log-reason">{{ reasonText(l.reason) }}</span>
        <span class="log-time">{{ l.created_at }}</span>
        <span class="log-delta" :class="{ plus: l.delta > 0 }">+{{ l.delta }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mall-page { max-width: 760px; margin: 0 auto; min-height: 100vh; padding: 96px 24px 60px; box-sizing: border-box; }
.page-title { font-size: 26px; font-weight: 800; margin: 0 0 20px; color: var(--text1); }
.balance-card {
  background: linear-gradient(135deg, color-mix(in srgb, var(--brand-1) 18%, var(--card-bg)), color-mix(in srgb, var(--brand-2) 12%, var(--card-bg)));
  border: 1px solid var(--border); border-radius: 20px;
  padding: 28px; text-align: center; margin-bottom: 26px;
  box-shadow: var(--shadow-1);
}
.balance-num { font-size: 44px; font-weight: 800; background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.balance-label { font-size: 13.5px; color: var(--text2); margin: 4px 0 10px; }
.balance-tip { font-size: 12.5px; color: var(--text2); margin: 0; }
.section-title { font-size: 16px; font-weight: 700; margin: 26px 0 14px; color: var(--text1); }
/* 兑换码 */
.redeem-card { margin-top: 6px; padding: 16px; border-radius: 14px; border: 1px dashed var(--border); background: var(--btn-bg); }
.redeem-card .section-title { margin: 0 0 6px; }
.redeem-tip { color: var(--text2); font-size: 12.5px; margin: 0 0 12px; }
.redeem-row { display: flex; gap: 10px; max-width: 460px; }
.redeem-input { flex: 1; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text1); font-size: 14px; letter-spacing: 1px; text-transform: uppercase; outline: none; }
.redeem-input:focus { border-color: var(--brand-1); }
.goods-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.goods-card {
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 16px; padding: 20px; text-align: center;
  backdrop-filter: blur(8px); transition: transform .25s, border-color .25s;
}
.goods-card:hover { transform: translateY(-3px); border-color: color-mix(in srgb, var(--brand-1) 40%, transparent); }
.goods-icon { font-size: 30px; margin-bottom: 8px; }
.goods-card h4 { margin: 0 0 6px; font-size: 15px; color: var(--text1); }
.goods-card p { margin: 0 0 14px; font-size: 12.5px; color: var(--text2); line-height: 1.5; }
.exchange-btn {
  width: 100%; padding: 9px 0; border: none; border-radius: 999px;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.log-list { display: flex; flex-direction: column; gap: 8px; }
.log-row {
  display: flex; align-items: center; gap: 12px;
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 12px; padding: 11px 16px; font-size: 13.5px;
}
.log-reason { flex: 1; color: var(--text1); }
.log-time { color: var(--text2); font-size: 12px; }
.log-delta { font-weight: 700; color: var(--brand-1); }
.center { text-align: center; color: var(--text2); padding: 24px 0; }
.modal-mask {
  position: fixed; inset: 0; z-index: 200;
  background: var(--overlay-bg);
  display: flex; align-items: center; justify-content: center;
}
.modal {
  width: 420px; max-width: 92vw; max-height: 70vh;
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: 18px; padding: 24px;
  display: flex; flex-direction: column;
}
.modal h3 { margin: 0 0 6px; color: var(--text1); }
.modal-tip { font-size: 12.5px; color: var(--text2); margin: 0 0 14px; }
.note-pick-list { overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 8px; }
.note-pick {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 14px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--card-bg);
  cursor: pointer; transition: all .2s;
}
.note-pick:hover { border-color: var(--brand-1); background: color-mix(in srgb, var(--brand-1) 6%, transparent); }
.np-title { flex: 1; font-size: 13.5px; color: var(--text1); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.np-stats { font-size: 12px; color: var(--text2); flex-shrink: 0; }
.modal-actions { display: flex; justify-content: flex-end; margin-top: 14px; }
.cancel { padding: 8px 18px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text2); cursor: pointer; }
.empty { font-size: 13px; }
</style>