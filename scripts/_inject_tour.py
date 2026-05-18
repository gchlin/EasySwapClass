"""
Inject the onboarding tour UI into school_wide/代課查詢_全校.html.

Run AFTER build_web_school.py has generated the target HTML:
    python scripts/build_web_school.py
    python scripts/_inject_tour.py

What this script does (3 insertion points):
  1. CSS  — appends tour CSS before </style>
  2. H1   — appends ? button to the <h1> tag
  3. JS   — appends tour JS before the closing </script> of the main block
  4. HTML — appends tour overlay <div> before </body>

Safe to re-run: each insertion is guarded by an idempotency check
(looks for a marker string; skips if already present).
"""

import re
from pathlib import Path

ROOT   = Path(__file__).parent.parent
TARGET = ROOT / "school_wide" / "代課查詢_全校.html"

# ── 1. Tour CSS ───────────────────────────────────────────────────────
TOUR_CSS = """
  /* ── 新手引導遮罩 ──────────────────────────── */
  #tour-overlay {
    display: none;
    position: fixed; inset: 0; z-index: 9000;
  }
  #tour-overlay.active { display: block; }
  #tour-spotlight {
    position: fixed;
    box-shadow: 0 0 0 9999px rgba(0,0,0,0.58);
    border-radius: 6px;
    z-index: 9001;
    pointer-events: none;
    transition: top 0.25s, left 0.25s, width 0.25s, height 0.25s;
  }
  #tour-box {
    position: fixed;
    background: #fff;
    border-radius: 10px;
    padding: 1.1em 1.4em 1em;
    z-index: 9002;
    max-width: 300px;
    min-width: 220px;
    box-shadow: 0 4px 28px rgba(0,0,0,0.28);
  }
  #tour-box h3 { margin: 0 0 0.4em; font-size: 1em; color: var(--primary); }
  #tour-box p  { margin: 0 0 0.85em; font-size: 0.88em; line-height: 1.55; }
  .tour-indicator { font-size: 0.78em; color: var(--muted); margin-bottom: 0.35em; }
  .tour-nav { display: flex; gap: 0.5em; align-items: center; justify-content: space-between; }
  .tour-skip { font-size: 0.8em; color: var(--muted); cursor: pointer; text-decoration: underline;
               background: none; border: none; padding: 0; }
  #tour-trigger { font-size: 0.55em; vertical-align: middle; margin-left: 0.6em;
                  padding: 0.15em 0.55em; border-radius: 50%;
                  background: var(--muted); color: #fff;
                  border: none; cursor: pointer; font-weight: bold; line-height: 1.4; }
"""

