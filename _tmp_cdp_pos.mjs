// 验证移动端首页：按钮视觉居中、跑马灯在 hero 下方独立延伸
const WS = process.argv[2];
const URL = process.argv[3];

const ws = new WebSocket(WS);
let id = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((res, rej) => {
  const mid = ++id;
  pending.set(mid, { res, rej });
  ws.send(JSON.stringify({ id: mid, method, params }));
});
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
  }
};
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const ready = new Promise((res, rej) => { ws.onopen = () => res(); ws.onerror = () => rej(new Error('ws error')); });
async function evalJS(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}

async function main() {
  await ready;
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await send('Page.navigate', { url: URL });
  await sleep(6500);
  await evalJS(`window.scrollTo(0, 0)`);
  await sleep(500);

  const out = await evalJS(`(() => {
    const btn = document.querySelector('.hero-explore-btn');
    const hero = document.querySelector('.kb-hero');
    const rm = document.querySelector('.recent-mobile');
    const inner = document.querySelector('.hero-inner');
    const btnR = btn.getBoundingClientRect();
    const heroR = hero.getBoundingClientRect();
    const innerR = inner.getBoundingClientRect();
    const rmR = rm.getBoundingClientRect();
    return {
      viewport: window.innerHeight,
      btnCenterY: Math.round(btnR.top + btnR.height / 2),
      viewportCenterY: Math.round(window.innerHeight / 2),
      btnCenterish: Math.abs((btnR.top + btnR.height / 2) - window.innerHeight / 2) < 80,
      heroTop: Math.round(heroR.top), heroBottom: Math.round(heroR.bottom),
      innerCenterY: Math.round(innerR.top + innerR.height / 2),
      rmTop: Math.round(rmR.top),
      rmBelowHero: rmR.top >= heroR.bottom - 5,
      marqueeInHero: !!document.querySelector('.kb-hero .recent-marquee'),
      marqueeInRm: !!document.querySelector('.recent-mobile .recent-marquee'),
      scrollHeight: document.documentElement.scrollHeight,
    };
  })()`);
  console.log('INFO', JSON.stringify(out, null, 1));

  ws.close();
  process.exit(0);
}
main().catch(e => { console.error('ERR', e.message); process.exit(1); });
