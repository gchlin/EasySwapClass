#!/usr/bin/env node
/*
 * 三角調 / 協同排除 自動化測試（node，無外部相依）
 *
 * 在 VM 沙箱載入 template/代課查詢_發布.html 的內嵌 <script>，搭配真實
 * template/data.js、en_name.js，以最小 DOM stub 直接呼叫內部函式做斷言。
 *
 * 需要本機存在（未進版控的）：template/data.js、template/en_name.js
 * 執行：  node tests/triangle.test.js
 * 全過回傳 exit 0，任一失敗回傳 exit 1。
 */
const fs = require('fs'), vm = require('vm'), path = require('path');
const TPL = path.join(__dirname, '..', 'template');

function load(lang) {
  const html = fs.readFileSync(path.join(TPL, '代課查詢_發布.html'), 'utf8').split(/\r?\n/);
  const s = html.findIndex(x => x.trim() === 'const DATA = (window.__DATA__ || []);');
  const e = html.findIndex((x, i) => i > s && x.trim() === 'init();');
  if (s < 0 || e < 0) throw new Error('找不到內嵌 script 邊界（檔案結構可能變了）');
  const exposed = ['DATA','TEACHERS','state','render','confirmSub','onCellClick','getCandidateGroups',
    'isSwapOption','computeCellState','generateOfficeList','officeRows','resetState','focusCode',
    'getEntry','isInquiryCourse','isSubOnlyCourse','coTeacherCodesAt','enterTriangle','onPickB',
    'exitTriangle','triangleMarks','generateTriangleSummary'];
  const body = html.slice(s, e).join('\n') + '\n;window.__T={' + exposed.join(',') + '};';
  let tv = '';
  const ec = {};
  const fe = id => ec[id] || (ec[id] = {
    _id: id, _html: '',
    get value() { return id === 'teacher' ? tv : (id === 'date-mode' ? 'this' : ''); },
    set value(v) { if (id === 'teacher') tv = v; },
    checked: false, style: {}, dataset: {}, hidden: false,
    get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; },
    insertAdjacentHTML(p, h) { this._html += h; },
    textContent: '', className: '', onclick: null,
    appendChild() {}, addEventListener() {}, querySelectorAll() { return []; },
    querySelector() { return null; }, setAttribute() {},
  });
  const ctx = {
    document: { getElementById: fe, querySelectorAll: () => [], querySelector: () => null,
      createElement: () => ({ style: {}, appendChild() {}, setAttribute() {}, dataset: {} }),
      documentElement: {}, title: '', body: { appendChild() {}, removeChild() {} } },
    localStorage: { getItem: k => k === 'langPref' ? lang : null, setItem() {}, removeItem() {} },
    navigator: {}, CSS: { escape: x => String(x) }, console,
    setInterval: () => 0, clearInterval() {}, setTimeout: () => 0, location: { hash: '' }, Date,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(TPL, 'data.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(path.join(TPL, 'en_name.js'), 'utf8'), ctx);
  vm.runInContext(body, ctx);
  ctx.__set = v => { tv = v; }; ctx.__ec = ec;
  return ctx;
}

let fails = 0, passes = 0;
const ck = (l, c) => { console.log((c ? 'PASS' : 'FAIL') + ' - ' + l); c ? passes++ : fails++; };
const head = l => console.log('\n== ' + l + ' ==');

const ctx = load('zh');
const T = ctx.__T, { DATA, TEACHERS, state } = T;
const busy = (d, p, ex) => TEACHERS.filter(t => t.code !== ex && DATA.some(x => x.tcode === t.code && x.day === d && x.period === p));
const free = (d, p, ex) => TEACHERS.filter(t => t.code !== ex && !DATA.some(x => x.tcode === t.code && x.day === d && x.period === p));
const entry = (tc, d, p) => DATA.find(x => x.tcode === tc && x.day === d && x.period === p);
const subOnly = n => !!n && (n.includes('多元') || n.includes('自主') || n.includes('行政會報'));

const A = DATA[0].tcode, day = DATA[0].day, period = DATA[0].period;
ctx.__set(A);

head('回歸：一般代課');
state.confirmed = []; state.triangle = null; state.leaveSlot = { day, period }; state.mode = 'leaveSelected';
ck('focusCode 一般時 = A', T.focusCode() === A);
const cand = T.getCandidateGroups(state.leaveSlot).flatMap(g => g.teachers.map(t => t.code));
ck('候選排除 A 本人', !cand.includes(A));
ck('候選皆為該節有空', cand.every(c => !DATA.some(x => x.tcode === c && x.day === day && x.period === period)));
state.mode = 'partnerSelected'; state.partnerCode = cand[0]; T.confirmSub();
ck('一般代課 → 1 筆 sub', state.confirmed.length === 1 && state.confirmed[0].type === 'sub');
ck('A 課表標為已代', T.computeCellState(day, period).cls === 'cell-confirmed-leave-sub');

head('回歸：一般調課');
state.confirmed = []; state.triangle = null;
const aS = DATA.filter(x => x.tcode === A);
let swp = null;
for (const ls of aS) { for (const pt of free(ls.day, ls.period, A)) { for (const pd of DATA) {
  if (pd.tcode !== pt.code || (pd.day === ls.day && pd.period === ls.period) || subOnly(pd.course)) continue;
  if (!DATA.some(x => x.tcode === A && x.day === pd.day && x.period === pd.period)) { swp = { ls, pt: pt.code, pd }; break; }
} if (swp) break; } if (swp) break; }
state.leaveSlot = { day: swp.ls.day, period: swp.ls.period }; state.mode = 'partnerSelected'; state.partnerCode = swp.pt;
ck('調課時段 isSwapOption=true', T.isSwapOption(swp.pd.day, swp.pd.period) === true);
T.onCellClick(swp.pd.day, swp.pd.period);
ck('一般調課 → 1 筆 swap', state.confirmed.length === 1 && state.confirmed[0].type === 'swap');

head('三角調：代課腿（A←B←C）');
state.confirmed = []; state.triangle = null;
const B = busy(day, period, A)[0].code;
const C = free(day, period, A).filter(c => c.code !== B)[0].code;
state.triangle = { aCode: A, bCode: B, slot: { day, period }, phase: 'pickC' };
state.leaveSlot = { day, period }; state.mode = 'leaveSelected';
const c3 = T.getCandidateGroups(state.leaveSlot).flatMap(g => g.teachers.map(t => t.code));
ck('focusCode 三角調時 = B', T.focusCode() === B);
ck('找 C 時排除 A', !c3.includes(A));
ck('找 C 時排除 B 自己', !c3.includes(B));
state.mode = 'partnerSelected'; state.partnerCode = C; T.confirmSub();
ck('確認 → 1 筆 triangle(sub)', state.confirmed.length === 1 && state.confirmed[0].type === 'triangle' && state.confirmed[0].legType === 'sub');
const sk = day + '-' + period, m = T.triangleMarks(state.confirmed[0]);
ck('B 樞紐格為分割格', m.b[sk].split === true);
ck('分割上綠(去代)/下橘(不用去)', m.b[sk].topCls === 'tri-go' && m.b[sk].botCls === 'tri-off');
ck('三角調摘要無 undefined', !/undefined/.test(T.generateTriangleSummary(state.confirmed[0])));
ctx.__set(A); T.onCellClick(day, period);
ck('點 A 的 S 格可復原三角調', state.confirmed.length === 0);

head('三角調：調課腿（swap）');
state.confirmed = []; state.triangle = null;
let sc = null;
o: for (const ar of DATA) { for (const bt of busy(ar.day, ar.period, ar.tcode)) {
  const be = entry(bt.code, ar.day, ar.period); if (!be || subOnly(be.course)) continue;
  for (const taC of TEACHERS) { if (taC.code === ar.tcode || taC.code === bt.code || DATA.some(x => x.tcode === taC.code && x.day === ar.day && x.period === ar.period)) continue;
    for (const cd of DATA) { if (cd.tcode !== taC.code || (cd.day === ar.day && cd.period === ar.period)) continue;
      if (!DATA.some(x => x.tcode === bt.code && x.day === cd.day && x.period === cd.period)) { sc = { A: ar.tcode, B: bt.code, C: taC.code, day: ar.day, period: ar.period, sd: cd.day, sp: cd.period }; break o; } } } } }
ctx.__set(sc.A);
state.triangle = { aCode: sc.A, bCode: sc.B, slot: { day: sc.day, period: sc.period }, phase: 'pickC' };
state.leaveSlot = { day: sc.day, period: sc.period }; state.mode = 'partnerSelected'; state.partnerCode = sc.C;
ck('B 自由的對調時段 isSwapOption=true', T.isSwapOption(sc.sd, sc.sp) === true);
T.onCellClick(sc.sd, sc.sp);
ck('確認 → triangle(swap) 含 swapDay/Period', state.confirmed[0].legType === 'swap' && state.confirmed[0].swapDay === sc.sd);

head('協同排除：探究/IPSS 併班（重點）');
// 動態找一組「同探究課名同節次、不同班級代碼」的協同（涵蓋 IPSS 各掛 114A/115A/116A）
const sess = {};
for (const d of DATA) { if (!T.isInquiryCourse(d.course)) continue; const k = d.course + '|' + d.day + '|' + d.period; (sess[k] ||= []).push(d); }
const pool = Object.values(sess).find(a => a.length >= 2 && new Set(a.map(x => x.klass)).size >= 2);
if (pool) {
  const me = pool[0], other = pool[1];
  ctx.__set(me.tcode);
  const co = T.coTeacherCodesAt(entry(me.tcode, me.day, me.period), me.day, me.period, me.tcode);
  console.log('  樣本：' + me.course + ' 第' + me.day + '/' + me.period + ' 節，老師 ' + pool.map(x => x.tcode + '(' + x.klass + ')').join(','));
  ck('協同集合涵蓋同課名不同班級的夥伴', co.has(other.tcode));
  const bList = busy(me.day, me.period, me.tcode).filter(t => !co.has(t.code));
  ck('B 選單已排除協同夥伴', !bList.some(t => t.code === other.tcode));
  // 同節不同課程的老師不應被誤排除
  const outsider = DATA.find(d => d.day === me.day && d.period === me.period && d.course !== me.course && d.tcode !== me.tcode && d.klass);
  if (outsider) ck('同節但不同課程者不被排除（' + outsider.course + '）', !co.has(outsider.tcode));
} else { console.log('SKIP - 資料中無「同課名不同班級」的探究協同'); }

// 具名案例（若該版本資料含 N68/N60/N69 週三第3節 IPSS 則一併驗證）
const n68 = entry('N68', 3, 3);
if (n68 && T.isInquiryCourse(n68.course)) {
  ctx.__set('N68');
  const co = T.coTeacherCodesAt(n68, 3, 3, 'N68');
  ck('N68 週三第3節：排除 N60', co.has('N60'));
  ck('N68 週三第3節：排除 N69', co.has('N69'));
} else { console.log('SKIP - 此版本資料無 N68 週三第3節 IPSS 案例'); }

head('協同排除：一般雙師（同班級同節）仍生效');
const km = {};
for (const d of DATA) { if (!d.klass || T.isInquiryCourse(d.course)) continue; const k = d.klass + '|' + d.day + '|' + d.period; (km[k] ||= []).push(d); }
const reg = Object.values(km).find(a => a.length >= 2);
if (reg) {
  ctx.__set(reg[0].tcode);
  const co = T.coTeacherCodesAt(entry(reg[0].tcode, reg[0].day, reg[0].period), reg[0].day, reg[0].period, reg[0].tcode);
  ck('一般同班雙師仍被排除（' + reg[0].course + '）', co.has(reg[1].tcode));
} else { console.log('SKIP - 資料中無一般同班雙師'); }

head('其他邊界');
// resetState 清 triangle
ctx.__set(A);
state.confirmed = [{ type: 'sub', day: 1, period: 1, partnerCode: TEACHERS[1].code }];
state.triangle = { aCode: A, bCode: TEACHERS[1].code, slot: { day: 1, period: 1 }, phase: 'pickC' };
T.resetState();
ck('清除全部 → triangle 一併清空', state.triangle === null && state.confirmed.length === 0);
// 焦點隔離：B 焦點時不畫 A 既有 confirmed
state.confirmed = [{ type: 'sub', day: aS[1].day, period: aS[1].period, partnerCode: free(aS[1].day, aS[1].period, A)[0].code }];
state.triangle = { aCode: A, bCode: B, slot: { day, period }, phase: 'pickC' };
ck('B 焦點時 A 的代課不汙染 B 課表', T.computeCellState(aS[1].day, aS[1].period).cls !== 'cell-confirmed-leave-sub');

head('EN 介面');
const en = load('en'); const ED = en.__T.DATA;
en.__set(ED[0].tcode);
const eB = en.__T.TEACHERS.filter(t => t.code !== ED[0].tcode && ED.some(x => x.tcode === t.code && x.day === ED[0].day && x.period === ED[0].period))[0].code;
const eC = en.__T.TEACHERS.filter(t => t.code !== ED[0].tcode && t.code !== eB && !ED.some(x => x.tcode === t.code && x.day === ED[0].day && x.period === ED[0].period))[0].code;
en.__T.state.confirmed = [{ type: 'triangle', slot: { day: ED[0].day, period: ED[0].period }, aCode: ED[0].tcode, bCode: eB, cCode: eC, legType: 'sub', swapDay: null, swapPeriod: null }];
en.__T.state.triangle = null; en.__T.state.mode = 'idle'; en.__T.state.leaveSlot = null;
en.__T.render();
ck('EN 教務處清單無 undefined', !/undefined/.test(en.__T.generateOfficeList()));
ck('EN 卡片/總表渲染無 undefined', !/undefined/.test(en.__ec['office-tables']._html) && !/undefined/.test(en.__ec['partner-schedules']._html));

console.log('\n' + (fails ? (fails + ' FAIL / ' + passes + ' PASS') : ('全部通過：' + passes + ' PASS')));
process.exitCode = fails ? 1 : 0;
