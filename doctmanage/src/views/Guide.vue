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
        <div class="step-body">
          <h3>{{ s.title }}</h3>
          <p>{{ s.desc }}</p>
          <div class="step-tags">
            <span v-for="t in s.tags" :key="t" class="step-tag">{{ t }}</span>
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
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const steps = [
  {
    title: '书房：你的私人笔记库',
    desc: '登录后顶部进入「书房」。左侧是分科目的多级目录（高等数学 → 各章节）；右上角可新建笔记（Markdown 编辑器 + ∑ 49 个 LaTeX 数学符号）、🤖 AI 构建（输入主题 → 生成草稿 → 预览 → 确认入库）、📤 上传（支持 md/pdf/ppt/word/图片/文本，非 md 自动存为附件）、🖌 涂鸦。发布时可设公开/私密、开放下载、收费（知屿币）或仅预览。',
    tags: ['多级目录', 'AI 构建', '多格式上传', '权限设置'],
  },
  {
    title: '阅览室：本次要学的工作台',
    desc: '「阅览室」= 把书房里的笔记（自己写的 + 从广场加入的）挑进来定点学习，按科目分组。在书房每张卡片点「📖 加入阅览室」即可放入；这里右键可「移出阅览室」。左侧导航与右侧大纲可收起展开（沉浸式）；作者本人可直接「✏️ 编辑此页」边看边改。',
    tags: ['右键管理', '沉浸式', '边看边改', '段落书签'],
  },
  {
    title: '笔记广场：微博式逛别人的笔记',
    desc: '「笔记广场」像刷信息流一样浏览公开笔记：点卡片直接阅览；觉得好就点「📥 加入书房」复制一份归你（带「来自广场」角标，可编辑）。分类用胶囊筛选，最热/最新/收藏三档排序。收费笔记显示 💎 徽章，未购买只能预览前 500 字。',
    tags: ['信息流', '分类筛选', '一键添加', '知屿币'],
  },
  {
    title: '阅读批注与成长',
    desc: '阅读页把鼠标移到段落左侧出现 ✎，可写批注、📑 书签、🖼 贴手写图——都挂在具体文字段落后，默认隐藏、点击展开；涂鸦模式支持钢笔/圆珠笔/彩笔。互动赚「知屿币」，商城兑换 AI 额度/置顶/徽章；🔔 收通知，主页看学习热力图。',
    tags: ['段落批注', '贴图', '知屿币', '热力图'],
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

.guide-list { display: flex; flex-direction: column; gap: 14px; }
.guide-step {
  display: flex; gap: 20px;
  padding: 24px 26px;
  border-radius: 18px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  transition: transform .3s, border-color .3s;
}
.guide-step:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--brand-1) 40%, var(--border));
}
.step-no {
  flex-shrink: 0;
  font-size: 15px; font-weight: 800;
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
  padding-top: 3px;
}
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

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}
</style>