<template>
  <div class="msg-page">
    <div class="msg-list">
      <div class="msg-list-head">
        <span class="head-title">💬 私信</span>
        <span class="head-acts">
          <button class="head-btn" data-tip="创建群聊" @click="openGroupModal">＋ 建群</button>
          <span class="head-sub">{{ convs.length + groups.length }} 会话</span>
        </span>
      </div>

      <!-- AI 助手（官方账号，默认置顶会话） -->
      <div v-if="aiInfo" class="msg-item ai" :class="{ on: !activeGroup && active === aiInfo.id }" @click="openConv(aiInfo.id)">
        <div class="m-avatar ai-avatar">🤖</div>
        <div class="m-info">
          <div class="m-top"><span class="m-name">{{ aiInfo.nickname || 'AI 助手' }}</span><span class="m-time">官方账号</span></div>
          <div class="m-last">随时问我问题，对话会一直保留</div>
        </div>
      </div>

      <!-- 群聊 -->
      <template v-if="groups.length">
        <div class="list-divider">群聊 · {{ groups.length }}</div>
        <div v-for="g in groups" :key="g.id" class="msg-item" :class="{ on: activeGroup === g.id }" @click="openGroup(g.id)">
          <div class="m-avatar group-avatar">👥</div>
          <div class="m-info">
            <div class="m-top"><span class="m-name">{{ g.name }}</span><span class="m-time">{{ g.member_count }} 人</span></div>
            <div class="m-last">{{ g.last_content || '群聊已创建' }}</div>
          </div>
        </div>
      </template>

      <!-- 私聊 -->
      <template v-if="convs.length">
        <div class="list-divider">私聊 · {{ convs.length }}</div>
        <div v-for="c in convs" :key="c.peer.id" class="msg-item" :class="{ on: !activeGroup && active === c.peer.id }" @click="openConv(c.peer.id)">
          <div class="m-avatar">
            <img v-if="c.peer.avatar" :src="c.peer.avatar" alt="" />
            <span v-else>{{ (c.peer.nickname || c.peer.username || '?').slice(0, 1) }}</span>
            <span v-if="c.unread" class="m-badge">{{ c.unread > 99 ? '99+' : c.unread }}</span>
          </div>
          <div class="m-info">
            <div class="m-top">
              <span class="m-name">{{ c.peer.nickname || c.peer.username || '未知用户' }}</span>
              <span class="m-time">{{ fmtTime(c.last_at) }}</span>
            </div>
            <div class="m-last" :class="{ unread: c.unread }">{{ (c.mine ? '我：' : '') + c.last }}</div>
          </div>
        </div>
      </template>

      <div v-if="!convs.length && !groups.length" class="center empty">
        <div class="empty-emoji">💌</div>
        还没有会话<br /><span class="sub">在别人主页点「✉️ 私信」即可开聊</span>
      </div>
    </div>

    <div class="msg-chat">
      <!-- 群聊会话 -->
      <template v-if="activeGroup">
        <div class="chat-head">
          <div class="ch-user">
            <span class="ch-avatar group-avatar">👥</span>
            <div class="ch-txt">
              <div class="ch-name">{{ gName }}</div>
              <div class="ch-id">{{ gMembers.length }} 位成员</div>
            </div>
          </div>
        </div>
        <div class="chat-body" ref="gBody">
          <div v-if="!gMsgs.length" class="center empty"><div class="empty-emoji">👋</div>群聊刚建立，说句话吧</div>
          <template v-for="(m, i) in gMsgs" :key="m.id">
            <div v-if="i === 0 || dateKey(m.created_at) !== dateKey(gMsgs[i - 1].created_at)" class="chat-date">{{ fmtDay(m.created_at) }}</div>
            <div class="chat-row" :class="{ mine: m.sender_id === meId }">
              <div class="bubble"><span v-if="m.sender_id !== meId" class="bubble-name">{{ m.nickname || m.username }}</span>{{ m.content }}</div>
              <div class="chat-time">{{ String(m.created_at || '').slice(11, 16) }}</div>
            </div>
          </template>
        </div>
        <div class="chat-input-row">
          <textarea v-model="draft" class="chat-input" rows="1" placeholder="发送到群聊…（Enter 发送）" @keydown.enter.exact.prevent="send"></textarea>
          <button class="send-btn" :disabled="sending || !draft.trim()" @click="send">{{ sending ? '发送中…' : '发送' }}</button>
        </div>
      </template>

      <!-- 私聊会话 -->
      <template v-else>
        <div v-if="!peer" class="center empty big">
          <div class="empty-emoji">💬</div>
          选择左侧会话开始聊天
        </div>
        <template v-else>
          <div class="chat-head">
            <div class="ch-user" @click="goUser(peer.id)">
              <span class="ch-avatar">
                <img v-if="peer.avatar" :src="peer.avatar" alt="" />
                <span v-else>{{ (peer.nickname || peer.username || '?').slice(0, 1) }}</span>
              </span>
              <div class="ch-txt">
                <div class="ch-name">{{ peer.nickname || peer.username }}</div>
                <div class="ch-id">@{{ peer.username }}</div>
              </div>
            </div>
            <button class="ch-go" @click="goUser(peer.id)">查看主页 →</button>
          </div>
          <div class="chat-body" ref="chatBody">
            <div v-if="!msgs.length" class="center empty"><div class="empty-emoji">👋</div>还没有消息，打个招呼吧</div>
            <template v-for="(m, i) in msgs" :key="m.id">
              <div v-if="i === 0 || dateKey(m.created_at) !== dateKey(msgs[i - 1].created_at)" class="chat-date">{{ fmtDay(m.created_at) }}</div>
              <div class="chat-row" :class="{ mine: m.mine }">
                <div class="bubble">{{ m.content }}</div>
                <div class="chat-time">{{ String(m.created_at || '').slice(11, 16) }}</div>
              </div>
            </template>
          </div>
          <div class="chat-input-row">
            <textarea v-model="draft" class="chat-input" rows="1" placeholder="输入消息…（Enter 发送，Shift+Enter 换行）" @keydown.enter.exact.prevent="send"></textarea>
            <button class="send-btn" :disabled="sending || !draft.trim()" @click="send">{{ sending ? '发送中…' : '发送' }}</button>
          </div>
        </template>
      </template>
    </div>

    <!-- 建群弹窗 -->
    <div v-if="groupModal" class="g-modal" @click.self="groupModal = false">
      <div class="g-dialog">
        <h3>＋ 创建群聊</h3>
        <input v-model="groupName" class="g-input" maxlength="30" placeholder="群名称（必填）" />
        <div class="g-label">选择好友（{{ groupPick.length }}）</div>
        <div class="g-pick">
          <div v-if="!groupFriends.length" class="center empty">还没有好友，先添加好友再建群</div>
          <div v-for="f in groupFriends" :key="f.other_id" class="g-user" :class="{ on: groupPick.includes(f.other_id) }" @click="togglePick(f.other_id)">
            <span class="g-avatar"><img v-if="f.avatar" :src="f.avatar" alt="" /><span v-else>{{ (f.nickname || f.username || '?').slice(0, 1) }}</span></span>
            <span class="g-uname">{{ f.nickname || f.username }}</span>
            <span class="g-check">✓</span>
          </div>
        </div>
        <div class="g-foot">
          <button class="g-cancel" @click="groupModal = false">取消</button>
          <button class="g-create" :disabled="!groupName.trim() || !groupPick.length" @click="createGroup">创建群聊</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api.js'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth.js'

