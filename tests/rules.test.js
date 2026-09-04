#!/usr/bin/env node
/*
 * 課程性質規則 自動化測試（node，無外部相依）
 *
 * 驗證 2026-09 確認的四條規則：
 *   Q1 行政會議        → 可調可代，只加 ⚠ 提示（不是藍框）
 *   Q2 領域時間(XX領域) → 排除出 __DATA__＝視同空堂；只用 __RYU__ 畫灰框標示
 *   Q3 團體活動時間     → 藍框，只能代課不能調課
 *   Q6 判斷方式         → 規則式比對（舊課名「行政會報」「團體活動」「領域時間」同樣命中）
 * 另驗證 115-1 的兩個資料修復：
 *   - 只排領域時間的老師（N28）仍須留在教師名冊（teachers.json，非 CSV 反推）
 *   - 班級被塞進課名的單行格子（E62「201 Wri」）要拆成 課名 + 班級
 *
 * 讀 versions/<目前版本>/代課查詢_單檔.html（已內嵌真實資料），
 * 在 VM 沙箱跑內嵌 <script>，以最小 DOM stub 直接呼叫內部函式做斷言。
 *
 * 需要本機存在（未進版控的）：versions/<版本>/代課查詢_單檔.html
 * 執行：  node tests/rules.test.js
 * 全過回傳 exit 0，任一失敗回傳 exit 1。
 */
const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.join(__dirname, '..');
const NL = String.fromCharCode(10);

const version = fs.readFileSync(path.join(ROOT, 'assets', '_current_version.txt'), 'utf8').trim();
const file = path.join(ROOT, 'versions', version, '代課查詢_單檔.html');
if (!fs.existsSync(file)) {
  console.error(`[skip] 找不到 ${file}；先跑 python scripts/build_single.py --version ${version}`);
  process.exit(0);
}

function load() {
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/);
  const s = lines.findIndex(x => x.trim() === 'const DATA = (window.__DATA__ || []);');
  const e = lines.findIndex((x, i) => i > s && x.trim() === 'init();');
  if (s < 0 || e < 0) throw new Error('找不到內嵌 script 邊界（檔案結構可能變了）');
  const exposed = ['DATA', 'TEACHERS', 'RYU', 'ryuAt', 'isSubOnlyCourse', 'isNoticeCourse',
    'isInquiryCourse', 'inquiryPositionFor', 'STRINGS',
    'getEntry', 'isOccupied', 'computeCellState', 'state', 'focusCode'];
  const body = lines.slice(s, e).join(NL) + NL + ';window.__T={' + exposed.join(',') + '};';
  const dataBlock = lines.filter(x => x.startsWith('window.__')).join(NL);

  const el = () => ({
    style: {}, dataset: {}, innerHTML: '', textContent: '', value: '', checked: false,
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    appendChild() {}, addEventListener() {}, remove() {}, focus() {}, scrollIntoView() {},
    insertAdjacentHTML() {}, querySelector() { return null; }, querySelectorAll() { return []; },
    closest() { return null; },
  });
  const doc = {
    getElementById: () => el(), createElement: () => el(), body: el(),
    documentElement: el(), querySelector: () => null, querySelectorAll: () => [],
    addEventListener() {},
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
  return ctx.window.__T;
}

const T = load();
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('PASS - ' + m); } else { fail++; console.log('FAIL - ' + m); } };

console.log(`== 資料載入（版本 ${version}）==`);
ok(T.DATA.length > 0, '__DATA__ 有資料');
ok(T.TEACHERS.length > 0, '__TEACHERS__ 有資料');
ok(Array.isArray(T.RYU), '__RYU__ 存在（舊版本缺檔時為空陣列）');
ok(T.DATA.every(d => !/領域$/.test(d.course) || d.course === '領域課程'),
   'Q2：__DATA__ 裡沒有殘留的「XX領域」（都已視同空堂）');

console.log(NL + '== Q1 行政會議：可調可代 + ⚠ ==');
ok(T.isSubOnlyCourse('行政會議') === false, '行政會議 不是藍框（可調課）');
ok(T.isNoticeCourse('行政會議') === true, '行政會議 有 ⚠ 提示');
ok(T.isNoticeCourse('行政會報') === true, 'Q6：舊課名 行政會報 也命中');

