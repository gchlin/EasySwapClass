"""
Generate sample_data/調代課小幫手(sample_data)_v3.1.html from scratch.

Uses build_web_school.TEMPLATE (so UI changes in build_web_school.py are
automatically reflected), injects sample CSV data, patches the version label,
then calls _inject_tour.inject() to add the onboarding tour overlay.

Run from the project root:
    python scripts/_gen_sample.py
"""

import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_web_school import TEMPLATE, H2C_JS, build_html  # noqa: E402
from _inject_tour import inject                              # noqa: E402

SRC_CSV  = ROOT / "sample_data" / "全校課表_長表_sample.csv"
HTML_OUT = ROOT / "sample_data" / "調代課小幫手(sample_data)_v3.1.html"

# ── 細科目短碼（sample 用虛構資料，不走 extract_school 分類器）──────
DETAIL_SHORT = {
    "物理": "物", "化學": "化", "生物": "生", "地科": "地科",
    "歷史": "史", "地理": "地理", "公民": "公民", "法律": "法律",
    "音樂": "音樂", "美術": "美術", "視覺藝術": "視覺藝術",
    "體育": "體育", "健護": "健護",
    "特教": "特",
    "日語": "日", "德語": "德",
}

# 虛構筆劃（給候選排序用）
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

SKIP_KEYWORDS = ["行政", "領域時間", "團體活動", "多元選修", "CAS", "IB admin", "TOK"]


def build_sample_data(rows):
    teachers_map = {}
    data_list = []

    for r in rows:
        code    = r["教師代號"]
        name    = r["教師姓名"]
        subject = r["主授科目"]
        detail  = DETAIL_SHORT.get(r["細科目"], r["細科目"])
        is_ib   = r["教師類別"] == "IB"
        homeroom = r["導師班級"]

        if code not in teachers_map:
            teachers_map[code] = {
                "code": code, "name": name, "subject": subject,
                "detail": detail, "isIB": is_ib,
                "homeroom": homeroom, "strokes": STROKES.get(code, 20),
            }
        elif homeroom and not teachers_map[code]["homeroom"]:
            teachers_map[code]["homeroom"] = homeroom

        klass  = r["班級"]
        course = r["課程名"]

        # 排除純行政 / 領域 / 彈性課程（無班級且含關鍵字）
        if not klass and any(kw in course for kw in SKIP_KEYWORDS):
            continue

        data_list.append({
            "tcode": code, "tname": name,
            "day": int(r["星期"]), "period": int(r["節次"]),
            "course": course, "klass": klass, "room": r["教室"],
            "courseDetail": detail,
        })

    teachers = sorted(teachers_map.values(), key=lambda t: t["code"])
    data_list.sort(key=lambda d: (d["tcode"], d["day"], d["period"]))
    return data_list, teachers


def main():
    if not SRC_CSV.exists():
        print(f"[ERROR] {SRC_CSV} not found.")
        return

    with open(SRC_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    data, teachers = build_sample_data(rows)

    # build_web_school の TEMPLATE から HTML を生成（__DATA__ / __TEACHERS__ 差し替え）
    html = build_html(data, teachers, h2c_js_path=H2C_JS)

    # バージョンラベルを sample data に変更
    html = html.replace("資料版本 114-2", "資料版本 sample data", 1)

    # 新手引導 tour を注入
    html, _ = inject(html)

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {HTML_OUT.name} generated ({len(teachers)} teachers, {len(data)} rows)")


if __name__ == "__main__":
    main()
