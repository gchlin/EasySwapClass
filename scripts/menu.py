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
  [7] 指定判不出科別的老師（他們在網頁選單上會漏掉）
  [5] 重新產生 live 網頁 index.html（改完 UI、或 live 的 html 不見了時）
  [6] 修復母檔（從 live/index.html 或最新單檔重建 template 母檔）
"""
import csv
import importlib.util
import json
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


# ── 判不出科別的老師：互動指定 ───────────────────────────────
# 課名判斷不出科別的老師（只排彈性課、或課名是學校內部縮寫），主授科目會是
# 「其他」；網頁下拉選單只列 paths.UI_SUBJECTS 裡的科目，這種老師整個人會消失。
# 這裡讓維護者逐位指定，存進 versions/<版本>/科別修正.json，之後自動沿用。

def unknown_subject_teachers(version):
    """回傳 [(代碼, 姓名, 目前科目)]；沒有 teachers.json 時回空清單。"""
    tj = paths.teachers_json_path(version)
    if not tj.exists():
        return []
    roster = json.loads(tj.read_text(encoding="utf-8"))
    ok = set(paths.UI_SUBJECTS)
    return [(t["code"], t.get("name", ""), t.get("subject", ""))
            for t in roster if t.get("subject") not in ok]


def _courses_of(version, code, limit=4):
    """該老師的課程名稱，指定科目時當判斷依據。"""
    csv_p = paths.csv_path(version)
    if not csv_p.exists():
        return ""
    names = []
    with open(csv_p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["教師代碼"] == code and r["課程名稱"] not in names:
                names.append(r["課程名稱"])
    if not names:
        return "（這學期沒有排課，可能只有會議／領域時間）"
    return "、".join(names[:limit]) + ("…" if len(names) > limit else "")


def ask_subjects(version):
    """逐位詢問判不出科別的老師，寫入 科別修正.json。回傳是否有新增指定。"""
    unknown = unknown_subject_teachers(version)
    if not unknown:
        print("[OK] 所有老師都判得出科別，不需要指定。")
        return False

    fix_p = paths.subject_fix_path(version)
    fixes = json.loads(fix_p.read_text(encoding="utf-8")) if fix_p.exists() else {}

    print("")
    print("─────────────────────────────────────────────")
    print(f" 有 {len(unknown)} 位老師的科別判不出來")
    print("─────────────────────────────────────────────")
    print(" 這通常是因為他們只排了會議／彈性課，或課名是校內縮寫。")
    print(" 不指定的話，他們在網頁的「我是誰」下拉選單裡會整個消失。")
    print("")
    print(f" 指定一次就會記住（存在 versions/{version}/科別修正.json），")
    print(" 之後重跑不用再問。直接 Enter 可以跳過，之後再按 [7] 補。")
    print("─────────────────────────────────────────────")

    opts = paths.UI_SUBJECTS
    menu_line = "  ".join(f"{i + 1}){x}" for i, x in enumerate(opts))
    changed = False
    for i, (code, name, cur) in enumerate(unknown, 1):
        print("")
        print(f" [{i}/{len(unknown)}] {code} {name}")
        print(f"       目前判定：{cur or '（空白）'}")
        print(f"       這學期的課：{_courses_of(version, code)}")
        print(f"       {menu_line}   (0 或 Enter = 跳過)")
        ans = input("       請選科目：").strip()
        if not ans or ans == "0":
            print("       → 跳過")
            continue
        pick = None
        if ans.isdigit() and 1 <= int(ans) <= len(opts):
            pick = opts[int(ans) - 1]
        elif ans in opts:
            pick = ans
        if not pick:
            print(f"       →「{ans}」不是有效選項，跳過")
            continue
        fixes[code] = pick
        changed = True
        print(f"       → 已指定為「{pick}」")

    if changed:
        fix_p.write_text(json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[已存檔] {fix_p}")
    else:
        print("\n[沒有變更] 沒有指定任何科目。")
    return changed


def apply_subject_fix(version):
    """把 科別修正.json 套進 teachers.json 與 CSV 的「主授科目」欄。

    刻意不重跑 extract_school——那會重讀 PDF、覆蓋手動修過的 CSV。
    這裡只改主授科目這一欄，其餘資料原封不動。
    （extract_school 自己跑的時候也會讀同一份修正表，兩條路徑結果一致。）
    """
    fix_p = paths.subject_fix_path(version)
    if not fix_p.exists():
        return False
    fixes = json.loads(fix_p.read_text(encoding="utf-8"))
    if not fixes:
        return False

    tj = paths.teachers_json_path(version)
    if tj.exists():
        roster = json.loads(tj.read_text(encoding="utf-8"))
        for t in roster:
            if t["code"] in fixes:
                t["subject"] = fixes[t["code"]]
        tj.write_text(json.dumps(roster, ensure_ascii=False, indent=1), encoding="utf-8")

    csv_p = paths.csv_path(version)
    if csv_p.exists():
        with open(csv_p, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        for r in rows:
            if r["教師代碼"] in fixes:
                r["主授科目"] = fixes[r["教師代碼"]]
        with open(csv_p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    print(f"[完成] 已套用 {len(fixes)} 筆科別修正")
    return True


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

 有老師在下拉選單裡找不到：
   通常是他的科別判不出來（只排會議／彈性課，或課名是校內縮寫）。
   按 [7] 逐位指定科目即可，指定一次就會記住，之後重跑不用再問。

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
            if not run("extract_school.py", "--version", version):
                continue
            # 判不出科別的老師會從網頁選單消失 → 趁這裡問清楚再往下走
            if unknown_subject_teachers(version) and ask_subjects(version):
                apply_subject_fix(version)
            if run("build_data.py", "--version", version):
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
        elif choice == "7":
            version = prompt_version()
            if not version:
                print("[停止] 請輸入版本。")
                continue
            if ask_subjects(version) and apply_subject_fix(version):
                if run("build_data.py", "--version", version):
                    run("build_single.py", "--version", version)
                    publish(version)
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