export default {
  name: 'Messages',
  data() {
    return {
      convs: [],
      groups: [],
      aiInfo: null,
      active: null,
      activeGroup: null,
      peer: null,
      msgs: [],
      gMsgs: [],
      gMembers: [],
      draft: '',
      sending: false,
      timer: null,
      groupModal: false,
      groupName: '',
      groupFriends: [],
      groupPick: [],
    }
  },
  computed: {
    meId() { return useAuthStore().user?.id },
    gName() { const g = this.groups.find(x => x.id === this.activeGroup); return g ? g.name : '群聊' },
  },
  mounted() {
    const withId = Number(this.$route.query.with || 0)
    this.loadAll()
    if (withId) this.openConv(withId)
    // 轻量轮询：有新消息时自动刷新（6s）
    this.timer = setInterval(() => {
      if (this.activeGroup) this.loadGMsgs()
      else if (this.active) this.loadMsgs()
    }, 6000)
  },
  beforeUnmount() { if (this.timer) clearInterval(this.timer) },
  methods: {
    async loadAll() {
      await Promise.all([this.loadConvs(), this.loadGroups()])
    },
    async loadConvs() {
      try {
        const res = await api.get('/messages/conversations')
        this.convs = res.data.list || []
        this.aiInfo = res.data.ai || null
      } catch (e) { /* 忽略 */ }
    },
    async loadGroups() {
      try {
        const res = await api.get('/groups')
        this.groups = res.data
      } catch (e) { /* 忽略 */ }
    },
    // ── 群聊 ──
    async openGroup(gid) {
      this.aiOpen = false
      this.activeGroup = gid
      this.active = null
      this.peer = null
      await Promise.all([this.loadGMsgs(), this.loadGroupDetail(gid)])
    },
    async loadGMsgs() {
      if (!this.activeGroup) return
      try {
        const res = await api.get('/groups/' + this.activeGroup + '/messages')
        this.gMsgs = res.data
        this.$nextTick(() => { const el = this.$refs.gBody; if (el) el.scrollTop = el.scrollHeight })
      } catch (e) { /* 忽略 */ }
    },
    async loadGroupDetail(gid) {
      try {
        const res = await api.get('/groups/' + gid)
        this.gMembers = res.data.members || []
      } catch (e) { /* 忽略 */ }
    },
    async sendGroup() {
      const text = this.draft.trim()
      if (!text || this.sending) return
      this.sending = true
      this.draft = ''
      // 乐观更新：自己的消息立即显示
      const now = new Date().toISOString().slice(0, 19).replace('T', ' ')
      this.gMsgs.push({ id: Date.now(), _tmp: true, sender_id: this.meId, content: text, created_at: now })
      this.$nextTick(() => { const el = this.$refs.gBody; if (el) el.scrollTop = el.scrollHeight })
      try {
        await api.post('/groups/' + this.activeGroup + '/messages', { content: text })
        await this.loadGMsgs()
        this.loadGroups()
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '发送失败')
        this.gMsgs = this.gMsgs.filter(m => !m._tmp)
      }
      this.sending = false
    },
    // ── 建群 ──
    async openGroupModal() {
      this.groupName = ''
      this.groupPick = []
      try {
        const res = await api.get('/friends')
        this.groupFriends = (res.data.list || []).filter(f => f.status === 'accepted')
      } catch (e) { this.groupFriends = [] }
      this.groupModal = true
    },
    togglePick(id) {
      const i = this.groupPick.indexOf(id)
      if (i >= 0) this.groupPick.splice(i, 1)
      else this.groupPick.push(id)
    },
    async createGroup() {
      if (!this.groupName.trim() || !this.groupPick.length) return
      try {
        const res = await api.post('/groups', { name: this.groupName.trim(), member_ids: this.groupPick })
        this.groupModal = false
        await this.loadGroups()
        ElMessage.success('群聊已创建')
        if (res.data.id) this.openGroup(res.data.id)
      } catch (e) { ElMessage.error(e.response?.data?.error || '创建失败') }
    },
    // ── 私聊 ──
    async openConv(pid) {
      this.active = pid
      this.activeGroup = null
      await this.loadMsgs()
    },
    async loadMsgs() {
      try {
        const res = await api.get('/messages?with=' + this.active)
        this.peer = res.data.peer
        this.msgs = res.data.messages
        const conv = this.convs.find(c => c.peer.id === this.active)
        if (conv) conv.unread = 0
        this.$nextTick(() => {
          const el = this.$refs.chatBody
          if (el) el.scrollTop = el.scrollHeight
        })
      } catch (e) { /* 忽略 */ }
    },
    async send() {
      if (this.activeGroup) return this.sendGroup()
      const text = this.draft.trim()
      if (!text || this.sending) return
      this.sending = true
      this.draft = ''
      // 乐观更新：自己的消息立即显示，不等后端（发 AI 时回复要几秒）
      const now = new Date().toISOString().slice(0, 19).replace('T', ' ')
      this.msgs.push({ id: Date.now(), _tmp: true, mine: true, content: text, created_at: now })
      this.$nextTick(() => { const el = this.$refs.chatBody; if (el) el.scrollTop = el.scrollHeight })
      try {
        await api.post('/messages', { to_user_id: this.active, content: text })
        await this.loadMsgs()
        this.loadConvs()
      } catch (e) {
        ElMessage.error(e.response?.data?.error || '发送失败')
        this.msgs = this.msgs.filter(m => !m._tmp)
      }
      this.sending = false
    },
    goUser(id) { this.$router.push('/user/' + id) },
    fmtTime(ts) {
      if (!ts) return ''
      const d = new Date(String(ts).replace(' ', 'T'))
      if (isNaN(d)) return String(ts).slice(5, 16)
      const now = new Date()
      const hm = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0')
      if (d.toDateString() === now.toDateString()) return hm
      const yest = new Date(now); yest.setDate(now.getDate() - 1)
      if (d.toDateString() === yest.toDateString()) return '昨天'
      return (d.getMonth() + 1) + '/' + d.getDate()
    },
    dateKey(ts) { return ts ? String(ts).slice(0, 10) : '' },
    fmtDay(ts) {
      const today = new Date()
      const k = this.dateKey(ts)
      if (k === today.toISOString().slice(0, 10)) return '今天'
      const yest = new Date(today); yest.setDate(today.getDate() - 1)
      if (k === yest.toISOString().slice(0, 10)) return '昨天'
      return k.replace('-', '年').replace('-', '月') + '日'
    },
  },
}
</script>

