<!-- 更新日志：版本档案，记录知屿的迭代历史 -->
<template>
  <div class="changelog-page">
    <div class="page-header">
      <p class="kicker">CHANGELOG</p>
      <h1 class="title">更新<span class="grad">日志</span></h1>
      <p class="desc">知屿知识库的每一次迭代，都记录在这里。</p>
    </div>

    <div class="cl-layout">
      <!-- 左栏：版本档案 -->
      <aside class="cl-sidebar">
        <p class="side-label">版本档案</p>
        <div class="side-group" v-for="g in versionGroups" :key="g.label">
          <p class="side-group-label" @click="toggleGroupFold(g.label)">
            {{ g.label }}
            <span class="fold-caret" :class="{ open: !collapsedGroups.has(g.label) }">▸</span>
          </p>
          <div v-if="!collapsedGroups.has(g.label)">
            <div
              class="side-item"
              v-for="v in g.items"
              :key="v.version"
              :class="{ on: v.version === activeVersion }"
              @click="activeVersion = v.version"
            >
              <span class="side-ver">v{{ v.version }}</span>
              <span class="side-date">{{ v.date }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右栏：当前版本详情 -->
      <div class="cl-detail">
        <div class="detail-card" v-for="v in versions" :key="v.version" :style="v.version === activeVersion ? {} : { display: 'none' }">
          <div class="detail-head">
            <h2 class="detail-version">v{{ v.version }} <span class="detail-tag" v-if="v.latest">最新</span></h2>
            <span class="detail-date">{{ v.date }}</span>
          </div>
          <p class="detail-summary">{{ v.summary }}</p>

          <div class="detail-section" v-for="(items, cat) in v.sections" :key="cat">
            <h3 class="section-title">
              <span class="section-badge" :class="'badge-' + cat">{{ catLabel(cat) }}</span>
            </h3>
            <div class="section-item" v-for="(item, i) in items" :key="i">
              <span class="item-no">{{ String(i + 1).padStart(2, '0') }}</span>
              <div class="item-body">
                <h4>{{ item.title }}</h4>
                <p v-if="item.desc">{{ item.desc }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const CAT = { feat: '新功能', fixed: '修复', improved: '改进' }
const catLabel = (k) => CAT[k] || k

const versions = [
  {
    version: '0.6.0', date: '2026-08-11', latest: true,
    summary: 'AI 修改全面 Cursor 化：内嵌红绿 diff 逐个确认、真流式 + 思考可见、所有 AI 写入都先预览后生效。',
    sections: {
      feat: [
        { title: 'AI 修改建议内嵌 diff（Cursor 式）', desc: '工具栏 ✨ AI 不选中文字时，AI 自己定位全文中的多处修改点，每处直接内嵌到正文对应位置显示红绿 diff，逐个接受/拒绝，也可全部接受/拒绝；选中文字时同样内嵌定点修改。' },
        { title: 'AI 流式输出 + 思考过程可见', desc: 'AI 回答改为真正的逐 token 打字机输出；DeepSeek 的思考过程单独以「🧠 查看思考过程」折叠块展示，可展开查看。' },
        { title: '所有 AI 写入统一先预览 diff', desc: 'AI 修改/插入/重写笔记一律先存草稿并跳编辑器弹红绿 diff，你确认后才保存；write_note 工具不再直接覆盖正式笔记。' },
        { title: 'AI 按标题搜笔记跳转', desc: '说「打开《数据结构大纲》」AI 会先按标题搜索到笔记 ID 再跳转，不用再手动提供链接。' },
        { title: 'AI 上下文扩容', desc: '当前笔记全文上限提升到 10 万字符（约 3-4 万 token），长笔记也能完整理解。' },
      ],
      improved: [
        { title: '插入内容按章节定位', desc: 'AI 插入的新内容（如「3.3 代码实现」）自动插到对应章节末尾，并剥离「用户要求…」等思考前缀，不再误插到全文末尾。' },
        { title: '多轮 AI 修改累积', desc: '未接受的 diff 不会因新一轮修改被覆盖，新旧修改点累积展示，可分批接受。' },
        { title: 'AI 修改后自动定位', desc: '生成 diff 后自动滚动到第一个修改点并高亮，编辑区直接看到改在哪。' },
      ],
      fixed: [
        { title: '修复表格保存后被拆成竖排文本', desc: '所见即所得编辑器保存时 turndown 不支持表格，导致表格内容被拆成逐行文本的根因问题已修复：新增表格还原规则，<table> 正确还原为 markdown 表格（含单元格内公式）。' },
        { title: '修复 AI 回复重复气泡', desc: '流式输出期间不再同时显示空的气泡与打字指示器。' },
      ],
    },
  },
  {
    version: '0.5.0', date: '2026-08-11', latest: false,
    summary: '社交升级：单向关注 + 私信上线；AI 助手按页面给动作；个人主页改版。',
    sections: {
      feat: [
        { title: '单向关注系统', desc: '好友改为关注/粉丝模式：主页一键关注/取关，粉丝与关注列表可回关/取关，支持按 ID（@用户名）或昵称搜索用户。' },
        { title: '私信上线', desc: '站内信对话：会话列表（未读角标）+ 对话窗口，Enter 发送、自动刷新新消息；在个人主页点「✉️ 私信」直达对方会话。' },
        { title: 'AI 助手页面感知', desc: 'AI 知道你在哪个页面：阅览室回答后可「📥 插入笔记」直接写进当前笔记，编辑器可「插入正文」，广场/阅读页可「存为笔记」「写评论」。' },
        { title: 'AI 章节结构规则', desc: '给笔记加新主题时按教材章节体系插入独立章节并自动重排后续编号，不再塞进现有章节当子小节（如「串」作为独立第四章）。' },
        { title: '个人主页改版', desc: '两栏布局：右侧「TA 的关注 / TA 的粉丝」卡片；资料卡右上角关注/私信按钮；统计改为关注/粉丝/笔记/获赞/积分/阅读。' },
        { title: '关注页重做', desc: '「我的关注 / 我的粉丝 / 发现用户」三个 Tab，一键取关/回关，搜索用户直接关注。' },
      ],
      improved: [
        { title: '编辑器可见性切换简化', desc: '私密/公开改为简洁小按钮，选中态低饱和不刺眼。' },
        { title: '星空主题适配', desc: '个人主页背景图在星空主题下自动淡化（透明度调高），文字自动对比（亮底黑字/暗底白字）；关注/私信按钮毛玻璃底，任何背景下清晰可读。' },
        { title: '私信页体验', desc: '会话列表 + 对话窗口，消息按日期分组、显示相对时间，标题栏可直达对方主页。' },
      ],
      fixed: [
        { title: '修复页面顶部被导航遮挡', desc: '关注页等页面顶部留白对齐固定导航高度，内容不再被压住。' },
      ],
    },
  },
  {
    version: '0.4.0', date: '2026-08-10', latest: false,
    summary: '广场三栏化 + 主题评分 + 首页搜索直达 + 隐私与体验全面升级。',
    sections: {
      feat: [
        { title: '主题评分系统', desc: '笔记末尾可评专业/实用/易读/感悟四维星级 + 五个主题评价标签；参与评分得 2 知屿币（每日 3 次）；综合得分（10 分制）、四维星级与评价占比雷达图展示。' },
        { title: '个人主页：修改密码 + 复制我的 ID', desc: '主页资料区可修改密码、一键复制自己的 ID（加好友用）。' },
        { title: '首页能力版图全部上线', desc: 'AI 助手 / 图片转笔记 / 多格式上传 / 全文检索均标为已上线，点卡片直达使用。' },
        { title: '首页匿名社区数据', desc: '原「最新动态」涉及隐私已移除，改为匿名聚合统计（篇数/点赞/评论/下载），不暴露个人行为。' },
        { title: '精选轮播持续自动播放', desc: '移除鼠标悬停暂停，卡片 2.5 秒自动轮换，更流畅的展示效果。' },
        { title: '笔记广场三栏布局', desc: '左栏科目导航 / 排序 / 快捷入口，右栏热门榜 TOP5 / 最新收录 / 社区数据，中间笔记时间线收窄居中。' },
        { title: '广场预览公式可读化', desc: 'LaTeX 公式转成可读文字：sin²α + cos²α = 1、√((x₁-x₂)² + (y₁-y₂)²)、Σᵢ₌₁ⁿ 等。' },
        { title: '广场预览多图展示', desc: '正文图片最多提取 5 张，一行横排缩略图，单张靠左顺延。' },
      ],
      improved: [
        { title: '首页搜索直达广场', desc: '搜索支持标题/内容/科目分类，回车直达笔记广场展示结果列表；科目图谱卡片直达广场对应科目。' },
        { title: '阅览室「添加笔记」只列自己的笔记', desc: '不再掺入广场/他人的笔记；想用广场笔记请先「加入书房」。' },
        { title: '广场预览统一两行', desc: '第一行满 + 第二行文字到中间接省略号，卡片高度整齐。' },
        { title: '后端搜索支持分类匹配', desc: '搜「高等数学」能命中高等数学分类的笔记，不再误跳。' },
      ],
      fixed: [
        { title: '修复头像不显示', desc: 'dev 代理补上 /uploads 静态资源转发，登录与 /me 接口返回 avatar 字段。' },
        { title: '修复后端进程不稳定', desc: 'Windows 下关闭自动重载改用稳定模式，避免进程反复崩溃。' },
      ],
    },
  },
  {
    version: '0.3.0', date: '2026-08', latest: false,
    summary: '社区化一期 + 全站打磨：多用户、互动、好友、积分、笔记广场、AI 检索问答、在线创作与阅读体验全面升级。',
    sections: {
      feat: [
        { title: '多用户系统', desc: '邮箱验证码注册 + 登录鉴权；首个注册用户为管理员；笔记公开/私密切换，各用户数据隔离。' },
        { title: '笔记广场与在线阅读', desc: '公开笔记流：搜索、分类筛选、最新/最热/收藏排序、分页加载；在线阅读支持点赞/收藏/转发/下载/评论。' },
        { title: '评论区楼中楼', desc: '@ 回复、子评论缩进、emoji 快捷插入、段落定位评论。' },
        { title: '好友系统', desc: '申请/同意/拒绝/删除，阅读页作者卡一键加好友。' },
        { title: '积分商城', desc: '互动得积分；真实兑换：AI 额度（100 分/5 次）、笔记置顶 24h（200 分）、学霸徽章（500 分）。' },
        { title: '个人主页', desc: '抖音式标签页（笔记/收藏/点赞/私密/动态）+ 91 格学习热力图 + 资料/头像编辑。' },
        { title: 'DeepSeek AI 助手', desc: '基于自己笔记的检索问答，免费 20 次基础额度；流式打字机、多轮对话记忆。' },
        { title: '在线编辑器', desc: 'Markdown 实时预览 + ∑ 数学符号面板（49 个 LaTeX 符号）+ AI 一键起稿。' },
        { title: '涂鸦式批注', desc: '荧光笔手绘（5 色/细中粗/橡皮擦），持久化保存，可隐藏收起。' },
        { title: '消息通知', desc: '🔔 铃铛实时提醒：点赞/收藏/评论/好友申请/每日摘要，未读红点 + 60 秒轮询。' },
        { title: '首页升级', desc: '社区动态流、登录用户今日概览（阅读时长/AI 用量/积分）、科目笔记数徽章。' },
        { title: '阅读体验', desc: '☰ 四级阅读大纲（滚动高亮）、上一篇/下一篇、顶部阅读进度条、沉浸模式。' },
      ],
      improved: [
        { title: '公式渲染三处统一', desc: '文库/在线阅读/编辑器全部接入 MathJax，数学笔记公式正确显示。' },
        { title: '打印友好', desc: '打印时隐藏交互元素，正文白底，公式可打印。' },
        { title: '移动端适配', desc: '广场/阅读/主页/商城/好友/编辑器在窄屏均无溢出。' },
        { title: '搜索高亮', desc: '文库搜索词在侧栏标题与正文中高亮，自动展开全部分组。' },
      ],
      fixed: [
        { title: '修复登录 500 与旧进程残留', desc: '清除过期后端进程，登录恢复稳定。' },
        { title: '修复首页统计、通知缓存、组件复用不刷新等问题' },
      ],
    },
  },
  {
    version: '0.2.0', date: '2026-08', latest: false,
    summary: '知识库首页全面改版：三套全局主题、精选轮播、科目图谱、AI 助手入口。',
    sections: {
      feat: [
        { title: '三套全局主题（深空星际 / 蓝天大气 / 纯色简约）', desc: '右上角下拉一键切换，全站统一，刷新后记忆选择。' },
        { title: '精选笔记轮播', desc: '最近收录的优质内容自动轮播，点击直达阅读。' },
        { title: '科目图谱横移漫游', desc: '408 四科、数学、英语、政治九大科目下滑横向探索。' },
        { title: 'AI 助手入口', desc: '界面与交互已就绪，模型接入将在下一阶段上线。' },
        { title: '全局导航与更新日志 / 修改记录 / 使用引导', desc: '站点结构更完整。' },
      ],
      improved: [
        { title: '星空背景：流星斜飞、鼠标光晕、渐变流动标题' },
        { title: '文档页统一主题与布局，与首页审美对齐' },
      ],
      fixed: [
        { title: '修复旧版黑夜白天按钮与主题系统不一致的问题' },
        { title: '修复页脚品牌名重复显示' },
      ],
    },
  },
  {
    version: '0.1.0', date: '2026-05', latest: false,
    summary: '考研笔记平台初版：Markdown 文档上传、分类管理与在线预览。',
    sections: {
      feat: [
        { title: '文档上传 / 删除 / 更新', desc: 'Markdown 笔记入库，自动解析章节。' },
        { title: '分类聚合展示', desc: '按科目分类浏览，侧边栏快速定位。' },
        { title: 'Markdown 渲染', desc: '公式、代码高亮、目录大纲支持。' },
        { title: '管理后台', desc: '登录后可上传与管理笔记。' },
      ],
    },
  },
]

const activeVersion = ref(versions[0].version)

// 切换版本时回到页面顶部（版本内容长短不一，避免停留在上一版的滚动位置）
watch(activeVersion, () => window.scrollTo({ top: 0 }))

const collapsedGroups = ref(new Set())
const toggleGroupFold = (label) => {
  const s = new Set(collapsedGroups.value)
  if (s.has(label)) s.delete(label)
  else s.add(label)
  collapsedGroups.value = s
}
const versionGroups = computed(() => {
  // 按主版本号分组（0.2.x / 0.1.x）
  const map = new Map()
  versions.forEach((v) => {
    const major = v.version.split('.').slice(0, 2).join('.')
    if (!map.has(major)) map.set(major, { label: major + '.x', items: [] })
    map.get(major).items.push(v)
  })
  return Array.from(map.values())
})
</script>

<style scoped>
.changelog-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 110px 28px 70px;
  min-height: calc(100vh - 60px);
  box-sizing: border-box;
}
.page-header { text-align: center; margin-bottom: 44px; }
.kicker {
  font-size: 12px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--brand-1); font-weight: 700; margin: 0 0 10px;
}
.title {
  font-size: clamp(30px, 4vw, 46px); font-weight: 800; margin: 0 0 12px;
}
.grad {
  background: var(--kb-grad); background-size: 260% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.desc { color: var(--text2); font-size: 15px; margin: 0; }

.cl-layout {
  display: grid;
  grid-template-columns: 250px 1fr;
  gap: 28px;
  align-items: start;
}
.cl-sidebar {
  position: sticky;
  top: 84px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  box-shadow: var(--shadow-1);
  padding: 18px 14px;
}
.side-label { font-size: 12px; color: var(--text2); margin: 0 6px 12px; font-weight: 600; }
.side-group { margin-bottom: 10px; }
.side-group-label { cursor: pointer; user-select: none; display: flex; align-items: center; justify-content: space-between; }
.fold-caret { font-size: 10px; color: var(--text2); transition: transform .2s; display: inline-block; }
.fold-caret.open { transform: rotate(90deg); }
.side-group-label {
  font-size: 11px; color: var(--text2); margin: 8px 6px 4px;
  letter-spacing: 1px; text-transform: uppercase;
}
.side-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 10px; border-radius: 10px; cursor: pointer;
  transition: background .2s;
}
.side-item:hover { background: var(--btn-bg); }
.side-item.on { background: color-mix(in srgb, var(--brand-1) 12%, transparent); }
.side-ver { font-size: 13.5px; font-weight: 600; color: var(--text1); }
.side-item.on .side-ver { color: var(--brand-1); }
.side-date { font-size: 12px; color: var(--text2); }

