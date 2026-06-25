# 尋找調代課小幫手（全校版）

全校 130 位老師課表的數位化、查詢、代課工具集。v2 架構採「資料與 UI 分離」：UI 只維護一份母檔 `代課查詢_發布.html`；課表資料獨立產出為 `data.js`，每次換學期或微調只需重生資料，HTML 一字不改。

> 需求演進與設計決策記錄：[DEVLOG.md](DEVLOG.md)
> 維護者操作手冊（非技術友善）：[維護說明.md](維護說明.md)

---

## 版本控制與隱私

這個 repository 只追蹤「程式、操作說明、維護知識」，不追蹤實際課表資料。

### 會上傳到 GitHub

- `README.md`、`DEVLOG.md`、`維護說明.md`
- `.gitignore`
- `scripts/`（含 `scripts/_legacy/`）
- `代課查詢_發布.html`（UI 母檔，不含實際課表資料）
- `assets/_html2canvas.min.js`（唯一例外上傳的 assets 檔）
- `docs/產品說明_代課查詢_全校.html`

### 不會上傳到 GitHub

- `source/`（原始 PDF，私有）
- `versions/`（所有學期 CSV、data.js、報告、單檔 HTML，私有）
- `live/`（nginx 服務目錄，含真實資料，私有）
- `assets/`（除 `_html2canvas.min.js` 外，私有）— 含 `_strokes.json`、`_unihan_irg.txt`、`_current_version.txt`
- 所有 `*.csv`
- `Analysis/`（授課節數 / 勞務分析輸出，私有）
- `docs/_help_demo.html`（含真實姓名，私有）

真實課表資料（CSV、含資料的 HTML、報告）一律留本機 / 內網，不進公開 GitHub。

每次 push 前先跑：

```powershell
git status --ignored
```

確認 PDF、CSV、版本資料夾、live/ 都在 ignored 清單中。

---

## 資料夾結構

```
Switch_time/
├── 代課查詢_發布.html      UI 母檔：唯一手改 UI 的檔（可進 git）。
│                           內含 <script src="data.js"> 引用；
│                           單獨開（無 data.js）會顯示「請放 data.js」提示。
│                           標題與確認視窗用 window.__DATA_VERSION__ 動態顯示版本。
├── 更新課表.bat            雙擊入口 → 跑 scripts/menu.py
├── README.md / DEVLOG.md / 維護說明.md / .gitignore
├── scripts/
│   ├── paths.py            集中所有路徑與「目前版本」邏輯（改版面只動這檔）
│   ├── extract_school.py   PDF → versions/<版本>/全校課表_長表.csv + 報告 + 領域時間.json
│   │                       參數：--version、--ryu-only（只重產領域時間，不動 CSV）
│   ├── extract_v2.py       PDF 解析底層，被 extract_school 引用（需保留）
│   ├── build_data.py       CSV → versions/<版本>/data.js
│   │                       （含 window.__DATA_VERSION__/__DATA__/__TEACHERS__）
│   │                       參數：--version
│   ├── build_single.py     母檔 + CSV → versions/<版本>/代課查詢_單檔.html
│   │                       （資料內嵌、自我包含）；參數：--version
│   ├── audit_categories.py CSV + 領域時間.json → versions/<版本>/分類確認表.md
│   │                       （含「9. 各科領域時間」一節）；參數：--version
│   ├── build_strokes.py    Unicode Unihan → assets/_strokes.json
│   │                       （一次性，教師名單變動才重跑）
│   ├── menu.py             互動選單；負責呼叫各腳本 + 發布到 live/
│   ├── analyze_workload.py / analyze_workload_114.py
│   ├── build_viz.py / build_viz_114.py
│   │                       授課節數 / 勞務分析（輸出 Analysis/，已 gitignore）
│   └── _legacy/            已退役封存：
│                             build_web_school.py（舊整頁生成器）
│                             build_web.py（自然科版，停止維護）
│                             _gen_sample.py（範例 HTML 注入）
│                             _inject_tour.py（新手引導注入）
├── source/                 輸入 PDF：全校課表.pdf（私有，不上傳）
├── versions/<版本>/        該版真相 CSV + 所有產出 + 報告
│                           （如 versions/114-2/；私有，不上傳）
├── live/                   nginx 服務這裡：
│                             index.html（= 母檔複本）
│                             data.js（= 目前版本資料）
│                           （私有，不上傳）
├── assets/                 跨版共用：
│                             _strokes.json（私有）
│                             _html2canvas.min.js（可上傳）
│                             _unihan_irg.txt（私有）
│                             _current_version.txt（私有）
└── docs/                   產品說明_代課查詢_全校.html（可上傳）
                            _help_demo.html（含真實姓名，本機不上傳）
```

