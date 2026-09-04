"""build_single.py  (v2 資料注入：發布版母檔 → 單檔 HTML)

把「發布版母檔」(代課查詢_發布.html，內含 <script src="data.js">) 的那行外部引用，
換成內嵌的正式資料，產生一份「自我包含」的單檔 HTML——適合自己手機 / email / 離線雙擊用。
輸出到 versions/<版本>/代課查詢_單檔.html。

設計：UI 只維護母檔一份；本腳本只把資料內嵌進去，不碰任何 UI。
資料邏輯重用 build_data.build_data_and_teachers（自包含、不牽動整頁重生）。

用法：
    python scripts/build_single.py                # 用目前版本
    python scripts/build_single.py --version 115-1
"""
import argparse
import csv
import json

import paths
from build_data import build_data_and_teachers

LOADER_TAG = '<script src="data.js"></script>'


def main():
    ap = argparse.ArgumentParser(description="發布版母檔 + CSV → 內嵌資料的單檔 HTML")
    ap.add_argument("--version", default=None, help="版本資料夾名；預設為目前版本")
    ap.add_argument("--csv", default=None, help="來源 CSV（預設 versions/<版本>/全校課表_長表.csv）")
    ap.add_argument("--master", default=None, help="發布版母檔（預設 代課查詢_發布.html）")
    ap.add_argument("--out", default=None, help="輸出單檔（預設 versions/<版本>/代課查詢_單檔.html）")
    args = ap.parse_args()

    version = args.version or paths.current_version()
    if not version:
        raise SystemExit("[err] 未指定版本，也沒有目前版本。請用 --version 指定。")

    master = args.master or str(paths.MASTER)
    csv_path = args.csv or str(paths.csv_path(version))
    out_path = args.out or str(paths.single_path(version))

    with open(master, encoding="utf-8") as f:
        html = f.read()
    if LOADER_TAG not in html:
        raise SystemExit(f"[err] 母檔找不到 {LOADER_TAG}；確認用的是發布版母檔。")

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    roster = None
    roster_json = paths.teachers_json_path(version)
    if roster_json.exists():
        roster = json.loads(roster_json.read_text(encoding="utf-8"))
    data, teachers = build_data_and_teachers(rows, roster)

    # 領域時間（視同空堂，網頁只畫灰框標示）；缺檔就空陣列
    ryu = []
    ryu_json = paths.ryu_json_path(version)
    if ryu_json.exists():
        ryu = [
            {"tcode": r["tcode"], "day": r["day"], "period": r["period"],
             "course": r.get("course", "領域時間")}
            for r in json.loads(ryu_json.read_text(encoding="utf-8"))
        ]

    def js_json(obj):
        # 防止資料裡萬一出現 </script> 提前關閉腳本標籤
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    inline = (
        "<script>\n"
        "window.__DATA_VERSION__ = " + js_json(version) + ";\n"
        "window.__DATA__ = " + js_json(data) + ";\n"
        "window.__TEACHERS__ = " + js_json(teachers) + ";\n"
        "window.__RYU__ = " + js_json(ryu) + ";\n"
        "</script>"
    )
    html = html.replace(LOADER_TAG, inline, 1)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] 已寫出 {out_path}")
    print(f"     資料版本：{version}／{len(data)} 筆課程 / {len(teachers)} 位老師"
          f" / 領域時間 {len(ryu)} 格（已內嵌，不需 data.js）")


if __name__ == "__main__":
    main()
