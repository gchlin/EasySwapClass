"""
用 pdfplumber 從 課表.pdf 結構化抽取，產生 課表_v2.csv，
然後與已校對的 課表_長表.csv 比對，計算錯誤率。

策略：
1. pdfplumber.extract_tables() 利用 PDF 的表格邊框抓出格子
2. 列固定對應節次（row index → period）、欄固定對應星期
3. 每格內容按 \\n 分行：第 1 行=課程名、第 2 行=班級、第 3 行=教室
4. 領域時間整列跳過（v1 已刪除）
"""
import csv
import re
from pathlib import Path
import pdfplumber
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = str(ROOT / "source" / "課表.pdf")
V1_CSV = str(ROOT / "natural_science" / "課表_長表.csv")
V2_CSV = str(ROOT / "natural_science" / "課表_v2.csv")
DIFF_MD = str(ROOT / "natural_science" / "v2_diff.md")

DAY_COL = {3: 1, 4: 2, 5: 3, 6: 4, 7: 5}  # 表格欄索引 → 星期 1-5
ROW_PERIOD = {4: 1, 5: 2, 6: 3, 7: 4, 9: 5, 10: 6, 11: 7, 12: 8}

DAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}

# ── 後處理規則 ─────────────────────────────────────────
# PDF 字型缺字（render 為 ?）的直接映射
COURSE_RENAMES = {
    "物理-探?": "物理地科探究",
    "化學-探?": "化學生物探究",
}

def is_class_like(line):
    """判斷一行是否為班級格式：開頭數字 或 共計 或 IB班(216A 等)"""
    if not line:
        return False
    if re.match(r"^\d", line):
        return True
    if line.startswith("共計"):
        return True
    return False

def is_room_like(line):
    """判斷一行是否為教室格式：T/A/S開頭+數字 / IB開頭"""
    if not line:
        return False
    if re.match(r"^[TAS]\d", line):
        return True
    if line.startswith("IB"):
        return True
    return False

def normalize_course(c):
    """課程名稱正規化：直接映射 + 去掉 PDF 亂碼字元（保留英文間空白）"""
    if c in COURSE_RENAMES:
        return COURSE_RENAMES[c]
    # 移除全形標點 + 字型缺失符號；空白保留（給英文課名用）
    return c.replace("、", "").replace("?", "")

def normalize_room(r):
    """教室正規化：T2106(ES → T2106(ES)（補回被截斷的右括號）"""
    if not r:
        return r
    if re.match(r"^[A-Z]\d+\([A-Za-z]+$", r):
        return r + ")"
    return r


def parse_cell(text):
    """把 cell 文字拆成 (課程名稱, 班級, 教室)。空字串/None 回傳 None。

    處理規則：
    - 第 1 行為課程名稱起始
    - 後續行：若不是「班級樣態」且未到末尾，視為課名延續（多行課名）
    - 直到遇到 class-like 行 → 該行為班級
    - 班級之後的行 → 教室
    - 若 rest 只剩 1 行：用 is_room_like 判斷是 class 還是 room
    """
    if not text or not text.strip():
        return None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return None

    # 累積課名行，直到遇到 class-like 行
    course_lines = [lines[0]]
    rest = lines[1:]
    while rest and not is_class_like(rest[0]):
        # 如果 rest[0] 看起來是教室（如 A1501(Mu)），停止累積，把它當教室
        if is_room_like(rest[0]):
            break
        course_lines.append(rest[0])
        rest = rest[1:]

    course = normalize_course("".join(course_lines))

    # 處理剩下的 1-2-3 行
    klass = ""
    room = ""
    if len(rest) == 1:
        if is_room_like(rest[0]):
            room = normalize_room(rest[0])
        else:
            klass = re.sub(r"\s+", "", rest[0])
    elif len(rest) >= 3 and is_room_like(rest[0]) and is_class_like(rest[1]) and is_room_like(rest[2]):
        # 重複教室 pattern: [room, class, room]（語文教師、健護等）
        # 取第 2 個教室（通常較完整，沒被截斷）
        klass = re.sub(r"\s+", "", rest[1])
        room = normalize_room(rest[2])
    elif len(rest) >= 2:
        klass = re.sub(r"\s+", "", rest[0])
        room = normalize_room(rest[1])

    return (course, klass, room)


def extract_teacher_header(row0_text):
    """從 row 0 抓教師代碼 + 名字。例：'教 師： 蔡玉珍 (N01) 210 導師' """
    if not row0_text:
        return None, None
    text = row0_text.replace("\n", " ")
    m = re.search(r"教\s*師[:：]\s*(\S+)\s*\(([A-Za-z]\d+)\)", text)
    if m:
        return m.group(2), m.group(1)
    return None, None


