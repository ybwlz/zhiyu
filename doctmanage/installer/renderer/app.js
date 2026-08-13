// 知屿自绘安装器 - 渲染进程
const $ = (id) => document.getElementById(id)

const api = window.installer

let theme = 'starlight'
let targetDir = ''
let installDoneDir = ''

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'))
  $(id).classList.remove('hidden')
}

// 标题栏
$('btnMin').onclick = () => api.minimize()
$('btnMax').onclick = () => api.toggleMax()
$('btnClose').onclick = () => api.close()

// ① 欢迎 → 预览
$('btnNext').onclick = () => showPage('pagePreview')
// ② 预览页
$('btnPvBack').onclick = () => showPage('pageWelcome')
$('btnPvNext').onclick = () => showPage('pageTheme')

// ③ 主题选择（树状三排）
document.querySelectorAll('.theme-row').forEach(row => {
  row.onclick = () => {
    document.querySelectorAll('.theme-row').forEach(r => r.classList.remove('on'))
    row.classList.add('on')
    theme = row.dataset.theme
  }
})
$('btnThBack').onclick = () => showPage('pagePreview')
$('btnThNext').onclick = async () => {
  targetDir = await api.getDefaultDir()
  $('dirInput').value = targetDir
  showPage('pageConfig')
}

// ④ 配置页
$('btnBack').onclick = () => showPage('pageTheme')
// 浏览选择安装目录（自动补 \知屿 子目录）
$('btnBrowse').onclick = async () => {
  const dir = await api.chooseDir()
  if (dir) {
    const clean = dir.replace(/[\\/]+$/, '')
    const parts = clean.split(/[\\/]/)
    const last = parts[parts.length - 1]
    targetDir = last === '知屿' ? clean : clean + '\\知屿'
    $('dirInput').value = targetDir
  }
}
// 条款勾选控制安装按钮
$('optAgree').onchange = () => {
  $('btnInstall').disabled = !$('optAgree').checked
}

// 条款弹窗
const TERMS = [
  '一、账号与安全',
  '1. 你负责自己账号的安全，请勿共享密码，发现异常及时修改。',
  '2. 每个账号对应独立的笔记与数据，请妥善保管登录信息。',
  '',
  '二、内容与版权',
  '1. 你的笔记内容归你所有（私密笔记仅自己可见；公开笔记会展示在笔记广场）。',
  '2. 请勿发布违反法律法规、侵犯他人权益的内容。',
  '',
  '三、AI 助手',
  '1. AI 生成内容仅供参考，不构成任何专业建议。',
  '2. AI 使用计入免费额度，超出后可前往知屿币商城兑换。',
  '',
  '四、服务说明',
  '1. 知屿为云端服务，数据存储于服务器，请勿存放极端敏感信息。',
  '2. 服务可能调整或升级，我们会尽力提前通知。',
  '3. 完整条款见官网：www.zhiyur.cn。',
]
const PRIVACY = [
  '一、我们收集的信息',
  '1. 账号信息：用户名、邮箱（仅用于登录与找回）。',
  '2. 内容数据：你创建的笔记、收藏、批注。',
  '3. 使用日志：访问时间、操作记录（用于安全与优化）。',
  '',
  '二、信息的使用',
  '1. 仅用于提供、维护与改进知屿服务。',
  '2. 不会向任何第三方出售或出租你的数据。',
  '',
  '三、信息的存储与保护',
  '1. 数据加密存储于服务器，传输使用加密通道。',
  '2. 你可以随时删除自己的笔记与账号。',
  '',
  '四、你的权利',
  '1. 可随时导出或删除自己的数据。',
  '2. 对本协议有疑问可联系我们。',
  '3. 完整协议见官网：www.zhiyur.cn。',
]
function openTerms(type) {
  $('termsTitle').textContent = type === 'terms' ? '服务条款' : '隐私协议'
  $('termsBody').innerHTML = (type === 'terms' ? TERMS : PRIVACY)
    .map(line => line.startsWith('一') || line.startsWith('二') || line.startsWith('三') || line.startsWith('四')
      ? '<div class="t-sec">' + line + '</div>'
      : '<div class="t-line">' + line + '</div>')
    .join('')
  $('termsBody').scrollTop = 0 // 每次打开都从顶部开始
  $('termsModal').classList.remove('hidden')
}
$('linkTerms').onclick = (e) => { e.preventDefault(); openTerms('terms') }
$('linkPrivacy').onclick = (e) => { e.preventDefault(); openTerms('privacy') }
$('btnTermsClose').onclick = () => $('termsModal').classList.add('hidden')
$('termsModal').addEventListener('click', (e) => { if (e.target === $('termsModal')) $('termsModal').classList.add('hidden') })

// ⑤ 安装
$('btnInstall').onclick = async () => {
  showPage('pageInstall')
  const result = await api.install({
    targetDir,
    theme,
    autoStart: $('optAutoStart').checked,
    createShortcut: $('optShortcut').checked,
  })
  if (result && result.ok) {
    installDoneDir = result.target
    setTimeout(() => { $('doneDir').textContent = '已安装到：' + installDoneDir; showPage('pageDone') }, 600)
  }
}

// 进度
api.onProgress(({ stage, pct, msg }) => {
  $('progressFill').style.width = pct + '%'
  $('progressPct').textContent = pct + '%'
  if (msg) $('progressTxt').textContent = msg
})

// ⑥ 完成
$('btnLaunch').onclick = () => { api.launchApp(installDoneDir); api.close() }
$('btnFinish').onclick = () => api.close()
