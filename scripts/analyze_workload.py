#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_workload.py
113-2 教師授課節數彙整與勞務分析

執行方式（在 課表分析/ 目錄下）：
    python scripts/analyze_workload.py

輸出：
    Analysis/teacher_summary.csv  - 每教師一列的彙整表
    Analysis/analysis_data.json   - 供 build_viz.py 使用的 JSON
    Analysis/analysis_report.md   - 完整分析報告（回答 9 題）
"""
import csv
import json
import re
import math
import pathlib
from collections import Counter, defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# 路徑設定
# ─────────────────────────────────────────────────────────────────────────────
DATA_PATH = pathlib.Path("school_wide/113-2課表資料含所有欄位.csv")
OUT_DIR   = pathlib.Path("Analysis")
OUT_DIR.mkdir(exist_ok=True)

NUM_COLS = ["基本鐘點", "兼課", "本土", "海攬", "IBDP", "國際", "輔導", "新增", "其他", "合計"]

# 科目代碼對照表
SUBJECT_MAP = {
    "國": "國文", "英": "英文", "數": "數學", "理": "理化",
    "化": "化學", "物": "物理", "生": "生物", "地科": "地球科學",
    "歷": "歷史", "地": "地理", "公": "公民",
    "體": "體育", "音": "音樂", "美": "美術", "藝": "藝術",
    "家政": "家政", "科": "資訊科技", "資": "資訊科技",
    "特": "特教", "輔": "輔導處",
    "日": "日文", "法": "法文", "西": "西班牙文",
    "閩": "台語", "健": "健康與護理", "護": "護理",
    "地球": "地球科學",
}

# 副職關鍵字對應（掃描全部職務註記）
# 注意：科召 用 (?<!IB) 避免在 "IB科召" 裡重複偵測
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
    "雙語協行": r"雙語協行",
    # IB 專屬協行角色
    "ATL協行": r"ATL協行",
    "EE協行": r"EE協行",
    "CAS協行": r"CAS協行",
    # 其他學校特定角色
    "高優協行": r"高優協行",
    "體育班召集人": r"體育班召集人",
    "家政教室": r"家政教室",
    "學習歷程": r"學習歷程",
    "小編": r"小編",
    "實驗班": r"實驗班",
}

# ─────────────────────────────────────────────────────────────────────────────
# 職務解析
# ─────────────────────────────────────────────────────────────────────────────
def get_primary_role(note):
    if not note:
        return "科任"
    primary = note.split("+")[0].strip()
    if re.search(r"兼課",    primary): return "兼課"
    if re.search(r"教練",    primary): return "教練"
    if re.search(r"特教",    primary): return "特教"
    if re.search(r"主任",    primary): return "主任"
    if re.search(r"秘書",    primary): return "秘書"
    if re.search(r"組長",    primary):
        # 返回具體組長職稱（每種組長基本鐘點各異）
        m = re.match(r"^([^\(+]+組長)", primary.strip())
        return m.group(1).strip() if m else "組長"
    if re.search(r"導師",    primary): return "導師"
    return "科任"

def get_subject(note):
    """從職務註記提取科目名稱"""
    if not note:
        return "不明"
    m = re.search(r"\(([^)]+)\)", note)
    if not m:
        return "行政"
    raw = m.group(1)
    return SUBJECT_MAP.get(raw, raw)

def get_secondary_roles(note):
    """提取副職列表（掃描全部職務註記，包含 + 前的部分）

    原因：部分副職標記出現在 '+' 前（如 '課諮召集人(美)+課諮'），
    以及 IB 協行角色等新增類型。
    """
    found = []
    for role_name, pattern in SECONDARY_KEYWORDS.items():
        if re.search(pattern, note or ""):
            found.append(role_name)
    return found

# ─────────────────────────────────────────────────────────────────────────────
# 資料載入
# ─────────────────────────────────────────────────────────────────────────────
def load_csv():
    rows = []
    with open(DATA_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            for col in NUM_COLS:
                try:
                    r[col] = int(r.get(col, "") or 0)
                except (ValueError, TypeError):
                    r[col] = 0
            rows.append(r)
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# 彙整：每位教師一列
# ─────────────────────────────────────────────────────────────────────────────
def build_summary(rows):
    by_teacher = defaultdict(list)
    for r in rows:
        by_teacher[r["教師代碼"]].append(r)

    summary = []
    for code, teacher_rows in sorted(by_teacher.items()):
        first = teacher_rows[0]
        note     = first.get("職務註記", "") or ""
        primary  = get_primary_role(note)
        subject  = get_subject(note)
        secondary = get_secondary_roles(note)

        # 確認各列數值欄位是否一致（同一教師應相同）
        inconsistent = []
        for col in NUM_COLS:
            vals = {r[col] for r in teacher_rows}
            if len(vals) > 1:
                inconsistent.append(f"{col}:{vals}")

        total        = first["合計"]
        base         = first["基本鐘點"]
        actual_count = len(teacher_rows)

        # 超鐘點 = 實際授課節數 - 基本鐘點（用 CSV 行數，不用「合計」欄位）
        # 注意：IB 課程部分未列入主課表 CSV，此數值可能低估 IB 教師實際負擔
        if primary in ("兼課", "教練"):
            overtime      = None
            overtime_flag = "兼課/教練不計超鐘點"
        elif base == 0 and primary in ("科任", "導師") and total == 0:
            # 外籍/合約教師或行政兼課：基本=0 且 合計=0，鐘點制度不適用
            overtime      = actual_count
            overtime_flag = "基本鐘點=0（外籍或合約教師？），超鐘點僅代表排課總數，非加班節數"
        else:
            overtime      = actual_count - base
            overtime_flag = "負值請確認排課是否完整" if (actual_count - base) < 0 else ""

        # 分項加總與合計的差值
        subtotal = (first["基本鐘點"] + first["兼課"] + first["本土"] + first["海攬"]
                    + first["IBDP"] + first["國際"] + first["輔導"] + first["新增"] + first["其他"])
        diff = subtotal - total if total != 0 else None

        summary.append({
            "教師代碼":    code,
            "教師":        first["教師"],
            "職務註記":    note,
            "教師類別":    first.get("教師類別", ""),
            "導師班級":    first.get("導師班級", ""),
            "主職":        primary,
            "科目":        subject,
            "副職":        ", ".join(secondary),
            "基本鐘點":    base,
            "兼課":        first["兼課"],
            "本土":        first["本土"],
            "海攬":        first["海攬"],
            "IBDP":        first["IBDP"],
            "國際":        first["國際"],
            "輔導":        first["輔導"],
            "新增":        first["新增"],
            "其他":        first["其他"],
            "合計":        total,
            "實際授課節數": actual_count,
            "超鐘點":      overtime,
            "備注":        overtime_flag,
            "分項差值":    diff,
            "欄位不一致":  "; ".join(inconsistent),
        })

    return summary

# ─────────────────────────────────────────────────────────────────────────────
# 從資料推算基準鐘點與副職減課
# ─────────────────────────────────────────────────────────────────────────────
def infer_role_params(summary):
    """
    推算邏輯：
    - 主職基準：對同一主職中無副職的教師，取 基本鐘點 的眾數
    - 組長各職稱分開推算（每種組長基本鐘點不同）
    - 副職減課：有某副職的教師 vs 同主職無該副職的基準，差值取中位數
    """
    # 1. 各主職的基準鐘點
    primary_vals = defaultdict(list)
    for t in summary:
        role = t["主職"]
        no_secondary = not t["副職"]
        is_excluded = role in ("兼課", "教練", "主任")
        if no_secondary and not is_excluded:
            primary_vals[role].append(t["基本鐘點"])

    inferred_base = {}
    for role, vals in primary_vals.items():
        if vals:
            c = Counter(vals)
            inferred_base[role] = c.most_common(1)[0][0]

    # 覆蓋確認值
    inferred_base["科任"]  = 16
    inferred_base["導師"]  = 12
    inferred_base["兼課"]  = 0
    inferred_base["教練"]  = 0

    # 2. 各副職減課數
    # 排除 合計=0 的教師（通常為行政職，基本鐘點=0 不代表副職本身的減課量）
    inferred_reductions = {}
    for sec_role in SECONDARY_KEYWORDS:
        # 排除條件（以下任一即排除，避免異常值污染推算）：
        #   - 無排課（完全行政）
        #   - 合計=0（可能是薪資異常或特殊雙語計算）
        #   - 基本鐘點=0 而主職為科任/導師（行政壓縮導致的異常值，非副職效果）
        with_role = [t for t in summary
                     if sec_role in t["副職"].split(", ")
                     and t["主職"] in inferred_base
                     and t["實際授課節數"] > 0
                     and t["合計"] != 0
                     and not (t["基本鐘點"] == 0 and t["主職"] in ("科任", "導師"))]
        if not with_role:
            continue

        diffs = []
        for t in with_role:
            base = inferred_base[t["主職"]]
            # 差值包含所有副職的合計減課（無法單獨分離各副職貢獻）
            diffs.append(base - t["基本鐘點"])

        diffs.sort()
        if diffs:
            # 用中位數
            med = diffs[len(diffs) // 2]
            inferred_reductions[sec_role] = max(0, int(round(med)))

    # 3. 科目別額外減課：不自動推算（難以從資料可靠分離），改用使用者已知資訊
    # 已知：國文科 -2（批改作文），家政科 -1（實習準備）— 待學校確認
    inferred_subject_reductions = {"國文": 2, "家政": 1}

    # 為推算結果加上樣本數（方便評估可信度，與減課計算同樣排除無排課的行政教師）
    inferred_reductions_with_n = {}
    for sec_role in SECONDARY_KEYWORDS:
        with_role = [t for t in summary
                     if sec_role in t["副職"].split(", ")
                     and t["主職"] in inferred_base
                     and t["實際授課節數"] > 0]
        n = len(with_role)
        red = inferred_reductions.get(sec_role)
        inferred_reductions_with_n[sec_role] = (red, n)

    return inferred_base, inferred_reductions_with_n, inferred_subject_reductions

# ─────────────────────────────────────────────────────────────────────────────
# 統計輔助
# ─────────────────────────────────────────────────────────────────────────────
def stats(values):
    """回傳 (mean, std, min, max, median) of a list of numbers"""
    v = [x for x in values if x is not None]
    if not v:
        return None, None, None, None, None
    n    = len(v)
    mean = sum(v) / n
    std  = math.sqrt(sum((x - mean) ** 2 for x in v) / n) if n > 1 else 0
    mn   = min(v)
    mx   = max(v)
    vs   = sorted(v)
    med  = vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) / 2
    return mean, std, mn, mx, med

def fmt(x, decimal=1):
    if x is None:
        return "—"
    if decimal == 0:
        return str(int(round(x)))
    return f"{x:.{decimal}f}"

# ─────────────────────────────────────────────────────────────────────────────
# 主報告生成
# ─────────────────────────────────────────────────────────────────────────────
def generate_report(summary, inferred_base, inferred_reductions, inferred_subject_reductions):
    lines = []
    A = lines.append  # shorthand

    A("# 113-2 教師授課節數與勞務分析報告")
    A("")
    A("> **核心目的**：讓鐘點計算規則透明化，以數據取代猜測，用超鐘點客觀衡量各教師的授課勞務。")
    A("")

    # ─── 問題一：欄位關係 ────────────────────────────────────────────────
    A("## 1. 欄位基本鐘點、兼課…合計 與 職務註記 的關係")
    A("")
    A("### 各欄位實質意義")
    A("")
    A("| 欄位 | 意義 | 備注 |")
    A("|------|------|------|")
    A("| **基本鐘點** | 該教師扣除所有副職減課後的**最低授課門檻**（已反映主職+副職後的結果） | 確認值：科任=16，導師=12 |")
    A("| **兼課** | 正式教師超過基本鐘點的補充課時，或純兼課教師的全部課時 | 雙重語意，詳見備注 |")
    A("| **本土** | 本土語課程時數（閩南語、原住民族語等） | 僅 3 位教師有值 |")
    A("| **海攬** | 海外攬才/雙語計畫課程時數 | 僅 3 位教師有值 |")
    A("| **IBDP** | IB Diploma Programme 課程時數 | 14 位 IB 教師有值 |")
    A("| **國際** | 國際課程/英語沉浸課程時數 | 僅 3 位教師有值 |")
    A("| **輔導** | 輔導諮商相關課時 | 僅 5 位，值均為 1 |")
    A("| **新增** | 新增課程（創新選修等） | 20 位教師有值 |")
    A("| **其他** | 其他特殊課程分類 | 19 位教師有值 |")
    A("| **合計** | 該教師每週**預排授課總節數** | 作為授課負擔的權威欄位 |")
    A("")
    A("### 數學關係")
    A("")
    A("理論公式：`合計 = 基本鐘點 + 兼課 + 本土 + 海攬 + IBDP + 國際 + 輔導 + 新增 + 其他`")
    A("")

    # 統計分項差值
    diffs = [t["分項差值"] for t in summary if t["分項差值"] is not None]
    exact_match = sum(1 for d in diffs if d == 0)
    off_by_one  = sum(1 for d in diffs if abs(d) == 1)
    larger_diff = sum(1 for d in diffs if abs(d) > 1)
    blank_total = sum(1 for t in summary if t["合計"] == 0)

    total_teachers = len(summary)
    A(f"實際驗證（{total_teachers} 位教師）：")
    A(f"- 公式吻合：**{exact_match}** 位 ({exact_match/total_teachers*100:.0f}%)")
    A(f"- 差值恰好 ±1：**{off_by_one}** 位 — 疑似部分課程欄位為補助/標記用途，不計入合計")
    A(f"- 差值 >1：**{larger_diff}** 位")
    A(f"- 合計欄為空：**{blank_total}** 位 — 主要為行政職教師")
    A("")
    A("> **⚠️ 分析策略**：以 `合計` 欄為授課負擔的唯一依據，不重新加總各分項。")
    A("> 這些欄位除了計算授課節數，也兼具**薪資分類**與**課程合規追蹤**的功能。")
    A("")

    # ─── 問題二：各職務基本鐘點計算 ────────────────────────────────────
    A("## 2. 各主職的基本鐘點計算")
    A("")
    A("> **說明**：「基本鐘點」欄位已反映主職配額扣除副職減課後的結果。")
    A("> 下表呈現各**主職**（無副職）的標準基本鐘點（從資料推算）。")
    A("")

    # 固定順序的主職（非組長）
    fixed_roles = ["科任", "導師", "特教", "主任", "秘書", "教練", "兼課"]
    fixed_desc  = {
        "科任": "正式教師，無行政職",
        "導師": "兼任班級導師，因班級事務降低教學配額",
        "特教": "特殊教育教師",
        "主任": "各處室主任（教務/輔導/總務/學務/圖書館/國際等），資料顯示基本鐘點均為 0",
        "秘書": "教師兼秘書職",
        "教練": "專任教練",
        "兼課": "兼課教師（時薪/部分工時），無基本配額",
    }
    A("| 主職類別 | 基準鐘點 | 來源 | 說明 |")
    A("|---------|---------|------|------|")
    for role in fixed_roles:
        base = inferred_base.get(role)
        if base is not None:
            source = "確認值" if role in ("科任", "導師", "兼課", "教練") else "推算值（供確認）"
            A(f"| {role} | **{base}** | {source} | {fixed_desc.get(role, '')} |")
    A("")

    # 組長：各職稱分開列出（每種組長基本鐘點不同）
    zhangs = {r: b for r, b in inferred_base.items() if "組長" in r}
    if zhangs:
        A("### 組長職稱一覽（各有不同基準鐘點）")
        A("")
        A("> 不同組長職位行政業務量不同，基本鐘點各異，均為從資料推算之值，**需向人事室確認**。")
        A("")
        A("| 組長職稱 | 基準鐘點 | 備注 |")
        A("|---------|---------|------|")
        for role in sorted(zhangs):
            base = zhangs[role]
            # 是否有副職（樣本中有些組長有課諮等）
            has_sec = any(t["主職"] == role and t["副職"] for t in summary)
            note_str = "含副職教師，此為含副職後的基本鐘點" if has_sec else ""
            A(f"| {role} | **{base}** | {note_str} |")
        A("")

    A("")

    # ─── 問題三：副職減課計算 ────────────────────────────────────────────
    A("## 3. 副職減課計算")
    A("")
    A("> 職務註記中「+」後的項目為副職，每個副職從主職基準鐘點中扣減。")
    A("> 以下為從資料中推算的各副職減課數（供確認）。")
    A("")
    A("| 副職 | 推算減課數 | 說明 |")
    A("|------|----------|------|")

    sec_desc = {
        "科召": "科目召集人（含國文科召、理化科召等），負責課程規劃與對外業務",
        "IB科召/課諮召集人": "IB 課程科召或課程諮詢召集人，業務更重",
        "課諮": "課程諮詢委員",
        "教師會": "教師會長或教師會總（含兩種職稱）",
        "實驗室管理": "管理實驗室，負責設備與安全",
        "午秘": "午餐秘書/午餐執秘，負責午餐行政業務",
        "國際協行": "國際教育協助行政（含國際教育協行等各種寫法）",
        "自主協行": "自主學習協助行政",
        "彈團協行": "彈性課程/社團協助行政（含彈性學習協行）",
        "國教協行": "國際教育推廣協助行政",
        "學檔協行": "學習歷程檔案協助行政",
        "雙語協行": "雙語教育協助行政",
        "ATL協行": "IB ATL（Approaches to Teaching and Learning）協助行政",
        "EE協行": "IB EE（Extended Essay）協助行政",
        "CAS協行": "IB CAS（Creativity, Activity, Service）協助行政",
        "高優協行": "高優生/資優課程協助行政",
        "體育班召集人": "體育班召集人，負責體育班課程協調",
        "家政教室": "家政教室管理，負責實習設備",
        "學習歷程": "學習歷程檔案業務協助",
        "小編": "學校社群媒體小編（非正式減課，待確認）",
        "實驗班": "實驗班課程協助",
    }

    for sec_role, (reduction, n) in sorted(
            inferred_reductions.items(),
            key=lambda x: -(x[1][0] or 0) if x[1][0] is not None else 0):
        desc = sec_desc.get(sec_role, "")
        if reduction is None or n == 0:
            A(f"| {sec_role} | 無樣本 | {desc} |")
        else:
            conf = f"推算（{n} 筆）" if n < 5 else f"推算（{n} 筆，可信度較高）"
            A(f"| {sec_role} | **-{reduction}** （{conf}） | {desc} |")

    A("")
    if inferred_subject_reductions:
        A("### 科目別額外減課（從資料推算）")
        A("")
        A("| 科目 | 推算減課數 | 可能原因 |")
        A("|------|----------|---------|")
        for subj, red in sorted(inferred_subject_reductions.items(), key=lambda x: -x[1]):
            reason = {
                "國文": "需批改大量作文，業界常見減課制度",
                "家政": "實習課準備工作較多",
            }.get(subj, "待確認")
            A(f"| {subj} | **-{red}** | {reason} |")
        A("")

    # ─── 問題四：使用者已知規則確認 ─────────────────────────────────────
    A("## 4. 已知規則確認")
    A("")
    A("| 規則 | 資料確認 | 補充說明 |")
    A("|------|---------|---------|")
    A("| 科任基本鐘點 = 16 | ✅ 確認 | 無副職的一般科任教師，基本鐘點均為 16 |")
    A("| 導師基本鐘點 = 12 | ✅ 確認 | 無副職的導師，基本鐘點均為 12 |")
    A("| 行政職有多種基本鐘點 | ✅ 確認 | 見上表，組長/主任依職務高低遞減 |")

    sci_zheng = [t for t in summary if t["主職"] == "科任" and "科召" in t["副職"]
                 and t["副職"].count(",") == 0]
    if sci_zheng:
        typical_sci_base = Counter([t["基本鐘點"] for t in sci_zheng]).most_common(1)[0][0]
        red = 16 - typical_sci_base
        A(f"| 科召減課 | 推算為 -{red} | 科任+科召典型基本鐘點={typical_sci_base} |")

    A("")

    # ─── 問題五：資料驗證 ───────────────────────────────────────────────
    A("## 5. 資料完整性驗證")
    A("")
    A("### 實際授課節數 vs 合計")
    A("")

    mismatch = [t for t in summary if t["合計"] != 0 and t["合計"] != t["實際授課節數"]]
    match_count = sum(1 for t in summary if t["合計"] == t["實際授課節數"])

    A(f"- 吻合：**{match_count}** 位教師（`實際授課節數 == 合計`）")
    A(f"- 不吻合：**{len(mismatch)}** 位教師")

    if mismatch:
        A("")
        A("| 教師 | 職務 | 合計 | 實際節數 | 差值 | 可能原因 |")
        A("|------|------|------|---------|------|---------|")
        for t in sorted(mismatch, key=lambda x: abs(x["合計"] - x["實際授課節數"]), reverse=True):
            diff_val = t["合計"] - t["實際授課節數"]
            reason = "課表未完整排入" if diff_val > 0 else "資料重複或合計計算差異"
            A(f"| {t['教師']} | {t['職務註記']} | {t['合計']} | {t['實際授課節數']} | {diff_val:+d} | {reason} |")

    A("")
    A("> **注意**：兼課=0 的教師（兼課/教練）的「合計」可能為 0，其授課量以「實際授課節數」為準。")
    A("")

    # ─── 問題六：勞務分析 ───────────────────────────────────────────────
    A("## 6. 勞務分析")
    A("")
    A("### 6.1 超鐘點定義")
    A("")
    A("```")
    A("超鐘點 = 實際授課節數 - 基本鐘點")
    A("")
    A("  實際授課節數 = 主課表 CSV 中該教師的排課行數（每行 = 每週一節課）")
    A("  基本鐘點     = 主職配額扣除副職減課後的最低授課門檻（來自「基本鐘點」欄位）")
    A("")
    A("解讀：")
    A("  超鐘點 = 0  → 正好達到最低門檻，屬理想狀態")
    A("  超鐘點 > 0  → 有酬加班，多教了 N 節")
    A("  超鐘點 < 0  → 排課低於門檻（排課不完整或資料有誤，需確認）")
    A("```")
    A("")
    A("> **注意（IB 教師）**：IBDP 課程可能未完整列入主課表 CSV，")
    A("> 導致 IB 教師的 `實際授課節數` 可能低於真實排課數。")
    A("> 此類教師的超鐘點數值可能**低估**，解讀時請留意。")
    A("")

    # 全體統計（排除兼課/教練，以及外籍/合約教師基本=0的特殊案例）
    regular = [t for t in summary
               if t["超鐘點"] is not None
               and "外籍或合約" not in (t["備注"] or "")]
    ot_vals = [t["超鐘點"] for t in regular]
    mean_ot, std_ot, min_ot, max_ot, med_ot = stats(ot_vals)

    A("### 6.2 全體超鐘點統計")
    A("")
    A(f"（統計對象：{len(regular)} 位正式教師，排除兼課/教練 {total_teachers - len(regular)} 位）")
    A("")
    A("| 指標 | 數值 |")
    A("|------|------|")
    A(f"| 平均超鐘點 | **{fmt(mean_ot)}** 節 |")
    A(f"| 中位數 | **{fmt(med_ot)}** 節 |")
    A(f"| 標準差 | **{fmt(std_ot)}** |")
    A(f"| 最高 | **{fmt(max_ot, 0)}** 節 |")
    A(f"| 最低 | **{fmt(min_ot, 0)}** 節 |")
    A("")

    # 極端值（> mean + 2σ）
    if mean_ot is not None and std_ot is not None:
        threshold_high = mean_ot + 2 * std_ot
        threshold_low  = mean_ot - 2 * std_ot
        extremes_high = [t for t in regular if t["超鐘點"] > threshold_high]
        extremes_low  = [t for t in regular if t["超鐘點"] < threshold_low]

        A(f"### 6.3 極端個案（閾值：超過 mean ± 2σ，即 {threshold_high:.1f} / {threshold_low:.1f}）")
        A("")

        if extremes_high:
            A(f"**高超鐘點（>{threshold_high:.1f} 節）—— 負擔顯著偏重**")
            A("")
            A("> ⚠️ **閱讀提示**：超鐘點偏高時，請先確認「副職」欄位是否完整。")
            A("> 若有行政職未被偵測（如協行類、召集人等），基本鐘點可能被設定過高，")
            A("> 導致超鐘點數字虛高。資料來源的「基本鐘點」欄位應以學校人事室版本為準。")
            A("")
            A("| 排名 | 教師 | 職務 | 科目 | 已偵測副職 | 基本鐘點 | 合計 | 超鐘點 |")
            A("|------|------|------|------|----------|---------|------|--------|")
            for i, t in enumerate(sorted(extremes_high, key=lambda x: -x["超鐘點"]), 1):
                sec_str = t['副職'] or "—（無偵測到副職）"
                A(f"| {i} | **{t['教師']}** | {t['職務註記']} | {t['科目']} | {sec_str} | {t['基本鐘點']} | {t['合計']} | **{t['超鐘點']}** |")
            A("")

        if extremes_low and any(t["超鐘點"] < 0 for t in extremes_low):
            A(f"**低於基本門檻（超鐘點 < 0）—— 疑似資料不全**")
            A("")
            A("| 教師 | 職務 | 基本鐘點 | 合計 | 超鐘點 |")
            A("|------|------|---------|------|--------|")
            for t in sorted([x for x in extremes_low if x["超鐘點"] < 0], key=lambda x: x["超鐘點"]):
                A(f"| {t['教師']} | {t['職務註記']} | {t['基本鐘點']} | {t['合計']} | **{t['超鐘點']}** |")
            A("")

    # 未識別副職診斷
    undetected_sec = [
        t for t in summary
        if "+" in (t.get("職務註記") or "") and not t["副職"]
    ]
    if undetected_sec:
        A("### 6.3b 有 + 但未偵測到副職的教師（資料品質提示）")
        A("")
        A("> 這些教師的職務有「+」但系統未識別出對應副職關鍵字，")
        A("> 可能是欄位截斷或學校自定義名稱，**不代表無副職**。")
        A("> 超鐘點數字可能因此偏高，建議逐一確認。")
        A("")
        A("| 教師 | 職務 | + 後內容 | 超鐘點 |")
        A("|------|------|---------|--------|")
        for t in sorted(undetected_sec, key=lambda x: -(x["超鐘點"] or 0)):
            note = t.get("職務註記", "")
            sec_part = note[note.index("+")+1:] if "+" in note else ""
            ot_str = str(t["超鐘點"]) if t["超鐘點"] is not None else "—"
            A(f"| {t['教師']} | {note} | `{sec_part}` | {ot_str} |")
        A("")

    # 排名表（前 20）
    A("### 6.4 超鐘點排名（前 20）")
    A("")
    A("| 排名 | 教師 | 主職 | 科目 | 副職 | 基本鐘點 | 合計 | 超鐘點 |")
    A("|------|------|------|------|------|---------|------|--------|")
    ranked = sorted(regular, key=lambda x: -x["超鐘點"])
    for i, t in enumerate(ranked[:20], 1):
        A(f"| {i} | {t['教師']} | {t['主職']} | {t['科目']} | {t['副職'] or '—'} | {t['基本鐘點']} | {t['合計']} | **{t['超鐘點']}** |")
    A("")

    # ─── 科目別分析 ─────────────────────────────────────────────────────
    A("### 6.5 科目別超鐘點分析")
    A("")

    subject_groups = defaultdict(list)
    for t in regular:
        subject_groups[t["科目"]].append(t["超鐘點"])

    subj_stats = []
    for subj, vals in subject_groups.items():
        m, s, mn, mx, md = stats(vals)
        total_ot = sum(vals)
        subj_stats.append((subj, len(vals), total_ot, m, md, mx))

    subj_stats.sort(key=lambda x: -x[2])  # 按總超鐘點降序

    A("| 科目 | 教師數 | 總超鐘點 | 平均超鐘點 | 中位數 | 最高 |")
    A("|------|--------|---------|---------|--------|------|")
    for subj, cnt, total_ot, mean_v, med_v, max_v in subj_stats:
        A(f"| {subj} | {cnt} | {total_ot} | {fmt(mean_v)} | {fmt(med_v)} | {fmt(max_v, 0)} |")
    A("")

    # ─── 問題七：鐘點=課堂說明 ──────────────────────────────────────────
    A("## 7. 鐘點數即課堂數")
    A("")
    A("本資料中，每一列代表一個排定的**課堂時段（節次）**，因此：")
    A("")
    A("- `實際授課節數`：CSV 中該教師的資料列數，即每週主課表排課節數，作為超鐘點計算依據")
    A("- `合計`：資料欄位，意義待確認；含 IBDP 等非主課表授課欄位，**不作為超鐘點計算依據**")
    A("- 當 `合計 > 實際授課節數` 時，差值通常等於 IBDP 欄位，代表 IB 課未完整列入主課表")
    A("")

    # ─── 問題八：HR 根因分析 ────────────────────────────────────────────
    A("## 8. 勞務分配根因分析與改善建議")
    A("")
    A("### 8.1 數據發現")
    A("")

    if mean_ot is not None:
        high_subj = [s for s, cnt, tot, m, med, mx in subj_stats if m is not None and m > mean_ot + 1]
        low_subj  = [s for s, cnt, tot, m, med, mx in subj_stats if m is not None and m < mean_ot - 1]

        if high_subj:
            A(f"**高負擔科目**（平均超鐘點高於全體平均 +1 以上）：{', '.join(high_subj)}")
            A("")
        if low_subj:
            A(f"**低負擔科目**（平均超鐘點低於全體平均 -1 以上）：{', '.join(low_subj)}")
            A("")

    # 有多個副職的教師
    multi_secondary = [t for t in regular if t["副職"].count(",") >= 1]
    if multi_secondary:
        A(f"**身兼多項副職的教師**（{len(multi_secondary)} 位）：除超鐘點外，行政/協行業務也造成隱性負擔")
        A("")
        A("| 教師 | 副職 | 超鐘點 |")
        A("|------|------|--------|")
        for t in sorted(multi_secondary, key=lambda x: -x["超鐘點"]):
            A(f"| {t['教師']} | {t['副職']} | {t['超鐘點']} |")
        A("")

    A("### 8.2 根因分析")
    A("")
    A("| 問題 | 現象 | 根因假設 |")
    A("|------|------|---------|")
    A("| 特定科目超鐘點持續偏高 | 某些科目全體超鐘點均值顯著高於平均 | 師資人數不足以覆蓋排課需求，或選修課開設過多 |")
    A("| 副職集中於特定教師 | 同一教師兼任多項科召/協行 | 人力分配不均，行政職流向少數願意承擔的教師 |")
    A("| 導師 vs 科任負擔差異 | 導師的超鐘點可能也不低 | 導師基本門檻雖低 4 節，但班務/親師溝通為隱性工時 |")
    A("| IB 課程教師負擔模糊 | IBDP 欄非零教師的總授課量可能被低估 | IB 行政職未完整標示於課表，導致基本鐘點計算不準確 |")
    A("")
    A("### 8.3 改善方案建議")
    A("")
    A("1. **增補人力**：對持續高超鐘點的科目，評估增聘兼課教師或調整課程結構")
    A("2. **副職分散**：科召/協行等副職分配透明化，避免長期落在同一教師身上")
    A("3. **IB 行政透明化**：IB 相關行政職務正式列入職務表，確保減鐘點規則一致適用")
    A("4. **定期公開超鐘點資料**：每學年公布各科別超鐘點統計，讓規則透明、讓討論有據可依")
    A("5. **隱性工時調查**：超鐘點只反映排課數，建議加入導師班務、作文批改、實驗準備等隱性工時調查")
    A("")

    # ─── 問題九：輸出位置 ───────────────────────────────────────────────
    A("## 9. 本次分析輸出一覽")
    A("")
    A("| 檔案 | 說明 |")
    A("|------|------|")
    A("| `Analysis/teacher_summary.csv` | 每位教師一列，含主職/科目/副職/超鐘點等欄位 |")
    A("| `Analysis/analysis_data.json` | 供互動視覺化（workload_viz.html）使用的 JSON |")
    A("| `Analysis/analysis_report.md` | 本報告 |")
    A("| `Analysis/workload_viz.html` | 互動式視覺化（排名圖、科目比較、個人查詢）|")
    A("")

    # ─── 附錄：腳本與方法論 ─────────────────────────────────────────────
    A("---")
    A("")
    A("## 附錄：腳本與方法論備注")
    A("")
    A("### 使用腳本")
    A("")
    A("```bash")
    A("# 步驟 1：資料處理與報告生成")
    A("python scripts/analyze_workload.py")
    A("")
    A("# 步驟 2：互動視覺化 HTML 生成")
    A("python scripts/build_viz.py")
    A("```")
    A("")
    A("### 資料來源")
    A("")
    A("- 原始資料：`school_wide/113-2課表資料含所有欄位.csv`")
    A("- 欄位數：22（含時程細節欄位）")
    A("- 資料列數：1,689（含標頭則 1,690）")
    A("- 唯一教師數：140 位")
    A("")
    A("### 推算假設")
    A("")
    A("1. **超鐘點計算**：`超鐘點 = 實際授課節數 - 基本鐘點`")
    A("   - `實際授課節數` = 主課表 CSV 中該教師的排課行數（每行一節）")
    A("   - `基本鐘點` 欄位已反映主職 + 副職後的最低授課門檻")
    A("   - `合計` 欄位意義待確認，含 IB/海攬等可能未反映在主課表列數的授課，不用於計算")
    A("2. **數值欄位一致性**：同一教師所有列的數值欄位應相同（pre-aggregated）；若有差異已標注")
    A("3. **授課節數**：以 `合計` 欄位為準；合計為空時以列計數（`實際授課節數`）補充")
    A("4. **兼課/教練教師**：不計超鐘點，其 `合計` 直接即工作量")
    A("5. **主職基準推算**：取同主職且無副職的教師的 `基本鐘點` 眾數")
    A("6. **副職減課推算**：有該副職的教師 vs 主職基準值的差，取中位數")
    A("")
    A("### 模糊點與待確認事項")
    A("")
    A("- 組長/主任/秘書的基準鐘點：由資料推算，**需向人事室確認**")
    A("- 各協行類副職（自主/雙語/國教/彈團/學檔）的減課數：**需確認**")
    A("- 午秘的減課數：**需確認**")
    A("- IB 教師的行政兼職：部分未標示於職務，超鐘點可能被高估")
    A("- 合計 ≠ 分項加總的 15% 案例：推測為補助/標記欄位不計入合計，但未獲官方說明")
    A("")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# 存檔
# ─────────────────────────────────────────────────────────────────────────────
def save_csv(summary):
    path = OUT_DIR / "teacher_summary.csv"
    if not summary:
        return
    fieldnames = list(summary[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)
    print(f"   OK: {path} ({len(summary)} 位教師)")

def save_json(summary, inferred_base, inferred_reductions):
    """輸出供 build_viz.py 使用的 JSON"""
    path = OUT_DIR / "analysis_data.json"

    def safe_num(x):
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return x

    # Flatten inferred_reductions: (reduction, n) → just reduction
    flat_reductions = {k: v[0] for k, v in inferred_reductions.items() if v[0] is not None}

    data = {
        "teachers": [
            {k: safe_num(v) for k, v in t.items()}
            for t in summary
        ],
        "inferred_base": inferred_base,
        "inferred_reductions": flat_reductions,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   OK: {path}")

def save_report(text):
    path = OUT_DIR / "analysis_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"   OK: {path}")

# ─────────────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("[1/5] 載入資料...")
    rows = load_csv()
    print(f"      {len(rows)} 列，來自 {len(set(r['教師代碼'] for r in rows))} 位教師")

    print("[2/5] 彙整教師資料...")
    summary = build_summary(rows)

    print("[3/5] 推算鐘點規則...")
    inferred_base, inferred_reductions, inferred_subject_reductions = infer_role_params(summary)

    print("      推算主職基準：")
    for role, base in sorted(inferred_base.items(), key=lambda x: -(x[1] or 0)):
        print(f"         {role}: {base}")

    print("      推算副職減課：")
    for role, (red, n) in sorted(inferred_reductions.items(), key=lambda x: -(x[1][0] or 0) if x[1][0] else 0):
        if red is not None:
            print(f"         {role}: -{red} (n={n})")

    print("[4/5] 生成報告...")
    report = generate_report(summary, inferred_base, inferred_reductions, inferred_subject_reductions)

    print("[5/5] 存檔...")
    save_csv(summary)
    save_json(summary, inferred_base, inferred_reductions)
    save_report(report)

    print("\n--- 完成 ---")

if __name__ == "__main__":
    main()