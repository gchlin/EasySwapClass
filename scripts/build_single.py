"""build_single.py  (v2 資料注入：發布版母檔 → 單檔 HTML)

把「發布版母檔」(代課查詢_發布.html，內含 <script src="data.js">) 的那行外部引用，
換成內嵌的正式資料，產生一份「自我包含」的單檔 HTML——適合自己手機 / email / 離線雙擊用。

設計：UI 只維護母檔一份；本腳本只把資料內嵌進去，不碰任何 UI。
資料邏輯重用 build_data.build_data_and_teachers（自包含、不牽動整頁重生）。

用法：
    python scripts/build_single.py
    python scripts/build_single.py --csv 路徑.csv --master 母檔.html --out 單檔.html
"""
import argparse
import csv
import json
from pathlib import Path

from build_data import build_data_and_teachers, resolve_version

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "school_wide" / "全校課表_長表.csv"
DEFAULT_MASTER = ROOT / "代課查詢_發布.html"
DEFAULT_OUT = ROOT / "school_wide" / "代課查詢_單檔.html"

LOADER_TAG = '<script src="data.js"></script>'


def main():
    ap = argparse.ArgumentParser(description="發布版母檔 + CSV → 內嵌資料的單檔 HTML")
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="來源 CSV")
    ap.add_argument("--master", default=str(DEFAULT_MASTER), help="發布版母檔 HTML")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="輸出單檔 HTML")
    ap.add_argument("--version", default=None, help="資料版本字串；不給則沿用上次")
    args = ap.parse_args()

    html = Path(args.master).read_text(encoding="utf-8")
    if LOADER_TAG not in html:
        raise SystemExit(f"[err] 母檔找不到 {LOADER_TAG}；確認用的是發布版母檔。")

    version = resolve_version(args.version)
    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    data, teachers = build_data_and_teachers(rows)

    def js_json(obj):
        # 防止資料裡萬一出現 </script> 提前關閉腳本標籤
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    inline = (
        "<script>\n"
        "window.__DATA_VERSION__ = " + js_json(version) + ";\n"
        "window.__DATA__ = " + js_json(data) + ";\n"
        "window.__TEACHERS__ = " + js_json(teachers) + ";\n"
        "</script>"
    )
    html = html.replace(LOADER_TAG, inline, 1)

    Path(args.out).write_text(html, encoding="utf-8")
    print(f"[ok] 已寫出 {args.out}")
    print(f"     資料版本：{version or '（未標示）'}／{len(data)} 筆課程 / {len(teachers)} 位老師（已內嵌，不需 data.js）")


if __name__ == "__main__":
    main()
