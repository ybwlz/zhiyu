<!-- 使用引导：如何高效使用知屿知识库 -->
<template>
  <div class="guide-page">
    <div class="page-header">
      <p class="kicker">GUIDE</p>
      <h1 class="title">使用<span class="grad">引导</span></h1>
      <p class="desc">三步上手知屿，把散落的笔记收进一座知识库。</p>
    </div>

    <div class="guide-list">
      <div class="guide-step" v-for="(s, i) in steps" :key="s.title">
        <div class="step-no">{{ String(i + 1).padStart(2, '0') }}</div>
        <div class="step-content" :ref="el => collectStep(el, i)">
          <div class="step-branch"></div>
          <div class="step-body">
            <h3>{{ s.title }}</h3>
            <p>{{ s.desc }}</p>
            <div class="step-tags">
              <span v-for="t in s.tags" :key="t" class="step-tag">{{ t }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="tips">
      <h3 class="tips-title">💡 小贴士</h3>
      <ul class="tips-list">
        <li v-for="tip in tips" :key="tip">{{ tip }}</li>
      </ul>
    </div>

    <!-- 底部浅色渐变：滚动时内容从底部柔和淡出 -->
    <div class="guide-fade"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 参天大树滚动动效：以视口中心为准，中间步骤最实，越远离中心越透明并横向滑出（上方往左、下方往右）
const stepEls = []
const collectStep = (el, i) => { if (el) stepEls[i] = el }
let rafId = null
const updateSteps = () => {
  const vh = window.innerHeight
  const mid = vh / 2
  const maxDist = vh * 0.62
  for (const el of stepEls) {
    if (!el) continue
    const r = el.getBoundingClientRect()
    const c = r.top + r.height / 2
    const dist = Math.abs(c - mid)
    const p = Math.max(0, Math.min(1, 1 - dist / maxDist))
    const dir = c < mid ? -1 : 1
    el.style.opacity = String(0.05 + 0.95 * p)
    el.style.transform = 'translateX(' + ((1 - p) * dir * 56).toFixed(1) + 'px)'
  }
}
const onScroll = () => {
  if (rafId) return
  rafId = requestAnimationFrame(() => { rafId = null; updateSteps() })
}
onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  updateSteps()
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
  if (rafId) cancelAnimationFrame(rafId)
})

const steps = [
  {
    title: '书房：你的私人笔记库',
    desc: '登录后顶部进入「书房」。左侧是分科目的多级目录（高等数学 → 各章节），右键笔记可打开/编辑/删除；右上角可新建笔记（Markdown 编辑器）、🤖 AI 构建（输入主题 → 生成草稿 → 预览 → 确认入库）、📤 上传（支持 md/pdf/ppt/word/图片/文本，非 md 自动存为附件）、🖌 涂鸦。发布时可设公开/私密、开放下载、收费（知屿币）或仅预览。',
    tags: ['多级目录', '右键管理', 'AI 构建', '多格式上传', '权限设置'],
  },
  {
    title: '编辑器：Markdown + LaTeX 双栏写作',
    desc: '编辑器左侧源码、右侧实时预览：∑ 工具栏一键插入 49 个 LaTeX 数学符号，公式用 $...$ 行内 / $$...$$ 独立（MathJax 渲染）；支持表格、代码块（语法高亮）、图片、批注与涂鸦。内容自动暂存到本机（防刷新丢失），「← 返回」按来源跳回书房/阅览室/笔记页。',
    tags: ['LaTeX 公式', '实时预览', '代码高亮', '自动暂存'],
  },
  {
    title: '阅览室：本次要学的工作台',
    desc: '「阅览室」= 把书房里的笔记（自己写的 + 从广场加入的）挑进来定点学习，按科目分组。在书房每张卡片点「📖 加入阅览室」即可放入；这里右键可「移出阅览室」。左侧导航与右侧大纲可收起展开（沉浸式）；作者本人可直接「✏️ 编辑此页」边看边改，切换笔记后自动回到顶部。',
    tags: ['右键管理', '沉浸式', '边看边改', '右侧大纲'],
  },
  {
    title: '笔记广场：逛别人的公开笔记',
    desc: '「笔记广场」像刷信息流一样浏览公开笔记：点卡片直接阅览，点 💬 直接跳到评论区；觉得好就点「📥 加入书房」复制一份归你（带「来自广场」角标，可编辑）。分类用胶囊筛选，最热/最新/收藏三档排序。收费笔记显示 💎 徽章，未购买只能预览前 500 字。',
    tags: ['信息流', '分类筛选', '一键添加', '点赞可取消'],
  },
  {
    title: 'AI 助手：全站智能体',
    desc: '右上角 🤖 AI 助手全站可用：回答知识库问题（优先检索你的笔记）、联网搜索实时信息；在编辑器/阅览室可直接帮你改笔记——修改以红绿 diff 展示，逐条接受或拒绝，也可让 AI 改标题、新建笔记（带分类）或搜笔记跳转。额度用完可去知屿币商城兑换。',
    tags: ['检索问答', '联网搜索', '红绿 diff', '改标题/建笔记'],
  },
  {
    title: '阅读批注与互动',
    desc: '阅读页把鼠标移到段落左侧出现 ✎，可写批注、📑 书签、🖼 贴手写图——都挂在具体文字段落后；选中文字可「引用」定位到评论。点赞（再点取消）、收藏、评论（可删除自己的）、评分都能赚「知屿币」。',
    tags: ['段落批注', '引用评论', '点赞/评分', '赚知屿币'],
  },
  {
    title: '知屿币商城与通知',
    desc: '互动获得的「知屿币」去「商城」兑换：AI 助手次数、笔记置顶、个性徽章等。🔔 顶部收通知（被赞、被评论、被回复、私信、系统公告）；「好友」管理关系、发私信（AI 也能帮你发）。',
    tags: ['知屿币', 'AI 额度兑换', '通知', '私信'],
  },
  {
    title: '个性化与成长',
    desc: '右上角切换三套主题（深空星际/蓝天大气/纯色简约）；「设置」页管理资料、换头像、改密码；个人主页有学习热力图（近 90 天阅读分布）、贡献统计与公开笔记。每天阅读、评分、互动都会沉淀为你的知识资产。',
    tags: ['三套主题', '设置页', '学习热力图', '成长记录'],
  },
]

