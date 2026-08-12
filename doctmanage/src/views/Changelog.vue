<!-- 更新日志：版本档案，记录知屿的迭代历史 -->
<template>
  <div class="changelog-page">
    <div class="page-header">
      <p class="kicker">CHANGELOG</p>
      <h1 class="title">更新<span class="grad">日志</span></h1>
      <p class="desc">知屿知识库的每一次迭代，都记录在这里。</p>
    </div>

    <div class="cl-layout">
      <div class="arch-wrap">
        <!-- 移动端：展开版本档案 -->
        <button class="arch-toggle" @click="archOpen = !archOpen">📦 版本档案 <span class="fold-caret" :class="{ open: archOpen }">▸</span></button>
        <!-- 左栏：版本档案 -->
        <aside class="cl-sidebar" :class="{ open: archOpen }">
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
                @click="pickVersion(v)"
              >
                <span class="side-ver">v{{ v.version }}</span>
                <span class="side-date">{{ v.date }}</span>
              </div>
            </div>
          </div>
        </aside>
      </div>

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

// 移动端：版本档案默认收起，点按钮展开
const archOpen = ref(false)

const CAT = { feat: '新功能', fixed: '修复', improved: '改进' }
const catLabel = (k) => CAT[k] || k

const versions = [
  {
    version: '1.3.0', date: '2026-08-12', latest: true,
    summary: '协议入口完善：条款链接直达首页页脚、协议页返回按钮、更新日志移动端修复。',
    sections: {
      improved: [
        { title: '协议页面返回按钮', desc: '服务条款 / 隐私协议页面新增「← BACK」返回按钮（与设置页同款），点击返回上一页，不再固定跳回登录页。' },
        { title: '首页页脚新增条款链接', desc: '首页底部新增「服务条款」「隐私协议」链接，直达 /terms 与 /privacy 页面。' },
      ],
      fixed: [
        { title: '修复更新日志移动端文字溢出', desc: '更新日志详情条目在窄屏下长文本撑破卡片边框、页面横向溢出；修复 flex 子项收缩与长文本断行（min-width/overflow-wrap），移动端卡片与页面间距同步适配。' },
      ],
    },
  },
  {
    version: '1.2.0', date: '2026-08-12', latest: false,
    summary: '后端架构拆分 + 阅览室侧栏平滑 + 平板首页布局修复。',
    sections: {
      improved: [
        { title: '侧栏收起/展开平滑化', desc: '阅览室左右侧栏收起/展开不再跳变：grid 列宽改为显式尺寸并由 grid-template-columns 过渡驱动，收起为窄条、展开恢复 280px 全程平滑伸缩，与右侧大纲栏体验一致。' },
        { title: '后端代码按功能拆分', desc: '单文件 app.py（约 3600 行）拆分为共享层（config/db/auth/utils/shared）+ routes/ 九个蓝图（auth/docs/notes/users/social/messages/ai/misc/annotations），入口与启动方式不变，接口行为经全链路回归保持一致。' },
        { title: '积分体系更名「知屿币」', desc: '积分商城改为知屿币商城，全站「积分」统一更名「知屿币」（首页今日概览、个人主页、好友列表、商城余额/明细/兑换、AI 额度提示等）；内部数据结构与接口字段保持不变，余额自动沿用原积分。' },
        { title: '首页最近更新改双行跑马灯', desc: '笔记较多时「最近更新」升级为精选笔记同款卡片墙：双行反向循环滚动（第一行向右、第二行向左）、持续滚动不因悬停暂停、左右淡出遮罩、速度随卡片数自适应（偏慢）；卡片不足 8 篇时保留原列表。' },
        { title: '首页移动端改版', desc: '手机端 hero 精简：删除搜索框与统计卡，改为「开始探索知屿」按钮（未登录跳登录页、已登录直达笔记广场）；副标题加长文案；最近更新跑马灯上移到 hero 文字下方；桌面端布局保持不变。' },
        { title: '登录页新增条款勾选与协议页面', desc: '注册时需勾选「我已阅读并同意《服务条款》和《隐私协议》」，条款文字加粗高亮；移动端点按弹出全屏条款弹窗，PC 端跳转独立页面（/terms 与 /privacy），正文完整丰富，覆盖账号、内容、AI 助手、知屿币、隐私等条款。' },
      ],
      fixed: [
        { title: '修复平板端科目图谱与能力版图间距过大', desc: '平板宽度下科目图谱仍占用桌面版 280vh 滚动漫游空间，导致与下方能力版图之间隔出大片空白；平板断点改为普通区块，图谱与能力版图紧邻，桌面端下滑漫游不受影响。' },
      ],
    },
  },
  {
    version: '1.1.0', date: '2026-08-12', latest: false,
    summary: '移动端体验集中优化：阅览室平板大纲、编辑器顶部精简、书房布局、广场搜索、更新日志档案交互。',
    sections: {
      improved: [
        { title: '阅览室平板端大纲栏与 PC 一致', desc: '平板宽度（≥960px）右侧大纲栏直接显示，不再替换为顶部大纲按钮；默认展开、收起为窄条，刷新后不残留窄条。' },
        { title: '左侧栏收起窄条精简为图标', desc: '收起后窄条只留侧栏图标、去掉竖排文字，与右侧窄条保持一致的干净样式。' },
        { title: '编辑器移动端顶部精简', desc: '移动端隐藏全局导航（页面自带「← 返回」）；顶部改为「返回 + 标题 + 保存」一行、分类 + 私密/公开一行；工具栏单行横滑不再换行错位，块公式按钮精简为「块公式」，源码按钮固定同行。' },
        { title: '书房移动端布局优化', desc: '关注 / 私信 / 商城移到「我的书房」标题右侧（右上小字、右下三链接）；☰ 抽屉按钮与「新建笔记」对齐、打开/关闭同款按钮；侧边栏抽屉毛玻璃半透明。' },
        { title: '笔记广场移动端搜索同一排', desc: '搜索框与「刷新」按钮同行，搜索框弹性占满剩余宽度，不再换行。' },
        { title: '更新日志移动端档案交互', desc: '选中版本后档案面板自动收起；面板紧贴「📦 版本档案」按钮下方。' },
        { title: '首页科目图谱移动端横移不滚页', desc: '触摸左右滑动图谱时锁定页面上下滚动、图谱跟手；桌面下滑漫游保持不变。' },
      ],
      fixed: [
        { title: '修复左侧栏展开/收起跳变与文字残影', desc: '左侧栏改为与右侧栏同构：内容 v-if 切换、sticky 内容 + 宽度过渡，展开不再上下跳动、收起不再残留文字残影。' },
      ],
    },
  },
  {
    version: '1.0.0', date: '2026-08-12', latest: false,
    summary: '品牌焕新：知屿正式定名 + 葫芦图标 + 手机端首页 App 化 + 分享链接脱敏。',
    sections: {
      feat: [
        { title: '品牌焕新：站名「知屿」+ 全新图标', desc: '网站标题正式定为「知屿」；葫芦线条图标（8 字去右上弧 + 底胖 + 蒂右弯）作为 favicon 与导航栏 logo 统一使用，深蓝渐变背景、居中完整显示。' },
        { title: '首页手机端 App 化改版', desc: '紧凑 hero（徽章 + 标题 + 搜索 + 今日概览 + 统计卡）、2×2 功能宫格（图标 + 标题居中）、精选笔记移至下滑可见，胶囊收窄、间距透气。' },
        { title: '分享链接脱敏', desc: '文档 / 笔记 / 用户页 URL 改用短 public_id 标识，不再暴露数字 id 与中文 slug；旧数字 id / 用户名链接不再兼容。' },
      ],
      improved: [
        { title: '统计卡居中微调', desc: '手机端统计卡整体左移 10px，视觉更居中。' },
      ],
      fixed: [
        { title: '修复 favicon 被裁切只剩左上角', desc: 'SVG 缺 width/height 导致浏览器按默认尺寸渲染取左上角；ico 路径坐标未按尺寸缩放导致线条画在画布外——均已修复，三端（favicon / ico / 导航栏）图形统一完整。' },
      ],
    },
  },
  {
    version: '0.9.0', date: '2026-08-12', latest: false,
    summary: '沉浸式阅读全面丝滑：一帧切换、只隐藏必要元素、导航栏固定置顶。',
    sections: {
      feat: [
        { title: '沉浸切换一帧完成', desc: '笔记广场 / 笔记阅读页 / 阅览室移除过渡动画，点沉浸直接瞬切，与 docs 页一致的轻量体验。' },
        { title: '沉浸只隐藏必要元素', desc: '阅读页沉浸仅隐藏右侧大纲栏，头部/操作栏/评论区保留；导航栏隐藏后内容自动向上补齐原空位。' },
      ],
      improved: [
        { title: '全局导航栏固定置顶', desc: '所有页面下滑时导航栏保持置顶不动，仅沉浸模式隐藏。' },
      ],
      fixed: [
        { title: '修复阅读页沉浸卡顿', desc: '移除 .reader-page 的 padding 过渡动画，沉浸切换从 0.3s 动画变为一帧完成。' },
      ],
    },
  },
  {
    version: '0.9.1', date: '2026-08-12', latest: false,
    summary: '侧栏与导航体验打磨 + 首页图谱横移回归：抽屉式丝滑动画、导航高亮修复、平板图谱左右滑动探索、悬浮球跨平台统一。',
    sections: {
      improved: [
        { title: '阅览室侧栏抽屉式丝滑', desc: '左右侧栏收起/展开不再跳变、不卡顿：内容常驻 DOM（连续点击不重建）、头部固定高度防止卡片上下跳动、动画启动不再停顿一帧；平板收起两侧栏后正文保持居中、展开不再遮挡侧栏。' },
        { title: '平板/手机首页科目图谱改为普通区块', desc: '触摸设备上图谱不再占用 280vh 滚动空间：下滑正常滚动直达下方内容，图谱区左右滑动探索，进度条随滑动同步；与精选笔记间距拉开。' },
        { title: '悬浮球与 AI 助手头像统一线条机器人图标', desc: '用内联 SVG 替代 🤖 emoji，消除 Android 平板把机器人渲染成方块的差异，全平台图标一致。' },
      ],
      fixed: [
        { title: '修复首页「下滑仅横移」失效', desc: '某次改动给首页容器加的 overflow-x:hidden 会破坏内部 sticky 定位，导致 PC 下滑时图谱不固定、页面跟着滚；改用 overflow-x:clip 后恢复：PC 端下滑驱动图谱横向平移，图谱不再随页面滚走。' },
        { title: '修复导航栏高亮不亮', desc: '阅览室（/docs/:key）、笔记广场（/notes/:key）等带参数子路由下，父入口导航项因路由 name 不匹配不显示高亮；改为按路径匹配，子路由下父入口正常点亮。' },
        { title: '修复侧栏收起后窄条消失', desc: '侧栏内容常驻后窄条按钮被 flex 排列挤出视口，改为绝对定位覆盖，收起后窄条始终可见可点。' },
        { title: '修复点击侧栏按钮闪现蓝色高亮', desc: '收起/展开按钮点击瞬间闪现浏览器默认焦点框与触屏高亮，统一去掉 outline 并禁用 tap-highlight。' },
      ],
      feat: [
        { title: '左侧窄条加「导航」文字', desc: '与右侧窄条「大纲」一致，收起后竖排文字标识。' },
        { title: '笔记广场移除多余沉浸按钮', desc: '广场列表页不再显示沉浸按钮（阅读页 / 阅览室保留）。' },
      ],
    },
  },
  {
    version: '0.8.0', date: '2026-08-11', latest: false,
    summary: '阅览室体验优化：大纲自绘面板、加载态简洁、移动端正文铺满。',
    sections: {
      feat: [
        { title: '大纲改为自绘固定面板', desc: '替代 el-popover：fixed 定位不跳出屏幕、滚动自动关闭，不再错位。' },
        { title: '上一篇/下一篇等正文就绪再显示', desc: '加载中只显示「加载中…」，正文渲染完成才出现前后翻页，与笔记页时序一致。' },
      ],
      improved: [
        { title: '加载态简洁化', desc: '去掉骨架屏占位条的跳动，统一为「加载中…」文字。' },
        { title: '移动端正文铺满', desc: '手机端去掉卡片围边与边框，正文铺满屏幕。' },
      ],
    },
  },
  {
    version: '0.7.0', date: '2026-08-11', latest: false,
    summary: '阅读页体验升级：代码块深色高亮、选中文字定位评论、自定义删除确认。',
    sections: {
      feat: [
        { title: '代码块深色高亮', desc: 'github-dark 主题 + 深色代码块背景，长代码不再白底浅字看不清。' },
        { title: '选中文字定位评论', desc: '选中正文文字弹出「📍 定位到评论」浮层，直接定位评论锚点，替代评论区按钮。' },
        { title: '删除评论自定义确认框', desc: '删除评论改用站内主题确认弹窗，不再使用浏览器原生弹窗。' },
        { title: '一键回到顶部 / 底部', desc: '右下角悬浮按钮，点击平滑跳转到页面顶部或底部。' },
      ],
    },
  },
  {
    version: '0.6.0', date: '2026-08-11', latest: false,
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

// 选择版本：移动端选中后自动收起档案面板
const pickVersion = (v) => {
  activeVersion.value = v.version
  if (window.innerWidth <= 860) archOpen.value = false
}

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
.arch-wrap { min-width: 0; }
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
  min-width: 0;
}
.section-item:hover { background: var(--btn-bg); }
.item-no {
  font-size: 12px; font-weight: 700; color: var(--brand-1);
  padding-top: 3px; flex-shrink: 0;
}
.item-body { min-width: 0; flex: 1; }
.item-body h4 { font-size: 15px; margin: 0 0 5px; color: var(--text1); }
.item-body p { font-size: 13.5px; color: var(--text2); margin: 0; line-height: 1.7; overflow-wrap: break-word; word-break: break-word; }

@keyframes grad-flow {
  0% { background-position: 0% 50%; filter: hue-rotate(0deg); }
  100% { background-position: 100% 50%; filter: hue-rotate(22deg); }
}

/* 移动端展开版本档案按钮（仅 ≤860px 显示） */
.arch-toggle {
  display: none;
  align-items: center; gap: 8px;
  border: 1px solid var(--border); background: var(--card-bg);
  color: var(--text1); font-size: 14px; font-weight: 700;
  padding: 10px 16px; border-radius: 12px; cursor: pointer;
  box-shadow: var(--shadow-1); margin-bottom: 14px;
}
.arch-toggle:hover { color: var(--brand-1); }

@media (max-width: 860px) {
  .changelog-page { padding: 100px 16px 60px; }
  .page-header { margin-bottom: 28px; }
  .detail-card { padding: 20px 18px; }
  .section-item { gap: 12px; padding: 12px 12px; }
  .cl-layout { grid-template-columns: 1fr; gap: 16px; }
  .arch-wrap { display: flex; flex-direction: column; }
  .arch-toggle { display: flex; margin-bottom: 0; box-shadow: none; }
  /* 版本档案默认收起（不顶到页面顶部），点按钮展开；面板紧贴按钮下方 */
  .cl-sidebar {
    position: static;
    display: none;
    border-radius: 14px;
  }
  .cl-sidebar.open { display: block; }
}
</style>