console.log(NL + '== Q3 團體活動時間：藍框只能代課 ==');
ok(T.isSubOnlyCourse('團體活動時間') === true, '團體活動時間 是藍框');
ok(T.isSubOnlyCourse('團體活動') === true, 'Q6：舊課名 團體活動 也命中');
ok(T.isNoticeCourse('團體活動時間') === true, '團體活動時間 也有 ⚠ 提示');

console.log(NL + '== 未波及 ==');
ok(T.isSubOnlyCourse('高一自主學習導航') === true, '自主 仍是藍框');
ok(T.isSubOnlyCourse('籃球裁判法高三多元') === true, '多元 仍是藍框');
ok(T.isSubOnlyCourse('國語文') === false && T.isNoticeCourse('國語文') === false,
   '一般課程不受影響');

console.log(NL + '== Q2 領域時間＝空堂 + 灰框標示 ==');
if (T.RYU.length) {
  const r = T.RYU[0];
  ok(T.isOccupied(r.tcode, r.day, r.period) === false,
     `${r.tcode} 週${r.day}第${r.period}節（${r.course}）視同空堂`);
  ok(T.ryuAt(r.tcode, r.day, r.period) === r.course, '該格灰框標示為原課名');
  const busy = T.DATA[0];
  ok(T.ryuAt(busy.tcode, busy.day, busy.period) === null, '有課的格子沒有灰框標示');
  // 只排領域時間、CSV 零筆的老師仍須在名冊裡
  const codes = new Set(T.DATA.map(d => d.tcode));
  const onlyRyu = [...new Set(T.RYU.map(x => x.tcode))].filter(c => !codes.has(c));
  const roster = new Set(T.TEACHERS.map(t => t.code));
  ok(onlyRyu.every(c => roster.has(c)),
     `只排領域時間的老師仍在名冊（${onlyRyu.length ? onlyRyu.join(',') : '本版無此情況'}）`);
} else {
  console.log('  （本版無領域時間資料，略過）');
}

console.log(NL + '== 連堂課（紫框）==');
ok(T.isInquiryCourse('化學-探究A') === true, '化學-探究A 是連堂');
ok(T.isInquiryCourse('物理-探究B') === true, '物理-探究B 是連堂');
ok(T.isInquiryCourse('生活科技') === true, '生活科技 是連堂（114-2 的「生科」改名）');
ok(T.isInquiryCourse('國語文') === false, '一般課程不是連堂');
// 協同探究課在 PDF 有「有空格 / 沒空格」兩種寫法，必須已被 COURSE_RENAMES 合併，
// 否則同一堂課的兩位老師會被當成不同課，連堂與協同排除都會失效。
const spaced = [...new Set(T.DATA.map(d => d.course))].filter(c => / [AB]$/.test(c) && c.includes('探究'));
ok(spaced.length === 0,
   spaced.length ? `探究課名仍有空格寫法未合併：${spaced.join(' / ')}` : '探究課名兩種寫法已合併');
// 白名單真的有命中資料（避免課名改版後判斷整組失效卻沒人發現）
let inqPairs = 0;
for (const d of T.DATA) if (T.inquiryPositionFor(d.tcode, d.day, d.period) === 'top') inqPairs++;
ok(inqPairs > 0, `連堂配對實際命中 ${inqPairs} 組（0 代表白名單已與課名脫節）`);

console.log(NL + '== 頁尾規則說明 ==');
for (const lang of ['zh', 'en']) {
  const b = T.STRINGS[lang].rulesBody;
  ok(typeof b === 'string' && b.length > 500, `${lang} 規則說明內容存在`);
  ok(typeof T.STRINGS[lang].rulesBtn === 'string', `${lang} 規則說明按鈕文字存在`);
}

console.log(NL + '== 班級代碼不得留在課名裡 ==');
const stuck = T.DATA.filter(d => /^\d{3}[A-Z]? /.test(d.course));
ok(stuck.length === 0,
   stuck.length ? `仍有 ${stuck.length} 筆課名以班級代碼開頭：${stuck[0].course}` : '課名開頭無班級代碼殘留');

console.log(NL + `${fail === 0 ? '全部通過' : '有失敗'}：${pass} PASS / ${fail} FAIL`);
process.exit(fail ? 1 : 0);
