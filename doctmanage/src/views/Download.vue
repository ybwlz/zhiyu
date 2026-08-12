<!-- 知屿桌面版下载页 -->
<template>
  <div class="download-page">
    <div class="page-header">
      <p class="kicker">DOWNLOAD</p>
      <h1 class="title">知屿<span class="grad">桌面版</span></h1>
      <p class="desc">Windows 客户端 · 本地渲染 · 一键连接云端知识库</p>
    </div>

    <!-- 桌面版：已安装，无需下载（Electron 中隐藏下载区） -->
    <div v-if="isDesktop" class="dl-card dl-card-installed">
      <div class="dl-ok">✅</div>
      <h2 class="dl-name">你正在使用知屿桌面版</h2>
      <p class="dl-hint">无需下载安装包，直接使用即可；网页版与桌面版数据实时同步。</p>
    </div>

    <div v-else class="dl-card">
      <div class="dl-logo">
        <svg viewBox="0 0 64 64" width="56" height="56">
          <defs>
            <linearGradient id="dlg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#3b82f6" />
              <stop offset="1" stop-color="#2563eb" />
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="64" height="64" rx="14" fill="url(#dlg)" />
          <path d="M31 7 C 37 7, 39 11, 34 16 A 10 10 0 0 0 34 36 A 16 16 0 0 0 34 58 A 16 16 0 0 0 34 26"
            fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </div>
      <h2 class="dl-name">知屿 · Windows 客户端</h2>
      <p class="dl-meta">版本 v1.2.0 · 2026-08-12 · 约 200MB</p>
      <a class="dl-btn desktop-only" :href="downloadUrl" download>
        ⬇ 下载 Windows 版
      </a>
      <p class="dl-hint desktop-only">下载后解压，双击「知屿.exe」即可使用</p>
      <!-- 移动端提示：不提供客户端下载，引导用网页版 -->
      <div class="dl-mobile-tip">
        📱 移动端无需下载客户端<br />
        直接用浏览器访问网页版即可，功能与桌面版完全一致。
      </div>
    </div>

    <div class="dl-grid">
      <div class="dl-item">
        <div class="dl-ico">⚡</div>
        <h3>本地渲染</h3>
        <p>公式、代码高亮全部本地计算，翻页不卡顿，离线也能看。</p>
      </div>
      <div class="dl-item">
        <div class="dl-ico">☁️</div>
        <h3>云端同步</h3>
        <p>打开即连接云端服务器，与网页版数据完全一致，多端无缝切换。</p>
      </div>
      <div class="dl-item">
        <div class="dl-ico">🔒</div>
        <h3>服务可切换</h3>
        <p>exe 同目录放 config.json 即可切换服务器地址，本地调试/云端使用都方便。</p>
      </div>
    </div>

    <div class="dl-steps">
      <h3 class="dl-sec-title">📦 安装步骤</h3>
      <ol class="dl-steps-list">
        <li>点击上方「下载 Windows 版」，得到压缩包（约 200MB）；</li>
        <li>解压到任意目录（建议 D 盘或桌面文件夹）；</li>
        <li>双击文件夹里的「知屿.exe」启动；</li>
        <li>若 Windows 提示「无法验证发布者」：点「更多信息」→「仍要运行」即可（未签名软件的默认提示，不影响使用）；</li>
        <li>用网页版同一账号登录，即可同步全部笔记。</li>
      </ol>
    </div>

    <div class="dl-steps" v-if="!isDesktop">
      <h3 class="dl-sec-title">⚠️ 被 Windows「智能应用控制」拦截？</h3>
      <p class="dl-text">新版 Windows 的「智能应用控制」会直接阻止无法验证发布者的应用（包括知屿下载器/客户端）。</p>
      <button class="sacl-toggle" type="button" @click="showSacl = !showSacl">{{ showSacl ? '收起步骤 ▲' : '查看关闭步骤 ▼' }}</button>
      <div v-show="showSacl" class="sacl-steps">
        <div class="sacl-step" v-for="(s, i) in saclSteps" :key="i">
          <div class="sacl-no">{{ i + 1 }}</div>
          <div class="sacl-body">
            <p class="sacl-text">{{ s.text }}</p>
            <img class="sacl-img" :src="s.img" :alt="s.text" loading="lazy" />
          </div>
        </div>
        <p class="dl-warn">⚠️ 智能应用控制一旦关闭将无法重新开启（除非重装系统）。关闭后下载器/客户端即可正常运行。</p>
      </div>
    </div>

    <div class="dl-steps" v-if="!isDesktop">
      <h3 class="dl-sec-title">🛠 服务器配置（可选）</h3>
      <p class="dl-text">默认已连接知屿云端服务器，无需任何配置。如需切换服务器，在 exe 同目录新建 <code>config.json</code>：</p>
      <pre class="dl-code">{ "backend": "http://182.254.209.123" }</pre>
      <p class="dl-text">改成本地地址 <code>http://localhost:5000</code> 即可连接本地调试后端。</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const downloadUrl = 'http://182.254.209.123/downloads/zhiyu-win32-x64.zip'
// Electron 桌面版：隐藏下载入口，显示已安装提示
const isDesktop = typeof document !== 'undefined' && document.documentElement.classList.contains('desktop-electron')
const showSacl = ref(true) // 默认展开，用户打开即可看到关闭步骤
// 智能应用控制关闭步骤（图片来自 public/sacl-guide/）
const saclSteps = [
  { text: '打开 Windows 安全中心', img: './sacl-guide/sacl-1.png' },
  { text: '进入「应用和浏览器控制」页面', img: './sacl-guide/sacl-2.png' },
  { text: '打开「智能应用控制」设置', img: './sacl-guide/sacl-3.png' },
  { text: '点击「关闭」按钮', img: './sacl-guide/sacl-4.png' },
]
</script>

