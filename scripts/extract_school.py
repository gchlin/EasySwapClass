"""
從 全校課表.pdf 抽取資料，輸出全校 CSV + 報告。
重用 extract_v2.py 的解析規則（parse_cell、normalize_course/room）。
"""
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict
import pdfplumber

from extract_v2 import (
    parse_cell, extract_teacher_header,
    ROW_PERIOD, DAY_COL, DAY_NAMES, COURSE_RENAMES,
)

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = str(ROOT / "source" / "全校課表.pdf")
OUT_CSV = str(ROOT / "school_wide" / "全校課表_長表.csv")
REPORT_MD = str(ROOT / "school_wide" / "全校_extraction_report.md")
RYU_MD = str(ROOT / "school_wide" / "全校_領域時間.md")


def extract_post(header_text):
    """從表頭抽出職務字串：'蔡玉珍 (N01) 210 導師 頁數： 100' → '210 導師'"""
    if not header_text:
        return ""
    m = re.search(r"\([A-Za-z]\d+\)\s*(.+?)\s*頁\s*數", header_text)
    return m.group(1).strip() if m else ""


def extract_homeroom_class(post_str):
    """從職務字串抽出導師班級：'210 導師' → '210'，'215A 導師' → '215A'。
    非普通班導師（如 '教師(特教導師)'）或非導師回傳空字串。"""
    if not post_str:
        return ""
    m = re.search(r"(\d{3}[A-Z]?)\s*導師", post_str)
    return m.group(1) if m else ""


# ─── 課程分類器（給「主授科目」/「教師類別」欄位用） ────────────────
# IB 課程判定：課程名稱不含中文字 = IB 課程
# （含 BiologyS/H、PhysSL、Chinese、Math、PE、VA、CT、IPSS 等所有純英文/縮寫課名）
# 普通班的多元/深廣選修即使被 IB 老師兼任也不算 IB 課程（名稱含中文）
def is_ib_course(name):
    if not name:
        return False
    return not any("一" <= c <= "鿿" for c in name)


def classify_course_subject(name):
    """課程 → 主授科目（國/英/數/自/社/藝/體/二外/其他）。
    彈性課/行政/IB 工具課回傳 None（不計入主授判定）。"""
    if not name:
        return None
    if "TOKCh" in name:
        return "國"
    if "TOKEng" in name:
        return "英"
    # 社（早期判斷以免被「探究」或「資訊」搶走）
    if any(k in name for k in [
        "歷史", "地理", "公民", "公社", "民主政治", "法律",
        "生涯規劃", "生命教育", "空間資訊", "科技環", "探究與實",
        "BM", "Geo", "Econ", "Psy",
    ]):
        return "社"
    # 二外（早期判斷：避免「韓語高一多元」這類 flex 把純第二外語老師吞掉）
    if any(k in name for k in ["日語", "德語", "法語", "西班", "西語", "韓語"]):
        return "二外"
    # 本土語（早期判斷，避免被「國」抓走；也不應被 flex 抓走）
    if any(k in name for k in ["閩南語", "客語", "原住民"]):
        return "本土語"
    flex = [
        "行政會報", "團體活動", "領域時間", "領域課程",
        "自主", "多元", "充實", "深廣", "探索", "圖書館",
        "學習的探", "表達力", "分科自學", "分組",
        "Fun ", "Let", "EWANT 數位學習", "EWANT數位學習",
        "Adm sup", "Eng sup", "CT", "TOK", "CAS", "INS",
    ]
    if any(k in name for k in flex):
        return None
    if any(k in name for k in [
        "國語文", "國寫", "國際時事", "各類文學", "語文表達", "新版文學",
        "ChineseA", "Chinese", "Mandarin", "ChiBS",
    ]):
        return "國"
    if any(k in name for k in ["英文", "英語", "English"]):
        return "英"
    if any(k in name for k in [
        "數學", "數甲", "數乙", "數 A", "數A", "數(輔",
        "Math", "EWANT 數", "EWANT數",
    ]):
        return "數"
    if any(k in name for k in [
        "物理", "化學", "生物", "地球科學", "地球", "地科",
        "Phys", "Chem", "Biology", "探究", "IPSS",
        "選修化學", "選修物理", "選修生物", "選修地",
    ]):
        return "自"
    if name == "ES" or name.startswith("ES "):
        return "自"
    # 體（體育/PE/健護/運動/體育班專項/SEHSSL/安全教育）
    if any(k in name for k in [
        "體育", "PE", "健護", "運動",
        "專項技術", "專項體能", "SEHSSL", "安全教育",
    ]):
        return "體"
    # 藝（音樂/美術/藝術生活/新媒體藝/生科/資訊科技/家政/VA/PA/AW）
    if any(k in name for k in [
        "音樂", "美術", "藝術", "新媒體", "生科", "資訊", "家政",
        "VA", "PA", "AW",
    ]):
        return "藝"
    # 其他（家政/全民國防/CP/...）
    return "其他"


