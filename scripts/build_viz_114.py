#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_viz_114.py
根據 Analysis_114/analysis_data.json 生成互動式 HTML 報告。

重用 build_viz.py 的 build_html()（版面/圖表邏輯一致），僅替換資料來源、
輸出路徑與標題（113-2 → 114）。

執行方式（在 課表分析/ 目錄下）：
    python scripts/build_viz_114.py
輸出：
    Analysis_114/workload_viz.html
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_viz  # 重用 build_html()

DATA_PATH = pathlib.Path("Analysis_114/analysis_data.json")
OUT_PATH = pathlib.Path("Analysis_114/workload_viz.html")


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    html = build_viz.build_html(data)
    # 標題年度替換（build_html 內標題硬編為 113-2）
    html = html.replace("113-2", "114")
    # footer 與依據文字改為 114 的定義與來源
    html = html.replace(
        "超鐘點 = 合計 − 基本鐘點 | 依據：school_wide/114課表資料含所有欄位.csv | "
        "腳本：scripts/analyze_workload.py + build_viz.py",
        "超鐘點 = 實際授課節數 − 最低門檻（=主職基準−副職減課−科目減課）| "
        "依據：Analysis_114/課表資料含所有欄位.csv（規則 import 自 113-2）| "
        "腳本：scripts/analyze_workload_114.py + build_viz_114.py")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   OK: {OUT_PATH}")


if __name__ == "__main__":
    main()