<style scoped>
.msg-page {
  height: calc(100vh - 64px);
  padding: 76px 16px 16px;
  box-sizing: border-box;
  max-width: 1100px; margin: 0 auto;
  display: grid; grid-template-columns: 300px minmax(0, 1fr);
  gap: 14px;
}
.msg-list {
  background: color-mix(in srgb, var(--card-bg) 80%, transparent);
  border: 1px solid var(--border); border-radius: 16px;
  overflow-y: auto; display: flex; flex-direction: column;
  backdrop-filter: blur(10px); box-shadow: var(--shadow-1);
}
.msg-list-head {
  position: sticky; top: 0; z-index: 2;
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  background: color-mix(in srgb, var(--card-bg) 88%, transparent);
  backdrop-filter: blur(10px);
}
.head-title { font-size: 15px; font-weight: 800; color: var(--text1); }
.head-acts { display: flex; align-items: center; gap: 10px; }
.head-sub { font-size: 11.5px; font-weight: 500; color: var(--text2); }
.head-btn {
  padding: 4px 12px; border-radius: 999px; cursor: pointer; font-size: 12px;
  border: 1px solid color-mix(in srgb, var(--brand-1) 45%, transparent);
  background: transparent; color: var(--brand-1); transition: all .18s;
}
.head-btn:hover { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.list-divider {
  padding: 8px 16px 4px; font-size: 11px; color: var(--text2); font-weight: 600;
  background: color-mix(in srgb, var(--btn-bg) 50%, transparent);
}
.msg-item {
  display: flex; gap: 11px; padding: 13px 14px; cursor: pointer;
  position: relative; transition: background .15s;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 55%, transparent);
}
.msg-item:hover { background: color-mix(in srgb, var(--brand-1) 6%, transparent); }
.msg-item.on { background: color-mix(in srgb, var(--brand-1) 13%, transparent); }
.msg-item.on::before {
  content: ''; position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px;
  border-radius: 3px; background: linear-gradient(180deg, var(--brand-1), var(--brand-2));
}
.m-avatar {
  position: relative; width: 42px; height: 42px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--brand-1) 70%, transparent), color-mix(in srgb, var(--brand-2) 60%, transparent));
  color: var(--text1); font-size: 16px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.m-avatar img { width: 100%; height: 100%; object-fit: cover; }
