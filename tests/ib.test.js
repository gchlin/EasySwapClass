#!/usr/bin/env node
/*
 * IB 課程候選排序 自動化測試（node，無外部相依）
 *
 * 驗證 2026-09 確認的 IB 三階優先序（依「子科目 / 細科目」，不是主授科目）：
 *   1. IB 教師且同子科目
 *   2. IB 教師、其他科目
 *   3. 其他老師
 *
 * 重點：這只是「排序」不是「限制」——該時段所有有空的老師都必須列出來，一個都不能少。
 * 鐘點不做個別老師的判定（要看代課當下是不是雙語授課，程式無從得知），
 * 只在候選面板／自己課表／對方課表顯示提醒文字，且非 IB 課程不顯示。
 * 另確認非 IB 課程的既有分組（同班 / 同科）完全不受影響。
 *
 * 需要本機存在（未進版控的）：versions/<目前版本>/代課查詢_單檔.html
 * 執行：  node tests/ib.test.js
 */
const fs = require('fs'), vm = require('vm'), path = require('path');
const REPO = path.join(__dirname, '..');
const NL = String.fromCharCode(10);

const version = fs.readFileSync(path.join(REPO, 'assets', '_current_version.txt'), 'utf8').trim();
const file = path.join(REPO, 'versions', version, '代課查詢_單檔.html');
if (!fs.existsSync(file)) {
  console.error(`[skip] 找不到 ${file}；先跑 python scripts/build_single.py --version ${version}`);
  process.exit(0);
}

const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
const s = lines.findIndex(x => x.trim() === 'const DATA = (window.__DATA__ || []);');
const e = lines.findIndex((x, i) => i > s && x.trim() === 'init();');
const exposed = ['DATA', 'TEACHERS', 'getCandidateGroups', 'getEntry', 'isIbCourse', 'isOccupied',
  'teacherInfo', 'state', 'focusCode', 'candBtn', 'confsCoverIbCourse', 'STRINGS'];
const body = lines.slice(s, e).join(NL) + NL + ';window.__T={' + exposed.join(',') + '};';
const dataBlock = lines.filter(x => x.startsWith('window.__')).join(NL);

const el = () => ({
  style: {}, dataset: {}, innerHTML: '', textContent: '', value: '', checked: false,
  classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
  appendChild() {}, addEventListener() {}, remove() {}, focus() {}, scrollIntoView() {},
  insertAdjacentHTML() {}, querySelector() { return null; }, querySelectorAll() { return []; },
  closest() { return null; },
});
const ibModeEl = el();
let teacherSel = { value: '', querySelector: () => null };
const doc = {
  getElementById: (id) => (id === 'ib-mode' ? ibModeEl : (id === 'teacher' ? teacherSel : el())),
  createElement: () => el(), body: el(), documentElement: el(),
  querySelector: () => null, querySelectorAll: () => [], addEventListener() {},
};
const win = {
  document: doc, console, location: { hash: '' }, CSS: { escape: x => x },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  addEventListener() {},
};
win.window = win;
const ctx = vm.createContext(win);
vm.runInContext(dataBlock, ctx);
vm.runInContext('var document=window.document, localStorage=window.localStorage,'
  + ' CSS=window.CSS, location=window.location;', ctx);
vm.runInContext(body, ctx);
const T = ctx.window.__T;

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('PASS - ' + m); } else { fail++; console.log('FAIL - ' + m); } };
const info = {};
for (const t of T.TEACHERS) info[t.code] = t;

function groupsFor(row) {
  teacherSel = { value: row.tcode, querySelector: () => null };
  T.state.mode = 'leaveSelected';
  T.state.leaveSlot = { day: row.day, period: row.period };
  T.state.partnerCode = null;
  T.state.confirmed = [];
  T.state.triangle = null;
  return T.getCandidateGroups(T.state.leaveSlot);
}

// ── 測試對象：一節 IB 課 ──
const ibRow = T.DATA.find(d => T.isIbCourse(d.course) && info[d.tcode].detail);
const myDetail = info[ibRow.tcode].detail;
console.log(`測試對象：${ibRow.tcode}（子科 ${myDetail}，`
  + `${info[ibRow.tcode].isIB ? 'IB' : '非IB'}）週${ibRow.day}第${ibRow.period}節 ${ibRow.course}`);