<style scoped>
.download-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 56px 24px 80px;
}
.page-header { text-align: center; margin-bottom: 40px; }
.kicker {
  font-size: 12px; letter-spacing: 3px; color: var(--brand-1, #3b82f6);
  text-transform: uppercase; margin: 0 0 10px; font-weight: 700;
}
.title { font-size: 34px; margin: 0 0 10px; color: var(--c-text-1, #e8ecf8); }
.grad { background: linear-gradient(120deg, var(--brand-1), var(--brand-2)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.desc { color: var(--c-text-2, #9aa4bd); margin: 0; font-size: 15px; }

.dl-card {
  text-align: center; padding: 36px 24px; border-radius: 16px;
  background: var(--c-card-bg, rgba(255,255,255,.05));
  border: 1px solid var(--c-border, rgba(255,255,255,.1));
  margin-bottom: 28px;
}
.dl-logo { margin-bottom: 14px; }
.dl-name { margin: 0 0 6px; font-size: 20px; color: var(--c-text-1, #e8ecf8); }
.dl-meta { color: var(--c-text-2, #9aa4bd); font-size: 13px; margin: 0 0 20px; }
.dl-btn {
  display: inline-block; padding: 14px 40px; border-radius: 999px;
  background: linear-gradient(120deg, var(--brand-1, #3b82f6), var(--brand-2, #2563eb));
  color: #fff; font-size: 16px; font-weight: 700; text-decoration: none;
  box-shadow: 0 12px 28px rgba(59, 130, 246, .35);
  transition: transform .2s, box-shadow .2s;
}
.dl-btn:hover { transform: translateY(-2px); box-shadow: 0 16px 34px rgba(59, 130, 246, .45); }
.dl-hint { color: var(--c-text-2, #9aa4bd); font-size: 13px; margin: 14px 0 0; }
.dl-mobile-tip { display: none; }
@media (max-width: 720px) {
  .desktop-only { display: none !important; }
  .dl-mobile-tip {
    display: block; padding: 14px; border-radius: 10px; font-size: 14px; line-height: 1.8;
    color: var(--c-text-2, #9aa4bd);
    background: rgba(59, 130, 246, .08); border: 1px dashed rgba(59, 130, 246, .3);
  }
}

.dl-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
.dl-item {
  padding: 20px; border-radius: 12px; text-align: center;
  background: var(--c-card-bg, rgba(255,255,255,.04));
  border: 1px solid var(--c-border, rgba(255,255,255,.08));
}
.dl-ico { font-size: 26px; margin-bottom: 8px; }
.dl-item h3 { margin: 0 0 8px; font-size: 15px; color: var(--c-text-1, #e8ecf8); }
.dl-item p { margin: 0; font-size: 13px; color: var(--c-text-2, #9aa4bd); line-height: 1.6; }

.dl-steps { margin-bottom: 24px; }
.dl-sec-title { font-size: 16px; color: var(--c-text-1, #e8ecf8); margin: 0 0 12px; }
.dl-steps-list { margin: 0; padding-left: 20px; color: var(--c-text-2, #9aa4bd); line-height: 2; font-size: 14px; }
.dl-text { color: var(--c-text-2, #9aa4bd); font-size: 14px; line-height: 1.8; margin: 0 0 10px; }
.dl-text code { background: rgba(127, 127, 127, .15); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.dl-code {
  background: #0b1220; color: #93c5fd; padding: 12px 16px; border-radius: 8px;
  font-size: 13px; overflow-x: auto; margin: 0 0 12px; border: 1px solid rgba(255,255,255,.08);
}

@media (max-width: 720px) {
  .dl-grid { grid-template-columns: 1fr; }
  .title { font-size: 28px; }
}
</style>

/* ── 桌面版已安装提示 ── */
.dl-card-installed { padding: 40px 24px; }
.dl-ok { font-size: 34px; margin-bottom: 10px; }

/* ── 智能应用控制说明 ── */
.sacl-toggle {
  display: inline-block; margin: 4px 0 14px; padding: 9px 20px;
  border-radius: 8px; border: 1px solid rgba(59, 130, 246, .4);
  background: rgba(59, 130, 246, .08); color: var(--c-text-1, #e8ecf8);
  font-size: 14px; cursor: pointer; transition: all .2s;
}
.sacl-toggle:hover { background: rgba(59, 130, 246, .16); }
.sacl-steps { margin-top: 6px; }
.sacl-step { display: flex; gap: 14px; margin-bottom: 18px; }
.sacl-no {
  flex: 0 0 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(120deg, var(--brand-1, #3b82f6), var(--brand-2, #2563eb));
  color: #fff; font-weight: 700; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
}
.sacl-body { flex: 1; min-width: 0; }
.sacl-text { color: var(--c-text-1, #e8ecf8); font-size: 14px; margin: 2px 0 8px; }
.sacl-img {
  max-width: 100%; border-radius: 10px;
  border: 1px solid var(--c-border, rgba(255, 255, 255, .12));
}
.dl-warn {
  color: #f59e0b; font-size: 13px; line-height: 1.7;
  padding: 10px 14px; border-radius: 8px;
  background: rgba(245, 158, 11, .08); border: 1px solid rgba(245, 158, 11, .25);
}
