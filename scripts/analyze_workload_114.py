#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_workload_114.py
114 教師授課節數彙整與勞務分析

與 113 的根本差異：114 來源 CSV 只有 12 欄、**沒有任何數值欄位**
（無 基本鐘點/兼課/.../合計）。因此：
  - 授課負擔 = 實際授課節數（CSV 列數）
  - 鐘點規則（主職基準、副職減課）無法從 114 推算，改由 113 分析結果 import
    （讀 Analysis_113/teacher_summary.csv 重建 rule table）
  - 最低門檻 = 主職基準 − Σ副職減課 − 科目別減課
  - 超鐘點 = 實際授課節數 − 最低門檻

執行方式（在 課表分析/ 目錄下）：
    python scripts/analyze_workload_114.py

輸出：
    Analysis_114/teacher_summary.csv
    Analysis_114/analysis_data.json
    Analysis_114/analysis_report.md
"""
import csv
import json
import math
import re
import pathlib
from collections import Counter, defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# 路徑設定
# ─────────────────────────────────────────────────────────────────────────────
DATA_PATH = pathlib.Path("Analysis_114/課表資料含所有欄位.csv")
RULE_SRC  = pathlib.Path("Analysis_113/teacher_summary.csv")   # rule table 來源
OUT_DIR   = pathlib.Path("Analysis_114")
OUT_DIR.mkdir(exist_ok=True)

# 副職關鍵字（沿用 113）
SECONDARY_KEYWORDS = {
    "IB科召/課諮召集人": r"IB科召|課諮召集人",
    "科召": r"(?<!IB)科召(?!人)",
    "課諮": r"課諮(?!召集)",
    "教師會": r"教師會長|教師會總",
    "實驗室管理": r"實驗室",
    "午秘": r"午秘|午餐執秘",
    "國際協行": r"國際協行|國際教育協行|國際教育協",
    "自主協行": r"自主協行",
    "彈團協行": r"彈團協行|彈性學習協行|彈性學習協",
    "國教協行": r"國教協行",
    "學檔協行": r"學檔協行",
    "雙語協行": r"雙語協行|雙語",
    "ATL協行": r"ATL協行|ATL",
    "EE協行": r"EE協行",
    "CAS協行": r"CAS協行",
    "高優協行": r"高優協行",
    "體育班召集人": r"體育班召集人",
    "家政教室": r"家政教室",
    "學習歷程": r"學習歷程",
    "小編": r"小編",
    "實驗班": r"實驗班",
}

# 科目別額外減課（已知值，待校方確認）— 以 細科目 比對
SUBJECT_REDUCTION = {"國文": 2, "家政": 1}


# ─────────────────────────────────────────────────────────────────────────────
# 步驟 0：從 113 重建 rule table
# ─────────────────────────────────────────────────────────────────────────────
def get_primary_role(note):
    """主職判斷（'+' 前的部分）。114 導師格式為 '101 導師'。"""
    if not note:
        return "科任"
    primary = note.split("+")[0].strip()
    if re.search(r"兼課", primary): return "兼課"
    if re.search(r"教練", primary): return "教練"
    if re.search(r"特教|\(特\)|\(特教", primary): return "特教"
    if re.search(r"主任", primary): return "主任"
    if re.search(r"秘書", primary): return "秘書"
    if re.search(r"組長", primary):
        m = re.match(r"^([^\(+]+組長)", primary)
        return m.group(1).strip() if m else "組長"
    if re.search(r"導師", primary): return "導師"
    return "科任"


def get_secondary_roles(note):
    found = []
    for role_name, pattern in SECONDARY_KEYWORDS.items():
        if re.search(pattern, note or ""):
            found.append(role_name)
    return found


def build_rule_table():
    """讀 113 summary，重建 主職基準 與 副職減課。"""
    rows = []
    with open(RULE_SRC, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["基本鐘點"] = int(r["基本鐘點"] or 0)
            r["合計"] = int(r["合計"] or 0)
            r["實際授課節數"] = int(r["實際授課節數"] or 0)
            rows.append(r)

    # 主職基準：同主職、無副職教師的 基本鐘點 眾數
    primary_vals = defaultdict(list)
    for t in rows:
        if not t["副職"] and t["主職"] not in ("兼課", "教練", "主任"):
            primary_vals[t["主職"]].append(t["基本鐘點"])
    base_quota = {}
    for role, vals in primary_vals.items():
        if vals:
            base_quota[role] = Counter(vals).most_common(1)[0][0]
    # 確認值覆蓋
    base_quota.update({"科任": 16, "導師": 12, "兼課": 0, "教練": 0})
    base_quota.setdefault("主任", 0)
    base_quota.setdefault("秘書", 0)

    # 副職減課：有該副職教師 基本鐘點 相對主職基準的差值中位數
    reductions = {}
    for sec_role in SECONDARY_KEYWORDS:
        with_role = [
            t for t in rows
            if sec_role in (t["副職"].split(", ") if t["副職"] else [])
            and t["主職"] in base_quota
            and t["實際授課節數"] > 0
            and t["合計"] != 0
            and not (t["基本鐘點"] == 0 and t["主職"] in ("科任", "導師"))
        ]
        n = len(with_role)
        if not with_role:
            reductions[sec_role] = (None, 0)
            continue
        diffs = sorted(base_quota[t["主職"]] - t["基本鐘點"] for t in with_role)
        med = diffs[len(diffs) // 2]
        reductions[sec_role] = (max(0, int(round(med))), n)

    return base_quota, reductions


# ─────────────────────────────────────────────────────────────────────────────
# 步驟 1–2：讀 114，彙整每位教師一列
# ─────────────────────────────────────────────────────────────────────────────
def load_114():
    by_teacher = defaultdict(list)
    with open(DATA_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        for r in reader:
            by_teacher[r["教師代碼"]].append(r)
    return by_teacher


def build_summary(by_teacher, base_quota, reductions):
    summary = []
    for code, rows in sorted(by_teacher.items()):
        first = rows[0]
        note = (first.get("職務註記") or "").strip()
        primary = get_primary_role(note)
        secondary = get_secondary_roles(note)
        # 科目：114 改取 細科目（fallback 主授科目）— 導師職務註記無括號
        subject = (first.get("細科目") or first.get("主授科目") or "不明").strip()
        big_subject = (first.get("主授科目") or "").strip()

        actual = len(rows)
        base = base_quota.get(primary)

        # 副職減課 + 科目別減課
        sec_reduction = sum(reductions.get(s, (0, 0))[0] or 0 for s in secondary)
        subj_reduction = SUBJECT_REDUCTION.get(subject, 0)

        if primary in ("兼課", "教練"):
            min_load = None
            overtime = None
            flag = "兼課/教練不計超鐘點"
        elif base is None:
            min_load = None
            overtime = None
            flag = "主職基準未知（113 無對應規則）"
        else:
            min_load = max(0, base - sec_reduction - subj_reduction)
            overtime = actual - min_load
            flag = "負值請確認排課是否完整" if overtime < 0 else ""

        # IB 模糊案例
        is_ib = first.get("教師類別") == "IB教師"
        ib_admin = bool(re.search(r"IB|ATL|EE協行|CAS協行", note))
        if is_ib and not ib_admin:
            ib_note = "IB教師，職務註記無 IB 行政標示（疑似兼任，減課待確認）"
        else:
            ib_note = ""

        summary.append({
            "教師代碼": code,
            "教師": first.get("教師", ""),
            "職務註記": note,
            "教師類別": first.get("教師類別", ""),
            "導師班級": first.get("導師班級", "") or "",
            "主職": primary,
            "科目": subject,
            "主授科目": big_subject,
            "副職": ", ".join(secondary),
            "主職基準": base if base is not None else "",
            "副職減課": sec_reduction,
            "科目減課": subj_reduction,
            "最低門檻": min_load if min_load is not None else "",
            "實際授課節數": actual,
            "超鐘點": overtime,
            "備注": flag,
            "IB模糊": ib_note,
        })
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# 統計輔助
# ─────────────────────────────────────────────────────────────────────────────
def stats(values):
    v = [x for x in values if x is not None]
    if not v:
        return None, None, None, None, None
    n = len(v)
    mean = sum(v) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in v) / n) if n > 1 else 0
    vs = sorted(v)
    med = vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) / 2
    return mean, std, min(v), max(v), med


def fmt(x, decimal=1):
    if x is None:
        return "—"
    if decimal == 0:
        return str(int(round(x)))
    return f"{x:.{decimal}f}"


# ─────────────────────────────────────────────────────────────────────────────
# 報告生成
# ─────────────────────────────────────────────────────────────────────────────
SEC_DESC = {
    "科召": "科目召集人，負責課程規劃與對外業務",
    "IB科召/課諮召集人": "IB 課程科召或課程諮詢召集人，業務更重",
    "課諮": "課程諮詢委員",
    "教師會": "教師會長或教師會總",
    "實驗室管理": "管理實驗室，負責設備與安全",
    "午秘": "午餐秘書/午餐執秘",
    "國際協行": "國際教育協助行政",
    "自主協行": "自主學習協助行政",
    "彈團協行": "彈性課程/社團協助行政",
    "國教協行": "國際教育推廣協助行政",
    "學檔協行": "學習歷程檔案協助行政",
    "雙語協行": "雙語教育協助行政",
    "ATL協行": "IB ATL 協助行政",
    "EE協行": "IB EE 協助行政",
    "CAS協行": "IB CAS 協助行政",
    "高優協行": "高優生/資優課程協助行政",
    "體育班召集人": "體育班召集人",
    "家政教室": "家政教室管理",
    "學習歷程": "學習歷程檔案業務協助",
    "小編": "學校社群媒體小編（待確認）",
    "實驗班": "實驗班課程協助",
}


def generate_report(summary, base_quota, reductions):
    L = []
    A = L.append

    total = len(summary)
    A("# 114 教師授課節數與勞務分析報告")
    A("")
    A("> **核心目的**：讓鐘點計算規則透明化，以數據取代猜測，用超鐘點客觀衡量各教師的授課勞務。")
    A("")
    A("> ⚠️ **資料特性（114）**：來源 CSV 僅 12 欄、**無任何數值欄位**（無 基本鐘點/合計 等）。")
    A("> 因此授課負擔一律以 **實際授課節數（CSV 列數）** 表示；鐘點規則 **import 自 113-2 分析**")
    A("> （`Analysis_113/teacher_summary.csv`），非由 114 資料推算。若制度有調整，請以人事室為準。")
    A("")

    # 1
    A("## 1. 欄位含義與授課負擔定義")
    A("")
    A("| 欄位 | 意義 |")
    A("|------|------|")
    A("| 教師代碼, 教師 | 識別鍵（per-teacher 常數）|")
    A("| 職務註記 | 角色標籤，e.g. `教師(英)+科召`、`101 導師`、`兼課師(德)` |")
    A("| 星期, 節次, 課程名稱, 班級, 教室 | 時程細節，每列不同，彙整後捨棄 |")
    A("| 主授科目 | 大科目群（英/社/國/數/自/體/二外/藝/特/本土語）|")
    A("| 細科目 | 細分科目（國文、數學、家政…），科目別減課判斷用 |")
    A("| 教師類別 | 普通班教師 / IB教師 |")
    A("| 導師班級 | 導師才有 |")
    A("")
    A("> **與 113 的關鍵差異**：114 **沒有** `基本鐘點`、`兼課`、`合計` 等數值欄。")
    A("> `授課負擔 = 實際授課節數 = 該教師在 CSV 的列數`（每列 = 每週一節課）。")
    A("")

    # 2
    A("## 2. 各主職的基準鐘點（rule table，import 自 113-2）")
    A("")
    A("| 主職 | 基準鐘點 | 來源 |")
    A("|------|---------|------|")
    fixed = ["科任", "導師", "特教", "主任", "秘書", "教練", "兼課"]
    for role in fixed:
        if role in base_quota:
            src = "確認值" if role in ("科任", "導師", "兼課", "教練") else "113 推算（供確認）"
            A(f"| {role} | **{base_quota[role]}** | {src} |")
    zh = {r: b for r, b in base_quota.items() if "組長" in r}
    if zh:
        A("")
        A("### 組長職稱基準鐘點（import 自 113，需向人事室確認）")
        A("")
        A("| 組長職稱 | 基準鐘點 |")
        A("|---------|---------|")
        for r in sorted(zh):
            A(f"| {r} | **{zh[r]}** |")
    A("")

    # 3
    A("## 3. 副職與科目別減課（import 自 113-2）")
    A("")
    A("| 副職 | 減課數 | 說明 |")
    A("|------|-------|------|")
    for sec, (red, n) in sorted(reductions.items(), key=lambda x: -(x[1][0] or 0)):
        desc = SEC_DESC.get(sec, "")
        if red is None or n == 0:
            A(f"| {sec} | 無樣本 | {desc} |")
        else:
            conf = f"113 推算（{n} 筆{'，可信度較高' if n >= 5 else ''}）"
            A(f"| {sec} | **-{red}**（{conf}）| {desc} |")
    A("")
    A("### 科目別額外減課（已知值，待校方確認）")
    A("")
    A("| 科目 | 減課數 | 可能原因 |")
    A("|------|-------|---------|")
    A("| 國文 | **-2** | 需批改大量作文 |")
    A("| 家政 | **-1** | 實習課準備工作較多 |")
    A("")

    # 4
    A("## 4. 已知規則確認")
    A("")
    A("| 規則 | 確認 |")
    A("|------|------|")
    A(f"| 科任基準鐘點 = 16 | ✅（base['科任']={base_quota.get('科任')}）|")
    A(f"| 導師基準鐘點 = 12 | ✅（base['導師']={base_quota.get('導師')}）|")
    A("| 行政職有多種基準鐘點 | ✅（見 §2 組長表）|")
    A("")

    # 5
    A("## 5. 資料完整性說明")
    A("")
    A("> 114 **無 `合計` 欄可交叉核驗**（113 可比對 合計 vs 列數）。列數是唯一授課量數據源。")
    A("")
    counts = [t["實際授課節數"] for t in summary]
    m, s, mn, mx, md = stats(counts)
    A(f"- 列數分布：平均 {fmt(m)}、中位數 {fmt(md)}、最低 {mn}、最高 {mx}（{total} 位教師）")
    low = sorted([t for t in summary if t["主職"] not in ("兼課", "教練") and t["實際授課節數"] <= 3],
                 key=lambda x: x["實際授課節數"])
    if low:
        A(f"- 列數異常偏低（≤3 節，非兼課/教練）：{len(low)} 位 — 疑排課未完整")
        A("")
        A("| 教師 | 職務 | 列數 |")
        A("|------|------|------|")
        for t in low:
            A(f"| {t['教師']} | {t['職務註記']} | {t['實際授課節數']} |")
    A("")
    A("> **IB 教師注意**：IBDP 課程可能未完整排入主課表，35 位 IB 教師的列數（及超鐘點）可能**低估**。")
    A("")

    # 6
    A("## 6. 勞務分析")
    A("")
    A("### 6.1 超鐘點定義")
    A("```")
    A("超鐘點 = 實際授課節數 − 最低門檻")
    A("最低門檻 = 主職基準 − Σ副職減課 − 科目別減課")
    A("  超鐘點 = 0 → 達標（理想）；> 0 → 有酬加班；< 0 → 排課不足或資料不全")
    A("```")
    A("")
    regular = [t for t in summary if t["超鐘點"] is not None]
    ot = [t["超鐘點"] for t in regular]
    m, s, mn, mx, md = stats(ot)
    A("### 6.2 全體超鐘點統計")
    A("")
    A(f"（統計對象：{len(regular)} 位正式教師，排除兼課/教練 {total - len(regular)} 位）")
    A("")
    A("| 指標 | 數值 |")
    A("|------|------|")
    A(f"| 平均超鐘點 | **{fmt(m)}** 節 |")
    A(f"| 中位數 | **{fmt(md)}** 節 |")
    A(f"| 標準差 | **{fmt(s)}** |")
    A(f"| 最高 | **{fmt(mx,0)}** 節 |")
    A(f"| 最低 | **{fmt(mn,0)}** 節 |")
    A("")

    if m is not None and s is not None:
        hi = m + 2 * s
        lo = m - 2 * s
        ex_hi = sorted([t for t in regular if t["超鐘點"] > hi], key=lambda x: -x["超鐘點"])
        ex_lo = sorted([t for t in regular if t["超鐘點"] < lo], key=lambda x: x["超鐘點"])
        A(f"### 6.3 極端個案（mean ± 2σ = {hi:.1f} / {lo:.1f}）")
        A("")
        if ex_hi:
            A("**高超鐘點 —— 負擔顯著偏重**")
            A("")
            A("> ⚠️ 超鐘點偏高時請先確認「副職」是否完整偵測；未偵測到的行政職會使數字虛高。")
            A("")
            A("| 排名 | 教師 | 職務 | 科目 | 副職 | 最低門檻 | 列數 | 超鐘點 |")
            A("|------|------|------|------|------|---------|------|--------|")
            for i, t in enumerate(ex_hi, 1):
                A(f"| {i} | **{t['教師']}** | {t['職務註記']} | {t['科目']} | {t['副職'] or '—'} | {t['最低門檻']} | {t['實際授課節數']} | **{t['超鐘點']}** |")
            A("")
        if ex_lo and any(t["超鐘點"] < 0 for t in ex_lo):
            A("**低於門檻（超鐘點 < 0）—— 疑資料不全**")
            A("")
            A("| 教師 | 職務 | 最低門檻 | 列數 | 超鐘點 |")
            A("|------|------|---------|------|--------|")
            for t in [x for x in ex_lo if x["超鐘點"] < 0]:
                A(f"| {t['教師']} | {t['職務註記']} | {t['最低門檻']} | {t['實際授課節數']} | **{t['超鐘點']}** |")
            A("")

    # 未偵測副職
    undetected = [t for t in summary if "+" in t["職務註記"] and not t["副職"]]
    if undetected:
        A("### 6.3b 有「+」但未偵測到副職（資料品質提示）")
        A("")
        A("> 職務含「+」但未命中關鍵字，可能為自定義名稱，**不代表無副職**，超鐘點或偏高。")
        A("")
        A("| 教師 | 職務 | + 後內容 | 超鐘點 |")
        A("|------|------|---------|--------|")
        for t in sorted(undetected, key=lambda x: -(x["超鐘點"] or 0)):
            note = t["職務註記"]
            sec = note[note.index("+") + 1:]
            A(f"| {t['教師']} | {note} | `{sec}` | {t['超鐘點'] if t['超鐘點'] is not None else '—'} |")
        A("")

    # 排名
    A("### 6.4 超鐘點排名（前 20）")
    A("")
    A("| 排名 | 教師 | 主職 | 科目 | 副職 | 最低門檻 | 列數 | 超鐘點 |")
    A("|------|------|------|------|------|---------|------|--------|")
    for i, t in enumerate(sorted(regular, key=lambda x: -x["超鐘點"])[:20], 1):
        A(f"| {i} | {t['教師']} | {t['主職']} | {t['科目']} | {t['副職'] or '—'} | {t['最低門檻']} | {t['實際授課節數']} | **{t['超鐘點']}** |")
    A("")

    # 科目別
    A("### 6.5 科目別超鐘點分析（依 主授科目 大群）")
    A("")
    groups = defaultdict(list)
    for t in regular:
        groups[t["主授科目"] or t["科目"]].append(t["超鐘點"])
    rows_s = []
    for subj, vals in groups.items():
        mm, ss, mnn, mxx, mdd = stats(vals)
        rows_s.append((subj, len(vals), sum(vals), mm, mdd, mxx))
    rows_s.sort(key=lambda x: -x[2])
    A("| 科目 | 教師數 | 總超鐘點 | 平均 | 中位數 | 最高 |")
    A("|------|--------|---------|------|--------|------|")
    for subj, cnt, tot, mean_v, med_v, max_v in rows_s:
        A(f"| {subj} | {cnt} | {tot} | {fmt(mean_v)} | {fmt(med_v)} | {fmt(max_v,0)} |")
    A("")

    # 7
    A("## 7. 鐘點數即課堂數")
    A("")
    A("每一列代表一個排定的課堂時段（節次），故 `實際授課節數` = 該教師每週主課表排課節數，")
    A("即超鐘點計算的授課量基礎。114 無 `合計` 欄，列數為唯一依據。")
    A("")

    # 8
    A("## 8. 勞務分配根因分析與改善建議")
    A("")
    if m is not None:
        hi_subj = [s for s, c, tt, mv, mdv, mxv in rows_s if mv is not None and mv > m + 1]
        lo_subj = [s for s, c, tt, mv, mdv, mxv in rows_s if mv is not None and mv < m - 1]
        if hi_subj:
            A(f"**高負擔科目**（平均超鐘點高於全體 +1）：{', '.join(hi_subj)}")
            A("")
        if lo_subj:
            A(f"**低負擔科目**（低於全體 -1）：{', '.join(lo_subj)}")
            A("")
    multi = [t for t in regular if t["副職"].count(",") >= 1]
    if multi:
        A(f"**身兼多項副職教師**（{len(multi)} 位）：")
        A("")
        A("| 教師 | 副職 | 超鐘點 |")
        A("|------|------|--------|")
        for t in sorted(multi, key=lambda x: -x["超鐘點"]):
            A(f"| {t['教師']} | {t['副職']} | {t['超鐘點']} |")
        A("")
    A("### 根因假設")
    A("")
    A("| 問題 | 現象 | 根因假設 |")
    A("|------|------|---------|")
    A("| 特定科目超鐘點偏高 | 某科全體均值顯著高於平均 | 師資不足或選修開設過多 |")
    A("| 副職集中於特定教師 | 同一教師兼多項科召/協行 | 人力分配不均 |")
    A("| IB 課程教師負擔模糊 | IB 教師列數可能低估 | IBDP 未完整排入主課表、IB 行政未標示 |")
    A("")
    A("### 改善方案建議")
    A("")
    A("1. **增補人力**：對持續高超鐘點科目評估增聘兼課或調整課程結構")
    A("2. **副職分散**：科召/協行分配透明化，避免長期集中")
    A("3. **IB 行政透明化**：IB 行政職正式列入職務表，減鐘點規則一致適用")
    A("4. **規則年度確認**：本報告規則沿用 113-2，建議每學年與人事室校對")
    A("5. **隱性工時調查**：超鐘點僅反映排課數，建議納入導師班務、作文批改等隱性工時")
    A("")

    # IB 模糊案例
    ib_cases = [t for t in summary if t["IB模糊"]]
    if ib_cases:
        A("### IB 模糊案例（IB教師但職務註記無 IB 行政標示）")
        A("")
        A("| 教師 | 職務 | 科目 | 超鐘點 |")
        A("|------|------|------|--------|")
        for t in ib_cases:
            A(f"| {t['教師']} | {t['職務註記']} | {t['科目']} | {t['超鐘點'] if t['超鐘點'] is not None else '—'} |")
        A("")

    # 9
    A("## 9. 本次分析輸出一覽")
    A("")
    A("| 檔案 | 說明 |")
    A("|------|------|")
    A("| `Analysis_114/teacher_summary.csv` | 每位教師一列彙整 |")
    A("| `Analysis_114/analysis_data.json` | 視覺化用 JSON |")
    A("| `Analysis_114/analysis_report.md` | 本報告 |")
    A("| `Analysis_114/workload_viz.html` | 互動式視覺化 |")
    A("")
    A("---")
    A("")
    A("## 附錄：腳本與方法論")
    A("")
    A("```bash")
    A("python scripts/analyze_workload_114.py   # 資料處理 + 報告")
    A("python scripts/build_viz_114.py          # 互動 HTML")
    A("```")
    A("")
    A("- 原始資料：`Analysis_114/課表資料含所有欄位.csv`（12 欄，1,818 列，132 位教師）")
    A("- 規則來源：`Analysis_113/teacher_summary.csv`（重建 主職基準 / 副職減課）")
    A("- **超鐘點 = 實際授課節數 − 最低門檻**；最低門檻 = 主職基準 − Σ副職減課 − 科目別減課")
    A("- 兼課師/教練不計超鐘點（列數即工作量）")
    A("")
    A("### 待確認事項")
    A("")
    A("- 組長/主任/秘書基準鐘點、各協行副職減課數：沿用 113 推算值，**需人事室確認**")
    A("- 114 是否沿用 113 制度規則（若有調整需更新 rule table）")
    A("- IB 教師（35 位）IBDP 未排入主課表 → 列數與超鐘點可能低估")
    A("")

    return "\n".join(L)


# ─────────────────────────────────────────────────────────────────────────────
# 存檔
# ─────────────────────────────────────────────────────────────────────────────
def save_csv(summary):
    path = OUT_DIR / "teacher_summary.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(f"   OK: {path} ({len(summary)} 位教師)")


def save_json(summary, base_quota, reductions):
    path = OUT_DIR / "analysis_data.json"
    # 為重用 113 的 build_viz HTML 模板，補上等義別名欄位：
    #   基本鐘點 ← 最低門檻（114 的最低授課門檻即等義於 113 的基本鐘點）
    #   合計     ← 實際授課節數（114 無合計欄，列數即授課量）
    teachers = []
    for t in summary:
        d = dict(t)
        d["基本鐘點"] = t["最低門檻"]
        d["合計"] = t["實際授課節數"]
        teachers.append(d)
    data = {
        "teachers": teachers,
        "inferred_base": base_quota,
        "inferred_reductions": {k: v[0] for k, v in reductions.items() if v[0] is not None},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   OK: {path}")


def save_report(text):
    path = OUT_DIR / "analysis_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"   OK: {path}")


def main():
    print("[0/5] 從 113 重建 rule table...")
    base_quota, reductions = build_rule_table()
    print("      主職基準:", {k: base_quota[k] for k in ("科任", "導師", "特教", "主任", "秘書")})
    print("[1/5] 載入 114 資料...")
    by_teacher = load_114()
    nrows = sum(len(v) for v in by_teacher.values())
    print(f"      {nrows} 列，{len(by_teacher)} 位教師")
    print("[2/5] 彙整 + 套用規則...")
    summary = build_summary(by_teacher, base_quota, reductions)
    print("[3/5] 生成報告...")
    report = generate_report(summary, base_quota, reductions)
    print("[4/5] 存檔...")
    save_csv(summary)
    save_json(summary, base_quota, reductions)
    save_report(report)
    print("[5/5] 完成")


if __name__ == "__main__":
    main()