def main():
    rows_v2 = []
    pages_info = []

    with pdfplumber.open(PDF_PATH) as pdf:
        for pi, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                print(f"page {pi+1}: no table")
                continue
            t = tables[0]
            tcode, tname = extract_teacher_header(t[0][0] if t and t[0] else "")
            if not tcode:
                print(f"page {pi+1}: 教師資訊解析失敗")
                continue
            pages_info.append((pi + 1, tcode, tname))

            for row_idx, period in ROW_PERIOD.items():
                if row_idx >= len(t):
                    continue
                row = t[row_idx]
                for col_idx, day in DAY_COL.items():
                    if col_idx >= len(row):
                        continue
                    cell = row[col_idx]
                    parsed = parse_cell(cell)
                    if parsed is None:
                        continue
                    course, klass, room = parsed
                    # 跳過 領域時間
                    if "領域時間" in course:
                        continue
                    rows_v2.append({
                        "教師代碼": tcode,
                        "教師": tname,
                        "星期": day,
                        "節次": period,
                        "課程名稱": course,
                        "班級": klass,
                        "教室": room,
                    })

    # 寫 v2 CSV
    with open(V2_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows_v2[0].keys()))
        writer.writeheader()
        writer.writerows(rows_v2)
    print(f"[ok] v2 寫出 {V2_CSV}（{len(rows_v2)} 筆，{len(pages_info)} 位老師）")

    # 載入 v1 (gold standard)
    with open(V1_CSV, encoding="utf-8-sig") as f:
        rows_v1 = list(csv.DictReader(f))

    # 建索引（教師代碼, 星期, 節次）→ row
    def to_key(r):
        return (r["教師代碼"], int(r["星期"]), int(r["節次"]))

    v1_idx = {to_key(r): r for r in rows_v1}
    v2_idx = {to_key(r): r for r in rows_v2}

    keys = set(v1_idx) | set(v2_idx)
    missing_in_v2 = sorted(k for k in keys if k in v1_idx and k not in v2_idx)
    extra_in_v2 = sorted(k for k in keys if k in v2_idx and k not in v1_idx)
    common = sorted(k for k in keys if k in v1_idx and k in v2_idx)

    # 比對共同 keys 的內容差異
    field_diffs = []
    for k in common:
        v1, v2 = v1_idx[k], v2_idx[k]
        diffs = {}
        for field in ["課程名稱", "班級", "教室"]:
            if v1[field] != v2.get(field, ""):
                diffs[field] = (v1[field], v2.get(field, ""))
        if diffs:
            field_diffs.append((k, diffs))

    # 統計
    total_cells = len(keys)
    perfect = total_cells - len(missing_in_v2) - len(extra_in_v2) - len(field_diffs)

    md = []
    md.append("# v2 (pdfplumber) vs v1 (人工校對) 差異報告\n")
    md.append(f"- v1 筆數：{len(rows_v1)}")
    md.append(f"- v2 筆數：{len(rows_v2)}")
    md.append(f"- 共同 key 數：{len(common)}")
    md.append(f"- 完全相同：**{perfect}** / {total_cells}（{perfect / total_cells * 100:.1f}%）")
    md.append(f"- v2 缺漏（v1 有 v2 沒有）：{len(missing_in_v2)}")
    md.append(f"- v2 多出（v2 有 v1 沒有）：{len(extra_in_v2)}")
    md.append(f"- 內容不一致：{len(field_diffs)}\n")

    if missing_in_v2:
        md.append("## v2 缺漏（v1 有，v2 沒有）\n")
        md.append("| 教師代碼 | 星期 | 節 | v1 課程 | v1 班級 | v1 教室 |")
        md.append("|----------|------|----|---------|---------|---------|")
        for k in missing_in_v2:
            v1 = v1_idx[k]
            md.append(f"| {k[0]} | {DAY_NAMES[k[1]]} | {k[2]} | {v1['課程名稱']} | {v1['班級']} | {v1['教室']} |")
        md.append("")

    if extra_in_v2:
        md.append("## v2 多出（v2 有，v1 沒有）\n")
        md.append("| 教師代碼 | 星期 | 節 | v2 課程 | v2 班級 | v2 教室 |")
        md.append("|----------|------|----|---------|---------|---------|")
        for k in extra_in_v2:
            v2 = v2_idx[k]
            md.append(f"| {k[0]} | {DAY_NAMES[k[1]]} | {k[2]} | {v2['課程名稱']} | {v2['班級']} | {v2['教室']} |")
        md.append("")

    if field_diffs:
        md.append("## 內容不一致\n")
        md.append("| 教師代碼 | 星期 | 節 | 欄位 | v1 (正確) | v2 (pdfplumber) |")
        md.append("|----------|------|----|------|-----------|-----------------|")
        for k, diffs in field_diffs:
            for field, (v1val, v2val) in diffs.items():
                md.append(f"| {k[0]} | {DAY_NAMES[k[1]]} | {k[2]} | {field} | `{v1val}` | `{v2val}` |")
        md.append("")

    # 系統性差異分析
    md.append("## 系統性差異分析\n")
    course_renames = Counter()
    for k, diffs in field_diffs:
        if "課程名稱" in diffs:
            v1c, v2c = diffs["課程名稱"]
            course_renames[(v2c, v1c)] += 1
    if course_renames:
        md.append("### 課程名稱常見差異（PDF → 校對後）\n")
        md.append("| pdfplumber 取到 | 校對後正確值 | 次數 |")
        md.append("|------------------|---------------|------|")
        for (v2c, v1c), n in course_renames.most_common():
            md.append(f"| `{v2c}` | `{v1c}` | {n} |")
        md.append("")
        md.append("（這類差異是系統性的——PDF 內的字無法正確 render 成繁體中文，"
                  "顯示為 `?` 或亂碼。可在後處理階段做 mapping 修正。）\n")

    with open(DIFF_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"[ok] 差異報告寫出 {DIFF_MD}")


if __name__ == "__main__":
    main()