---

## 系統概覽：資料流

```
source/全校課表.pdf
   │
   │  [scripts/extract_school.py --version 114-2]
   │  pdfplumber 抽取 + 分類規則
   ▼
versions/114-2/全校課表_長表.csv   ← 單一真相來源
   │
   ├─ [scripts/build_data.py --version 114-2]
   │   ▼
   │  versions/114-2/data.js
   │   │
   │   │  [menu 發布]
   │   ▼
   │  live/data.js   ← nginx 服務（URL 穩定、永遠最新）
   │
   └─ [scripts/build_single.py --version 114-2]
       ▼
      versions/114-2/代課查詢_單檔.html  ← 自我包含，離線雙擊可用

代課查詢_發布.html（母檔，手動維護 UI）
   │
   │  [menu 發布 / 選單 [5]]
   ▼
live/index.html   ← 執行時引用同層的 live/data.js
```

### 兩條並存發布路徑

| 路徑 | 用途 | 特性 |
|------|------|------|
| (A) `versions/<版本>/代課查詢_單檔.html` | 自己手機 / email / 離線雙擊 | 資料內嵌、自我包含、不需網路 |
| (B) `live/`（HTML + data.js） | 內網 nginx 給老師用網址 | URL 永遠穩定、最新資料、內網無隱私顧慮 |

### 版本管理

- 版本字串（如 `114-2`、`115-1`）= 版本資料夾名 = 頁面顯示版本。
- 目前版本記在 `assets/_current_version.txt`，由選單 [1] / [2] 自動更新。
- 同一版本重跑 = 覆蓋（選項 [1] 重抽 CSV 時會先詢問確認）。
- 要保留舊版本就使用不同版本字串（舊資料夾不會被刪）。

---

## 檔案地圖

### scripts/（腳本）

| 檔案 | 用途 | 是否上傳 |
|------|------|----------|
| `paths.py` | 集中所有路徑與「目前版本」邏輯；改版面只動這一個檔 | ✓ |
| `menu.py` | 互動選單（雙擊 更新課表.bat 進入）；呼叫各腳本 + 發布到 live/ | ✓ |
| `extract_school.py` | 全校 PDF → CSV + 抽取報告 + 領域時間.json；含分類規則 | ✓ |
| `extract_v2.py` | PDF 解析底層（parse_cell 等），被 extract_school 引用；需保留 | ✓ |
| `build_data.py` | CSV → data.js（含 `__DATA_VERSION__`、`__DATA__`、`__TEACHERS__`） | ✓ |
| `build_single.py` | 母檔 + CSV → 單檔 HTML（資料內嵌）；適合自己手機 / email | ✓ |
| `audit_categories.py` | CSV + 領域時間.json → 分類確認表.md（人工審查用） | ✓ |
| `build_strokes.py` | Unicode Unihan → assets/_strokes.json（一次性；首次下載 8 MB） | ✓ |
| `analyze_workload.py` / `analyze_workload_114.py` | 授課節數 / 勞務分析，輸出 Analysis/ | ✓ |
| `build_viz.py` / `build_viz_114.py` | 視覺化分析（輸出 Analysis/，已 gitignore） | ✓ |
| `_legacy/build_web_school.py` | 已退役：舊全校整頁生成器（已封存） | ✓（_legacy） |
| `_legacy/build_web.py` | 已退役：自然科版流程（停止維護，已封存） | ✓（_legacy） |
| `_legacy/_gen_sample.py` | 已退役：範例 HTML 注入工具（已封存） | ✓（_legacy） |
| `_legacy/_inject_tour.py` | 已退役：新手引導注入（已封存） | ✓（_legacy） |

