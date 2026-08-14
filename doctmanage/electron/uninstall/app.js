// 知屿卸载页 - 渲染进程（毛玻璃窗口，与安装器同款）
const $ = (id) => document.getElementById(id)
const api = window.uninstaller

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'))
  $(id).classList.remove('hidden')
}

// 标题栏
$('btnMin').onclick = () => api.minimize()
$('btnClose').onclick = () => api.close()

// 取消 = 关闭窗口
$('btnCancel').onclick = () => api.close()

// 显示安装目录
;(async () => {
  try {
    const root = await api.getRoot()
    if (root) $('rootDir').textContent = root
  } catch (e) { /* 忽略 */ }
})()

// 确认卸载 → 进挽留页
$('btnConfirm').onclick = () => showPage('pageRetain')

// 挽留页：再想想 = 关闭
$('btnRetainStay').onclick = () => api.close()
// 挽留页：改用网页版
$('btnWeb').onclick = () => api.openWeb('http://182.254.209.123/zhiyu/')

// 挽留页：仍要卸载 → 执行卸载
$('btnRetainGo').onclick = async () => {
  showPage('pageProgress')
  $('progressTxt').textContent = '正在删除程序文件…'
  $('progressFill').style.width = '55%'
  $('progressPct').textContent = '55%'
  const purge = $('optPurge').checked
  try {
    await api.uninstall({ purgeUserData: purge })
  } catch (e) { /* 忽略 */ }
  $('progressFill').style.width = '100%'
  $('progressPct').textContent = '100%'
  $('progressTxt').textContent = '清理完成'
  setTimeout(() => showPage('pageDone'), 350)
}

// 完成 → 后台延迟删除整个安装目录（含自身）后退出
$('btnFinish').onclick = () => api.finishUninstall()