# ── 2. Tour JS ────────────────────────────────────────────────────────
TOUR_JS = """
// ── 新手引導（5 步驟互動版）─────────────────────────────────────────
// 步驟設計：
//   1. 選老師（idle）
//   2. 課表 → 下一步後延遲 1 秒自動點第一格有課的時段（leaveSelected）
//   3. 候選面板 → 下一步後自動點第一位候選老師（partnerSelected）
//   4. 課表顯示可調時段 → 下一步後自動點第一個可調格子（confirmed）
//   5. 清除按鈕 → 完成後 resetState() + 捲回頂端
//
// 上一步：清除狀態後重新執行到上一步所需的所有 setup actions。
// ─────────────────────────────────────────────────────────────────────
const TOUR_STEPS = [
  {
    targetId: "teacher",
    title: "第 1 步：選擇誰要調代課",
    body: "下拉選單選擇要調代課的老師，通常就是你自己。",
  },
  {
    targetId: "schedule",
    title: "第 2 步：點擊請假時段",
    body: "在課表中選擇要調代課的時段（黃色格子）。\\n譬如我先選這堂：",
    nextDelay: 1000,
    nextAction: "_tourClickFirstCell",
  },
  {
    targetId: "panel",
    title: "第 3 步：選代課人",
    body: "在這裡，顯示可以協助的老師列表。我們可以找到同一個任教班的老師，也可以找到同科別的老師，當然還有其他時段允許的老師。",
    nextDelay: 1000,
    nextAction: "_tourClickFirstCandidate",
    restoreActions: ["_tourClickFirstCell"],
  },
  {
    targetId: "schedule",
    title: "第 4 步：選擇可以調換的課",
    body: "課表中出現可調課的時段（橘色格子）。點擊其中一個完成調課配對。",
    nextDelay: 1000,
    nextAction: "_tourClickFirstSwapOption",
    restoreActions: ["_tourClickFirstCell", "_tourClickFirstCandidate"],
  },
  {
    targetId: "reset-btn",
    title: "第 5 步：確認或取消",
    body: "如果你覺得點錯了，可以按這裡取消，重新開始。",
    isLast: true,
    restoreActions: ["_tourClickFirstCell", "_tourClickFirstCandidate", "_tourClickFirstSwapOption"],
  },
];
let _tourStep = 0;
let _tourTimer = null;

function _tourClickFirstCell() {
  const tcode = meCode();
  const entry = DATA.find(d => d.tcode === tcode);
  if (!entry) return;
  if (state.mode !== "idle") return;
  onCellClick(entry.day, entry.period);
}
function _tourClickFirstCandidate() {
  const btn = document.querySelector("#panel .cand-btn");
  if (!btn || !btn.dataset.pcode) return;
  onCandidateClick(btn.dataset.pcode);
}
function _tourClickFirstSwapOption() {
  const td = document.querySelector("#schedule td.cell-swap-option");
  if (!td) return;
  onCellClick(parseInt(td.dataset.day), parseInt(td.dataset.period));
}
function _tourRunAction(name) {
  if (name === "_tourClickFirstCell")      _tourClickFirstCell();
  if (name === "_tourClickFirstCandidate") _tourClickFirstCandidate();
  if (name === "_tourClickFirstSwapOption") _tourClickFirstSwapOption();
}

function startTour() {
  if (_tourTimer) { clearTimeout(_tourTimer); _tourTimer = null; }
  resetState();
  _tourStep = 0;
  _showTourStep();
}

function _showTourStep() {
  const step = TOUR_STEPS[_tourStep];
  document.getElementById("tour-overlay").classList.add("active");
  document.getElementById("tour-indicator").textContent = `步驟 ${_tourStep + 1} / ${TOUR_STEPS.length}`;
  document.getElementById("tour-title").textContent = step.title;
  document.getElementById("tour-body").textContent = step.body;
  document.getElementById("tour-next").textContent = step.isLast ? "完成" : "下一步";
  const prevBtn = document.getElementById("tour-prev");
  if (prevBtn) prevBtn.style.visibility = _tourStep === 0 ? "hidden" : "visible";

  setTimeout(() => {
    let el = document.getElementById(step.targetId);
    if (el && el.style.display === "none") el = null;
    const target = el || document.getElementById("schedule");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => _positionTour(target), 320);
  }, 60);
}

function _positionTour(el) {
  const sp  = document.getElementById("tour-spotlight");
  const box = document.getElementById("tour-box");
  const pad = 10;
  const r   = el.getBoundingClientRect();
  sp.style.top    = (r.top  - pad) + "px";
  sp.style.left   = (r.left - pad) + "px";
  sp.style.width  = (r.width  + pad * 2) + "px";
  sp.style.height = (r.height + pad * 2) + "px";

  const boxW = 300;
  let bx = Math.max(8, Math.min(r.left, window.innerWidth - boxW - 16));
  const belowY = r.bottom + pad + 14;
  const by = (belowY + 190 < window.innerHeight) ? belowY : r.top - pad - 200;
  box.style.left = bx + "px";
  box.style.top  = Math.max(8, by) + "px";
}

function tourNext() {
  if (_tourTimer) return;
  const step = TOUR_STEPS[_tourStep];
  if (step.isLast) { closeTour(); return; }

  if (step.nextDelay) {
    if (step.nextAction) _tourRunAction(step.nextAction);
    document.getElementById("tour-next").disabled = true;
    _tourTimer = setTimeout(() => {
      _tourTimer = null;
      document.getElementById("tour-next").disabled = false;
      _tourStep++;
      _showTourStep();
    }, step.nextDelay);
  } else {
    if (step.nextAction) _tourRunAction(step.nextAction);
    _tourStep++;
    _showTourStep();
  }
}

function tourPrev() {
  if (_tourTimer) { clearTimeout(_tourTimer); _tourTimer = null;
    document.getElementById("tour-next").disabled = false; }
  if (_tourStep <= 0) return;
  _tourStep--;
  resetState();
  const prevStep = TOUR_STEPS[_tourStep];
  if (prevStep.restoreActions) {
    prevStep.restoreActions.forEach(a => _tourRunAction(a));
  }
  _showTourStep();
}

function closeTour() {
  if (_tourTimer) { clearTimeout(_tourTimer); _tourTimer = null; }
  document.getElementById("tour-overlay").classList.remove("active");
  document.getElementById("tour-next").disabled = false;
  localStorage.setItem("tourDone", "1");
  resetState();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// 首次使用：延遲顯示引導
if (!localStorage.getItem("tourDone")) setTimeout(startTour, 600);
"""

# ── 3. Tour overlay HTML ──────────────────────────────────────────────
TOUR_HTML = """
<div id="tour-overlay">
  <div id="tour-spotlight"></div>
  <div id="tour-box">
    <div class="tour-indicator" id="tour-indicator"></div>
    <h3 id="tour-title"></h3>
    <p id="tour-body"></p>
    <div class="tour-nav">
      <button class="tour-skip" onclick="closeTour()">略過說明</button>
      <div style="display:flex; gap:0.4em; align-items:center">
        <button class="btn" id="tour-prev" onclick="tourPrev()"
          style="visibility:hidden">上一步</button>
        <button class="btn" id="tour-next" onclick="tourNext()">下一步</button>
      </div>
    </div>
  </div>
</div>
"""

IDEMPOTENCY_MARKER = "#tour-overlay"


def inject(html: str) -> tuple[str, bool]:
    if IDEMPOTENCY_MARKER in html:
        return html, False  # already injected

    # 1. CSS — insert before </style>
    html = html.replace("</style>", TOUR_CSS + "</style>", 1)

    # 2. H1 — append ? button inside the <h1> closing tag
    html = re.sub(
        r'(<h1>.*?)(</h1>)',
        r'\1<button id="tour-trigger" onclick="startTour()" title="顯示操作說明">？</button>\2',
        html,
        count=1,
        flags=re.DOTALL,
    )

    # 3. JS — insert before the last </script> that contains init()
    #    build_web_school.py ends its main script block with "init();\n</script>"
    html = html.replace("init();\n</script>", "init();\n" + TOUR_JS + "</script>", 1)

    # 4. HTML overlay — insert before </body>
    html = html.replace("</body>", TOUR_HTML + "</body>", 1)

    return html, True


def main():
    if not TARGET.exists():
        print(f"[ERROR] {TARGET} not found. Run build_web_school.py first.")
        return

    html = TARGET.read_text(encoding="utf-8")
    html, changed = inject(html)

    if not changed:
        print("[SKIP] Tour already present in target HTML.")
        return

    TARGET.write_text(html, encoding="utf-8")
    print(f"[OK] Tour injected into {TARGET.name}")


if __name__ == "__main__":
    main()