### 根目錄與其他

| 路徑 | 用途 | 是否上傳 |
|------|------|----------|
| `代課查詢_發布.html` | UI 母檔；唯一手改 UI 的檔 | ✓ |
| `更新課表.bat` | 雙擊入口，呼叫 menu.py | ✓ |
| `source/全校課表.pdf` | 原始 PDF（私有） | ✗ |
| `versions/<版本>/全校課表_長表.csv` | 單一真相 CSV（私有） | ✗ |
| `versions/<版本>/data.js` | 該版資料 JS（私有） | ✗ |
| `versions/<版本>/代課查詢_單檔.html` | 單檔成品（含課表資料，私有） | ✗ |
| `versions/<版本>/全校_extraction_report.md` | PDF 抽取健檢報告（私有） | ✗ |
| `versions/<版本>/全校_領域時間.md` | 領域時間獨立列表（私有） | ✗ |
| `versions/<版本>/領域時間.json` | 結構化領域時間，供 audit 用（私有） | ✗ |
| `versions/<版本>/分類確認表.md` | 人工審查表（私有） | ✗ |
| `live/index.html` | nginx 服務的 HTML（= 母檔複本，私有） | ✗ |
| `live/data.js` | nginx 服務的資料（= 目前版本，私有） | ✗ |
| `assets/_strokes.json` | 姓名筆劃對照（build_strokes 產出，私有） | ✗ |
| `assets/_html2canvas.min.js` | 截圖函式庫（唯一例外上傳） | ✓ |
| `assets/_unihan_irg.txt` | Unihan 快取（私有） | ✗ |
| `assets/_current_version.txt` | 目前版本記錄（私有） | ✗ |
| `Analysis/` | 授課節數 / 勞務分析輸出（私有） | ✗ |
| `docs/產品說明_代課查詢_全校.html` | 產品說明（可上傳） | ✓ |
| `docs/_help_demo.html` | 含真實姓名的說明（私有） | ✗ |

---

## 工作流程

### 互動選單（最常用的入口）

雙擊 `更新課表.bat` 進入選單：

```
[1] 新學期完整更新（PDF → data.js → 單檔 → 發布）
[2] 微調 CSV 後重生 data.js 並發布（nginx 立即更新）
[3] 只產單檔 HTML（自己手機 / email）
[4] 分類確認表，人工檢查
[5] 把母檔重新部署到 live/（改完 UI 後用）
[H] 使用說明      [0] 離開
```

### 各場景對應選項

| 場景 | 做法 |
|------|------|
| 改幾筆 CSV 資料，更新給老師看 | 編輯 `versions/<版本>/全校課表_長表.csv` → 選單 [2] |
| 要產單檔給自己手機 / email | 選單 [3] |
| 換學期、拿到新 PDF | 新 PDF 命名 `全校課表.pdf` 放 `source/` → 選單 [1] 輸入新版本 |
| 改 UI 外觀 / 文字 | 只編輯 `代課查詢_發布.html` → 選單 [5] 部署 → [3] 重產單檔 |
| 人工確認分類正確性 | 選單 [4] → 看 `versions/<版本>/分類確認表.md` |

### 指令行對照（手動執行）

```powershell
# 從 PDF 重新抽取（新學期）
python scripts/extract_school.py --version 115-1

# 從 CSV 重生 data.js（微調後）
python scripts/build_data.py --version 114-2

# 產單檔 HTML
python scripts/build_single.py --version 114-2

# 產分類確認表
python scripts/audit_categories.py --version 114-2

# 建立筆劃表（僅教師名單變動時需要；首次下載 Unihan.zip 約 8 MB）
python scripts/build_strokes.py
```

### 陷阱：改 CSV 後絕對不要再跑 extract_school

| 操作順序 | 結果 |
|----------|------|
| 改 CSV → 跑 `build_data.py` | ✓ 安全，手動修正保留 |
| 改 CSV → 跑 `extract_school.py` | ✗ **手動修正全部被覆蓋**；extract 會從 PDF 重抽並用規則重算 |

