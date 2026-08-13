// 诊断 v2：确认进入 admin-panel + 抓 console 错误 + 图表状态
const WS = process.argv[2];
const TOKEN = process.argv[3];
const ws = new WebSocket(WS);
let id = 0;
const pending = new Map();
const errors = [];
const send = (m, p = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method: m, params: p })) });
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.method === 'Runtime.exceptionThrown') errors.push('EXC: ' + String(m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || '').slice(0, 300))
  if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) errors.push('CONSOLE[' + m.params.type + ']: ' + (m.params.args || []).map(a => a.value || a.description || '').join(' ').slice(0, 300))
  if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id) }
};
const ev = async x => { const r = await send('Runtime.evaluate', { expression: x, returnByValue: true }); return r.exceptionDetails ? 'EXC' : r.result.value };
await new Promise(r => ws.onopen = r);
await send('Runtime.enable');
await send('Page.enable');
await ev(`localStorage.setItem('kb_token', '${TOKEN}'); 'ok'`);
await send('Page.navigate', { url: 'http://localhost:5174/zhiyu/admin-panel' });
await new Promise(r => setTimeout(r, 12000));
console.log('当前路径:', await ev('location.pathname'));
console.log('echart-box 容器数:', await ev('document.querySelectorAll(".echart-box").length'));
console.log('canvas 数:', await ev('document.querySelectorAll(".echart-box canvas").length'));
console.log('stat 卡用户数:', await ev('document.querySelector(".stat-card b")?.textContent'));
console.log('--- console 错误 ---');
console.log(errors.length ? errors.join('\n---\n') : '无错误');
ws.close();
process.exit(0);