const tips = [
  'AI 助手（右上角 🤖）全站可用：既回答知识库相关问题，也能在书房帮你构建整篇笔记（生成 → 预览 → 确认）。',
  '公式在阅览室、在线阅读、编辑器三处均已接入 MathJax 渲染；打印页面自动隐藏导航与按钮，公式正常输出。',
  '公开笔记默认可下载、可添加；作者可设「收费 N 知屿币」或「仅预览」，未购买者只能看到前 500 字。',
  '批注/书签挂在具体文字后：默认只显示小标记，点击展开内容；选中文字再点「📑 加书签」最快。',
  '搜索框关键词会同时高亮阅览室侧栏与正文匹配内容，并自动展开全部分组。',
  '「修改记录」只记录你自己的笔记变更；三套主题右上角一键切换，全站生效并记住选择。',
]
</script>

<style scoped>
.guide-page {
  max-width: 820px;
  margin: 0 auto;
  padding: 110px 28px 70px;
  overflow-x: hidden; /* 防止内容横向溢出把页面往右撑 */
}
.page-header { text-align: center; margin-bottom: 44px; }
.kicker {
  font-size: 12px; letter-spacing: 3px; text-transform: uppercase;
  color: var(--brand-1); font-weight: 700; margin: 0 0 10px;
}
.title { font-size: clamp(30px, 4vw, 46px); font-weight: 800; margin: 0 0 12px; }
.grad {
  background: var(--kb-grad); background-size: 260% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: grad-flow 10s ease-in-out infinite alternate;
}
.desc { color: var(--text2); font-size: 15px; margin: 0; }

/* ── 树干 + 树枝布局 ── */
.guide-list { position: relative; display: flex; flex-direction: column; gap: 28px; }
/* 树干：贯穿左侧的细长竖线 */
.guide-list::before {
  content: ''; position: absolute; left: 19px; top: 26px; bottom: 26px;
  width: 2px; border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-1), color-mix(in srgb, var(--brand-2) 55%, transparent));
}
.guide-step { display: flex; align-items: flex-start; gap: 0; position: relative; }
/* 节点：树干上的圆形数字 */
.step-no {
  flex-shrink: 0; width: 40px; height: 40px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 800; color: #fff;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  box-shadow: 0 0 0 4px var(--bg), var(--shadow-1);
}
/* 内容：树枝横线 + 卡片 */
.step-content { flex: 1; display: flex; align-items: flex-start; gap: 16px; min-width: 0; }
.step-branch {
  width: 34px; height: 2px; flex-shrink: 0; margin-top: 20px; border-radius: 2px;
  background: linear-gradient(90deg, var(--brand-1), color-mix(in srgb, var(--brand-1) 35%, transparent));
}
.step-body {
  flex: 1; min-width: 0;
  padding: 22px 24px; border-radius: 18px;
  background: var(--card-bg); border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  transition: transform .3s, border-color .3s, box-shadow .3s;
}
.step-body:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--brand-1) 40%, var(--border));
  box-shadow: var(--shadow-1);
}
/* 滚动驱动动效：opacity/transform 由 JS 按视口位置连续设置（参天大树：中间实、两侧淡出滑移） */
.guide-step .step-content { will-change: transform, opacity; }
.step-body h3 { font-size: 18px; margin: 0 0 8px; color: var(--text1); }
.step-body p { font-size: 14.5px; line-height: 1.8; color: var(--text2); margin: 0 0 12px; }
.step-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.step-tag {
  font-size: 12px; color: var(--brand-1);
  background: color-mix(in srgb, var(--brand-1) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--brand-1) 28%, transparent);
  padding: 4px 11px; border-radius: 999px;
}

.tips {
  margin-top: 30px;
  padding: 24px 26px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--brand-1) 6%, var(--card-bg));
  border: 1px solid color-mix(in srgb, var(--brand-1) 22%, var(--border));
}
.tips-title { margin: 0 0 12px; font-size: 16px; }
.tips-list { margin: 0; padding-left: 20px; color: var(--text2); font-size: 14px; line-height: 2; }

/* 底部浅色渐变：固定于视口底部，内容滚入时柔和淡出（不拦截点击） */
.guide-fade {
  position: fixed; left: 0; right: 0; bottom: 0; height: 96px;
  pointer-events: none; z-index: 5;
  background: linear-gradient(180deg, transparent, var(--bg) 88%);
}

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}
</style>