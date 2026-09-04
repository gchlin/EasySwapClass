#!/usr/bin/env node
/*
 * IB 課程候選排序 + 鐘點標記 自動化測試（node，無外部相依）
 *
 * 驗證 2026-09 確認的 IB 四階優先序（依「子科目 / 細科目」，不是主授科目）：
 *   1. 同子科 IB 教師      → 2 倍鐘點
 *   2. 同子科教師（非 IB）  → 雙語 2 倍鐘點、非雙語原鐘點
 *   3. 其他 IB 教師
 *   4. 其他老師
 * 並確認非 IB 課程的既有分組（同班 / 同科）完全不受影響。
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
const exposed = ['DATA', 'TEACHERS', 'getCandidateGroups', 'getEntry', 'isIbCourse',
  'teacherInfo', 'state', 'focusCode', 'resetState', 'candBtn', 'rateTagHtml', 'STRINGS'];
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
const doc = {
  getElementById: (id) => (id === 'ib-mode' ? ibModeEl : el()),
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

// 找一節 IB 課來測
const ibRow = T.DATA.find(d => T.isIbCourse(d.course) && info[d.tcode].detail);
console.log(`測試對象：${ibRow.tcode}（子科 ${info[ibRow.tcode].detail}，`
  + `${info[ibRow.tcode].isIB ? 'IB' : '非IB'}）週${ibRow.day}第${ibRow.period}節 ${ibRow.course}`);

T.state.mode = 'leaveSelected';
T.state.leaveSlot = { day: ibRow.day, period: ibRow.period };
T.state.partnerCode = null;
T.state.confirmed = [];
T.state.triangle = null;
// focusCode() 讀下拉；直接改 meCode 來源不易，改用 state 覆寫方式：
// getCandidateGroups 用 focusCode()，在無三角調時等於下拉選的老師。
// 這裡直接呼叫並比對群組結構即可（focusCode 會回 '' → 用 DATA 第一位）。
const groups = (() => {
  // 讓 focusCode() 回傳我們要的老師：覆寫 teacher select 的 value
  const sel = { value: ibRow.tcode, querySelector: () => null };
  doc.getElementById = (id) => (id === 'ib-mode' ? ibModeEl : (id === 'teacher' ? sel : el()));
  return T.getCandidateGroups(T.state.leaveSlot);
})();

console.log(NL + '== 群組結構 ==');
for (const g of groups) {
  console.log(`  p${g.priority} ${g.label}  [${g.teachers.length} 人] kind=${g.kind || '-'} rate=${g.rate || '-'}`);
}

const byPri = Object.fromEntries(groups.map(g => [g.priority, g]));
const myDetail = info[ibRow.tcode].detail;

console.log(NL + '== 四階順序 ==');
ok(byPri[1] && byPri[1].kind === 'sameDetail' && byPri[1].rate === 'double',
   '第一階 = 同子科 IB 教師，rate=double');
ok(byPri[1] && byPri[1].teachers.every(t => t.isIB && t.detail === myDetail),
   '第一階全員：IB 且同子科');
ok(byPri[2] && byPri[2].kind === 'sameDetail' && byPri[2].rate === 'byBilingual',
   '第二階 = 同子科（非IB），rate=byBilingual');
ok(byPri[2] && byPri[2].teachers.every(t => !t.isIB && t.detail === myDetail),
   '第二階全員：非 IB 且同子科');
ok(byPri[3] && byPri[3].teachers.every(t => t.isIB && t.detail !== myDetail),
   '第三階全員：IB 且非同子科');
ok(byPri[5] && byPri[5].teachers.every(t => !t.isIB && t.detail !== myDetail),
   '第四階全員：非 IB 且非同子科');
ok(!groups.some(g => g.kind === 'sameKlass'), 'IB 課程不再另立「同班」群組');

// 候選不重複、不遺漏
const all = groups.flatMap(g => g.teachers.map(t => t.code));
ok(new Set(all).size === all.length, `候選無重複（${all.length} 人）`);
ok(!all.includes(ibRow.tcode), '候選不含自己');

console.log(NL + '== 鐘點標記 ==');
const ibT = T.TEACHERS.find(t => t.isIB);
const biT = T.TEACHERS.find(t => t.isBilingual);
const plainT = T.TEACHERS.find(t => !t.isIB && !t.isBilingual);
ok(/2倍鐘點/.test(T.rateTagHtml(ibT, 'double')), '同子科 IB 教師 → 2倍鐘點');
ok(biT && /2倍鐘點/.test(T.rateTagHtml(biT, 'byBilingual')), '同子科雙語教師 → 2倍鐘點');
ok(/原鐘點/.test(T.rateTagHtml(plainT, 'byBilingual')), '同子科非雙語教師 → 原鐘點');
ok(T.rateTagHtml(ibT, null) === '', '非 IB 課程的群組不標鐘點');
ok(T.TEACHERS.filter(t => t.isBilingual).length === 2,
   `雙語教師 ${T.TEACHERS.filter(t => t.isBilingual).length} 位（N51/N52）`);

console.log(NL + '== 非 IB 課程不受影響 ==');
const nonIb = T.DATA.find(d => !T.isIbCourse(d.course) && d.klass && info[d.tcode].detail);
const sel2 = { value: nonIb.tcode, querySelector: () => null };
doc.getElementById = (id) => (id === 'ib-mode' ? ibModeEl : (id === 'teacher' ? sel2 : el()));
T.state.leaveSlot = { day: nonIb.day, period: nonIb.period };
const g2 = T.getCandidateGroups(T.state.leaveSlot);
ok(g2.some(g => g.kind === 'sameKlass'), '非 IB 課程仍有「同班」群組');
ok(g2.some(g => g.kind === 'sameSub'), '非 IB 課程仍有「同科」群組');
ok(!g2.some(g => g.rate), '非 IB 課程的群組不帶 rate');

console.log(NL + '== i18n ==');
for (const lang of ['zh', 'en']) {
  const S = T.STRINGS[lang];
  ok(typeof S.grpIbSameDetail === 'function' && typeof S.grpSameDetail === 'function'
     && typeof S.grpIbOther === 'string' && typeof S.grpNonIbOther === 'string',
     `${lang} 四階群組標籤齊全`);
  ok(typeof S.rateDouble === 'string' && typeof S.rateNormal === 'string'
     && typeof S.ibRateNote === 'string', `${lang} 鐘點字串齊全`);
  ok(typeof S.emptyBusyDetail === 'function', `${lang} 同子科群組的「都在上課」訊息存在`);
}

console.log(NL + `${fail === 0 ? '全部通過' : '有失敗'}：${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