def classify_course_detail(name):
    """課程 → 細科目（用於 UI 在 同科 群組內 同細科 子排序）。
    只在大類本身有多個細科目時才有意義（自/社/藝/體/二外/特）。
    無法判定回傳 None。"""
    if not name:
        return None
    # IB 特殊（先處理避免 substring 衝突）
    if "TOKCh" in name:
        return "國文"
    if "TOKEng" in name:
        return "英文"
    # 自
    # 探究 / IPSS 都是協同教學（物理+地科 / 化學+生物 / 物化生 三合一），各老師教自己的學科
    # → 回傳 None，讓老師的細科目由其他課程決定（譬如選修物理 / 選修生物）
    if "物理地科探究" in name or "化學生物探究" in name or "IPSS" in name:
        return None
    if any(k in name for k in ["物理", "Phys"]):
        return "物"
    if any(k in name for k in ["化學", "Chem"]):
        return "化"
    if any(k in name for k in ["生物", "Biology"]):
        return "生"
    if any(k in name for k in ["地球科學", "地球", "地科"]):
        return "地科"
    if name == "ES" or name.startswith("ES "):
        return "地科"
    # 社
    if "歷史" in name:
        return "史"
    if any(k in name for k in ["地理", "空間資訊"]):
        return "地理"
    if any(k in name for k in ["公民", "公社", "民主政治"]):
        return "公民"
    if "法律" in name:
        return "法律"
    if any(k in name for k in ["Psy", "心理"]):
        return "心理"
    if any(k in name for k in ["BM", "Econ"]):
        return "商管"
    if "生命教育" in name:
        return "生命教育"
    if "生涯規劃" in name:
        return "生涯規劃"
    # 藝
    if "音樂" in name:
        return "音樂"
    if "美術" in name:
        return "美術"
    if "藝術生活" in name:
        return "藝術生活"
    if "新媒體" in name:
        return "新媒體藝"
    if "VA" in name or "AW" in name:
        return "視覺藝術"
    if "PA" in name or "表演" in name:
        return "表演藝術"
    if "家政" in name:
        return "家政"
    if "資訊" in name:
        return "資訊"
    if "生科" in name:
        return "生科"
    # 體
    if any(k in name for k in ["體育", "PE", "專項技術", "專項體能", "SEHSSL"]):
        return "體育"
    if any(k in name for k in ["健護", "運動"]):
        return "健護"
    if "安全教育" in name:
        return "安全教育"
    if "全民國防" in name:
        return "全民國防"
    # 二外（語言，單字標示）
    if "日語" in name:
        return "日"
    if "德語" in name:
        return "德"
    if "法語" in name:
        return "法"
    if any(k in name for k in ["西班", "西語"]):
        return "西"
    if "韓語" in name:
        return "韓"
    # 本土語
    if "客語" in name:
        return "客"
    if "閩南" in name:
        return "閩"
    if "原住民" in name:
        return "原"
    # 國/英/數
    if any(k in name for k in [
        "國語文", "國寫", "各類文學", "語文表達", "新版文學", "國際時事",
        "ChineseA", "Chinese", "Mandarin", "ChiBS",
    ]):
        return "國文"
    if any(k in name for k in ["英文", "英語", "English"]):
        return "英文"
    if any(k in name for k in ["數學", "數甲", "數乙", "數 A", "數A", "數(輔", "Math"]):
        return "數學"
    return None


