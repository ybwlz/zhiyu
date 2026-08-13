// 验证：管理后台仪表盘图表（ECharts 折线/饼图）——查 console 错误 + canvas
const WS = process.argv[2];
const TOKEN = process.argv[3];
const ws = new WebSocket(WS);
let id = 0;
const pending = new Map();
const errors = [];
const send = (m, p = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method: m, params: p })) });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.method === 'Runtime.exceptionThrown') errors.push('EXC: ' + (m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || ''))
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('CONSOLE: ' + (m.params.args || []).map(a => a.value || a.description || '').join(' '))
  if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id) }
};
const ev = async x => { const r = await send('Runtime.evaluate', { expression: x, returnByValue: true }); return r.exceptionDetails ? 'EXC' : r.result.value };
await new Promise(r => ws.onopen = r);
await send('Runtime.enable');
await send('Page.enable');
await ev(`localStorage.setItem('kb_token', '${TOKEN}'); 'ok'`);
await send('Page.navigate', { url: 'http://localhost:5174/zhiyu/admin-panel' });
await new Promise(r => setTimeout(r, 8000));
console.log('页面标题:', await ev('document.title'));
console.log('echart canvas 数:', await ev('document.querySelectorAll(".echart-box canvas").length'));
console.log('echart-box 容器数:', await ev('document.querySelectorAll(".echart-box").length'));
console.log('折线容器尺寸:', await ev('(() => { const el = document.querySelector(".chart-pair .echart-box"); return el ? el.clientWidth + "x" + el.clientHeight : "NO" })()'));
console.log('stat 卡片用户数:', await ev('document.querySelector(".stat-card b")?.textContent'));
console.log('--- 错误 ---');
console.log(errors.length ? errors.join('\n') : '无错误');
ws.close();
process.exit(0);