「資料型」修改（單筆教室寫錯、單一老師主授不對）→ 改 CSV。
「規則型」修改（要把某代號族群整批改科目）→ 改 `scripts/extract_school.py`，重跑 extract。

---

## 設定規則位置

不是所有規則都在 CSV 裡，有些在 .py 裡：

| 規則 | 位置 |
|------|------|
| 代號 prefix → 主授科目（PREFIX_TO_SUBJECT） | `scripts/extract_school.py` |
| 課程名稱 → 主授科目分類（classify_course_subject） | `scripts/extract_school.py` |
| 課程名稱 → 細科目（classify_course_detail） | `scripts/extract_school.py` |
| 教師類別（IB / 普通班）判斷 | `scripts/extract_school.py` |
| 領域時間偵測（course == "領域時間"） | `scripts/extract_school.py` |
| JS 端 IB 課程偵測（決定走幾階優先順序） | `代課查詢_發布.html` 的 `isIbCourse()`（課名不含中文＝IB） |
| JS 端連堂課偵測（探究 / IPSS） | `代課查詢_發布.html` 的 `isInquiryCourse()` |

---

## 為什麼是這個架構

設計取捨：

- **資料與 UI 分離**：UI 只維護 `代課查詢_發布.html` 一份；更新資料只重生 `data.js`，HTML 一字不改。避免舊架構「整頁重生器」在 UI 功能改版後要同步兩份程式碼的問題。
- **CSV 為單一真相來源**：所有產出（data.js、單檔 HTML、分類確認表）都從 CSV 衍生，不會資料漂移。
- **兩條並存發布路徑**：(A) 單檔 HTML 供自己手機 / 離線使用；(B) live/ 供內網給老師用穩定網址。
- **data.js 引用而非資料嵌入母檔**：母檔可在瀏覽器直接預覽（無 data.js 時顯示提示），開發體驗好；發布到 live/ 時引用同層 data.js，資料與 UI 可獨立更新。
- **版本資料夾歸檔**：同一版本重跑覆蓋；要保留舊版本換不同版本字串即可，不做序號編號。
- **姓名筆劃排序**：build_strokes.py 從 Unicode Unihan 抽 kTotalStrokes，一次性離線快取；候選排序鍵：該班導師 → 同細科 → 姓名筆劃（小→大）→ 教師代號。
- **退役自然科版**：自然科版（build_web.py、natural_science/）已停止維護；全校版工具集取代其角色。相關腳本移入 `scripts/_legacy/` 保留備查。

---

## 環境 / 相依

- **Python 3.10+**
- **pdfplumber**（僅 `extract_school.py` 用到；選單 [2] / [3] 不需要）：

```powershell
pip install pdfplumber
```

- `build_strokes.py` 只在教師名單變動時跑一次（首次下載 Unihan.zip 約 8 MB）。

---

## pdfplumber 抽取原理

直接讀 PDF 內部的「向量文字 + 繪圖指令」，不用 OCR。對「電腦輸出的有邊框 PDF」幾乎 100% 準確。

### 後處理規則（在 `scripts/extract_v2.py`）

| 類型 | 問題 | 處理規則 |
|------|------|----------|
| 字型缺字 | `物理-探?`（「究」字 PDF 缺字） | `COURSE_RENAMES` 直接 mapping |
| 結尾括號截斷 | `T2106(ES` 沒有 `)` | 偵測 `^[A-Z]\d+\([A-Za-z]+$` 自動補回 |
| 多行課程名 | `選修地球科學` + `-大氣、海洋?` 換行 | 累積非「班級樣態」的行為課名延續 |

判斷規則：
- **班級樣態**：開頭數字（308、211A）或開頭「共計」
- **教室樣態**：T / A / S 開頭 + 數字、IB 開頭
- 都不是 → 視為課名延續

---

## nginx 部署

nginx 服務路徑：`Switch_time/live/index.html`（舊版為 `school_wide/index.html`，已一次性切換）。

之後 URL 永遠穩定。每次選單發布後，`live/index.html` 與 `live/data.js` 會自動更新，nginx 立即反映，不需改 `nginx.conf`。
