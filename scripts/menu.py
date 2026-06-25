# -*- coding: utf-8 -*-
"""menu.py — 「尋找調代課小幫手」更新工具（互動選單）

雙擊 更新課表.bat 會呼叫本檔。維護者不必記指令，選 1/2/3 即可。
本檔負責「依序呼叫各專責腳本 + 中文提示 + 發布到 live/」，不放業務邏輯。

版面：產出依版本歸檔在 versions/<版本>/；nginx 服務固定的 live/；
「發布」(複製 data.js 與母檔到 live/、記住目前版本) 集中在本檔。

對應動作：
  [1] 新學期完整更新：extract_school → build_data → build_single → 發布
  [2] 微調 CSV 後重生 data.js 並發布（nginx 立即更新）
  [3] 只產單檔 HTML（自己手機 / email）
  [4] 產分類確認表，人工檢查
  [5] 重新產生 live 網頁 index.html（改完 UI、或 live 的 html 不見了時）
  [6] 修復母檔（從 live/index.html 或最新單檔重建 template 母檔）
"""
import importlib.util
import re
import subprocess
import sys

import paths

PY = sys.executable


def extract_ready():
    """選項 1/4 需要 PDF 解析能力。缺東西時給友善提示，不噴 traceback。"""
    missing = []
    if not (paths.ROOT / "scripts" / "extract_v2.py").exists():
        missing.append("scripts/extract_v2.py（PDF 解析底層，目前不在；需從 git 還原）")
    if importlib.util.find_spec("pdfplumber") is None:
        missing.append("pdfplumber 套件（請先執行 pip install pdfplumber）")
    if missing:
        print("\n[無法執行] 這個選項需要先準備：")
        for m in missing:
            print("   - " + m)
        print("（選項 2 / 3 不需要這些，可正常使用）")
        return False
    return True


def prompt_version():
    """詢問版本（＝版本資料夾名＋頁面顯示版本）；直接 Enter 沿用目前。"""
    cur = paths.current_version()
    hint = f"（目前：{cur}，直接 Enter 沿用）" if cur else "（如 114-2）"
    v = input(f"請輸入資料版本 {hint}：").strip()
    return v or cur


def run(script, *args):
    """跑 scripts/<script>，回傳是否成功。"""
    cmd = [PY, str(paths.ROOT / "scripts" / script), *args]
    print(f"\n>>> 執行 {script} {' '.join(args)}\n", flush=True)
    ok = subprocess.run(cmd, cwd=str(paths.ROOT)).returncode == 0
    print("\n" + ("[完成]" if ok else f"[失敗] {script}"))
    return ok