.cl-detail { min-width: 0; }
.detail-card {
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  box-shadow: var(--shadow-1);
  padding: 30px 32px;
}
.detail-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
}
.detail-version { font-size: 26px; font-weight: 800; margin: 0; display: flex; align-items: center; gap: 10px; }
.detail-tag {
  font-size: 12px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  padding: 3px 10px; border-radius: 999px;
}
.detail-date { font-size: 13px; color: var(--text2); }
.detail-summary { color: var(--text2); line-height: 1.8; margin: 16px 0 26px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }

.detail-section { margin-bottom: 26px; }
.section-title { margin: 0 0 14px; }
.section-badge {
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
  padding: 5px 13px; border-radius: 999px;
}
.badge-feat { color: #10b981; background: rgba(16, 185, 129, .12); border: 1px solid rgba(16, 185, 129, .3); }
.badge-fixed { color: #ef4444; background: rgba(239, 68, 68, .12); border: 1px solid rgba(239, 68, 68, .3); }
.badge-improved { color: #f59e0b; background: rgba(245, 158, 11, .12); border: 1px solid rgba(245, 158, 11, .3); }

.section-item {
  display: flex; gap: 16px; padding: 14px 16px;
  border-radius: 14px;
  transition: background .2s;
}
.section-item:hover { background: var(--btn-bg); }
.item-no {
  font-size: 12px; font-weight: 700; color: var(--brand-1);
  padding-top: 3px; flex-shrink: 0;
}
.item-body h4 { font-size: 15px; margin: 0 0 5px; color: var(--text1); }
.item-body p { font-size: 13.5px; color: var(--text2); margin: 0; line-height: 1.7; }

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}

@media (max-width: 860px) {
  .cl-layout { grid-template-columns: 1fr; }
  .cl-sidebar { position: static; }
}
</style>