.ai-avatar { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 20px; }
.group-avatar { background: linear-gradient(135deg, #10b981, #38bdf8); color: #fff; font-size: 18px; }
.m-badge {
  position: absolute; top: -3px; right: -3px; min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 999px; background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 10.5px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 4px rgba(0,0,0,.25);
}
.m-info { flex: 1; min-width: 0; }
.m-top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.m-name { font-size: 13.5px; font-weight: 700; color: var(--text1); }
.m-time { font-size: 11px; color: var(--text2); flex-shrink: 0; }
.m-last { font-size: 12px; color: var(--text2); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.m-last.unread { color: var(--text1); font-weight: 600; }

.msg-chat {
  background: color-mix(in srgb, var(--card-bg) 80%, transparent);
  border: 1px solid var(--border); border-radius: 16px;
  display: flex; flex-direction: column; overflow: hidden;
  backdrop-filter: blur(10px); box-shadow: var(--shadow-1);
}
.chat-head {
  padding: 12px 18px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--brand-1) 7%, transparent), transparent);
}
.ch-user { display: flex; align-items: center; gap: 11px; cursor: pointer; }
.ch-avatar {
  width: 42px; height: 42px; border-radius: 50%; overflow: hidden;
  background: linear-gradient(135deg, color-mix(in srgb, var(--brand-1) 70%, transparent), color-mix(in srgb, var(--brand-2) 60%, transparent));
  color: var(--text1); font-size: 16px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.ch-avatar img { width: 100%; height: 100%; object-fit: cover; }
.ch-txt { line-height: 1.3; }
.ch-name { font-size: 14.5px; font-weight: 800; color: var(--text1); }
.ch-id { font-size: 11.5px; color: var(--text2); }
.ch-go {
  padding: 6px 16px; border-radius: 999px; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--brand-1) 50%, transparent);
  background: transparent; color: var(--brand-1); font-size: 12.5px; transition: all .18s;
}
.ch-go:hover { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }

