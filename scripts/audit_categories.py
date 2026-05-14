"""
產出全校課表的「分類確認表」md 檔，方便人工審查：
  · 35 位 IB 教師清單
  · 48 位班級導師清單
  · 9 個主授科目分布 + 每位老師主授
  · IB 課程清單（match IB_PATTERNS 的不重複課程名）
  · 含「領域」字樣的課程（區分 領域時間 vs 其他）
  · 自主學習相關課程
  · 各主授科目 → 實際課程清單（看分類器把哪些課歸到哪一類）
"""
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "school_wide" / "全校課表_長表.csv"
OUT_MD = ROOT / "school_wide" / "分類確認表.md"

# 與 build_web_school.py / extract_school.py 同步：
# IB 課程 = 課程名稱不含中文字（純英文/縮寫）
SUBJECT_ORDER = ["國", "英", "自", "數", "社", "藝", "體", "特", "二外", "本土語"]
SELF_STUDY_KEYWORDS = ["自主", "自學"]


def is_ib_course(name):
    if not name:
        return False
    return not any("一" <= c <= "鿿" for c in name)


def main():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # ── 1. 教師清單與分類 ──
    teachers = {}  # code → (name, subject, isIB, homeroom, detail)
    for r in rows:
        code = r["教師代碼"]
        if code not in teachers:
            teachers[code] = (
                r["教師"],
                r["主授科目"],
                r["教師類別"] == "IB教師",
                r["導師班級"],
                r.get("細科目", ""),
            )
    sorted_codes = sorted(teachers.keys())

    md = []
    md.append("# 全校課表分類確認表\n")
    md.append("自動產出，由 `scripts/audit_categories.py` 從 `全校課表_長表.csv` 統計。\n")
    md.append("**用途**：人工審查每位老師的分類、IB 課程定義、領域與自主課程是否歸對。\n")
    md.append(f"資料規模：**130 位老師 / 1816 筆課程**（兩位純領域時間老師沒實際課程，未列入此表）\n")

    # ── 2. 主授科目分布 ──
    subj_count = Counter(t[1] for t in teachers.values())
    md.append("## 1. 主授科目分布\n")
    md.append("| 科目 | 人數 |")
    md.append("|------|------|")
    for s in SUBJECT_ORDER:
        md.append(f"| {s} | {subj_count.get(s, 0)} |")
    md.append(f"| **總計** | **{sum(subj_count.values())}** |")
    md.append("")

    # ── 3. 每位老師的主授科目 ──
    md.append("## 2. 每位老師主授科目（依代號排序）\n")
    md.append("| 代號 | 教師 | 主授 | 細科目 | IB | 導師班 |")
    md.append("|------|------|------|--------|------|--------|")
    for code in sorted_codes:
        name, subj, isIB, hr, det = teachers[code]
        ib_mark = "✓" if isIB else ""
        hr_mark = hr if hr else ""
        md.append(f"| {code} | {name} | {subj} | {det} | {ib_mark} | {hr_mark} |")
    md.append("")

    # ── 4. IB 教師清單 ──
    ib_teachers = [(c, teachers[c][0]) for c in sorted_codes if teachers[c][2]]
    md.append(f"## 3. IB 教師（{len(ib_teachers)} 位）\n")
    md.append("依教師代號排序。\n")
    md.append("| 代號 | 教師 | 主授 | 細科目 |")
    md.append("|------|------|------|--------|")
    for code, name in ib_teachers:
        md.append(f"| {code} | {name} | {teachers[code][1]} | {teachers[code][4]} |")
    md.append("")

    # ── 5. 班級導師 ──
    homeroom = [(c, teachers[c][0], teachers[c][3]) for c in sorted_codes if teachers[c][3]]
    homeroom_by_class = sorted(homeroom, key=lambda x: x[2])
    md.append(f"## 4. 班級導師（{len(homeroom)} 位）\n")
    md.append("依班級號排序，方便對照。\n")
    md.append("| 班級 | 代號 | 教師 | 主授 | 細科目 |")
    md.append("|------|------|------|------|--------|")
    for code, name, klass in homeroom_by_class:
        md.append(f"| {klass} | {code} | {name} | {teachers[code][1]} | {teachers[code][4]} |")
    md.append("")

    # ── 6. IB 課程清單（match IB_PATTERNS） ──
    ib_courses = sorted({r["課程名稱"] for r in rows if is_ib_course(r["課程名稱"])})
    course_count = Counter(r["課程名稱"] for r in rows)
    md.append(f"## 5. IB 課程（{len(ib_courses)} 種）\n")
    md.append(f"判定規則：課程名稱**不含中文字**即為 IB 課程（純英文/縮寫）。\n")
    md.append(f"代課查詢介面遇到這些課程會走「IB同科 → IB同班 → IB其他科 → 同科 → 其他科」5 階優先。\n")
    md.append("| 課程名稱 | 出現次數 |")
    md.append("|----------|----------|")
    for c in ib_courses:
        md.append(f"| `{c}` | {course_count[c]} |")
    md.append("")

    # ── 7. 含「領域」的課程 ──
    domain_courses = sorted({r["課程名稱"] for r in rows if "領域" in r["課程名稱"]})
    md.append(f"## 6. 含「領域」字樣的課程\n")
    md.append("`領域時間` 在抽取階段已從主表移除（另存於 `全校_領域時間.md`），下表只列實際存在於主課表的「領域」課程。\n")
    if domain_courses:
        md.append("| 課程名稱 | 出現次數 | 是否為「領域時間」 |")
        md.append("|----------|----------|-------------------|")
        for c in domain_courses:
            is_ryu = "✓" if c == "領域時間" else "✗（其他領域課程）"
            md.append(f"| `{c}` | {course_count[c]} | {is_ryu} |")
    else:
        md.append("（主課表中沒有任何含「領域」字樣的課程）")
    md.append("")

    # ── 8. 自主學習相關課程 ──
    self_study = sorted({r["課程名稱"] for r in rows
                         if any(k in r["課程名稱"] for k in SELF_STUDY_KEYWORDS)})
    md.append(f"## 7. 含「自主」/「自學」字樣的課程（{len(self_study)} 種）\n")
    md.append("這些都被分類器歸為「彈性課」，**不計入主授科目判定**。\n")
    md.append("| 課程名稱 | 出現次數 |")
    md.append("|----------|----------|")
    for c in self_study:
        md.append(f"| `{c}` | {course_count[c]} |")
    md.append("")

    # ── 9. 各主授科目 → 實際課程列表 ──
    md.append("## 8. 各主授科目對應的課程\n")
    md.append("看分類器把哪些課歸到哪個科目，方便驗證分類是否合理。\n")
    md.append("（類別 None 代表彈性課/行政/IB 工具課，不參與主授判定）\n")
    # 我們不能 import classify_course_subject 嗎？可以，只是要從 scripts.extract_school import
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from extract_school import classify_course_subject

    courses_by_subject = defaultdict(list)
    for c in sorted(course_count.keys()):
        s = classify_course_subject(c)
        courses_by_subject[s if s else "（彈性／不計入）"].append((c, course_count[c]))

    order = SUBJECT_ORDER + ["（彈性／不計入）"]
    for s in order:
        if s not in courses_by_subject:
            continue
        items = courses_by_subject[s]
        md.append(f"### {s}（{len(items)} 種課程，共 {sum(n for c,n in items)} 節）\n")
        md.append("| 課程名稱 | 次數 |")
        md.append("|----------|------|")
        for c, n in items:
            md.append(f"| `{c}` | {n} |")
        md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"[ok] 已寫出 {OUT_MD}")


if __name__ == "__main__":
    main()
