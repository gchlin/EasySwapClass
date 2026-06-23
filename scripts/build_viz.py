#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_viz.py
根據 Analysis/analysis_data.json 生成互動式 HTML 報告

執行方式（在 課表分析/ 目錄下）：
    python scripts/build_viz.py

輸出：
    Analysis/workload_viz.html  - 互動式超鐘點視覺化報告
"""
import json
import pathlib

DATA_PATH = pathlib.Path("Analysis/analysis_data.json")
OUT_PATH  = pathlib.Path("Analysis/workload_viz.html")

def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)

def build_html(data):
    teachers = data["teachers"]

    # 分組：正式教師 vs 兼課/教練
    regular   = [t for t in teachers if t.get("超鐘點") is not None]
    parttime  = [t for t in teachers if t.get("超鐘點") is None]

    regular_sorted = sorted(regular, key=lambda x: -(x["超鐘點"] or 0))

    # 科目別統計
    from collections import defaultdict
    subj_data = defaultdict(list)
    for t in regular:
        if t.get("科目"):
            subj_data[t["科目"]].append(t["超鐘點"] or 0)

    subj_stats = []
    for subj, vals in subj_data.items():
        n = len(vals)
        total = sum(vals)
        avg   = total / n if n else 0
        subj_stats.append({"subject": subj, "count": n, "total": total, "avg": round(avg, 1)})
    subj_stats.sort(key=lambda x: -x["avg"])

    # 全體統計
    all_ot = [t["超鐘點"] for t in regular if t.get("超鐘點") is not None]
    mean_ot = sum(all_ot) / len(all_ot) if all_ot else 0
    import math
    std_ot  = math.sqrt(sum((x - mean_ot)**2 for x in all_ot) / len(all_ot)) if all_ot else 0
    threshold = mean_ot + 2 * std_ot

    teachers_json  = json.dumps(teachers,       ensure_ascii=False)
    regular_json   = json.dumps(regular_sorted, ensure_ascii=False)
    subj_json      = json.dumps(subj_stats,     ensure_ascii=False)
    mean_json      = json.dumps(round(mean_ot, 1))
    std_json       = json.dumps(round(std_ot, 1))
    threshold_json = json.dumps(round(threshold, 1))

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>113-2 教師超鐘點勞務分析</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --primary: #2563eb;
    --danger:  #dc2626;
    --warn:    #f59e0b;
    --ok:      #16a34a;
    --bg:      #f8fafc;
    --card:    #ffffff;
    --border:  #e2e8f0;
    --text:    #1e293b;
    --muted:   #64748b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
    background: var(--bg); color: var(--text);
    font-size: 14px; line-height: 1.6;
  }}
  header {{
    background: var(--primary); color: #fff;
    padding: 20px 24px;
  }}
  header h1 {{ font-size: 20px; }}
  header p  {{ font-size: 13px; opacity: .8; margin-top: 4px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .stats-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .stat-card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px; text-align: center;
  }}
  .stat-card .val {{ font-size: 28px; font-weight: 700; color: var(--primary); }}
  .stat-card .lbl {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px; margin-bottom: 24px;
  }}
  .card h2 {{ font-size: 16px; margin-bottom: 12px; }}
  .controls {{
    display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;
  }}
  input[type=text], select {{
    border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 10px; font-size: 13px; outline: none;
    font-family: inherit;
  }}
  input[type=text]:focus, select:focus {{ border-color: var(--primary); }}
  .search-box {{ flex: 1; min-width: 200px; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 13px;
  }}
  th, td {{
    padding: 8px 10px; text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  th {{
    background: #f1f5f9; font-weight: 600; cursor: pointer;
    user-select: none; white-space: nowrap;
  }}
  th:hover {{ background: #e2e8f0; }}
  th.sort-asc::after  {{ content: " ▲"; font-size: 11px; }}
  th.sort-desc::after {{ content: " ▼"; font-size: 11px; }}
  tr:hover {{ background: #f8fafc; }}
  .badge {{
    display: inline-block; padding: 2px 7px; border-radius: 10px;
    font-size: 11px; font-weight: 600; white-space: nowrap;
  }}
  .badge-danger  {{ background: #fee2e2; color: var(--danger); }}
  .badge-warn    {{ background: #fef3c7; color: #b45309; }}
  .badge-ok      {{ background: #dcfce7; color: var(--ok); }}
  .badge-neutral {{ background: #f1f5f9; color: var(--muted); }}
  .chart-wrap {{ position: relative; }}
  #chartRankingWrap {{ height: 500px; overflow-y: auto; }}
  #chartSubjectWrap {{ height: 380px; }}
  .note {{
    background: #fffbeb; border-left: 4px solid var(--warn);
    padding: 10px 14px; border-radius: 4px; font-size: 12px;
    color: #78350f; margin-bottom: 16px;
  }}
  .highlight {{ background: #fef9c3 !important; }}
  .pagination {{
    display: flex; gap: 6px; align-items: center;
    margin-top: 12px; flex-wrap: wrap;
  }}
  .pagination button {{
    border: 1px solid var(--border); border-radius: 4px;
    padding: 4px 10px; cursor: pointer; background: var(--card);
    font-family: inherit; font-size: 12px;
  }}
  .pagination button.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
  .pagination button:hover:not(.active) {{ background: #f1f5f9; }}
  #pageInfo {{ font-size: 12px; color: var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>113-2 教師超鐘點勞務分析</h1>
  <p>超鐘點 = 合計 − 基本鐘點 | 依據：school_wide/113-2課表資料含所有欄位.csv | 腳本：scripts/analyze_workload.py + build_viz.py</p>
</header>

<div class="container">

  <!-- 統計摘要 -->
  <div class="stats-grid" id="statsGrid"></div>

  <!-- 個人查詢 -->
  <div class="card">
    <h2>個人查詢</h2>
    <div class="controls">
      <input id="personSearch" type="text" class="search-box" placeholder="輸入教師姓名或代碼...">
    </div>
    <div id="personResult" style="font-size:13px; color:var(--muted);">請輸入姓名或代碼</div>
  </div>

  <!-- 全員排名圖 -->
  <div class="card">
    <h2>全員超鐘點排名（正式教師，依超鐘點由高至低）</h2>
    <div class="note">
      橘紅色 = 超過 mean+2σ 的極端值 ｜ 藍色 = 一般超鐘點 ｜ 虛線 = 全體平均
    </div>
    <div class="controls">
      <select id="filterSubject">
        <option value="">全部科目</option>
      </select>
      <select id="filterRole">
        <option value="">全部主職</option>
      </select>
    </div>
    <div id="chartRankingWrap">
      <canvas id="chartRanking"></canvas>
    </div>
  </div>

  <!-- 科目比較圖 -->
  <div class="card">
    <h2>科目別超鐘點比較（平均值）</h2>
    <div id="chartSubjectWrap">
      <canvas id="chartSubject"></canvas>
    </div>
  </div>

  <!-- 明細表 -->
  <div class="card">
    <h2>教師明細表</h2>
    <div class="controls">
      <input id="tableSearch" type="text" class="search-box" placeholder="姓名 / 職務 / 科目 搜尋...">
      <select id="tableRoleFilter">
        <option value="">全部主職</option>
      </select>
      <select id="tableSubjectFilter">
        <option value="">全部科目</option>
      </select>
    </div>
    <div style="overflow-x:auto;">
      <table id="mainTable">
        <thead>
          <tr>
            <th data-col="教師代碼">代碼</th>
            <th data-col="教師">姓名</th>
            <th data-col="主職">主職</th>
            <th data-col="科目">科目</th>
            <th data-col="副職">副職</th>
            <th data-col="基本鐘點" title="最低授課門檻（已含副職減課）">基本鐘點</th>
            <th data-col="合計" title="預排授課總節數">合計</th>
            <th data-col="實際授課節數" title="CSV 中的排課列數">實際節數</th>
            <th data-col="超鐘點" title="合計 − 基本鐘點">超鐘點</th>
            <th data-col="備注">備注</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
    <div class="pagination" id="paginationControls">
      <span id="pageInfo"></span>
    </div>
  </div>

  <!-- 兼課/教練列表 -->
  <div class="card">
    <h2>兼課教師與教練（工作量直接看合計）</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:10px;">此類教師基本鐘點為 0，合計即其每週授課節數，不計算超鐘點。</p>
    <div style="overflow-x:auto;">
      <table id="parttimeTable">
        <thead>
          <tr>
            <th>代碼</th><th>姓名</th><th>職務</th><th>科目</th>
            <th>合計</th><th>實際節數</th><th>備注</th>
          </tr>
        </thead>
        <tbody id="parttimeBody"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
// ── 資料 ─────────────────────────────────────────────────────────────────────
const ALL_TEACHERS  = {teachers_json};
const REGULAR       = {regular_json};
const SUBJ_STATS    = {subj_json};
const MEAN_OT       = {mean_json};
const STD_OT        = {std_json};
const THRESHOLD     = {threshold_json};

// ── 統計摘要 ─────────────────────────────────────────────────────────────────
(function buildStats() {{
  const regular = REGULAR;
  const ots = regular.map(t => t['超鐘點'] || 0);
  const total   = ALL_TEACHERS.length;
  const regCnt  = regular.length;
  const extreme = regular.filter(t => t['超鐘點'] >= THRESHOLD).length;
  const zeroOt  = regular.filter(t => t['超鐘點'] === 0).length;

  const stats = [
    {{ val: total,           lbl: '教師總數' }},
    {{ val: regCnt,          lbl: '正式教師' }},
    {{ val: MEAN_OT.toFixed(1), lbl: '平均超鐘點' }},
    {{ val: Math.max(...ots), lbl: '最高超鐘點' }},
    {{ val: extreme,         lbl: '極端個案 (>2σ)' }},
    {{ val: zeroOt,          lbl: '剛好 0 超鐘點' }},
  ];
  const grid = document.getElementById('statsGrid');
  stats.forEach(s => {{
    grid.insertAdjacentHTML('beforeend',
      `<div class="stat-card"><div class="val">${{s.val}}</div><div class="lbl">${{s.lbl}}</div></div>`);
  }});
}})();

// ── 個人查詢 ─────────────────────────────────────────────────────────────────
document.getElementById('personSearch').addEventListener('input', function() {{
  const q = this.value.trim().toLowerCase();
  const el = document.getElementById('personResult');
  if (!q) {{ el.innerHTML = '請輸入姓名或代碼'; el.style.color = 'var(--muted)'; return; }}
  const matches = ALL_TEACHERS.filter(t =>
    (t['教師'] || '').includes(q) || (t['教師代碼'] || '').toLowerCase().includes(q));
  if (!matches.length) {{ el.innerHTML = '找不到符合的教師'; el.style.color = 'var(--muted)'; return; }}

  el.style.color = 'var(--text)';
  el.innerHTML = matches.map(t => {{
    const ot = t['超鐘點'];
    const otStr = ot !== null && ot !== undefined
      ? `<span class="badge ${{ot >= THRESHOLD ? 'badge-danger' : ot > 0 ? 'badge-warn' : 'badge-ok'}}">超鐘點：${{ot}}</span>`
      : `<span class="badge badge-neutral">兼課/教練</span>`;
    const rankIdx = REGULAR.findIndex(r => r['教師代碼'] === t['教師代碼']);
    const rankStr = rankIdx >= 0 ? `全體排名：第 ${{rankIdx+1}} / ${{REGULAR.length}}` : '';
    return `<div style="margin:8px 0; padding:10px; background:#f8fafc; border-radius:6px; border:1px solid var(--border);">
      <strong>${{t['教師']}}（${{t['教師代碼']}}）</strong>
      ${{otStr}}
      <span style="color:var(--muted);font-size:12px; margin-left:8px;">${{rankStr}}</span>
      <div style="margin-top:6px; font-size:12px; color:var(--muted);">
        職務：${{t['職務註記'] || '—'}} ｜ 科目：${{t['科目'] || '—'}} ｜
        基本鐘點：${{t['基本鐘點']}} ｜ 合計：${{t['合計']}} ｜ 實際節數：${{t['實際授課節數']}}
        ${{t['副職'] ? ' ｜ 副職：' + t['副職'] : ''}}
      </div>
    </div>`;
  }}).join('');
}});

// ── 全員排名圖 ────────────────────────────────────────────────────────────────
let rankingChart = null;

function buildRankingChart(data) {{
  const labels = data.map(t => t['教師']);
  const values = data.map(t => t['超鐘點'] || 0);
  const colors = values.map(v => v >= THRESHOLD ? 'rgba(220,38,38,0.8)' : 'rgba(37,99,235,0.7)');

  const canvas = document.getElementById('chartRanking');
  const wrapH  = Math.max(500, data.length * 22);
  canvas.style.height = wrapH + 'px';
  canvas.height = wrapH;

  if (rankingChart) rankingChart.destroy();
  rankingChart = new Chart(canvas, {{
    type: 'bar',
    data: {{
      labels,
      datasets: [{{
        label: '超鐘點',
        data: values,
        backgroundColor: colors,
        borderRadius: 3,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: false,
      plugins: {{
        legend: {{ display: false }},
        annotation: {{}}  ,
        tooltip: {{
          callbacks: {{
            afterLabel: function(ctx) {{
              const t = data[ctx.dataIndex];
              return [`職務：${{t['職務註記'] || '—'}}`,
                      `基本鐘點：${{t['基本鐘點']}} | 合計：${{t['合計']}}`];
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          beginAtZero: true,
          title: {{ display: true, text: '超鐘點（節）' }}
        }},
        y: {{
          ticks: {{ font: {{ size: 12 }} }}
        }}
      }}
    }}
  }});
}};

// 篩選選單
function populateFilters() {{
  const subjects = [...new Set(REGULAR.map(t => t['科目']).filter(Boolean))].sort();
  const roles    = [...new Set(REGULAR.map(t => t['主職']).filter(Boolean))].sort();
  const selSubj = document.getElementById('filterSubject');
  const selRole = document.getElementById('filterRole');
  const tSelSubj = document.getElementById('tableSubjectFilter');
  const tSelRole = document.getElementById('tableRoleFilter');

  subjects.forEach(s => {{
    [selSubj, tSelSubj].forEach(el => el.insertAdjacentHTML('beforeend', `<option>${{s}}</option>`));
  }});
  roles.forEach(r => {{
    [selRole, tSelRole].forEach(el => el.insertAdjacentHTML('beforeend', `<option>${{r}}</option>`));
  }});
}};

function getFilteredRanking() {{
  const subj = document.getElementById('filterSubject').value;
  const role = document.getElementById('filterRole').value;
  return REGULAR.filter(t =>
    (!subj || t['科目'] === subj) && (!role || t['主職'] === role));
}};

['filterSubject','filterRole'].forEach(id => {{
  document.getElementById(id).addEventListener('change', () => buildRankingChart(getFilteredRanking()));
}});

// ── 科目比較圖 ────────────────────────────────────────────────────────────────
(function buildSubjectChart() {{
  const labels = SUBJ_STATS.map(s => s.subject);
  const avgs   = SUBJ_STATS.map(s => s.avg);
  const counts = SUBJ_STATS.map(s => s.count);

  const canvas = document.getElementById('chartSubject');
  new Chart(canvas, {{
    type: 'bar',
    data: {{
      labels,
      datasets: [{{
        label: '平均超鐘點',
        data: avgs,
        backgroundColor: avgs.map(v => v > MEAN_OT + 1 ? 'rgba(220,38,38,0.75)'
                                      : v < MEAN_OT - 1 ? 'rgba(22,163,74,0.7)'
                                      : 'rgba(37,99,235,0.65)'),
        borderRadius: 3,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            afterLabel: (ctx) => `教師數：${{counts[ctx.dataIndex]}}`
          }}
        }}
      }},
      scales: {{
        y: {{
          beginAtZero: true,
          title: {{ display: true, text: '平均超鐘點' }},
          annotations: {{ mean: {{
            type: 'line', yMin: MEAN_OT, yMax: MEAN_OT,
            borderColor: '#f59e0b', borderWidth: 1.5, borderDash: [4,4]
          }}}}
        }},
        x: {{
          ticks: {{ font: {{ size: 11 }}, maxRotation: 45 }}
        }}
      }}
    }}
  }});
}})();

// ── 明細表 ────────────────────────────────────────────────────────────────────
const PAGE_SIZE = 30;
let tableData = [...ALL_TEACHERS.filter(t => t['超鐘點'] !== null && t['超鐘點'] !== undefined)];
let tableSortCol = '超鐘點';
let tableSortAsc  = false;
let currentPage   = 1;

function badgeOT(v) {{
  if (v === null || v === undefined) return '<span class="badge badge-neutral">—</span>';
  if (v >= THRESHOLD) return `<span class="badge badge-danger">${{v}}</span>`;
  if (v >  0)         return `<span class="badge badge-warn">${{v}}</span>`;
  return `<span class="badge badge-ok">${{v}}</span>`;
}}

function renderTable() {{
  const q    = document.getElementById('tableSearch').value.toLowerCase();
  const role = document.getElementById('tableRoleFilter').value;
  const subj = document.getElementById('tableSubjectFilter').value;

  let filtered = tableData.filter(t =>
    (!q    || (t['教師']||'').includes(q) || (t['職務註記']||'').includes(q) || (t['科目']||'').includes(q))
    && (!role || t['主職'] === role)
    && (!subj || t['科目'] === subj));

  filtered.sort((a, b) => {{
    const av = a[tableSortCol], bv = b[tableSortCol];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
    return tableSortAsc ? cmp : -cmp;
  }});

  const total   = filtered.length;
  const pages   = Math.ceil(total / PAGE_SIZE);
  currentPage   = Math.min(currentPage, pages || 1);
  const start   = (currentPage - 1) * PAGE_SIZE;
  const pageData = filtered.slice(start, start + PAGE_SIZE);

  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = pageData.map(t => {{
    const ot = t['超鐘點'];
    const diffMismatch = t['合計'] != t['實際授課節數'] && t['合計'] !== 0;
    return `<tr class="${{ot >= THRESHOLD ? 'highlight' : ''}}">
      <td>${{t['教師代碼']}}</td>
      <td><strong>${{t['教師']}}</strong></td>
      <td>${{t['主職']}}</td>
      <td>${{t['科目']}}</td>
      <td style="font-size:12px;color:var(--muted)">${{t['副職'] || '—'}}</td>
      <td>${{t['基本鐘點']}}</td>
      <td>${{t['合計']}}</td>
      <td style="color:${{diffMismatch ? 'var(--warn)' : 'inherit'}}" title="${{diffMismatch ? '與合計不符' : ''}}">
        ${{t['實際授課節數']}}${{diffMismatch ? ' ⚠' : ''}}
      </td>
      <td>${{badgeOT(ot)}}</td>
      <td style="font-size:12px;color:var(--muted)">${{t['備注'] || ''}}</td>
    </tr>`;
  }}).join('');

  // 分頁
  const pc = document.getElementById('paginationControls');
  pc.innerHTML = `<span id="pageInfo">共 ${{total}} 筆，第 ${{currentPage}}/${{pages}} 頁</span>`;
  if (pages > 1) {{
    const maxBtn = 7;
    let startP = Math.max(1, currentPage - Math.floor(maxBtn/2));
    let endP   = Math.min(pages, startP + maxBtn - 1);
    if (currentPage > 1)   pc.insertAdjacentHTML('beforeend', `<button onclick="goPage(${{currentPage-1}})">‹ 上頁</button>`);
    for (let p = startP; p <= endP; p++) {{
      pc.insertAdjacentHTML('beforeend', `<button class="${{p===currentPage?'active':''}}" onclick="goPage(${{p}})">${{p}}</button>`);
    }}
    if (currentPage < pages) pc.insertAdjacentHTML('beforeend', `<button onclick="goPage(${{currentPage+1}})">下頁 ›</button>`);
  }}

  // 更新排序指示
  document.querySelectorAll('#mainTable th').forEach(th => {{
    th.classList.remove('sort-asc','sort-desc');
    if (th.dataset.col === tableSortCol)
      th.classList.add(tableSortAsc ? 'sort-asc' : 'sort-desc');
  }});
}}

function goPage(p) {{ currentPage = p; renderTable(); }}

document.querySelectorAll('#mainTable th[data-col]').forEach(th => {{
  th.addEventListener('click', function() {{
    const col = this.dataset.col;
    if (col === tableSortCol) tableSortAsc = !tableSortAsc;
    else {{ tableSortCol = col; tableSortAsc = false; }}
    currentPage = 1;
    renderTable();
  }});
}});

['tableSearch','tableRoleFilter','tableSubjectFilter'].forEach(id => {{
  document.getElementById(id).addEventListener('input', () => {{ currentPage = 1; renderTable(); }});
}});

// 兼課/教練表
(function buildParttime() {{
  const pt = ALL_TEACHERS.filter(t => t['超鐘點'] === null || t['超鐘點'] === undefined);
  pt.sort((a,b) => (b['合計']||0) - (a['合計']||0));
  document.getElementById('parttimeBody').innerHTML = pt.map(t => `<tr>
    <td>${{t['教師代碼']}}</td>
    <td>${{t['教師']}}</td>
    <td style="font-size:12px">${{t['職務註記']}}</td>
    <td>${{t['科目']}}</td>
    <td><strong>${{t['合計']}}</strong></td>
    <td>${{t['實際授課節數']}}</td>
    <td style="font-size:12px;color:var(--muted)">${{t['備注'] || ''}}</td>
  </tr>`).join('');
}})();

// 初始化
populateFilters();
buildRankingChart(REGULAR);
renderTable();
</script>
</body>
</html>"""
    return html


def main():
    print("[1/2] 載入資料...")
    data = load_data()
    print(f"      {len(data['teachers'])} 位教師")

    print("[2/2] 生成 HTML...")
    html = build_html(data)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   OK: {OUT_PATH}")
    print("\n--- 完成 ---")


if __name__ == "__main__":
    main()
