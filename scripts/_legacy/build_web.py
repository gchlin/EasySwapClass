"""
從 課表_長表.csv 產生互動式代課/調課查詢網頁。
精神：所有操作在同一張自己的課表上完成，不另開課表。
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = str(ROOT / "natural_science" / "課表_長表.csv")
HTML_PATH = str(ROOT / "natural_science" / "代課查詢.html")

with open(CSV_PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

data = [
    {
        "tcode": r["教師代碼"],
        "tname": r["教師"],
        "subj": r["主授科目"],
        "day": int(r["星期"]),
        "period": int(r["節次"]),
        "course": r["課程名稱"],
        "klass": r["班級"],
        "room": r["教室"],
    }
    for r in rows
]

teachers_map = {}
for r in rows:
    teachers_map[r["教師代碼"]] = {
        "name": r["教師"],
        "post": r["職務"],
        "subj": r["主授科目"],
    }
teachers = [{"code": c, **info} for c, info in sorted(teachers_map.items())]

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>代課 / 調課 查詢</title>
<style>
  :root {
    --primary: #2563eb;
    --bg: #f9fafb;
    --border: #d1d5db;
    --muted: #6b7280;
    --leave: #f59e0b;
    --partner: #ea580c;
    --swap: #16a34a;
    --sub: #2563eb;
  }
  * { box-sizing: border-box; }
  body {
    font-family: "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif;
    max-width: 900px;
    margin: 1em auto;
    padding: 0 0.8em 3em;
    background: var(--bg);
    line-height: 1.5;
  }
  h1 { margin: 0.3em 0; }
  section {
    margin: 1em 0;
    padding: 0.8em 1em;
    background: white;
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  section h2 { margin: 0 0 0.5em; font-size: 1em; color: var(--primary); }
  select { font-size: 1em; padding: 0.4em; min-width: 14em; }
  button {
    font-size: 0.9em; padding: 0.4em 0.9em;
    border: 1px solid var(--primary); background: white;
    color: var(--primary); border-radius: 4px; cursor: pointer;
    margin: 0.2em 0.2em 0.2em 0;
  }
  button:hover { background: #eff6ff; }
  button.primary { background: var(--primary); color: white; }
  button.primary:hover { background: #1d4ed8; }
  button.danger { border-color: #dc2626; color: #dc2626; }
  button.danger:hover { background: #fef2f2; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }

  table.schedule { border-collapse: collapse; width: 100%; table-layout: fixed; }
  table.schedule th, table.schedule td {
    border: 1px solid var(--border);
    padding: 5px 3px;
    text-align: center;
    font-size: 0.78em;
    vertical-align: middle;
    height: 4.5em;
  }
  table.schedule th { background: #f3f4f6; height: auto; }
  td.cell-occupied { background: #fef9c3; cursor: pointer; }
  td.cell-occupied:hover { background: #fde68a; }
  td.cell-empty { color: #d1d5db; background: #fafafa; }
  td.cell-partner-context {
    background: #e5e7eb; color: #9ca3af; cursor: default;
  }
  td.cell-leave-active {
    background: var(--leave); color: white; font-weight: bold;
    border: 3px solid #b45309;
    cursor: pointer;
  }
  td.cell-swap-option {
    background: #ffedd5; border: 3px dashed var(--partner);
    cursor: pointer; font-weight: bold; color: #9a3412;
  }
  td.cell-swap-option:hover { background: #fed7aa; }
  td.cell-confirmed-leave-sub {
    background: #dbeafe; border: 2px solid var(--sub);
    color: #1e40af; font-weight: 500;
  }
  td.cell-confirmed-leave-swap {
    background: #fde68a; border: 2px solid #b45309;
    color: #78350f; font-weight: 500;
  }
  td.cell-confirmed-swap-in {
    background: #d1fae5; border: 2px solid var(--swap);
    color: #064e3b; font-weight: 500;
  }
  /* 探究連堂大粗框（不論狀態都顯示，提醒不要拆） */
  td.inquiry-top {
    box-shadow:
      inset 0 3px 0 #7c3aed,
      inset 3px 0 0 #7c3aed,
      inset -3px 0 0 #7c3aed;
  }
  td.inquiry-bottom {
    box-shadow:
      inset 0 -3px 0 #7c3aed,
      inset 3px 0 0 #7c3aed,
      inset -3px 0 0 #7c3aed;
  }
  /* 上下午分隔（第 4 節與第 5 節之間粗黑線） */
  table.schedule tbody tr:nth-child(4) > th,
  table.schedule tbody tr:nth-child(4) > td {
    border-bottom: 3px solid #000;
  }
  td .anno {
    display: block; font-size: 0.85em; margin-top: 2px;
  }

  /* 候選人面板 */
  #panel {
    margin-top: 0.6em;
    padding: 0.6em 0.8em;
    background: #fffbeb;
    border: 1px solid var(--leave);
    border-radius: 6px;
  }
  #panel.partner-mode {
    background: #ffedd5;
    border-color: var(--partner);
  }
  #panel-status {
    margin-bottom: 0.5em;
    font-size: 0.95em;
  }
  .candidate-group { margin: 0.4em 0; }
  .candidate-group h3 {
    margin: 0.3em 0 0.2em;
    font-size: 0.85em;
    color: var(--muted);
    font-weight: normal;
  }
  .cand-btn {
    display: inline-block;
    margin: 0.15em 0.2em 0.15em 0;
    padding: 0.35em 0.8em;
    border: 1px solid var(--border);
    background: white;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9em;
  }
  .cand-btn:hover { background: #f3f4f6; }
  .cand-btn.same-subj { border-color: var(--sub); color: var(--sub); }
  .cand-btn.cross-subj { border-color: var(--muted); color: var(--muted); }
  .cand-btn.active {
    background: var(--partner); color: white; border-color: var(--partner);
    font-weight: bold;
  }

  .legend {
    display: flex; flex-wrap: wrap; gap: 0.5em;
    font-size: 0.8em; margin: 0.4em 0;
  }
  .legend span { padding: 2px 8px; border-radius: 3px; border: 1px solid; }
  .lg-yellow { background: #fef9c3; border-color: #ca8a04; color: #713f12; }
  .lg-leave { background: var(--leave); border-color: #b45309; color: white; }
  .lg-swap-opt { background: #ffedd5; border-color: var(--partner); color: #9a3412; }
  .lg-conf-sub { background: #dbeafe; border-color: var(--sub); color: #1e40af; }
  .lg-conf-swap { background: #fde68a; border-color: #b45309; color: #78350f; }
  .lg-conf-in { background: #d1fae5; border-color: var(--swap); color: #064e3b; }
  .lg-inquiry { background: white; border: 2px solid #7c3aed; color: #5b21b6; }

  @media (max-width: 600px) {
    body { font-size: 14px; padding: 0 0.4em 3em; }
    table.schedule th, table.schedule td {
      font-size: 0.7em; padding: 3px 2px; height: 4em;
    }
    .cand-btn { font-size: 0.85em; padding: 0.4em 0.7em; }
  }
</style>
</head>
<body>

<h1>代課 / 調課</h1>

<section>
  <h2>1. 我是誰</h2>
  <select id="teacher"></select>
</section>

<section>
  <h2>2. 我的課表（點請假時段 → 點代課人選 → 點換課時段或按代課）</h2>
  <div style="margin: 0.4em 0; font-size:0.9em">
    顯示日期：
    <select id="date-mode" style="font-size:0.9em; padding:0.25em 0.4em; min-width:auto">
      <option value="none">不顯示</option>
      <option value="this">當週</option>
      <option value="next">下週</option>
    </select>
  </div>
  <table class="schedule" id="schedule"></table>
  <div id="panel" style="display:none"></div>
  <div class="legend" style="margin-top:0.6em">
    <span class="lg-yellow">我有課</span>
    <span class="lg-leave">↩ 我選的請假</span>
    <span class="lg-swap-opt">★ 可換的時段</span>
    <span class="lg-conf-sub">✓ 已選代課</span>
    <span class="lg-conf-swap">✓ 已選換課</span>
    <span class="lg-conf-in">✓ 我代他的課</span>
    <span class="lg-inquiry">紫框 = 連堂課（探究 / IPSS，盡量別動，但仍可選）</span>
  </div>
  <p style="font-size:0.85em; color:var(--muted); margin:0.4em 0">
    提示：點已確認的格子可退回「選代課人」那步（再點請假格子才完全取消）；紫色粗框是連堂課（探究 / IPSS）的提醒，不是禁止。
  </p>
  <div style="margin-top:0.6em">
    <button class="danger" id="reset-btn">清除全部已選方案</button>
  </div>
</section>

<section id="partner-section" style="display:none">
  <h2>3. 對方課表（給對方看，可截圖）</h2>
  <div id="partner-schedules"></div>
</section>

<script>
const DATA = __DATA__;
const TEACHERS = __TEACHERS__;
const SUBJECT_FULL = {"物": "物理", "化": "化學", "生": "生物", "地科": "地球科學"};
const DAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"};

const SCHED = {};
for (const d of DATA) SCHED[`${d.tcode}-${d.day}-${d.period}`] = d;
function getEntry(tc, d, p) { return SCHED[`${tc}-${d}-${p}`]; }
function isOccupied(tc, d, p) { return !!getEntry(tc, d, p); }

const state = {
  mode: "idle",  // idle | leaveSelected | partnerSelected
  leaveSlot: null,
  partnerCode: null,
  confirmed: [],  // [{day, period, partnerCode, type:'sub'|'swap', swapDay?, swapPeriod?}]
};

function teacherInfo(code) { return TEACHERS.find(t => t.code === code); }
function meCode() { return document.getElementById("teacher").value; }
function me() { return teacherInfo(meCode()); }

function getWeekDates(mode) {
  if (mode === "none" || !mode) return null;
  const today = new Date();
  const dow = today.getDay();  // 0=Sun, 1=Mon
  const mondayOffset = dow === 0 ? -6 : 1 - dow;
  const monday = new Date(today);
  monday.setDate(today.getDate() + mondayOffset + (mode === "next" ? 7 : 0));
  const out = [];
  for (let i = 0; i < 5; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    out.push(d);
  }
  return out;
}
function fmtDate(d) { return `${d.getMonth() + 1}/${d.getDate()}`; }

// 課表表頭（位置：'below' 日期在星期下、'before' 日期在星期前）
function buildHeader(position) {
  const mode = document.getElementById("date-mode").value;
  const dates = getWeekDates(mode);
  let html = '<thead><tr><th style="width:7%">節</th>';
  for (let d = 1; d <= 5; d++) {
    if (dates) {
      if (position === "before") {
        html += `<th>${fmtDate(dates[d-1])} 星期${DAY_NAMES[d]}</th>`;
      } else {
        html += `<th>星期${DAY_NAMES[d]}<br><span style="font-weight:normal; font-size:0.85em; color:var(--muted)">${fmtDate(dates[d-1])}</span></th>`;
      }
    } else {
      html += `<th>星期${DAY_NAMES[d]}</th>`;
    }
  }
  html += '</tr></thead>';
  return html;
}

function isInquiryCourse(name) {
  // 連堂課（會用實驗室、不宜拆開）
  return name === "物理地科探究" || name === "化學生物探究" || name === "IPSS";
}
// 連堂判斷：top/bottom/null（任意老師）
function inquiryPositionFor(tcode, d, p) {
  const e = getEntry(tcode, d, p);
  if (!e || !isInquiryCourse(e.course)) return null;
  const next = getEntry(tcode, d, p + 1);
  if (next && next.course === e.course && next.klass === e.klass) return "top";
  const prev = getEntry(tcode, d, p - 1);
  if (prev && prev.course === e.course && prev.klass === e.klass) return "bottom";
  return null;
}
function inquiryPosition(d, p) {
  return inquiryPositionFor(meCode(), d, p);
}

function init() {
  const sel = document.getElementById("teacher");
  for (const t of TEACHERS) {
    const opt = document.createElement("option");
    opt.value = t.code;
    opt.textContent = `${t.name}（${t.code}・${SUBJECT_FULL[t.subj] || t.subj}）`;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => {
    state.mode = "idle";
    state.leaveSlot = null;
    state.partnerCode = null;
    state.confirmed = [];
    render();
  });
  document.getElementById("date-mode").addEventListener("change", render);
  document.getElementById("reset-btn").addEventListener("click", () => {
    state.mode = "idle";
    state.leaveSlot = null;
    state.partnerCode = null;
    state.confirmed = [];
    render();
  });
  render();
}

// 找到該 cell 的所有 confirmed 關聯
function findConfirmed(d, p) {
  for (const c of state.confirmed) {
    if (c.day === d && c.period === p) return {role: "leave", c};
    if (c.type === "swap" && c.swapDay === d && c.swapPeriod === p) return {role: "swap-in", c};
  }
  return null;
}

function isInLeave(d, p) {
  return state.leaveSlot && state.leaveSlot.day === d && state.leaveSlot.period === p;
}

function isSwapOption(d, p) {
  // partnerSelected 時，cell 對 me 是空堂、對 partner 有課 → swap option
  if (state.mode !== "partnerSelected") return false;
  if (isInLeave(d, p)) return false;
  if (findConfirmed(d, p)) return false;
  if (isOccupied(meCode(), d, p)) return false;
  return isOccupied(state.partnerCode, d, p);
}

function computeCellState(d, p) {
  const tcode = meCode();
  const e = getEntry(tcode, d, p);
  const conf = findConfirmed(d, p);

  if (conf) {
    const partner = teacherInfo(conf.c.partnerCode);
    if (conf.role === "leave") {
      if (conf.c.type === "sub") {
        return {
          cls: "cell-confirmed-leave-sub",
          html: `${e.course}${e.klass ? " " + e.klass : ""}<span class="anno">↩ 請 ${partner.name} 代</span>`,
        };
      } else {
        const partnerClass = getEntry(conf.c.partnerCode, conf.c.swapDay, conf.c.swapPeriod);
        return {
          cls: "cell-confirmed-leave-swap",
          html: `${e.course}${e.klass ? " " + e.klass : ""}<span class="anno">↔ 換 ${partner.name} (${partnerClass.klass})</span>`,
        };
      }
    } else {
      // swap-in
      const partnerClass = getEntry(conf.c.partnerCode, d, p);
      return {
        cls: "cell-confirmed-swap-in",
        html: `<span class="anno">↪ 代 ${partner.name}</span>${partnerClass.course}${partnerClass.klass ? " " + partnerClass.klass : ""}`,
      };
    }
  }

  if (isInLeave(d, p)) {
    return {
      cls: "cell-leave-active",
      html: `${e.course}${e.klass ? " " + e.klass : ""}<span class="anno">↩ 請假中</span>`,
    };
  }

  if (isSwapOption(d, p)) {
    const partnerClass = getEntry(state.partnerCode, d, p);
    return {
      cls: "cell-swap-option",
      html: `${partnerClass.course}${partnerClass.klass ? " " + partnerClass.klass : ""}<span class="anno">★ 點此換</span>`,
    };
  }

  if (e) {
    return {
      cls: "cell-occupied",
      html: `${e.course}${e.klass ? " " + e.klass : ""}`,
    };
  }
  return { cls: "cell-empty", html: "·" };
}

function render() {
  // schedule
  const tbl = document.getElementById("schedule");
  let html = buildHeader("below") + '<tbody>';
  for (let p = 1; p <= 7; p++) {
    html += `<tr><th>${p}</th>`;
    for (let d = 1; d <= 5; d++) {
      const s = computeCellState(d, p);
      const pos = inquiryPosition(d, p);
      const inqCls = pos === "top" ? " inquiry-top" : pos === "bottom" ? " inquiry-bottom" : "";
      html += `<td class="${s.cls}${inqCls}" data-day="${d}" data-period="${p}">${s.html}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody>';
  tbl.innerHTML = html;
  tbl.querySelectorAll("td").forEach(td => {
    td.addEventListener("click", () => onCellClick(parseInt(td.dataset.day), parseInt(td.dataset.period)));
  });

  renderPanel();
  renderPartnerSchedules();
}

function renderPartnerSchedules() {
  const sec = document.getElementById("partner-section");
  const div = document.getElementById("partner-schedules");
  if (state.confirmed.length === 0) {
    sec.style.display = "none";
    div.innerHTML = "";
    return;
  }
  sec.style.display = "block";

  const myCode = meCode();
  const meName = me().name;
  // 依 partner 分組
  const byPartner = {};
  for (const c of state.confirmed) {
    (byPartner[c.partnerCode] ||= []).push(c);
  }

  let html = "";
  for (const [pcode, confs] of Object.entries(byPartner)) {
    const partner = teacherInfo(pcode);
    const summary = confs.map(c => {
      if (c.type === "sub") return `代 星期${DAY_NAMES[c.day]}${c.period}`;
      return `星期${DAY_NAMES[c.day]}${c.period} ↔ 星期${DAY_NAMES[c.swapDay]}${c.swapPeriod}`;
    }).join("、");
    html += `<div style="margin: 0.6em 0;">`;
    html += `<h3 style="margin: 0 0 0.3em; color:var(--primary);">${partner.name} 老師（${SUBJECT_FULL[partner.subj] || partner.subj}）— ${summary}</h3>`;
    html += renderPartnerScheduleTable(pcode, confs, myCode, meName);
    html += `</div>`;
  }
  div.innerHTML = html;
}

function renderPartnerScheduleTable(pcode, confs, myCode, meName) {
  const marks = {};
  for (const c of confs) {
    const myClass = getEntry(myCode, c.day, c.period);
    marks[`${c.day}-${c.period}`] = { role: "cover-me", myClass };
    if (c.type === "swap") {
      marks[`${c.swapDay}-${c.swapPeriod}`] = { role: "off-swap" };
    }
  }
  let html = '<table class="schedule">' + buildHeader("before") + '<tbody>';
  for (let p = 1; p <= 7; p++) {
    html += `<tr><th>${p}</th>`;
    for (let d = 1; d <= 5; d++) {
      const k = `${d}-${p}`;
      const e = getEntry(pcode, d, p);
      const m = marks[k];
      let cls, content;
      if (m && m.role === "cover-me") {
        cls = "cell-confirmed-swap-in";
        content = `${m.myClass.course}${m.myClass.klass ? " " + m.myClass.klass : ""}<span class="anno">↻ 代 ${meName}</span>`;
      } else if (m && m.role === "off-swap") {
        cls = "cell-confirmed-leave-swap";
        content = `${e.course}${e.klass ? " " + e.klass : ""}<span class="anno">⨯ 不用上 (${meName} 代)</span>`;
      } else {
        // 沒變動的格子：一律灰底（保留課程內容供對方確認位置）
        cls = "cell-partner-context";
        content = e ? `${e.course}${e.klass ? " " + e.klass : ""}` : "·";
      }
      // 對方課表不顯示紫色連堂框
      html += `<td class="${cls}" style="cursor:default">${content}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  return html;
}

function renderPanel() {
  const panel = document.getElementById("panel");
  if (state.mode === "idle") {
    panel.style.display = "none";
    panel.className = "";
    return;
  }
  panel.style.display = "block";
  panel.className = state.mode === "partnerSelected" ? "partner-mode" : "";

  const tcode = meCode();
  const ls = state.leaveSlot;
  const e = getEntry(tcode, ls.day, ls.period);
  const allOthers = TEACHERS.filter(t => t.code !== tcode);
  const myMode = me();
  const sameSubj = allOthers.filter(t => t.subj === myMode.subj);
  const otherSubj = allOthers.filter(t => t.subj !== myMode.subj);
  const freeSame = sameSubj.filter(t => !isOccupied(t.code, ls.day, ls.period));
  const freeCross = otherSubj.filter(t => !isOccupied(t.code, ls.day, ls.period));

  let html = '';
  html += `<div id="panel-status">`;
  html += `<strong>請假時段</strong>：星期${DAY_NAMES[ls.day]} 第 ${ls.period} 節 — ${e.course}${e.klass ? " " + e.klass : ""}`;
  if (state.mode === "leaveSelected") {
    html += `<br>請從下方選一位老師：`;
  } else if (state.mode === "partnerSelected") {
    const p = teacherInfo(state.partnerCode);
    const swapOpts = DATA.filter(d => d.tcode === state.partnerCode && !isOccupied(tcode, d.day, d.period));
    html += `<br><strong style="color:var(--partner)">已選 ${p.name}</strong>`;
    if (swapOpts.length > 0) {
      html += `——課表中橘色虛線 ${swapOpts.length} 格是 <strong>可換的時段</strong>，點下去完成換課；或按下方<strong>「直接代課」</strong>不用換。`;
    } else {
      html += `——他沒有可換的時段，只能直接代課。`;
    }
  }
  html += `</div>`;

  if (state.mode === "leaveSelected" || state.mode === "partnerSelected") {
    html += `<div class="candidate-group"><h3>同科老師（${freeSame.length}）</h3>`;
    if (freeSame.length === 0) {
      html += `<span style="color:var(--muted); font-size:0.9em">該時段同科老師都有課</span>`;
    } else {
      for (const t of freeSame) {
        const active = state.partnerCode === t.code;
        html += `<button class="cand-btn same-subj${active ? ' active' : ''}" data-pcode="${t.code}">${t.name}</button>`;
      }
    }
    html += `</div>`;
    html += `<div class="candidate-group"><h3>自然科其他老師（${freeCross.length}）</h3>`;
    if (freeCross.length === 0) {
      html += `<span style="color:var(--muted); font-size:0.9em">無</span>`;
    } else {
      for (const t of freeCross) {
        const active = state.partnerCode === t.code;
        html += `<button class="cand-btn cross-subj${active ? ' active' : ''}" data-pcode="${t.code}">${t.name}<span style="font-size:0.75em; opacity:0.7"> (${SUBJECT_FULL[t.subj] || t.subj})</span></button>`;
      }
    }
    html += `</div>`;
  }

  if (state.mode === "partnerSelected") {
    html += `<div style="margin-top:0.5em">`;
    html += `<button class="primary" id="confirm-sub-btn">直接代課（不換）</button>`;
    html += `<button id="back-to-leave-btn">換別人</button>`;
    html += `<button id="cancel-btn">取消</button>`;
    html += `</div>`;
  } else {
    html += `<div style="margin-top:0.5em"><button id="cancel-btn">取消</button></div>`;
  }

  panel.innerHTML = html;

  panel.querySelectorAll(".cand-btn").forEach(b => {
    b.addEventListener("click", () => onCandidateClick(b.dataset.pcode));
  });
  const subBtn = document.getElementById("confirm-sub-btn");
  if (subBtn) subBtn.addEventListener("click", confirmSub);
  const backBtn = document.getElementById("back-to-leave-btn");
  if (backBtn) backBtn.addEventListener("click", () => {
    state.mode = "leaveSelected";
    state.partnerCode = null;
    render();
  });
  const cancel = document.getElementById("cancel-btn");
  if (cancel) cancel.addEventListener("click", () => {
    state.mode = "idle";
    state.leaveSlot = null;
    state.partnerCode = null;
    render();
  });
}

function onCellClick(d, p) {
  // 點已確認的 cell → 退回「選代課人」那步（leave 還在，可重選或取消）
  const conf = findConfirmed(d, p);
  if (conf) {
    state.confirmed = state.confirmed.filter(c => c !== conf.c);
    state.mode = "leaveSelected";
    state.leaveSlot = {day: conf.c.day, period: conf.c.period};
    state.partnerCode = null;
    render();
    return;
  }

  if (state.mode === "idle") {
    if (!isOccupied(meCode(), d, p)) return;
    state.mode = "leaveSelected";
    state.leaveSlot = {day: d, period: p};
    render();
    return;
  }

  if (state.mode === "leaveSelected") {
    if (isInLeave(d, p)) {
      // 取消
      state.mode = "idle";
      state.leaveSlot = null;
      render();
      return;
    }
    // 切換成另一格
    if (isOccupied(meCode(), d, p)) {
      state.leaveSlot = {day: d, period: p};
      render();
    }
    return;
  }

  if (state.mode === "partnerSelected") {
    if (isInLeave(d, p)) {
      state.mode = "leaveSelected";
      state.partnerCode = null;
      render();
      return;
    }
    if (isSwapOption(d, p)) {
      // 確認換課
      state.confirmed.push({
        day: state.leaveSlot.day,
        period: state.leaveSlot.period,
        partnerCode: state.partnerCode,
        type: "swap",
        swapDay: d,
        swapPeriod: p,
      });
      state.mode = "idle";
      state.leaveSlot = null;
      state.partnerCode = null;
      render();
      return;
    }
  }
}

function onCandidateClick(pcode) {
  if (state.partnerCode === pcode) {
    state.mode = "leaveSelected";
    state.partnerCode = null;
  } else {
    state.mode = "partnerSelected";
    state.partnerCode = pcode;
  }
  render();
}

function confirmSub() {
  if (state.mode !== "partnerSelected") return;
  state.confirmed.push({
    day: state.leaveSlot.day,
    period: state.leaveSlot.period,
    partnerCode: state.partnerCode,
    type: "sub",
  });
  state.mode = "idle";
  state.leaveSlot = null;
  state.partnerCode = null;
  render();
}

init();
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
html = html.replace("__TEACHERS__", json.dumps(teachers, ensure_ascii=False))

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"[ok] 已寫出 {HTML_PATH}")
print(f"     資料：{len(data)} 筆課程 / {len(teachers)} 位老師")
