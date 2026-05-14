"""
從 Unicode Unihan 資料庫抽出教師姓名漢字的筆劃數，存到 _strokes.json。

Unihan 是 Unicode 官方的中日韓漢字資料，含 kTotalStrokes（康熙總筆劃）欄位。
本腳本只在「教師名單變動」時需要重跑（新增/刪除老師、姓名漢字有變動）。

執行：python scripts/build_strokes.py
產出：school_wide/_strokes.json
快取：school_wide/_unihan_irg.txt（首次下載 8MB Unihan.zip 後抽出，後續離線可重跑）
"""
import csv
import json
import urllib.request
import zipfile
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "school_wide" / "全校課表_長表.csv"
OUT_JSON = ROOT / "school_wide" / "_strokes.json"
CACHE_PATH = ROOT / "school_wide" / "_unihan_irg.txt"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"


def main():
    # 1. 抓出所有教師姓名的 unique 漢字
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    chars = set()
    for r in rows:
        for c in r["教師"]:
            if "一" <= c <= "鿿":
                chars.add(c)
    print(f"教師姓名共 {len(chars)} 個 unique 漢字")

    # 2. 取得 Unihan_IRGSources.txt（含 kTotalStrokes）
    if CACHE_PATH.exists():
        text = CACHE_PATH.read_text(encoding="utf-8")
        print(f"使用快取 {CACHE_PATH.name}")
    else:
        print(f"下載 {UNIHAN_URL} ...")
        with urllib.request.urlopen(UNIHAN_URL, timeout=60) as r:
            data = r.read()
        zf = zipfile.ZipFile(io.BytesIO(data))
        text = zf.read("Unihan_IRGSources.txt").decode("utf-8")
        CACHE_PATH.write_text(text, encoding="utf-8")
        print(f"  下載 {len(data) / 1024:.0f} KB，快取 IRGSources 至 {CACHE_PATH.name}")

    # 3. 解析 kTotalStrokes，只挑出我們需要的字
    strokes = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[1] != "kTotalStrokes":
            continue
        code_point = int(parts[0][2:], 16)  # "U+4E00" → 19968
        char = chr(code_point)
        if char in chars:
            # 多值 (e.g., "5 6") 取第一個（簡繁有時不同）
            strokes[char] = int(parts[2].split()[0])

    missing = chars - set(strokes.keys())
    print(f"解析到 {len(strokes)}/{len(chars)} 個漢字筆劃")
    if missing:
        print(f"找不到筆劃（會用 fallback 0）: {''.join(sorted(missing))}")

    OUT_JSON.write_text(
        json.dumps(strokes, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[ok] {OUT_JSON}")


if __name__ == "__main__":
    main()
