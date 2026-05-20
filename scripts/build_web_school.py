"""
從 全校課表_長表.csv 產生「全校版」互動式代課/調課查詢網頁。
與 build_web.py 自然科版的差異：
  · 候選教師依「主授科目」(國/英/自/數/社/其他) 分組
  · IB 課程例外：IB同科 → IB其他科 → 同科 → 其他科 (4 階優先)
  · 130 位老師、`<datalist>` 支援姓名 + 教師代號搜尋
  · UI 不顯示「IB教師／普通班教師」字樣（內部仍用於 IB 分組）
  · 連堂課判斷沿用（探究、IPSS）
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = str(ROOT / "school_wide" / "全校課表_長表.csv")
HTML_PATH = str(ROOT / "school_wide" / "代課查詢_全校.html")
STROKES_JSON = ROOT / "school_wide" / "_strokes.json"
H2C_JS = ROOT / "school_wide" / "_html2canvas.min.js"

# 借用 extract_school 的細科目分類器（給每筆 DATA 預先算課程的細科目）
sys.path.insert(0, str(ROOT / "scripts"))
from extract_school import classify_course_detail

# 載入姓名筆劃表（由 build_strokes.py 從 Unihan 抽取）
strokes_table = {}
if STROKES_JSON.exists():
    strokes_table = json.loads(STROKES_JSON.read_text(encoding="utf-8"))

def name_strokes(name):
    """姓名總筆劃。非中文字（如 Andrew）回傳 999 排到最後。"""
    if not name:
        return 999
    total = 0
    for c in name:
        if c in strokes_table:
            total += strokes_table[c]
        elif "一" <= c <= "鿿":
            total += 0  # 漢字但無筆劃資料 → 算 0
        else:
            return 999  # 含非中文字（英文名）→ 排最後
    return total

def build_data_and_teachers(rows):
    data = [
        {
            "tcode": r["教師代碼"],
            "tname": r["教師"],
            "day": int(r["星期"]),
            "period": int(r["節次"]),
            "course": r["課程名稱"],
            "klass": r["班級"],
            "room": r["教室"],
            "courseDetail": classify_course_detail(r["課程名稱"]) or "",
        }
        for r in rows
    ]
    teachers_map = {}
    for r in rows:
        teachers_map[r["教師代碼"]] = {
            "name": r["教師"],
            "subject": r["主授科目"],
            "detail": r["細科目"],
            "isIB": r["教師類別"] == "IB教師",
            "homeroom": r["導師班級"],
            "strokes": name_strokes(r["教師"]),
        }
    teachers = [{"code": c, **info} for c, info in sorted(teachers_map.items())]
    return data, teachers

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>尋找調代課小幫手</title>
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
  input[type="search"] {
    font-size: 1em; padding: 0.4em; min-width: 11em;
    border: 1px solid var(--border); border-radius: 4px;
  }
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
    color: #010101; font-weight: 500;
  }
  td.cell-confirmed-swap-in {
    background: #d1fae5; border: 2px solid var(--swap);
    color: #064e3b; font-weight: 500;
  }
  /* 探究／IPSS 連堂大粗框 */
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
  table.schedule tbody tr:nth-child(4) > th,
  table.schedule tbody tr:nth-child(4) > td {
    border-bottom: 3px solid #000;
  }
  td .anno {
    display: block; font-size: 0.85em; margin-top: 2px;
  }

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
  .panel-title {
    display: flex;
    align-items: center;
    gap: 0.45em;
    flex-wrap: wrap;
    color: #111827;
    font-weight: 700;
  }
  .panel-badge {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 999px;
    background: #eff6ff;
    color: var(--primary);
    font-size: 0.78em;
    font-weight: 600;
  }
  .panel-guide {
    margin-top: 0.2em;
    color: var(--muted);
    font-size: 0.82em;
  }
  .panel-guide .guide-hr { color: #dc2626; font-weight: 700; }
  .panel-guide .guide-star { color: #16a34a; font-weight: 700; }
  .panel-note {
    margin-top: 0.3em;
    color: #5b21b6;
    font-size: 0.86em;
  }
  .candidate-group { margin: 0.4em 0; }
  .candidate-group h3 {
    margin: 0.3em 0 0.2em;
    font-size: 0.85em;
    color: var(--muted);
    font-weight: normal;
  }
  .candidate-group h3.collapsible {
    cursor: pointer;
    user-select: none;
    padding: 0.4em 0.5em;
    background: #f3f4f6;
    border-radius: 4px;
    margin: 0.4em 0;
  }
  .candidate-group h3.collapsible:hover { background: #e5e7eb; }
  .caret { display: inline-block; width: 0.8em; transition: transform 0.15s; }
  .caret.collapsed { transform: rotate(-90deg); }
  .group-body[hidden] { display: none; }
  .candidate-subgroup { margin: 0.15em 0 0.15em 0.6em; }
  .candidate-subgroup h4 {
    display: inline-block;
    margin: 0.1em 0.3em 0.1em 0;
    font-size: 0.78em;
    color: var(--muted);
    font-weight: normal;
    min-width: 2.6em;
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
  .cand-btn.pri-1 { border-color: var(--sub); color: var(--sub); }
  .cand-btn.pri-2 { border-color: #6366f1; color: #4338ca; }
  .cand-btn.pri-3 { border-color: var(--muted); color: #374151; }
  .cand-btn.pri-4 { border-color: var(--muted); color: var(--muted); }
  .cand-btn.active {
    background: var(--partner); color: white; border-color: var(--partner);
    font-weight: bold;
  }
  #find-partner-hint .hint-keyword {
    cursor: default;
    margin: 0 0.1em;
    background: white;
  }
  #find-partner-hint .hint-keyword:hover { background: white; }

  .legend {
    display: flex; flex-wrap: wrap; gap: 0.5em;
    font-size: 0.8em; margin: 0.4em 0;
  }
  .legend span,
  .legend-chip { padding: 2px 8px; border-radius: 3px; border: 1px solid; }
  .lg-yellow { background: #fef9c3; border-color: #ca8a04; color: #713f12; }
  .lg-leave { background: var(--leave); border-color: #b45309; color: white; }
  .lg-swap-opt { background: #ffedd5; border-color: var(--partner); color: #9a3412; }
  .lg-conf-sub { background: #dbeafe; border-color: var(--sub); color: #1e40af; }
  .lg-conf-swap { background: #fde68a; border-color: #b45309; color: #78350f; }
  .lg-conf-in { background: #d1fae5; border-color: var(--swap); color: #064e3b; }
  .lg-inquiry { background: white; border: 2px solid #7c3aed; color: #5b21b6; }

  /* ⓘ 說明 折疊式按鈕 */
  .help-btn {
    cursor: pointer;
    padding: 0.35em 0.7em;
    color: var(--primary);
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 0.85em;
    user-select: none;
    margin: 0.2em 0;
    line-height: 1;
  }
  .help-btn:hover { background: #eff6ff; border-color: #dbeafe; }
  .help-btn::before {
    content: "▶";
    display: inline-block;
    transition: transform 0.15s;
    font-size: 0.7em;
    color: var(--muted);
    margin-right: 0.25em;
  }
  .help-btn.open::before { transform: rotate(90deg); }
  .help-body {
    padding: 0.5em 0.8em;
    background: #fffbeb;
    border-left: 3px solid var(--primary);
    border-radius: 0 4px 4px 0;
    font-size: 0.85em;
    color: #4b5563;
    margin: 0.2em 0 0.6em 0.3em;
    line-height: 1.6;
  }
  .help-body p { margin: 0.25em 0; }
  .help-body code {
    background: #e5e7eb; padding: 1px 4px;
    border-radius: 3px; font-family: monospace;
  }

  @media (max-width: 600px) {
    body { font-size: 14px; padding: 0 0.4em 3em; }
    table.schedule th, table.schedule td {
      font-size: 0.7em; padding: 3px 2px; height: 4em;
    }
    .cand-btn { font-size: 0.85em; padding: 0.4em 0.7em; }
  }

  /* ── 資料版本確認視窗 ──────────────────────── */
  #version-modal {
    position: fixed; inset: 0; z-index: 9000;
    background: rgba(0,0,0,0.45);
    display: flex; align-items: center; justify-content: center;
  }
  #version-modal .modal-card {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.4em 1.6em 1.2em;
    max-width: 320px;
    text-align: center;
    box-shadow: 0 4px 28px rgba(0,0,0,0.28);
  }
  #version-modal .modal-card h2 {
    margin: 0 0 0.3em; color: var(--primary); font-size: 1.2em;
  }
  #version-modal .modal-card .modal-sub {
    color: var(--muted); font-size: 0.8em; margin: 0 0 1em;
  }

</style>
</head>
<body>


<h1>尋找調代課小幫手 <button class="help-btn" data-target="help-title">ⓘ 說明</button></h1>
<div id="help-title" class="help-body" hidden>
  <p>● 操作流程：1.選你自己 2.看課表選時段 3.選調課老師 4.完成分享訊息</p>
</div>

<section>
  <h2>1. 我是誰</h2>
  <button class="help-btn" data-target="help-1">ⓘ 說明</button>
  <div id="help-1" class="help-body" hidden>
    <p>● 瀏覽器會記得你，下次打開直接是你。</p>
    <p>● 要書籤化「自己」這個身分：在網址後加 <code>#代號</code>（例如 <code>#N60</code>）。</p>
  </div>
  <div style="display:flex; align-items:center; gap:0.75em; flex-wrap:wrap">
    <select id="teacher"></select>
    <span style="color:#9a3412; font-weight:bold">↓在下方點選找要調代課的<span class="legend-chip lg-yellow">時段框框</span>↓</span>
  </div>
  <div style="margin-top:0.5em; font-size:0.9em">
    <label style="cursor:pointer">
      <input type="checkbox" id="ib-mode"> IB 模式
    </label>
  </div>
</section>

<section id="my-schedule-section" style="display:none">
  <h2>2. 我的課表</h2>
  <button class="help-btn" data-target="help-2">ⓘ 說明</button>
  <div id="help-2" class="help-body" hidden>
    <p>● 點黃色格子＝請假該時段，再點一次取消。</p>
    <p>● 確認後的格子再點一次也可以取消。</p>
    <p>● 紫色粗框＝連堂課，兩堂都點，才能找兩節都有空的老師。</p>
  </div>
  <p style="color:#dc2626; font-weight:bold; margin:0.3em 0 0.4em;"></p>
  <div id="legend" class="legend" style="margin:0.4em 0"></div>
  <div style="margin: 0.4em 0; font-size:0.9em">
    顯示日期：
    <select id="date-mode" style="font-size:0.9em; padding:0.25em 0.4em; min-width:auto">
      <option value="none">不顯示</option>
      <option value="this">當週</option>
      <option value="next">下週</option>
    </select>
    <span id="find-partner-hint" hidden style="margin-left:0.6em; color:#2563eb; font-weight:bold"><span class="hint-arrow">↓</span>在下方找調代課<span class="hint-keyword cand-btn pri-1">老師</span><span class="hint-arrow">↓</span></span>
  </div>
  <table class="schedule" id="schedule"></table>
  <div id="panel" style="display:none"></div>
  <div style="margin-top:0.6em">
    <button class="danger" id="reset-btn">清除全部已選方案</button>
    <span id="post-confirm-hint" hidden style="margin-left:0.5em; font-size:0.9em; color:var(--swap)"><br>完成，↑可以再點下一節要請假的時段↑；↓也可以下方確認課表↓</span>
  </div>
</section>

<section id="partner-section" style="display:none">
  <h2>3. 對方課表</h2>
  <button class="help-btn" data-target="help-3">ⓘ 說明</button>
  <div id="help-3" class="help-body" hidden>
    <p>● 每位對方一段獨立的「訊息」「按鈕」「課表」。</p>
    <p>● 訊息：可複製到 LINE / 分享給對方（手機可直接喚起分享面板）。</p>
    <p>● 截圖：把對方課表存成 PNG。手機自動開分享面板，桌面則下載檔案。</p>
    <p>● 日期：依「顯示日期來輔助」的選擇；選「不顯示」時，週一~五自動用當週、週六日用下週。</p>
  </div>
  <div id="partner-schedules"></div>
</section>

<section id="self-section" style="display:none">
  <h2>4. 自己的課表</h2>
  <div id="self-schedule"></div>
  <div style="margin:0.4em 0">
    <button id="self-screenshot" style="padding:0.5em 1em">📸 截圖（自己課表）</button>
    <span id="self-fb" style="margin-left:0.6em; font-size:0.9em; display:none"></span>
  </div>
</section>

<script>
__HTML2CANVAS__
</script>
<script>
const DATA = __DATA__;
const TEACHERS = __TEACHERS__;
const DAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"};
const SUBJECT_ORDER = ["國", "英", "自", "數", "社", "藝", "體", "特", "二外", "本土語"];
// 「我是誰」下拉選單把 自 移到最前面（多數使用者為自然科），其他維持原順序
const DROPDOWN_ORDER = ["自", "國", "英", "數", "社", "藝", "體", "特", "二外", "本土語"];

// 主授／細科 顯示用的全名
const SUBJECT_FULL = {
  "國": "國文科", "英": "英文科", "自": "自然科", "數": "數學科",
  "社": "社會科", "藝": "藝能科", "體": "健體科", "特": "輔導／生命教育",
  "二外": "第二外語", "本土語": "本土語",
};
const DETAIL_FULL = {
  "物": "物理科", "化": "化學科", "生": "生物科", "地科": "地球科學科", "IPSS": "IPSS",
  "史": "歷史科", "地理": "地理科", "公民": "公民科", "心理": "心理",
  "商管": "商業管理", "法律": "法律", "生命教育": "生命教育", "生涯規劃": "生涯規劃",
  "音樂": "音樂科", "美術": "美術科", "藝術生活": "藝術生活", "新媒體藝": "新媒體藝",
  "視覺藝術": "視覺藝術", "表演藝術": "表演藝術",
  "家政": "家政科", "資訊": "資訊科", "生科": "生活科技",
  "體育": "體育科", "健護": "健康教育", "安全教育": "安全教育", "全民國防": "全民國防",
  "日": "日語", "德": "德語", "法": "法語", "西": "西班牙語", "韓": "韓語",
  "客": "客語", "閩": "閩南語", "原": "原住民語",
  "國文": "國文科", "英文": "英文科", "數學": "數學科", "特": "輔導／生命教育",
};
function fullSub(s) { return SUBJECT_FULL[s] || s; }
function fullDet(d) { return DETAIL_FULL[d] || d; }

const SCHED = {};
for (const d of DATA) SCHED[`${d.tcode}-${d.day}-${d.period}`] = d;
function getEntry(tc, d, p) { return SCHED[`${tc}-${d}-${p}`]; }
function isOccupied(tc, d, p) { return !!getEntry(tc, d, p); }

const state = {
  mode: "idle",  // idle | leaveSelected | partnerSelected
  leaveSlot: null,
  partnerCode: null,
  confirmed: [],
  groupOverrides: {},        // 群組摺疊狀態 (label → bool); 不在此 dict 用 priority 預設
};

function teacherInfo(code) { return TEACHERS.find(t => t.code === code); }
function meCode() { return document.getElementById("teacher").value; }
function me() { return teacherInfo(meCode()); }

function getWeekDates(mode) {
  if (mode === "none" || !mode) return null;
  const today = new Date();
  const dow = today.getDay();
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
  return name === "物理地科探究" || name === "化學生物探究" || name === "IPSS";
}
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

// 判斷單一課程名稱是否為 IB 課程：課程名稱不含中文字 = IB 課程
// （與 scripts/extract_school.py 的 is_ib_course 一致）
function isIbCourse(name) {
  if (!name) return false;
  for (const c of name) {
    if (c >= "一" && c <= "鿿") return false;  // 含中文字
  }
  return true;
}

const STORAGE_KEY = "schoolWideSubstituteTeacher";

// 建立「我是誰」下拉選單。IB 模式開啟時只列 IB 教師（35 位）；否則全部 130 位
// 已選的教師若在新清單中仍存在則保留；不存在時瀏覽器自動 fallback 到第一個 option
function populateTeacherDropdown() {
  const sel = document.getElementById("teacher");
  const ibOnly = document.getElementById("ib-mode").checked;
  sel.innerHTML = "";

  const grouped = {};
  for (const t of TEACHERS) {
    if (ibOnly && !t.isIB) continue;
    (grouped[t.subject] ||= []).push(t);
  }
  for (const sub of DROPDOWN_ORDER) {
    const list = grouped[sub];
    if (!list || list.length === 0) continue;
    const og = document.createElement("optgroup");
    og.label = `── ${sub}（${list.length}）──`;
    for (const t of list) {
      const opt = document.createElement("option");
      opt.value = t.code;
      opt.textContent = `${t.name}（${t.code}）`;
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }

  // 還原 localStorage 偏好（若仍在新清單中）；不在則 sel.value 維持瀏覽器自動的第一個
  const saved = localStorage.getItem(STORAGE_KEY) || "";
  if (saved && sel.querySelector(`option[value="${CSS.escape(saved)}"]`)) {
    sel.value = saved;
  }
}

// 顯示「2. 我的課表」（選過身分後才呼叫）
function revealMySchedule() {
  document.getElementById("my-schedule-section").style.display = "block";
}

function init() {
  const sel = document.getElementById("teacher");

  // IB 模式狀態先讀好（影響下拉選單內容）
  const ibModeEl = document.getElementById("ib-mode");
  ibModeEl.checked = localStorage.getItem("ibMode") === "1";

  populateTeacherDropdown();

  // URL hash 優先（如 #N60）；若該老師被 IB 模式擋住則忽略
  const hashCode = location.hash ? location.hash.slice(1).toUpperCase() : "";
  if (hashCode && sel.querySelector(`option[value="${CSS.escape(hashCode)}"]`)) {
    sel.value = hashCode;
    localStorage.setItem(STORAGE_KEY, hashCode);
  }

  // 「2. 我的課表」一開始隱藏；曾選過身分（localStorage 或網址 #代號）才顯示
  if (localStorage.getItem(STORAGE_KEY)) revealMySchedule();

  sel.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEY, sel.value);
    revealMySchedule();
    resetState();
  });
  // 智能預設「顯示日期來輔助」：週一~五 → 當週；週六日 → 下週
  // （使用者仍可手動改成「也可以不顯示」）
  const dateModeEl = document.getElementById("date-mode");
  const dow0 = new Date().getDay();
  dateModeEl.value = (dow0 === 0 || dow0 === 6) ? "next" : "this";
  dateModeEl.addEventListener("change", render);

  // IB 模式 toggle：重建下拉選單（dropdown 也只列 IB 教師）+ 重新算候選
  // 注意 ibModeEl.checked 已在 init 開頭設好，這裡只掛 change handler
  ibModeEl.addEventListener("change", () => {
    localStorage.setItem("ibMode", ibModeEl.checked ? "1" : "0");
    populateTeacherDropdown();
    resetState();
  });

  document.getElementById("reset-btn").addEventListener("click", resetState);
  document.getElementById("self-screenshot").addEventListener("click", doCaptureSelf);

  // 三個 section 的「ⓘ 說明」按鈕（樣式 B）
  document.querySelectorAll(".help-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      target.hidden = !target.hidden;
      btn.classList.toggle("open", !target.hidden);
    });
  });

  render();
}

function resetState() {
  state.mode = "idle";
  state.leaveSlot = null;
  state.partnerCode = null;
  state.confirmed = [];
  state.groupOverrides = {};
  render();
}

function isGroupExpanded(g) {
  if (g.label in state.groupOverrides) return state.groupOverrides[g.label];
  return g.priority < 3;  // 預設：高優先群（連堂/同科/同班）展開，其他科摺疊
}

function toggleGroup(label) {
  // Find the group's default state via priority — but we don't have it here easily,
  // so just flip whatever the current state is.
  const g = currentGroups.find(x => x.label === label);
  if (!g) return;
  state.groupOverrides[label] = !isGroupExpanded(g);
  render();
}

let currentGroups = [];  // 暫存當前 render 的 groups，給 toggleGroup 查用

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
  if (state.mode !== "partnerSelected") return false;
  if (isInLeave(d, p)) return false;
  if (findConfirmed(d, p)) return false;
  if (isOccupied(meCode(), d, p)) return false;
  // 連堂 + partner 兩節都空堂（「兩節都能代的老師」群組）→ 不顯示調課，直接代兩節即可
  if (state.leaveSlot) {
    const paired = getPairedPeriod(meCode(), state.leaveSlot.day, state.leaveSlot.period);
    if (paired && !isOccupied(state.partnerCode, state.leaveSlot.day, paired)) return false;
  }
  const partnerEntry = getEntry(state.partnerCode, d, p);
  if (!partnerEntry) return false;
  // 同班 partner（不同科但教我這個班級）→ 只允許同班級的調課
  const myInfo = teacherInfo(meCode());
  const partnerInfo = teacherInfo(state.partnerCode);
  const myLeave = state.leaveSlot ? getEntry(meCode(), state.leaveSlot.day, state.leaveSlot.period) : null;
  if (myLeave && myLeave.klass) {
    const isSameClassGroup = partnerInfo.subject !== myInfo.subject && teachesKlass(partnerInfo.code, myLeave.klass);
    if (isSameClassGroup && partnerEntry.klass !== myLeave.klass) return false;
  }
  return true;
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
      html: `${partnerClass.course}${partnerClass.klass ? " " + partnerClass.klass : ""}<span class="anno">↔ 點此調課</span>`,
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

  renderLegend();
  renderPanel();
  renderPartnerSchedules();
  renderSelfSchedule();
  document.getElementById("post-confirm-hint").hidden = state.confirmed.length === 0;
  // 點完請假時段後才出現「↓在下方列表找要調代課的時段」
  document.getElementById("find-partner-hint").hidden = !state.leaveSlot;
  updateFindPartnerHintBlink();
}

let findPartnerHintTimer = null;
let findPartnerHintBlinkDone = false;
function updateFindPartnerHintBlink() {
  const hint = document.getElementById("find-partner-hint");
  const arrows = hint ? hint.querySelectorAll(".hint-arrow") : [];
  if (!hint || arrows.length === 0) return;
  if (hint.hidden) {
    if (findPartnerHintTimer) {
      clearInterval(findPartnerHintTimer);
      findPartnerHintTimer = null;
    }
    findPartnerHintBlinkDone = false;
    arrows.forEach(a => { a.innerText = "↓"; });
    return;
  }
  if (findPartnerHintTimer || findPartnerHintBlinkDone) return;
  let alternate = false;
  let count = 0;
  findPartnerHintTimer = setInterval(() => {
    arrows[0].innerText = alternate ? "↓" : "⬇";
    arrows[1].innerText = alternate ? "⬇" : "↓";
    alternate = !alternate;
    count++;
    if (count >= 4) {
      clearInterval(findPartnerHintTimer);
      findPartnerHintTimer = null;
      findPartnerHintBlinkDone = true;
    }
  }, 500);
}

// 動態圖例：只顯示畫面上「實際出現」的格子類型，避免一開始就堆一排不知道意義的色塊
function renderLegend() {
  const tcode = meCode();
  const items = ['<span class="lg-yellow">我有課</span>'];

  if (state.leaveSlot) {
    items.push('<span class="lg-leave">↩ 我請假的時段</span>');
  }

  if (state.mode === "partnerSelected") {
    let hasSwap = false;
    outer: for (let dd = 1; dd <= 5; dd++) {
      for (let pp = 1; pp <= 7; pp++) {
        if (isSwapOption(dd, pp)) { hasSwap = true; break outer; }
      }
    }
    if (hasSwap) items.push('<span class="lg-swap-opt">↔ 可調課的時段</span>');
  }

  const hasSubConfirmed = state.confirmed.some(c => c.type === "sub");
  const hasSwapConfirmed = state.confirmed.some(c => c.type === "swap");
  if (hasSubConfirmed) items.push('<span class="lg-conf-sub">✓ 已選代課</span>');
  if (hasSwapConfirmed) {
    items.push('<span class="lg-conf-swap">✓ 已選調課</span>');
    items.push('<span class="lg-conf-in">✓ 我代他的時段</span>');
  }

  // 紫框連堂提示：使用者課表中有探究/IPSS 連堂才顯示
  let hasInquiry = false;
  outer2: for (let d = 1; d <= 5; d++) {
    for (let p = 1; p <= 7; p++) {
      if (inquiryPositionFor(tcode, d, p)) { hasInquiry = true; break outer2; }
    }
  }
  if (hasInquiry) items.push('<span class="lg-inquiry">紫框表示連堂課（考慮盡量同一個老師）</span>');

  document.getElementById("legend").innerHTML = items.join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

// 自己的課表：完成代/調課後顯示一張非互動的快照表，供截圖
function renderSelfSchedule() {
  const sec = document.getElementById("self-section");
  const div = document.getElementById("self-schedule");
  if (state.confirmed.length === 0) {
    sec.style.display = "none";
    div.innerHTML = "";
    return;
  }
  sec.style.display = "block";

  const myCode = meCode();
  // 標記有變動的格子：請假時段、以及我代課（調課）的時段；其餘維持灰色
  const marks = {};
  for (const c of state.confirmed) {
    marks[`${c.day}-${c.period}`] = { role: "my-leave", c };
    if (c.type === "swap") {
      marks[`${c.swapDay}-${c.swapPeriod}`] = { role: "my-cover", c };
    }
  }

  let html = '<table class="schedule">' + buildHeader("before") + '<tbody>';
  for (let p = 1; p <= 7; p++) {
    html += `<tr><th>${p}</th>`;
    for (let d = 1; d <= 5; d++) {
      const m = marks[`${d}-${p}`];
      const e = getEntry(myCode, d, p);
      let cls, content;
      if (m && m.role === "my-leave") {
        // 我請假、由對方代的時段 → 與「對方課表」的「不用上」風格一致
        const partner = teacherInfo(m.c.partnerCode);
        cls = "cell-confirmed-leave-swap";
        content = `${e.course}${e.klass ? " " + e.klass : ""}<span class="anno">⨯ 不用上 ${partner.name}代</span>`;
      } else if (m && m.role === "my-cover") {
        // 我去代對方課的時段 → 與「對方課表」的「代 XXX」風格一致
        const partner = teacherInfo(m.c.partnerCode);
        const partnerEntry = getEntry(m.c.partnerCode, d, p);
        cls = "cell-confirmed-swap-in";
        content = `${partnerEntry.course}${partnerEntry.klass ? " " + partnerEntry.klass : ""}<span class="anno">↻ 代 ${partner.name}</span>`;
      } else {
        // 沒有變動 → 灰色
        cls = "cell-partner-context";
        content = e ? `${e.course}${e.klass ? " " + e.klass : ""}` : "·";
      }
      const pos = inquiryPositionFor(myCode, d, p);
      const inqCls = pos === "top" ? " inquiry-top" : pos === "bottom" ? " inquiry-bottom" : "";
      html += `<td class="${cls}${inqCls}" style="cursor:default">${content}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  div.innerHTML = html;
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
  const byPartner = {};
  for (const c of state.confirmed) {
    (byPartner[c.partnerCode] ||= []).push(c);
  }

  let html = "";
  for (const [pcode, confs] of Object.entries(byPartner)) {
    const fullText = generateSummaryForPartner(pcode, confs);

    html += `<div data-pcard-pcode="${pcode}" style="margin: 1em 0; padding: 0.8em; border:1px solid var(--border); border-radius:6px;">`;
    // 訊息預覽（先寫出來再讓使用者複製）
    html += `<pre style="background:#f9fafb; border:1px solid var(--border); padding:0.6em 0.8em; border-radius:4px; margin:0.4em 0; white-space:pre-wrap; word-break:break-word; font-size:0.9em; line-height:1.6; font-family:inherit;">${escapeHtml(fullText)}</pre>`;
    // 按鈕
    html += `<div style="margin:0.4em 0">`;
    html += `<button class="primary act-copy" data-pcode="${pcode}" style="padding:0.5em 1em">📋 複製文字訊息</button>`;
    html += `<button class="act-share" data-pcode="${pcode}" style="padding:0.5em 1em">📤 分享文字訊息</button>`;
    html += `<button class="act-screenshot" data-pcode="${pcode}" style="padding:0.5em 1em">📸 截圖（對方課表）</button>`;
    html += `<span class="act-fb" data-pcode="${pcode}" style="margin-left:0.6em; font-size:0.9em; display:none"></span>`;
    html += `</div>`;
    // 對方課表
    html += renderPartnerScheduleTable(pcode, confs, myCode, meName);
    html += `</div>`;
  }
  div.innerHTML = html;

  // Wire up per-partner buttons
  div.querySelectorAll(".act-copy").forEach(btn => {
    btn.addEventListener("click", () => doCopyForPartner(btn.dataset.pcode));
  });
  div.querySelectorAll(".act-share").forEach(btn => {
    btn.addEventListener("click", () => doShareForPartner(btn.dataset.pcode));
  });
  div.querySelectorAll(".act-screenshot").forEach(btn => {
    btn.addEventListener("click", () => doCaptureForPartner(btn.dataset.pcode));
  });
}

function dateStamp() {
  const t = new Date();
  return `${t.getFullYear()}${String(t.getMonth()+1).padStart(2,"0")}${String(t.getDate()).padStart(2,"0")}`;
}

// 共用：把一張表格截圖 → 行動裝置分享 / 桌面下載。fb 是 (msg, ok) 回呼
async function captureTable(table, fname, fb) {
  if (!table) return;
  fb("處理中…", true);
  try {
    const canvas = await html2canvas(table, {
      scale: 2,
      backgroundColor: "#ffffff",
      logging: false,
    });
    canvas.toBlob(async (blob) => {
      if (!blob) { fb("截圖失敗", false); return; }
      const file = new File([blob], fname, { type: "image/png" });
      // 行動裝置先試 Web Share API (檔案分享)
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({ files: [file] });
          fb("分享面板已開啟", true);
          return;
        } catch (e) {
          if (e.name === "AbortError") return;  // 使用者取消
          // 否則 fall through 下載
        }
      }
      // 桌面或不支援 → 下載 PNG
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      fb("已下載 PNG", true);
    }, "image/png");
  } catch (err) {
    console.error(err);
    fb("截圖失敗（請看 console）", false);
  }
}

function doCaptureForPartner(pcode) {
  const card = document.querySelector(`[data-pcard-pcode="${pcode}"]`);
  if (!card) return;
  const table = card.querySelector("table.schedule");
  const partner = teacherInfo(pcode);
  const fname = `${me().name}_${partner.name}_${dateStamp()}.png`;
  captureTable(table, fname, (msg, ok) => showFb(pcode, msg, ok));
}

function doCaptureSelf() {
  const table = document.querySelector("#self-schedule table.schedule");
  const fname = `${me().name}_自己課表_${dateStamp()}.png`;
  captureTable(table, fname, showSelfFb);
}

function feedbackEl(pcode) {
  return document.querySelector(`.act-fb[data-pcode="${pcode}"]`);
}

function showFb(pcode, msg, ok) {
  const el = feedbackEl(pcode);
  if (!el) return;
  el.textContent = msg;
  el.style.display = "inline";
  el.style.color = ok ? "var(--swap)" : "#dc2626";
  setTimeout(() => { if (el) el.style.display = "none"; }, 2500);
}

function showSelfFb(msg, ok) {
  const el = document.getElementById("self-fb");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "inline";
  el.style.color = ok ? "var(--swap)" : "#dc2626";
  setTimeout(() => { el.style.display = "none"; }, 2500);
}

async function doCopyForPartner(pcode) {
  const confs = state.confirmed.filter(c => c.partnerCode === pcode);
  if (confs.length === 0) return;
  const text = generateSummaryForPartner(pcode, confs);
  const ok = await copyToClipboard(text);
  showFb(pcode, ok ? "已複製到剪貼簿" : "複製失敗（請長按上方文字選取）", ok);
}

async function doShareForPartner(pcode) {
  const confs = state.confirmed.filter(c => c.partnerCode === pcode);
  if (confs.length === 0) return;
  const text = generateSummaryForPartner(pcode, confs);
  if (navigator.share) {
    try {
      await navigator.share({ text });
      showFb(pcode, "分享面板已開啟", true);
    } catch (e) {
      if (e.name !== "AbortError") showFb(pcode, "分享失敗", false);
    }
  } else {
    // Fallback: copy
    const ok = await copyToClipboard(text);
    showFb(pcode, ok ? "瀏覽器不支援分享，已複製" : "分享/複製都失敗", ok);
  }
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e2) {}
    document.body.removeChild(ta);
    return ok;
  }
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
        cls = "cell-partner-context";
        content = e ? `${e.course}${e.klass ? " " + e.klass : ""}` : "·";
      }
      html += `<td class="${cls}" style="cursor:default">${content}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  return html;
}

// 預先索引：班級 → 教過的老師 set
const KLASS_TO_TEACHERS = {};
for (const d of DATA) {
  if (!d.klass) continue;
  (KLASS_TO_TEACHERS[d.klass] ||= new Set()).add(d.tcode);
}
function teachesKlass(tcode, klass) {
  return klass && KLASS_TO_TEACHERS[klass] && KLASS_TO_TEACHERS[klass].has(tcode);
}

// 找連堂的另一節（top → next, bottom → prev, 否則 null）
function getPairedPeriod(tcode, day, period) {
  const pos = inquiryPositionFor(tcode, day, period);
  if (pos === "top") return period + 1;
  if (pos === "bottom") return period - 1;
  return null;
}

// 取得候選老師分組
//   連堂課額外最高優先群組「兩堂都能代」（不論科目）
//   非 IB 課程：3 階  同科 → 同班 → 其他科
//   IB 課程：5 階    IB同科 → IB同班 → IB其他科 → 同科 → 其他科
//   群組互斥（高優先群已收的不會再進低優先群）
function getCandidateGroups(leaveSlot) {
  const tcode = meCode();
  const myInfo = teacherInfo(tcode);
  const mySub = myInfo.subject;
  const e = getEntry(tcode, leaveSlot.day, leaveSlot.period);
  const ibLeave = isIbCourse(e.course);
  const myKlass = e.klass;
  const pairedPeriod = getPairedPeriod(tcode, leaveSlot.day, leaveSlot.period);

  let free = TEACHERS.filter(t => t.code !== tcode && !isOccupied(t.code, leaveSlot.day, leaveSlot.period));
  const groups = [];

  // 連堂候選（兩節都空堂）先計算，後面依 IB / 非 IB 分開推入
  // 連堂群組 priority 0 = 顯示在最頂端、預設展開
  let bothAll = [];
  let lo = 0, hi = 0;
  if (pairedPeriod) {
    bothAll = free.filter(t => !isOccupied(t.code, leaveSlot.day, pairedPeriod));
    const bothCodes = new Set(bothAll.map(t => t.code));
    free = free.filter(t => !bothCodes.has(t.code));
    lo = Math.min(leaveSlot.period, pairedPeriod);
    hi = Math.max(leaveSlot.period, pairedPeriod);
  }

  const isSame = t => t.subject === mySub;
  const isSameClass = t => teachesKlass(t.code, myKlass);

  // 同班候選需要：teaches my class AND 至少有一個同班級時段我空堂（才有調課可能）
  // 沒有同班級調課可能性的老師會落到「其他科」群組（直接代課仍可）
  const canSwapMyKlass = (tcode) => {
    if (!myKlass) return false;
    return DATA.some(d =>
      d.tcode === tcode &&
      d.klass === myKlass &&
      !isOccupied(meCode(), d.day, d.period)
    );
  };

  // 同科群組標籤：含 ★ 提示同子科。若主授和細科顯示相同（國/英/數/特單一細科），就不重複加 ★ 提示
  const myDetail = myInfo.detail;
  const sameSubLabel = (myDetail && fullDet(myDetail) !== fullSub(mySub))
    ? `第二優先 · 同領域（${fullSub(mySub)}）的老師 ★表示${fullDet(myDetail)}`
    : `第二優先 · 同領域（${fullSub(mySub)}）的老師`;
  const sameKlassLabel = `第一優先 · 相同任課班級的老師`;

  if (ibLeave) {
    // IB 課程 → 找 IB 老師優先級 > 找同科。連堂群組也拆成 IB / 非 IB
    // IB 模式開啟時，所有非 IB 群組（連堂/同科/其他）一律隱藏
    const ibOnly = document.getElementById("ib-mode").checked;
    const ibBoth = bothAll.filter(t => t.isIB);
    const nonIbBoth = bothAll.filter(t => !t.isIB);
    if (ibBoth.length > 0) {
      groups.push({
        label: `兩節都能代的 IB 老師（連堂第 ${lo}-${hi} 節）`,
        priority: 0, teachers: ibBoth, coverBoth: true,
      });
    }
    const ibSameSub = free.filter(t => t.isIB && isSame(t));
    const ibSameKlass = free.filter(t => t.isIB && !isSame(t) && isSameClass(t) && canSwapMyKlass(t.code));
    const ibSameKlassCodes = new Set(ibSameKlass.map(t => t.code));
    const ibOther = free.filter(t => t.isIB && !isSame(t) && !ibSameKlassCodes.has(t.code));
    if (myKlass) groups.push({ label: `IB優先 · ${sameKlassLabel}`, priority: 1, teachers: ibSameKlass, kind: "sameKlass" });
    groups.push({ label: `IB優先 · ${sameSubLabel}`, priority: 2, teachers: ibSameSub, kind: "sameSub" });
    groups.push({ label: "IB · 其他科別選擇", priority: 3, teachers: ibOther, splitByDomain: true });
    if (!ibOnly) {
      const sameSub = free.filter(t => !t.isIB && isSame(t));
      const other = free.filter(t => !t.isIB && !isSame(t));
      if (nonIbBoth.length > 0) {
        groups.push({
          label: `兩節都能代的其他老師（連堂第 ${lo}-${hi} 節）`,
          priority: 4, teachers: nonIbBoth, coverBoth: true,
        });
      }
      groups.push({ label: sameSubLabel, priority: 4, teachers: sameSub, kind: "sameSub" });
      groups.push({ label: "其他科別選擇", priority: 5, teachers: other, splitByDomain: true });
    }
    return groups;
  }

  // 非 IB 課程：連堂群組不分 IB / 非 IB（一起列）
  if (bothAll.length > 0) {
    groups.push({
      label: `兩節都能代的老師（連堂第 ${lo}-${hi} 節）`,
      priority: 0, teachers: bothAll, coverBoth: true,
    });
  }
  const sameSub = free.filter(isSame);
  const sameKlassNotSub = free.filter(t => !isSame(t) && isSameClass(t) && canSwapMyKlass(t.code));
  const sameKlassCodes = new Set(sameKlassNotSub.map(t => t.code));
  const other = free.filter(t => !isSame(t) && !sameKlassCodes.has(t.code));
  if (myKlass) groups.push({ label: sameKlassLabel, priority: 1, teachers: sameKlassNotSub, kind: "sameKlass" });
  groups.push({ label: sameSubLabel, priority: 2, teachers: sameSub, kind: "sameSub" });
  groups.push({ label: "其他科別選擇", priority: 3, teachers: other, splitByDomain: true });
  return groups;
}

// 排序：本班導師 → 同細科 → 姓名筆劃 小→大 → (tie) 教師代號
function sortCandidates(arr, leaveKlass, leaveDetail) {
  return arr.slice().sort((a, b) => {
    const aHr = (leaveKlass && a.homeroom === leaveKlass) ? 0 : 1;
    const bHr = (leaveKlass && b.homeroom === leaveKlass) ? 0 : 1;
    if (aHr !== bHr) return aHr - bHr;
    const aDt = (leaveDetail && a.detail === leaveDetail) ? 0 : 1;
    const bDt = (leaveDetail && b.detail === leaveDetail) ? 0 : 1;
    if (aDt !== bDt) return aDt - bDt;
    if (a.strokes !== b.strokes) return a.strokes - b.strokes;
    return a.code.localeCompare(b.code);
  });
}

function candBtn(t, priority, leaveKlass, leaveDetail) {
  const active = state.partnerCode === t.code;
  const isHomeroom = leaveKlass && t.homeroom === leaveKlass;
  const isSameDetail = leaveDetail && t.detail === leaveDetail;
  const hrTag = isHomeroom ? `<span style="color:#dc2626; font-weight:bold; margin-left:0.15em;">（導師）</span>` : '';
  // 同細科加 ★ 標記
  const dtTag = (isSameDetail && !isHomeroom) ? `<span style="color:var(--swap); margin-left:0.15em;">★</span>` : '';
  // 括弧內顯示細科目全名（譬如「物理科」）；無細科則 fallback 主授全名
  const labelInParen = t.detail ? fullDet(t.detail) : fullSub(t.subject);
  return `<button class="cand-btn pri-${priority}${active ? ' active' : ''}" data-pcode="${t.code}"><strong style="font-weight:700">${t.name}</strong>${hrTag}${dtTag}<span style="font-size:0.75em; opacity:0.68; margin-left:0.25em">${labelInParen}</span></button>`;
}

function groupSubtitle(g) {
  if (g.coverBoth) return "DOUBLE PERIOD";
  if (g.kind === "sameKlass") return "SAME CLASS";
  if (g.kind === "sameSub") {
    const starHint = (g.label.match(/★表示(.+)$/) || [])[1];
    return starHint ? `SAME SUBJECT　★ = ${starHint}` : "SAME SUBJECT";
  }
  if (g.splitByDomain) return "OTHER SUBJECTS";
  return "";
}

function groupTitleHtml(g, caretHtml) {
  const label = escapeHtml(g.label).replace(/\s*★表示.+$/, "");
  const subtitle = groupSubtitle(g);
  const subHtml = subtitle
    ? `<small style="display:block; margin-top:0.2em; font-size:0.78em; font-weight:600; color:#9ca3af; letter-spacing:0.04em;">${escapeHtml(subtitle)}</small>`
    : "";
  return `${caretHtml}<span style="font-size:1.18em; font-weight:800; color:#1c1917; line-height:1.2;">${label}</span>${subHtml}`;
}

function renderGroups(groups, leaveKlass, leaveDetail) {
  currentGroups = groups;
  let html = '';
  for (const g of groups) {
    const expanded = isGroupExpanded(g);

    const headerCls = (g.priority >= 3) ? "collapsible" : "";
    const caretHtml = (g.priority >= 3) ? `<span class="caret${expanded ? '' : ' collapsed'}">▼</span> ` : '';
    const dataAttr = (g.priority >= 3) ? `data-toggle-label="${escapeHtml(g.label)}"` : '';
    html += `<div class="candidate-group">`;
    html += `<h3 class="${headerCls}" ${dataAttr}>${groupTitleHtml(g, caretHtml)}</h3>`;
    html += `<div class="group-body" ${expanded ? '' : 'hidden'}>`;

    if (g.splitByDomain) {
      if (g.teachers.length === 0) {
        html += `<span style="color:var(--muted); font-size:0.9em">無</span>`;
      } else {
        for (const sub of SUBJECT_ORDER) {
          const subT = sortCandidates(g.teachers.filter(t => t.subject === sub), leaveKlass, leaveDetail);
          if (subT.length === 0) continue;
          html += `<div class="candidate-subgroup"><h4>${sub}</h4>`;
          for (const t of subT) html += candBtn(t, g.priority, leaveKlass, leaveDetail);
          html += `</div>`;
        }
      }
    } else {
      const sorted = sortCandidates(g.teachers, leaveKlass, leaveDetail);
      if (sorted.length === 0) {
        let emptyMsg = "都在上課";
        if (g.kind === "sameKlass") emptyMsg = "這班的老師這節都在上課";
        else if (g.kind === "sameSub") {
          const meInfo = teacherInfo(meCode());
          emptyMsg = `${fullSub(meInfo.subject)}老師這節都在上課`;
        }
        html += `<span style="color:var(--muted); font-size:0.9em">${emptyMsg}</span>`;
      } else {
        for (const t of sorted) html += candBtn(t, g.priority, leaveKlass, leaveDetail);
      }
    }

    html += `</div></div>`;
  }
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
  const ibLeave = isIbCourse(e.course);
  const paired = getPairedPeriod(tcode, ls.day, ls.period);
  const groups = getCandidateGroups(ls);

  let html = '';
  html += `<div id="panel-status">`;
  html += `<div class="panel-title"><span style="font-size:1.3em; font-weight:900; line-height:1.15; color:#1c1917;">這節有空的老師</span>`;
  if (ibLeave) {
    const ibOnly = document.getElementById("ib-mode").checked;
    const ibLabel = ibOnly ? "IB 課程 · 只列 IB 老師" : "IB 課程";
    html += `<span class="panel-badge">${ibLabel}</span>`;
  }
  html += `</div>`;
  html += `<div class="panel-guide" style="font-size:0.82em; color:#78716c; line-height:1.6;"><span class="guide-hr">（導師）</span>＝該班導師　<span class="guide-star">★</span>＝同科目老師　右側小字顯示任教科目</div>`;
  if (paired) {
    const lo = Math.min(ls.period, paired);
    const hi = Math.max(ls.period, paired);
    html += `<div class="panel-note">⚠️ 這是連堂第 ${lo}-${hi} 節。「兩節都能代的老師」可一人代兩節；要分兩位代，就分開處理。</div>`;
  }
  if (state.mode === "partnerSelected") {
    const p = teacherInfo(state.partnerCode);
    const partnerCoversBoth = paired && !isOccupied(state.partnerCode, ls.day, paired);
    if (partnerCoversBoth) {
      html += `<br><strong style="color:var(--partner)">（${p.name} 老師 兩節都有空，可一次代完）</strong>`;
    } else if (paired) {
      html += `<br><strong style="color:var(--partner)">（${p.name} 老師 只有這節空，另一節要再找人）</strong>`;
    } else {
      // 真實算可調課時段數（套用同班限制）
      let swapCount = 0;
      for (let dd = 1; dd <= 5; dd++) {
        for (let pp = 1; pp <= 7; pp++) {
          if (isSwapOption(dd, pp)) swapCount++;
        }
      }
      if (swapCount > 0) {
        html += `<div style="margin-top:0.55em; color:#9a3412; line-height:1.7;">`;
        html += `<div><b style="color:#7c2d12; font-weight:900; margin-right:0.35em;">要調課</b>在上方↑選擇要調課的時段</div>`;
        html += `<div><b style="color:#7c2d12; font-weight:900; margin-right:0.35em;">要代課</b>在下方↓點「確認代課」</div>`;
        html += `</div>`;
      } else {
        html += `<br><strong style="color:var(--partner)">（${p.name} 老師 沒有空堂可調，只能請他代課）</strong>`;
      }
    }
  }
  html += `</div>`;

  if (state.mode === "leaveSelected" || state.mode === "partnerSelected") {
    html += renderGroups(groups, e.klass, e.courseDetail);
  }

  if (state.mode === "partnerSelected") {
    const partnerCoversBoth = paired && !isOccupied(state.partnerCode, ls.day, paired);
    const btnText = partnerCoversBoth ? "確認代課（兩節）" : (paired ? "確認代課（這節）" : "確認代課");
    html += `<div style="margin-top:0.5em">`;
    html += `<button class="primary" id="confirm-sub-btn">${btnText}</button>`;
    html += `<button id="cancel-btn">取消</button>`;
    html += `</div>`;
  } else {
    html += `<div style="margin-top:0.5em"><button id="cancel-btn">取消</button></div>`;
  }

  panel.innerHTML = html;

  // accordion: 群組標題點擊摺疊/展開
  panel.querySelectorAll("h3.collapsible").forEach(h => {
    h.addEventListener("click", () => toggleGroup(h.dataset.toggleLabel));
  });

  panel.querySelectorAll(".cand-btn").forEach(b => {
    b.addEventListener("click", () => onCandidateClick(b.dataset.pcode));
  });
  const subBtn = document.getElementById("confirm-sub-btn");
  if (subBtn) subBtn.addEventListener("click", confirmSub);
  const cancel = document.getElementById("cancel-btn");
  if (cancel) cancel.addEventListener("click", () => {
    state.mode = "idle";
    state.leaveSlot = null;
    state.partnerCode = null;
    render();
  });
}

function onCellClick(d, p) {
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
      state.mode = "idle";
      state.leaveSlot = null;
      render();
      return;
    }
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
  const ls = state.leaveSlot;
  const partner = state.partnerCode;
  // 連堂偵測：若這節是連堂、且 partner 在另一節也空堂 → 兩節一起代
  const paired = getPairedPeriod(meCode(), ls.day, ls.period);
  const partnerCoversBoth = paired && !isOccupied(partner, ls.day, paired);

  state.confirmed.push({
    day: ls.day, period: ls.period, partnerCode: partner, type: "sub",
  });
  if (partnerCoversBoth) {
    state.confirmed.push({
      day: ls.day, period: paired, partnerCode: partner, type: "sub",
    });
  }
  state.mode = "idle";
  state.leaveSlot = null;
  state.partnerCode = null;
  render();
}

// ─── 摘要產生（每位對方一段） ──────────────────────
function pickWeekMode() {
  // 用使用者已選的「顯示日期來輔助」；若選不顯示，週一~五預設當週、週六日預設下週
  const explicit = document.getElementById("date-mode").value;
  if (explicit === "this" || explicit === "next") return explicit;
  const dow = new Date().getDay();  // 0=週日 6=週六
  return (dow === 0 || dow === 6) ? "next" : "this";
}

function generateSummaryForPartner(pcode, confs) {
  const meInfo = teacherInfo(meCode());
  const partner = teacherInfo(pcode);
  const dates = getWeekDates(pickWeekMode());
  const lines = [];
  for (const c of confs) {
    const myEntry = getEntry(meCode(), c.day, c.period);
    const dateStr = `${dates[c.day-1].getMonth()+1}/${dates[c.day-1].getDate()}`;
    const klassStr = myEntry.klass ? ` ${myEntry.klass}班` : "";
    lines.push(`・${dateStr}(${DAY_NAMES[c.day]}) 第${c.period}節 ${myEntry.course}${klassStr} →${partner.name}老師 代課 (${meInfo.name}請假)`);
    if (c.type === "swap") {
      const partnerEntry = getEntry(pcode, c.swapDay, c.swapPeriod);
      const swapDateStr = `${dates[c.swapDay-1].getMonth()+1}/${dates[c.swapDay-1].getDate()}`;
      const pKlassStr = partnerEntry.klass ? ` ${partnerEntry.klass}班` : "";
      lines.push(`・${swapDateStr}(${DAY_NAMES[c.swapDay]}) 第${c.swapPeriod}節 ${partnerEntry.course}${pKlassStr} ↔${meInfo.name}老師 上課 (請${partner.name}老師休息)`);
    }
  }
  return `${meInfo.name}老師與${partner.name}老師 代課/調課提醒：\n${lines.join("\n")}`;
}

init();
</script>

<p style="color: #718096; font-size: 14px; letter-spacing: 0.5px;">
    用起來有問題？
    <a href="mailto:chaher@dysh.tyc.edu.tw" style="color: #2d3748; font-weight: 600; text-decoration: none; border-bottom: 1px solid #2d3748; padding-bottom: 2px; transition: 0.2s;">
        mail &#10142;
    </a>
</p>

<div id="version-modal">
  <div class="modal-card">
    <h2>資料版本 114-2</h2>
    <p class="modal-sub">這個程式只能幫忙對課表找時段，但不知道其他調代課規則。</p>
    <button class="primary" id="version-modal-ok">我知道了</button>
  </div>
</div>
<script>
(function () {
  const modal = document.getElementById("version-modal");
  function closeModal() { modal.style.display = "none"; }
  document.getElementById("version-modal-ok").addEventListener("click", closeModal);
  modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
})();
</script>
</body>
</html>
"""

def build_html(data, teachers, h2c_js_path=None):
    h2c_path = h2c_js_path or H2C_JS
    h2c_src = h2c_path.read_text(encoding="utf-8") if h2c_path.exists() else "// html2canvas missing"
    html = TEMPLATE.replace("__HTML2CANVAS__", h2c_src)
    html = html.replace("__DATA__",     json.dumps(data,     ensure_ascii=False))
    html = html.replace("__TEACHERS__", json.dumps(teachers, ensure_ascii=False))
    return html

if __name__ == "__main__":
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    data, teachers = build_data_and_teachers(rows)
    html = build_html(data, teachers)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] 已寫出 {HTML_PATH}")
    print(f"     資料：{len(data)} 筆課程 / {len(teachers)} 位老師")