const groups = groupsFor(ibRow);
console.log(NL + '== 群組結構 ==');
for (const g of groups) {
  console.log(`  p${g.priority} ${g.label}  [${g.teachers.length} 人] kind=${g.kind || '-'}`);
}
const byPri = {};
for (const g of groups) (byPri[g.priority] ||= []).push(g);
const tier = (p, kindOrSplit) =>
  (byPri[p] || []).find(g => (kindOrSplit === 'sameDetail' ? g.kind === 'sameDetail' : !g.coverBoth));

console.log(NL + '== 三階順序 ==');
const t1 = tier(1, 'sameDetail'), t2 = tier(2), t3 = tier(3);
ok(t1 && t1.kind === 'sameDetail', '第一階 = IB 教師且同子科');
ok(t1 && t1.teachers.every(x => x.isIB && x.detail === myDetail), '第一階全員：IB 且同子科');
ok(t2 && t2.teachers.every(x => x.isIB && x.detail !== myDetail), '第二階全員：IB 且非同子科');
ok(t3 && t3.teachers.every(x => !x.isIB), '第三階全員：非 IB 教師（不分科目）');
ok(!groups.some(g => g.kind === 'sameKlass'), 'IB 課程不另立「同班」群組');
ok(!groups.some(g => g.rate), '群組不再帶 rate（鐘點不做個別判定）');

console.log(NL + '== 只排序、不限制：一個有空的老師都不能少 ==');
const all = groups.flatMap(g => g.teachers.map(x => x.code));
ok(new Set(all).size === all.length, `候選無重複（${all.length} 人）`);
ok(!all.includes(ibRow.tcode), '候選不含自己');
const freeAll = T.TEACHERS
  .filter(x => x.code !== ibRow.tcode && !T.isOccupied(x.code, ibRow.day, ibRow.period))
  .map(x => x.code);
const missing = freeAll.filter(c => !all.includes(c));
ok(missing.length === 0,
   missing.length ? `有 ${missing.length} 位有空的老師沒被列出：${missing.slice(0, 5).join(',')}`
                  : `所有有空的老師（${freeAll.length} 位）都在候選裡`);

console.log(NL + '== 鐘點提醒：純文字，不標個別老師 ==');
ok(!/rate-tag|rateTagHtml/.test(String(T.candBtn)), 'candBtn 不再產生鐘點徽章');
ok(T.confsCoverIbCourse([{ day: ibRow.day, period: ibRow.period }], ibRow.tcode) === true,
   '代 IB 課程 → 顯示鐘點提醒');
const nonIbRow = T.DATA.find(d => !T.isIbCourse(d.course) && d.klass && info[d.tcode].detail);
ok(T.confsCoverIbCourse([{ day: nonIbRow.day, period: nonIbRow.period }], nonIbRow.tcode) === false,
   '代非 IB 課程 → 不顯示鐘點提醒');

console.log(NL + '== 非 IB 課程的分組不受影響 ==');
const g2 = groupsFor(nonIbRow);
ok(g2.some(g => g.kind === 'sameKlass'), '非 IB 課程仍有「同班」群組');
ok(g2.some(g => g.kind === 'sameSub'), '非 IB 課程仍有「同科」群組');
ok(!g2.some(g => g.kind === 'sameDetail'), '非 IB 課程不走同子科分組');
const all2 = g2.flatMap(g => g.teachers.map(x => x.code));
const free2 = T.TEACHERS
  .filter(x => x.code !== nonIbRow.tcode && !T.isOccupied(x.code, nonIbRow.day, nonIbRow.period))
  .map(x => x.code);
ok(free2.every(c => all2.includes(c)), `非 IB 課程也一個不漏（${free2.length} 位）`);

console.log(NL + '== 教師資料 ==');
ok(T.TEACHERS.every(x => !('isBilingual' in x)),
   '教師資料不再帶 isBilingual（雙語是授課方式，不是老師屬性）');

console.log(NL + '== i18n ==');
for (const lang of ['zh', 'en']) {
  const S = T.STRINGS[lang];
  ok(typeof S.grpIbSameDetail === 'function' && typeof S.grpIbOtherSub === 'string'
     && typeof S.grpNonIbOther === 'string', `${lang} 三階群組標籤齊全`);
  ok(typeof S.ibRateNote === 'string' && S.ibRateNote.includes('2'),
     `${lang} 鐘點提醒文字存在`);
  ok(S.rateDouble === undefined && S.rateNormal === undefined,
     `${lang} 舊的個別鐘點徽章字串已移除`);
  ok(S.grpSameDetail === undefined, `${lang} 舊的第二階（同子科非IB）標籤已移除`);
}

console.log(NL + `${fail === 0 ? '全部通過' : '有失敗'}：${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