.chat-body {
  flex: 1; overflow-y: auto; padding: 18px 20px;
  display: flex; flex-direction: column; gap: 4px;
}
.chat-date {
  align-self: center; font-size: 11px; color: var(--text2);
  background: color-mix(in srgb, var(--btn-bg) 85%, transparent);
  padding: 3px 12px; border-radius: 999px; margin: 10px 0 6px;
}
.chat-row { display: flex; flex-direction: column; max-width: 74%; margin-top: 2px; align-self: flex-start; }
.chat-row.mine { align-self: flex-end; align-items: flex-end; }
.bubble {
  padding: 9px 14px; border-radius: 14px; font-size: 13.5px; line-height: 1.55;
  background: var(--btn-bg); color: var(--text1); border: 1px solid var(--border);
  white-space: pre-wrap; word-break: break-word;
}
.chat-row.mine .bubble {
  background: linear-gradient(120deg, color-mix(in srgb, var(--brand-1) 22%, transparent), color-mix(in srgb, var(--brand-2) 20%, transparent));
  border-color: color-mix(in srgb, var(--brand-1) 36%, transparent);
  color: var(--text1); border-bottom-right-radius: 4px;
}
.chat-row:not(.mine) .bubble { border-bottom-left-radius: 4px; }
.ai-bubble { background: color-mix(in srgb, #6366f1 10%, var(--btn-bg)); border-color: color-mix(in srgb, #6366f1 30%, var(--border)); }
.bubble-name { display: block; font-size: 11.5px; color: var(--brand-1); font-weight: 600; margin-bottom: 3px; }
.chat-time { font-size: 10px; color: var(--text2); margin: 3px 4px 8px; }

.chat-input-row {
  display: flex; gap: 10px; padding: 12px 14px; border-top: 1px solid var(--border); align-items: flex-end;
  background: color-mix(in srgb, var(--card-bg) 70%, transparent);
}
.chat-input {
  flex: 1; padding: 10px 14px; border-radius: 13px; resize: none;
  border: 1px solid var(--border); background: var(--btn-bg); color: var(--text1);
  font-size: 13.5px; font-family: inherit; outline: none; transition: border-color .18s;
}
.chat-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.chat-input::placeholder { color: var(--text2); }
.send-btn {
  padding: 10px 24px; border-radius: 13px; border: none; cursor: pointer;
  background: linear-gradient(120deg, var(--brand-1), var(--brand-2));
  color: #fff; font-size: 13.5px; font-weight: 700; transition: all .18s;
}
.send-btn:hover { filter: brightness(1.08); }
.send-btn:disabled { opacity: .45; cursor: not-allowed; }

.center.empty { text-align: center; color: var(--text2); font-size: 13px; padding: 40px 16px; line-height: 1.8; }
.center.empty.big { font-size: 14px; padding: 80px 16px; }
.empty-emoji { font-size: 34px; margin-bottom: 8px; }
.center.empty .sub { font-size: 12px; color: var(--text2); opacity: .75; }

/* 建群弹窗 */
.g-modal { position: fixed; inset: 0; background: var(--overlay-bg); z-index: 1200; display: flex; align-items: center; justify-content: center; padding: 20px; }
.g-dialog { width: 420px; max-width: 100%; background: var(--bg-soft); border: 1px solid var(--border); border-radius: 16px; padding: 20px 22px; box-shadow: var(--shadow-1); box-sizing: border-box; }
.g-dialog h3 { margin: 0 0 14px; font-size: 16px; }
.g-input { width: 100%; padding: 9px 14px; border-radius: 10px; border: 1px solid var(--border); background: var(--card-bg); color: var(--text1); font-size: 13.5px; box-sizing: border-box; outline: none; }
.g-input:focus { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); }
.g-label { font-size: 12.5px; color: var(--text2); margin: 14px 0 8px; }
.g-pick { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.g-user {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 10px;
  cursor: pointer; border: 1px solid var(--border); transition: all .15s;
}
.g-user.on { border-color: color-mix(in srgb, var(--brand-1) 55%, transparent); background: color-mix(in srgb, var(--brand-1) 10%, transparent); }
.g-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.g-avatar img { width: 100%; height: 100%; object-fit: cover; }
.g-uname { flex: 1; font-size: 13px; color: var(--text1); min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.g-check { color: var(--brand-1); font-weight: 800; opacity: 0; }
.g-user.on .g-check { opacity: 1; }
.g-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.g-cancel { padding: 8px 18px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text2); cursor: pointer; }
.g-create { padding: 8px 20px; border: none; border-radius: 999px; background: linear-gradient(135deg, var(--brand-1), var(--brand-2)); color: #fff; cursor: pointer; font-weight: 600; }
.g-create:disabled { opacity: .45; cursor: not-allowed; }

/* 细滚动条 */
.msg-list::-webkit-scrollbar, .chat-body::-webkit-scrollbar, .g-pick::-webkit-scrollbar { width: 6px; }
.msg-list::-webkit-scrollbar-thumb, .chat-body::-webkit-scrollbar-thumb, .g-pick::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

@media (max-width: 720px) {
  .msg-page { grid-template-columns: 1fr; height: auto; min-height: calc(100vh - 64px); }
  .msg-list { max-height: 220px; }
}
</style>
