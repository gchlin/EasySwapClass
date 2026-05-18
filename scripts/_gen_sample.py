"""
Rewrite sample_data CSV with 50/60-range codes and inject the data
into 調代課小幫手(sample_data)_v3.1.html.

Run from the project root:
    python scripts/_gen_sample.py
"""

import csv, json, re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── 代號對照表：舊 → 新 ──────────────────────────────────────────────
CODE_MAP = {
    "C01": "C50", "C02": "C51", "C03": "C52",
    "E01": "E60", "E02": "E61", "E03": "E62",
    "M01": "M50", "M02": "M51", "M03": "M52",
    "N01": "N50", "N02": "N51", "N03": "N52",
    "F01": "F60", "F02": "F61", "F03": "F62",
    "A01": "A60", "A02": "A61",
    "G01": "G50",
    "L01": "L60", "L02": "L61",
}
# 姓名的數字後綴同步更新（01→50 etc.）
NUM_MAP = {f"{int(o[1:]):02d}": f"{int(n[1:]):02d}" for o, n in CODE_MAP.items()}

# ── 細科目 → HTML 用的短碼 ─────────────────────────────────────────
DETAIL_SHORT = {
    "物理": "物", "化學": "化", "生物": "生", "地科": "地科",
    "歷史": "史", "地理": "地理", "公民": "公民", "法律": "法律",
    "音樂": "音樂", "美術": "美術", "視覺藝術": "視覺藝術",
    "體育": "體育", "健護": "健護",
    "特教": "特",
    "日語": "日", "德語": "德",
}

# 虛構筆劃（不含真實姓名，給固定值即可）
STROKES = {
    "C50": 15, "C51": 18, "C52": 12,
    "E60": 20, "E61": 16, "E62": 22,
    "M50": 14, "M51": 17, "M52": 19,
    "N50": 16, "N51": 13, "N52": 21,
    "F60": 18, "F61": 15, "F62": 17,
    "A60": 12, "A61": 14,
    "G50": 19,
    "L60": 16, "L61": 20,
}


def remap_row(row):
    old_code = row["教師代號"]
    new_code = CODE_MAP.get(old_code, old_code)
    old_num  = old_code[1:]                    # e.g. "01"
    new_num  = new_code[1:]                    # e.g. "50"
    new_name = row["教師姓名"].replace(f"{int(old_num):02d}", f"{int(new_num):02d}")
    return {**row, "教師代號": new_code, "教師姓名": new_name}


def main():
    src_csv  = ROOT / "sample_data" / "全校課表_長表_sample.csv"
    html_src = ROOT / "調代課小幫手(sample_data)_v3.1.html"

    # ── 1. 讀原 CSV，重寫代號 ─────────────────────────────────────
    rows = []
    with open(src_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for r in reader:
            rows.append(remap_row(r))

    with open(src_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] CSV updated ({len(rows)} rows)")

    # ── 2. 從更新後的 CSV 建立 TEACHERS & DATA ───────────────────
    teachers_map = {}   # code → teacher dict
    data_list    = []

    for r in rows:
        code    = r["教師代號"]
        name    = r["教師姓名"]
        subject = r["主授科目"]
        detail  = DETAIL_SHORT.get(r["細科目"], r["細科目"])
        is_ib   = r["教師類別"] == "IB"
        homeroom = r["導師班級"]

        # 只取第一次出現的導師班資訊（可能多筆，取非空的那筆）
        if code not in teachers_map:
            teachers_map[code] = {
                "code": code, "name": name, "subject": subject,
                "detail": detail, "isIB": is_ib,
                "homeroom": homeroom, "strokes": STROKES.get(code, 20),
            }
        elif homeroom and not teachers_map[code]["homeroom"]:
            teachers_map[code]["homeroom"] = homeroom

        # 排除彈性課程（無班級 & 課名含行政/領域/多元 等）
        klass  = r["班級"]
        course = r["課程名"]
        room   = r["教室"]

        if not klass and any(kw in course for kw in ["行政", "領域時間", "團體活動", "多元選修"]):
            continue

        data_list.append({
            "tcode": code, "tname": name,
            "day": int(r["星期"]), "period": int(r["節次"]),
            "course": course, "klass": klass, "room": room,
            "courseDetail": detail,
        })

    # 排序：照代號字母順序，再照 day/period
    teachers_list = sorted(teachers_map.values(), key=lambda t: t["code"])
    data_list.sort(key=lambda d: (d["tcode"], d["day"], d["period"]))

    teachers_js = "const TEACHERS = " + json.dumps(teachers_list, ensure_ascii=False) + ";"
    data_js     = "const DATA = "     + json.dumps(data_list,     ensure_ascii=False) + ";"

    # ── 3. 注入 HTML ──────────────────────────────────────────────
    html_text = html_src.read_text(encoding="utf-8")

    # DATA 在 327 行、TEACHERS 在 328 行（兩行都是超長單行）
    html_text = re.sub(r"^const DATA = \[.*\];$",     data_js,     html_text, flags=re.MULTILINE)
    html_text = re.sub(r"^const TEACHERS = \[.*\];$", teachers_js, html_text, flags=re.MULTILINE)

    html_src.write_text(html_text, encoding="utf-8")
    print(f"[OK] HTML updated ({len(teachers_list)} teachers, {len(data_list)} schedule rows)")


if __name__ == "__main__":
    main()
