"""build_data.py  (v2 資料注入：CSV → data.js)

把 全校課表_長表.csv 轉成 data.js，內容為兩個全域變數：
    window.__DATA__     = [...每一筆課程...];
    window.__TEACHERS__ = [...每位老師...];

「發布版」HTML 用 <script src="data.js"></script> 引用它；更新資料只要重跑本腳本，
HTML 一個字都不用改。data.js 與 HTML 放同層即可（nginx 或本機）。

刻意寫成「自包含」：直接讀 CSV 既有欄位（含已分類好的『細科目』），
不 import build_web_school / extract_school，避免牽動整頁重生或其他相依。
唯一外部相依是 _strokes.json（姓名筆劃，用於候選排序），缺檔則筆劃以 0 計。

用法：
    python scripts/build_data.py
    python scripts/build_data.py --csv 路徑.csv --out 路徑.js
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "school_wide" / "全校課表_長表.csv"
DEFAULT_OUT = ROOT / "school_wide" / "data.js"
STROKES_JSON = ROOT / "school_wide" / "_strokes.json"

# 姓名筆劃表（由 build_strokes.py 從 Unihan 抽取）。與 build_web_school.name_strokes 同邏輯。
strokes_table = {}
if STROKES_JSON.exists():
    strokes_table = json.loads(STROKES_JSON.read_text(encoding="utf-8"))


def name_strokes(name):
    """姓名總筆劃。非中文字（如 E59）回傳 999 排到最後。"""
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
    """與 build_web_school.build_data_and_teachers 產出相同結構；
    courseDetail 直接取 CSV 已分類好的『細科目』欄。"""
    data = [
        {
            "tcode": r["教師代碼"],
            "tname": r["教師"],
            "day": int(r["星期"]),
            "period": int(r["節次"]),
            "course": r["課程名稱"],
            "klass": r["班級"],
            "room": r["教室"],
            "courseDetail": r["細科目"] or "",
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


def main():
    ap = argparse.ArgumentParser(description="CSV → data.js（資料注入用）")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="來源 CSV 路徑")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="輸出 data.js 路徑")
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    data, teachers = build_data_and_teachers(rows)

    js = (
        "window.__DATA__ = " + json.dumps(data, ensure_ascii=False) + ";\n"
        "window.__TEACHERS__ = " + json.dumps(teachers, ensure_ascii=False) + ";\n"
    )
    Path(args.out).write_text(js, encoding="utf-8")
    print(f"[ok] 已寫出 {args.out}")
    print(f"     資料：{len(data)} 筆課程 / {len(teachers)} 位老師")


if __name__ == "__main__":
    main()
