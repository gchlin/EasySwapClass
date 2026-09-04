"""paths.py — 集中所有檔案路徑與「目前版本」邏輯。

v2 版面：產出依資料版本歸檔在 versions/<版本>/，nginx 服務固定的 live/，
共用資源放 assets/。其他腳本一律從這裡取路徑，改版面時只動這一個檔。

    Switch_time/
    ├── 代課查詢_發布.html      MASTER（UI 母檔）
    ├── source/                 輸入 PDF
    ├── versions/<版本>/        該版真相 CSV + 產出 + 報告
    ├── live/                   nginx 服務（index.html + data.js）
    └── assets/                 _strokes.json / _html2canvas.min.js / _unihan / 目前版本
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ROOT / "source"
VERSIONS = ROOT / "versions"
LIVE = ROOT / "live"
ASSETS = ROOT / "assets"

MASTER = ROOT / "template" / "代課查詢_發布.html"

# 共用資源（跨版穩定）
STROKES_JSON = ASSETS / "_strokes.json"
H2C_JS = ASSETS / "_html2canvas.min.js"
UNIHAN_CACHE = ASSETS / "_unihan_irg.txt"
CUR_FILE = ASSETS / "_current_version.txt"

# nginx 服務的固定位置
LIVE_INDEX = LIVE / "index.html"
LIVE_DATA = LIVE / "data.js"

# 來源 PDF（全校版）
PDF = SOURCE / "全校課表.pdf"


def current_version():
    """目前作業中的版本字串（如 "114-2"）；未設定回傳空字串。"""
    if CUR_FILE.exists():
        return CUR_FILE.read_text(encoding="utf-8").strip()
    return ""


def set_current_version(v):
    """記住目前版本（發布時由選單呼叫）。"""
    ASSETS.mkdir(parents=True, exist_ok=True)
    CUR_FILE.write_text(v.strip(), encoding="utf-8")


def vdir(version):
    """某版本的資料夾，並確保存在。"""
    d = VERSIONS / version
    d.mkdir(parents=True, exist_ok=True)
    return d


def csv_path(version):
    return vdir(version) / "全校課表_長表.csv"


def data_js_path(version):
    return vdir(version) / "data.js"


def single_path(version):
    return vdir(version) / "代課查詢_單檔.html"


def audit_path(version):
    return vdir(version) / "分類確認表.md"


def extraction_report_path(version):
    return vdir(version) / "全校_extraction_report.md"


def ryu_md_path(version):
    return vdir(version) / "全校_領域時間.md"


def ryu_json_path(version):
    return vdir(version) / "領域時間.json"


# 網頁下拉選單會列出的科目。主授科目不在這個集合裡的老師，網頁上會整個漏掉，
# 所以 extract_school 會出聲警告、menu 會互動詢問。改這裡要同步改
# template/代課查詢_發布.html 的 DROPDOWN_ORDER。
UI_SUBJECTS = ["國", "英", "自", "數", "社", "藝", "體", "特", "二外", "本土語"]


def subject_fix_path(version):
    """人工指定的主授科目修正表（{教師代碼: 科目}）。

    課名判斷不出科別時（例如只排彈性課、或課名是學校內部縮寫），
    由維護者在 更新課表.bat 的選單裡指定，存在這裡下次自動沿用。"""
    return vdir(version) / "科別修正.json"


def teachers_json_path(version):
    """完整教師名冊（134 位，來源＝PDF 每頁表頭，不是 CSV 反推）。

    有老師全學期只排領域時間（如 115-1 的 N28），這種人在 CSV 裡是零筆，
    若名冊從 CSV 反推就會整個人消失。名冊獨立出檔才不會漏。"""
    return vdir(version) / "teachers.json"


def list_versions():
    """已存在的版本資料夾名稱（排序）。"""
    if not VERSIONS.exists():
        return []
    return sorted(d.name for d in VERSIONS.iterdir() if d.is_dir())