def main():
    rows = []
    ryu_entries = []  # 領域時間 entries：另外保留作部門時段表
    page_status = []  # (page_idx, tcode, tname, entry_count, status)
    suspicious = []  # 解析後仍含 ? 的格子
    raw_4plus = []   # 4+ 行的 cell（可能是新 pattern）
    teacher_set = set()
    teacher_post = {}  # tcode -> 職務（從 header 抽取）

    with pdfplumber.open(PDF_PATH) as pdf:
        n_pages = len(pdf.pages)
        for pi, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                page_status.append((pi + 1, None, None, 0, "no table"))
                continue
            t = tables[0]
            header_text = t[0][0] if t and t[0] and t[0][0] else ""
            tcode, tname = extract_teacher_header(header_text)
            if not tcode:
                page_status.append((pi + 1, None, None, 0, f"header fail: {header_text[:40]!r}"))
                continue
            teacher_set.add(tcode)
            teacher_post[tcode] = extract_post(header_text)

            entry_count = 0
            for row_idx, period in ROW_PERIOD.items():
                if row_idx >= len(t):
                    continue
                row = t[row_idx]
                for col_idx, day in DAY_COL.items():
                    if col_idx >= len(row):
                        continue
                    cell = row[col_idx]
                    if not cell or not cell.strip():
                        continue

                    # 紀錄 4+ 行的原始 cell（可能是新 pattern）
                    n_lines = len([l for l in cell.split("\n") if l.strip()])
                    if n_lines >= 4:
                        raw_4plus.append({
                            "page": pi + 1, "tcode": tcode,
                            "day": day, "period": period,
                            "raw": cell,
                        })

                    parsed = parse_cell(cell)
                    if parsed is None:
                        continue
                    course, klass, room = parsed
                    # 嚴格相符才當作 領域時間 排除（並另存）
                    if course == "領域時間":
                        ryu_entries.append({
                            "tcode": tcode, "tname": tname,
                            "day": day, "period": period,
                        })
                        continue

                    if "?" in course or "?" in klass or "?" in room:
                        suspicious.append({
                            "page": pi + 1, "tcode": tcode,
                            "day": day, "period": period,
                            "raw": cell,
                            "course": course, "klass": klass, "room": room,
                        })

                    rows.append({
                        "教師代碼": tcode,
                        "教師": tname,
                        "星期": day,
                        "節次": period,
                        "課程名稱": course,
                        "班級": klass,
                        "教室": room,
                    })
                    entry_count += 1

            page_status.append((pi + 1, tcode, tname, entry_count, "ok"))

    # ── 計算每位老師的「主授科目」與「教師類別」 ──
    subj_count = defaultdict(Counter)
    for r in rows:
        s = classify_course_subject(r["課程名稱"])
        if s:
            subj_count[r["教師代碼"]][s] += 1

    main_subject = {}
    for code in teacher_set:
        cnt = subj_count.get(code)
        main_subject[code] = cnt.most_common(1)[0][0] if cnt else "其他"
    # 代號 prefix 強制覆蓋：以學校的代號分類為準，避免 IB 跨領域老師等例外
    # A 例外：沿用課程式分類（體/藝/社 並存）
    # L 例外：沿用課程式分類（二外 / 本土語 並存）
    PREFIX_TO_SUBJECT = {
        "C": "國", "E": "英", "F": "特", "G": "體",
        "M": "數", "N": "自", "S": "社",
    }
    for code in teacher_set:
        p = code[0]
        if p in PREFIX_TO_SUBJECT:
            main_subject[code] = PREFIX_TO_SUBJECT[p]

    # IB 教師：教過至少一門 IB 課程（純英文課名）
    ib_codes = set()
    for r in rows:
        if is_ib_course(r["課程名稱"]):
            ib_codes.add(r["教師代碼"])

    # 導師班級
    homeroom = {}
    for code in teacher_set:
        homeroom[code] = extract_homeroom_class(teacher_post.get(code, ""))

    # 細科目（每位老師取其課程中最常見的細科目）
    detail_count = defaultdict(Counter)
    for r in rows:
        d = classify_course_detail(r["課程名稱"])
        if d:
            detail_count[r["教師代碼"]][d] += 1
    detail = {}
    for code in teacher_set:
        cnt = detail_count.get(code)
        detail[code] = cnt.most_common(1)[0][0] if cnt else ""
    # F 系細科目強制為「特」（F 老師教生命教育/CP/輔導活動，視為「特」類別）
    for code in teacher_set:
        if code.startswith("F"):
            detail[code] = "特"

    for r in rows:
        r["主授科目"] = main_subject[r["教師代碼"]]
        r["教師類別"] = "IB教師" if r["教師代碼"] in ib_codes else "普通班教師"
        r["導師班級"] = homeroom[r["教師代碼"]]
        r["細科目"] = detail[r["教師代碼"]]

    # 輸出 CSV
    fieldnames = ["教師代碼", "教師", "星期", "節次", "課程名稱", "班級", "教室",
                  "主授科目", "細科目", "教師類別", "導師班級"]
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    n_homeroom = sum(1 for v in homeroom.values() if v)
    print(f"[ok] {OUT_CSV}: {len(rows)} 筆 / {len(teacher_set)} 位老師 / {n_pages} 頁")
    print(f"     IB 教師：{len(ib_codes)} 位 / 班級導師：{n_homeroom} 位")

    # 報告
    md = []
    md.append("# 全校 PDF 抽取報告\n")
    md.append(f"- 來源：`全校課表.pdf`")
    md.append(f"- 頁數：**{n_pages}**")
    md.append(f"- 解析成功老師數：**{len(teacher_set)}**")
    md.append(f"- 課程資料筆數：**{len(rows)}**")
    md.append(f"- 含 `?` 的可疑筆數（待 mapping 修正）：**{len(suspicious)}**")
    md.append(f"- 4 行以上的 cell（可能新 pattern）：**{len(raw_4plus)}**")
    md.append("")

    # 解析失敗的頁
    failed_pages = [p for p in page_status if p[4] != "ok"]
    if failed_pages:
        md.append("## 解析失敗的頁\n")
        md.append("| 頁 | 狀態 |")
        md.append("|----|------|")
        for p in failed_pages:
            md.append(f"| {p[0]} | {p[4]} |")
        md.append("")

    # 含 ? 的課程／班級／教室分類
    bad_courses = Counter(s["course"] for s in suspicious if "?" in s["course"])
    bad_klass = Counter(s["klass"] for s in suspicious if "?" in s["klass"])
    bad_rooms = Counter(s["room"] for s in suspicious if "?" in s["room"])
    if bad_courses:
        md.append("## 含 `?` 的課程名稱（需要加進 COURSE_RENAMES）\n")
        md.append("| 課程名稱 (亂碼版) | 出現次數 |")
        md.append("|--------------------|----------|")
        for name, n in bad_courses.most_common():
            md.append(f"| `{name}` | {n} |")
        md.append("")
    if bad_klass:
        md.append("## 含 `?` 的班級欄\n")
        md.append("| 班級 | 次數 |")
        md.append("|------|------|")
        for k, n in bad_klass.most_common():
            md.append(f"| `{k}` | {n} |")
        md.append("")
    if bad_rooms:
        md.append("## 含 `?` 的教室欄\n")
        md.append("| 教室 | 次數 |")
        md.append("|------|------|")
        for r, n in bad_rooms.most_common():
            md.append(f"| `{r}` | {n} |")
        md.append("")

    # 4+ 行 cell 的範例
    if raw_4plus:
        md.append("## 4 行以上的 cell（前 30 筆）\n")
        md.append("這些可能有新的多行格式，請檢查 `parse_cell` 是否正確處理：\n")
        md.append("| 頁 | 教師 | 星期 | 節 | 原始 cell |")
        md.append("|----|------|------|----|-----------|")
        for c in raw_4plus[:30]:
            raw_inline = c["raw"].replace("\n", " ↵ ")
            md.append(f"| {c['page']} | {c['tcode']} | {DAY_NAMES[c['day']]} | {c['period']} | `{raw_inline}` |")
        if len(raw_4plus) > 30:
            md.append(f"\n（共 {len(raw_4plus)} 筆，僅顯示前 30）")
        md.append("")

    # 課程名稱統計（前 30）
    course_count = Counter(r["課程名稱"] for r in rows)
    md.append(f"## 課程名稱出現次數（前 30 / 共 {len(course_count)} 種）\n")
    md.append("| 課程名稱 | 次數 |")
    md.append("|----------|------|")
    for name, n in course_count.most_common(30):
        md.append(f"| {name} | {n} |")
    md.append("")

    # 教室統計
    room_count = Counter(r["教室"] for r in rows if r["教室"])
    md.append(f"## 教室出現次數（前 30 / 共 {len(room_count)} 種）\n")
    md.append("| 教室 | 次數 |")
    md.append("|------|------|")
    for name, n in room_count.most_common(30):
        md.append(f"| {name} | {n} |")
    md.append("")

    # 老師清單
    teacher_codes = sorted(teacher_set, key=lambda x: int(x[1:]) if x[1:].isdigit() else 999)
    md.append(f"## 老師清單（{len(teacher_codes)} 位）\n")
    by_letter = defaultdict(list)
    for r in rows:
        by_letter[r["教師代碼"]] = r["教師"]
    teacher_lines = [f"{code}={by_letter.get(code, '?')}" for code in teacher_codes]
    md.append("```\n" + "\n".join(teacher_lines) + "\n```\n")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"[ok] {REPORT_MD}")

    # ── 領域時間 額外列表（依部門前綴分組） ──
    rmd = []
    rmd.append("# 全校 領域時間時段表\n")
    rmd.append(f"資料來源：{len(ryu_entries)} 筆領域時間（依教師代碼前綴分組為部門）\n")
    rmd.append("**每位老師代表一個科目，列出他們的領域時間。**"
               "同前綴內若所有老師時段一致，視為部門共識；不一致會逐位列出。\n")

    # 每位老師的領域時間 slot set
    teacher_slots = defaultdict(set)
    for e in ryu_entries:
        teacher_slots[e["tcode"]].add((e["day"], e["period"]))

    # 依前綴分組
    by_prefix = defaultdict(list)
    for tcode in sorted(teacher_set):
        by_prefix[tcode[0]].append(tcode)

    rmd.append("## 各部門代表領域時間\n")
    rmd.append("| 前綴 | 部門人數 | 共同時段 | 代表老師 | 代表老師職務 |")
    rmd.append("|------|----------|----------|----------|--------------|")
    teacher_name = {}
    for r in rows:
        teacher_name[r["教師代碼"]] = r["教師"]
    for ryu in ryu_entries:
        teacher_name[ryu["tcode"]] = ryu["tname"]

    def slot_str(slots):
        return "、".join(f"{DAY_NAMES[d]}{p}" for d, p in sorted(slots))

    for prefix in sorted(by_prefix.keys()):
        members = by_prefix[prefix]
        # 取所有有領域時間的成員之共同 slots（intersection）
        members_with_ryu = [t for t in members if t in teacher_slots]
        if not members_with_ryu:
            common = set()
            rep = members[0]
        else:
            common = set.intersection(*(teacher_slots[t] for t in members_with_ryu))
            rep = members_with_ryu[0]
        rep_name = teacher_name.get(rep, "?")
        rep_post = teacher_post.get(rep, "")
        rmd.append(f"| {prefix} | {len(members)} | {slot_str(common) or '（無）'} | {rep_name} ({rep}) | {rep_post} |")
    rmd.append("")

    # 顯示部門內不一致（有人的領域時間跟同部門他人不同）
    rmd.append("## 部門內時段不一致情形\n")
    has_inconsistency = False
    for prefix in sorted(by_prefix.keys()):
        members = by_prefix[prefix]
        members_with_ryu = [t for t in members if t in teacher_slots]
        if not members_with_ryu:
            continue
        common = set.intersection(*(teacher_slots[t] for t in members_with_ryu))
        # 個別差異
        odd = [t for t in members_with_ryu if teacher_slots[t] != common]
        no_ryu = [t for t in members if t not in teacher_slots]
        if odd or no_ryu:
            has_inconsistency = True
            rmd.append(f"### 前綴 `{prefix}`（部門共同：{slot_str(common) or '無'}）\n")
            if no_ryu:
                rmd.append("**完全沒有領域時間的老師：**")
                for t in no_ryu:
                    rmd.append(f"- {teacher_name.get(t, '?')} ({t}) {teacher_post.get(t, '')}")
                rmd.append("")
            if odd:
                rmd.append("**時段與多數人不同的老師：**")
                rmd.append("| 老師 | 職務 | 時段 |")
                rmd.append("|------|------|------|")
                for t in odd:
                    rmd.append(f"| {teacher_name.get(t, '?')} ({t}) | {teacher_post.get(t, '')} | {slot_str(teacher_slots[t])} |")
                rmd.append("")
    if not has_inconsistency:
        rmd.append("（所有部門內所有老師領域時間一致）\n")

    with open(RYU_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(rmd))
    print(f"[ok] {RYU_MD}: 領域時間 {len(ryu_entries)} 筆")


if __name__ == "__main__":
    main()