def deploy_ui():
    """把發布版母檔複製到 live/index.html。"""
    if not paths.MASTER.exists():
        print(f"[略過] 找不到母檔 {paths.MASTER.name}")
        return
    paths.LIVE.mkdir(parents=True, exist_ok=True)
    paths.LIVE_INDEX.write_text(paths.MASTER.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[完成] 已部署母檔到 {paths.LIVE_INDEX}")


def publish(version):
    """發布某版本到 live/：data.js + 母檔 → live/，並記住目前版本。"""
    src = paths.data_js_path(version)
    if src.exists():
        paths.LIVE.mkdir(parents=True, exist_ok=True)
        paths.LIVE_DATA.write_bytes(src.read_bytes())
        print(f"[完成] 已更新 {paths.LIVE_DATA}")
    deploy_ui()
    paths.set_current_version(version)
    print(f"[發布完成] 目前版本 = {version}（nginx 的 live/ 已是最新）")


def repair_master():
    """母檔 template/代課查詢_發布.html 不見時，從備援重建它。
    優先序：live/index.html（逐字複本）→ 最新單檔（把內嵌資料換回引用）。"""
    if paths.MASTER.exists():
        print("[OK] 母檔存在，無需修復。")
        return
    paths.MASTER.parent.mkdir(parents=True, exist_ok=True)

    # 1) live/index.html 是母檔的逐字複本
    if paths.LIVE_INDEX.exists():
        paths.MASTER.write_text(paths.LIVE_INDEX.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[修復] 已從 {paths.LIVE_INDEX} 還原母檔 → {paths.MASTER}")
        return

    # 2) 從最新的單檔重建：把內嵌資料區塊換回 <script src="data.js">
    singles = []
    if paths.VERSIONS.exists():
        singles = sorted(paths.VERSIONS.glob("*/代課查詢_單檔.html"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    if singles:
        html = singles[0].read_text(encoding="utf-8")
        html = re.sub(
            r'<script>\nwindow\.__DATA_VERSION__ = .*\nwindow\.__DATA__ = .*\n'
            r'window\.__TEACHERS__ = .*\n</script>',
            '<script src="data.js"></script>', html, count=1)
        paths.MASTER.write_text(html, encoding="utf-8")
        print(f"[修復] 已從單檔 {singles[0]} 重建母檔 → {paths.MASTER}")
        return

    print("[失敗] 找不到 live/index.html 或任何單檔可還原。")
    print("       請用 git 還原：git checkout template/代課查詢_發布.html")


HELP = """
─────────────────────────────────────────────
 使用說明
─────────────────────────────────────────────
 平常改資料給老師看（最常用）：
   1. 編輯 versions/<目前版本>/全校課表_長表.csv
   2. 回選單按 [2] → 重生 data.js 並發布
   → nginx 網址立刻變新資料，HTML 不用動。

 自己手機 / 想要單一檔：
   按 [3] → versions/<版本>/代課查詢_單檔.html
   這個檔自我包含，斷網雙擊也能用。

 換學期、拿到新 PDF：
   1. 新 PDF 命名 全校課表.pdf 放進 source/
   2. 按 [1]，輸入新版本（如 115-1），一條龍跑完並發布。

 改網頁外觀 / 文字：
   只編輯 template/代課查詢_發布.html（瀏覽器可直接預覽），
   改完按 [5] 部署到 live/，再按 [3] 重產單檔。

 網頁不見了怎麼辦：
   live 的 index.html 不見 → 按 [5] 用母檔重建。
   連 template 母檔也不見 → 按 [6] 從 live 或單檔重建母檔，
   或用 git 還原 template/代課查詢_發布.html。
─────────────────────────────────────────────
"""


def show_menu():
    vers = "、".join(paths.list_versions()) or "（無）"
    cur = paths.current_version() or "（未設定）"
    print(f"""
═════════════════════════════════════════════
  尋找調代課小幫手 — 更新工具
  目前版本：{cur}　已有版本：{vers}
═════════════════════════════════════════════
  [1] 新學期完整更新（PDF → data.js → 單檔 → 發布）
  [2] 微調 CSV 後重生 data.js 並發布（nginx 立即更新）
  [3] 只產單檔 HTML（自己手機 / email）
  [4] 分類確認表，人工檢查
  [5] 重新產生 live 網頁 index.html（改完 UI、或 live 的 html 不見了時）
  [6] 修復母檔（連 template 母檔都不見時用）
  [H] 使用說明      [0] 離開
═════════════════════════════════════════════""")
    if not paths.PDF.exists():
        print("  ⚠ 尚未偵測到 source/全校課表.pdf（選 1 前請先放好）")
    if not paths.MASTER.exists():
        print("  ⚠ 母檔 template/代課查詢_發布.html 不見了，請按 [6] 修復")
    elif not paths.LIVE_INDEX.exists():
        print("  ⚠ live/index.html 不存在，請按 [5] 重新產生")


def main():
    while True:
        show_menu()
        choice = input("請輸入選項：").strip().lower()

        if choice == "1":
            if not extract_ready():
                continue
            if not paths.PDF.exists():
                print("[停止] 請先把新學期 PDF 命名為「全校課表.pdf」放進 source/ 再選 1。")
                continue
            version = prompt_version()
            if not version:
                print("[停止] 請輸入版本。")
                continue
            if paths.csv_path(version).exists():
                ans = input(f"⚠ 版本 {version} 已存在，重新抽取會覆蓋它的 CSV。確定覆蓋？(y/N) ")
                if ans.strip().lower() != "y":
                    print("已取消。")
                    continue
            if run("extract_school.py", "--version", version) and \
               run("build_data.py", "--version", version):
                run("build_single.py", "--version", version)
                publish(version)
        elif choice == "2":
            version = prompt_version()
            if version and run("build_data.py", "--version", version):
                publish(version)
        elif choice == "3":
            version = prompt_version()
            if version:
                run("build_single.py", "--version", version)
        elif choice == "4":
            if not extract_ready():
                continue
            run("audit_categories.py", "--version", prompt_version())
        elif choice == "5":
            deploy_ui()
        elif choice == "6":
            repair_master()
        elif choice == "h":
            print(HELP)
        elif choice == "0":
            print("再見！")
            return
        else:
            print("[?] 沒有這個選項，請重新輸入。")


if __name__ == "__main__":
    main()
