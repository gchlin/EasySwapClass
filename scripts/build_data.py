"""build_data.py  (v2 資料注入：CSV → data.js)

把某版本的 全校課表_長表.csv 轉成該版的 data.js，內容為三個全域變數：
    window.__DATA_VERSION__ = "114-2";
    window.__DATA__     = [...每一筆課程...];
    window.__TEACHERS__ = [...每位老師...];
    window.__RYU__      = [...領域時間時段...];   // 視同空堂，網頁只畫灰框標示

「發布版」HTML 用 <script src="data.js"></script> 引用它。本腳本只寫到
versions/<版本>/data.js；「複製到 live/（發布）」由選單負責，避免建舊版時誤動線上。

刻意寫成「自包含」：直接讀 CSV 既有欄位（含已分類好的『細科目』），
不 import build_web_school / extract_school，避免牽動整頁重生或其他相依。
唯一外部相依是 assets/_strokes.json（姓名筆劃），缺檔則筆劃以 0 計。

用法：
    python scripts/build_data.py                 # 用目前版本
    python scripts/build_data.py --version 115-1  # 指定版本資料夾
"""
import argparse
import csv
import json

import paths

# 姓名筆劃表（由 build_strokes.py 從 Unihan 抽取）。
strokes_table = {}
if paths.STROKES_JSON.exists():
    strokes_table = json.loads(paths.STROKES_JSON.read_text(encoding="utf-8"))


def name_strokes(name):
    """姓名總筆劃。非中文字（如英文名）回傳 999 排到最後。"""
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


def build_data_and_teachers(rows, roster=None):
    """產出 (data, teachers)；courseDetail 直接取 CSV 已分類好的『細科目』欄。

    roster：extract_school 產出的完整教師名冊（teachers.json）。有給就以它為準——
    有老師全學期只排領域時間（領域時間視同空堂、不進 CSV），從 CSV 反推名冊會漏掉他。
    沒給（舊版本沒這個檔）則沿用從 CSV 反推的舊行為。"""
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
    if roster:
        teachers = [
            {
                "code": t["code"],
                "name": t["name"],
                "subject": t["subject"],
                "detail": t["detail"],
                "isIB": t["isIB"],
                "homeroom": t["homeroom"],
                "strokes": name_strokes(t["name"]),
            }
            for t in sorted(roster, key=lambda x: x["code"])
        ]
        return data, teachers

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
    ap.add_argument("--version", default=None, help="版本資料夾名（如 114-2）；預設為目前版本")
    ap.add_argument("--csv", default=None, help="來源 CSV（預設 versions/<版本>/全校課表_長表.csv）")
    ap.add_argument("--out", default=None, help="輸出 data.js（預設 versions/<版本>/data.js）")
    args = ap.parse_args()

    version = args.version or paths.current_version()
    if not version:
        raise SystemExit("[err] 未指定版本，也沒有目前版本。請用 --version 指定。")

    csv_path = args.csv or str(paths.csv_path(version))
    out_path = args.out or str(paths.data_js_path(version))

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    roster = None
    roster_json = paths.teachers_json_path(version)
    if roster_json.exists():
        roster = json.loads(roster_json.read_text(encoding="utf-8"))
    data, teachers = build_data_and_teachers(rows, roster)

    # 領域時間：extract_school 已把這些格子排除出 CSV（＝視同空堂、可被調進來），
    # 這裡另外帶給網頁做灰框標示用。缺檔（舊版本）就給空陣列，網頁照樣運作。
    ryu = []
    ryu_json = paths.ryu_json_path(version)
    if ryu_json.exists():
        ryu = [
            {"tcode": r["tcode"], "day": r["day"], "period": r["period"],
             "course": r.get("course", "領域時間")}
            for r in json.loads(ryu_json.read_text(encoding="utf-8"))
        ]

    js = (
        "window.__DATA_VERSION__ = " + json.dumps(version, ensure_ascii=False) + ";\n"
        "window.__DATA__ = " + json.dumps(data, ensure_ascii=False) + ";\n"
        "window.__TEACHERS__ = " + json.dumps(teachers, ensure_ascii=False) + ";\n"
        "window.__RYU__ = " + json.dumps(ryu, ensure_ascii=False) + ";\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"[ok] 已寫出 {out_path}")
    print(f"     資料版本：{version}／{len(data)} 筆課程 / {len(teachers)} 位老師"
          f" / 領域時間 {len(ryu)} 格（視同空堂）")


if __name__ == "__main__":
    main()
