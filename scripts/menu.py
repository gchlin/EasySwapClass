# -*- coding: utf-8 -*-
"""menu.py — 「尋找調代課小幫手」更新工具（互動選單）

雙擊 更新課表.bat 會呼叫本檔。維護者不必記指令，選 1/2/3 即可。
本檔只負責「依序呼叫各專責腳本 + 中文提示」，不放任何業務邏輯。

對應動作：
  [1] 新學期完整更新：extract_school → build_data → build_single
  [2] 微調 CSV 後重生 data.js（nginx 立即更新）         → build_data
  [3] 只產單檔 HTML（自己手機 / email）                 → build_single
  [4] 產分類確認表，人工檢查                            → audit_categories
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
PDF = ROOT / "source" / "全校課表.pdf"
INDEX = ROOT / "school_wide" / "index.html"
MASTER = ROOT / "代課查詢_發布.html"
VERSION_FILE = ROOT / "school_wide" / "_data_version.txt"


def prompt_version():
    """詢問資料版本，直接 Enter 沿用上次。回傳要附加的參數 list。"""
    cur = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""
    hint = f"（目前：{cur}，直接 Enter 沿用）" if cur else "（如 114-2）"
    v = input(f"請輸入資料版本 {hint}：").strip()
    return ["--version", v] if v else []


def run(script, *args):
    """跑 scripts/<script>，回傳是否成功。"""
    cmd = [PY, str(ROOT / "scripts" / script), *args]
    print(f"\n>>> 執行 {script} {' '.join(args)}\n", flush=True)
    result = subprocess.run(cmd, cwd=str(ROOT))
    ok = result.returncode == 0
    print("\n" + ("[完成]" if ok else f"[失敗] {script} 回傳碼 {result.returncode}"))
    return ok


def deploy_ui():
    """把發布版母檔複製到 nginx 提供的 index.html。"""
    if not MASTER.exists():
        print(f"[略過] 找不到母檔 {MASTER.name}")
        return
    INDEX.write_text(MASTER.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[完成] 已把母檔部署到 {INDEX}")


HELP = """
─────────────────────────────────────────────
 使用說明
─────────────────────────────────────────────
 平常改資料給老師看（最常用）：
   1. 直接編輯 school_wide/全校課表_長表.csv
   2. 回到本選單按 [2] → 重生 data.js
   → nginx 網址立刻變新資料，HTML 不用動。

 自己手機 / 想要單一檔：
   按 [3] → 產出 school_wide/代課查詢_單檔.html
   這個檔自我包含，斷網雙擊也能用。

 換學期、拿到新 PDF：
   1. 把新 PDF 命名 全校課表.pdf 放進 source/
   2. 按 [1] 一條龍跑完。

 改網頁外觀 / 文字：
   只編輯 代課查詢_發布.html（瀏覽器可直接預覽），
   改完按 [5] 部署到 nginx，再按 [3] 重產單檔。
─────────────────────────────────────────────
"""

MENU = """
═════════════════════════════════════════════
  尋找調代課小幫手 — 更新工具
═════════════════════════════════════════════
  [1] 新學期完整更新（PDF → data.js → 單檔）
  [2] 微調 CSV 後重生 data.js（nginx 立即更新）
  [3] 只產單檔 HTML（自己手機 / email）
  [4] 分類確認表，人工檢查
  [5] 把母檔部署到 nginx（改完 UI 後用）
  [H] 使用說明      [0] 離開
═════════════════════════════════════════════"""


def main():
    while True:
        print(MENU)
        if not PDF.exists():
            print("  ⚠ 尚未偵測到 source/全校課表.pdf（選 1 前請先放好）")
        choice = input("請輸入選項：").strip().lower()

        if choice == "1":
            if not PDF.exists():
                print("[停止] 請先把新學期 PDF 命名為「全校課表.pdf」放進 source/ 再選 1。")
                continue
            ver = prompt_version()
            if run("extract_school.py") and run("build_data.py", *ver):
                run("build_single.py")
                deploy_ui()
        elif choice == "2":
            run("build_data.py", *prompt_version())
        elif choice == "3":
            run("build_single.py")
        elif choice == "4":
            run("audit_categories.py")
        elif choice == "5":
            deploy_ui()
        elif choice == "h":
            print(HELP)
        elif choice == "0":
            print("再見！")
            return
        else:
            print("[?] 沒有這個選項，請重新輸入。")


if __name__ == "__main__":
    main()
