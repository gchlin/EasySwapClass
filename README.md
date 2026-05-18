# 課表分析

114 學年第 2 學期教師課表的數位化、查詢、代課工具集。
**自然科版**（16 位老師、人工 OCR + pdfplumber 校對）與 **全校版**（130 位老師、pdfplumber 直接抽取）並存。

> 需求演進與設計決策記錄：[DEVLOG.md](DEVLOG.md)

## 版本控制與隱私

這個 repository 只追蹤「程式、操作說明、維護知識」，不追蹤實際課表資料。

### 會上傳到 GitHub

- `README.md`、`DEVLOG.md`、`維護說明.md`
- `.gitignore`
- `scripts/` 中不含真實課表資料的程式
- 不含課表資料的第三方靜態檔，例如 `school_wide/_html2canvas.min.js`

### 不會上傳到 GitHub

- `source/` 整個資料夾
- `natural_science/` 整個資料夾
- 專案內所有 `*.csv`
- `school_wide/*.md`、`school_wide/*.json`
- 產出的 `school_wide/*.html`
- 所有 v1 / v2 / v3 HTML 成果，因為 HTML 內已經嵌入完整課表資料
- `scripts/build_schedule.py`，因為目前內含自然科老師與課表資料

### 版本規劃

Git tag 用來記錄「程式版本」：

```powershell
git tag v1.0.0
git tag v1.1.0
git tag v2.0.0
```

課表資料版本留在本機或學校內部儲存空間，例如：

```text
private_data/
  114-2/
    source/
    natural_science/
    school_wide/
  115-1/
    source/
    natural_science/
    school_wide/
```

Git tag 記錄「哪一版程式」；私有資料夾記錄「哪一學期資料」。不要把產出的 HTML 放到公開 GitHub release，除非已確認裡面沒有任何私有課表資料。

第一次建立 Git repository 時：

```powershell
git init
git add .gitignore README.md DEVLOG.md 維護說明.md scripts school_wide/README.md school_wide/_html2canvas.min.js
git status
git commit -m "Initialize timetable tool repository"
```

建立 GitHub 空 repository 後再連線：

```powershell
git branch -M main
git remote add origin https://github.com/<account>/<repo>.git
git push -u origin main
```

每次 push 前先跑：

```powershell
git status --ignored
```

確認 PDF、CSV、產出報告、產出 HTML 都在 ignored 清單中。

## 資料夾

```
課表分析/
├── README.md
├── scripts/         # 程式；build_schedule.py 因含資料不上傳
├── sample_data/     # 匿名範例資料與測試 HTML（安全上傳）
├── source/          # 本機私有：原始 PDF，不上傳
├── natural_science/ # 本機私有：自然科資料與成果，不上傳
└── school_wide/     # 本機私有成果；只允許少數無資料檔案上傳
```

## 系統概覽

兩條獨立資料流，共用 `extract_v2.py` 的解析規則。

### 自然科流程（gold standard，人工校對）

```
source/課表.pdf
   │
   │  [scripts/extract_v2.py]   pdfplumber 結構化抽取
   ▼
natural_science/課表_v2.csv ─► 與 課表_長表.csv 比對 (v2_diff.md)
   │
   │  （課表_長表.csv 是手動微調過的真相來源）
   ▼
natural_science/課表_長表.csv
   │
   ├─ [scripts/build_schedule.py] ─► 8 個 MD 視圖（校對統計、實驗室使用、各科時段表…）
   │
   └─ [scripts/build_web.py]      ─► natural_science/代課查詢.html
```

### 全校流程（pdfplumber 直接輸出）

```
source/全校課表.pdf
   │
   │  [scripts/extract_school.py]  重用 extract_v2 的 parse_cell
   ▼
school_wide/全校課表_長表.csv  （含「教師類別」欄：IB教師 / 普通班教師）
   │
   └─ [scripts/build_web_school.py] ─► school_wide/代課查詢_全校.html
```

## 檔案說明

### 腳本 [scripts/](scripts/)

| 檔案 | 用途 | 何時跑 |
|------|------|--------|
| [extract_v2.py](scripts/extract_v2.py) | 自然科 PDF → CSV，pdfplumber 結構化抽取 + 後處理 | 拿到新自然科 PDF 時 |
| [extract_school.py](scripts/extract_school.py) | 全校 PDF → CSV + 抽取報告 | 拿到新全校 PDF 時 |
| [build_schedule.py](scripts/build_schedule.py) | 自然科 RAW 內嵌資料 → 主 CSV + 8 個 MD 視圖 | 修改自然科資料／視圖時 |
| [build_web.py](scripts/build_web.py) | 自然科 CSV → 代課查詢.html | 自然科資料更新後 |
| [build_web_school.py](scripts/build_web_school.py) | 全校 CSV → 代課查詢_全校.html | 全校資料更新後 |
| [audit_categories.py](scripts/audit_categories.py) | 全校 CSV → 分類確認表.md（IB/導師/科目歸類審查） | 想驗證分類是否合理時 |
| [build_strokes.py](scripts/build_strokes.py) | 從 Unicode Unihan 抽教師姓名漢字筆劃 → `_strokes.json`（給 build_web_school 排序用） | 教師名單變動時（首次下載 Unihan.zip 8MB，後續離線可重跑） |
| [_gen_sample.py](scripts/_gen_sample.py) | 將 `sample_data/全校課表_長表_sample.csv` 的 TEACHERS/DATA 注入 `sample_data/調代課小幫手(sample_data)_v3.1.html`（只更新資料，不覆蓋 UI 程式碼） | 範例資料改動後 |
| _html2canvas.min.js | html2canvas 函式庫（截圖功能用，內嵌進 HTML） | 升級時手動下載 `cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js` |

### 來源 `source/`（本機私有，不上傳）

| 檔案 | 內容 |
|------|------|
| [課表.pdf](source/課表.pdf) | 自然科原始 PDF（16 頁） |
| [全校課表.pdf](source/全校課表.pdf) | 全校原始 PDF（130 頁） |

### 自然科 `natural_science/`（本機私有，不上傳）

| 檔案 | 內容 |
|------|------|
| [課表_長表.csv](natural_science/課表_長表.csv) | **主資料**，long format 229 筆 |
| [課表_v2.csv](natural_science/課表_v2.csv) | pdfplumber 抽取結果（驗證主資料用） |
| [v2_diff.md](natural_science/v2_diff.md) | v1 vs v2 比對報告 |
| [代課查詢.html](natural_science/代課查詢.html) | 互動式代課/調課查詢網頁（單檔離線、手機友善） |
| [校對統計.md](natural_science/校對統計.md) | 5 種交叉驗證表 |
| [簡化課表_視覺核對.md](natural_science/簡化課表_視覺核對.md) | 16 位老師個人 5×7 簡化版 |
| [自然科時段表.md](natural_science/自然科時段表.md) | 全 16 位老師合併視圖 |
| [物理科時段表.md](natural_science/物理科時段表.md) ／ [化學科時段表.md](natural_science/化學科時段表.md) ／ [生物科時段表.md](natural_science/生物科時段表.md) ／ [地球科學科時段表.md](natural_science/地球科學科時段表.md) | 各科代課查詢 |
| [實驗室使用.md](natural_science/實驗室使用.md) | 實驗室排程：依教室分組 / IPSS / 熱力圖 / 各實驗室 5×7 |
| [各實驗室課表.md](natural_science/各實驗室課表.md) ／ [.docx](natural_science/各實驗室課表.docx) | 實驗室使用 Section D 抽出獨立檔 |

### 全校 `school_wide/`（部分本機私有，不上傳）

| 檔案 | 內容 |
|------|------|
| [全校課表_長表.csv](school_wide/全校課表_長表.csv) | pdfplumber 抽取的全校課表，含四個衍生欄：主授科目（國/英/數/自/社/藝/體/特/其他，由代號 prefix 強制；A 例外沿用課程分類）、**細科目**（物/化/生/地科、史/地理/公民、音樂/美術/家政/資訊…約 30 種，給「同細科」UI 子排序用）、教師類別（IB／普通班）、導師班級 |
| [分類確認表.md](school_wide/分類確認表.md) | 自動產出的人工審查表（IB 教師、班級導師、IB 課程、領域課程、自主課程、各科目實際課程列表） |
| [全校_extraction_report.md](school_wide/全校_extraction_report.md) | 抽取報告（成功率、教室統計） |
| [全校_領域時間.md](school_wide/全校_領域時間.md) | 領域時間時段（已從主表移除，另存） |
| [代課查詢_全校.html](school_wide/代課查詢_全校.html) | 全校版互動式代課/調課網頁 |

## UI 功能與範例資料維護

### 兩個 HTML，兩種用途

| 檔案 | 用途 | 資料來源 | 是否上傳 GitHub |
|------|------|----------|-----------------|
| `sample_data/調代課小幫手(sample_data)_v3.1.html` | UI 開發測試、功能展示 | 匿名範例 CSV（20 人） | ✓ 安全上傳 |
| `school_wide/代課查詢_全校.html` | 學校實際使用 | 全校真實 CSV（130 人） | ✗ 含隱私，不上傳 |

### 分離維護的原因

`build_web_school.py` 從 CSV **重新生成整個 HTML**，包含 JS 邏輯。
`_gen_sample.py` 只用 regex 替換 `const DATA = [...]` 和 `const TEACHERS = [...]` 兩行，其餘 HTML 完全不動。

因此：

- **新手引導遮罩（tour overlay）** 與 **空堂承諾模式** 等 UI 功能，**直接在 `sample_data/` 的 HTML 裡維護**。開發完成、測試通過後，再手動將對應程式碼貼入 `build_web_school.py` 的 HTML 樣板區段，下次重生 `school_wide/` 主 HTML 時就會帶入。
- `_gen_sample.py` 可以隨時重跑，**不會覆蓋 UI 功能程式碼**。
- `build_web_school.py` 重跑會完全重生 `school_wide/` HTML；若 UI 功能尚未移植過去，重生後那些功能就消失。

### 更新範例資料

```powershell
# 修改 sample_data/全校課表_長表_sample.csv 後：
python scripts/_gen_sample.py
# → 只更新 sample HTML 的 TEACHERS / DATA，UI 功能不受影響
```

### 更新正式 HTML（school_wide）

```powershell
python scripts/extract_school.py    # 有新 PDF 時才跑；否則直接從下一步
python scripts/build_web_school.py  # CSV → school_wide/代課查詢_全校.html
```

---

## 怎麼跑

從專案根目錄執行：

```bash
# 自然科
python scripts/build_schedule.py    # → CSV + 8 個 MD
python scripts/build_web.py         # → 代課查詢.html

# 全校
python scripts/extract_school.py    # → 全校課表_長表.csv + 報告
python scripts/build_web_school.py  # → 代課查詢_全校.html
```

從新 PDF 抽取自然科並驗證：

```bash
python scripts/extract_v2.py        # → 課表_v2.csv + v2_diff.md
```

如果 v2_diff 顯示有未知錯誤，看 `## 系統性差異分析` 段落，依規則加進 [extract_v2.py](scripts/extract_v2.py) 的 `COURSE_RENAMES` 或 `parse_cell` 函式。

## 工作流程與注意事項

CSV 是單一資料源；`代課查詢*.html` 一律由 `build_web*.py` 從 CSV 重新生成。**檢查資料只看 CSV 即可**，HTML 不需要另外校對。

### 日常使用

```
發現 CSV 有錯
  ↓
直接編輯 CSV
  ↓
python scripts/build_web_school.py     # 或 build_web.py
  ↓
HTML 同步更新，完成
```

### PDF 重新發行（換學期、課表大改）

```
python scripts/extract_school.py        # 重抽 CSV（教師類別、主授科目同時重算）
python scripts/build_web_school.py      # 重生 HTML
```

### 兩個陷阱要避開

| 操作順序 | 結果 |
|----------|------|
| 改 CSV → 跑 `build_web_school.py` | ✓ 安全 |
| 改 CSV → 跑 `extract_school.py` | ✗ **手動修正全部被覆蓋**。extract_school 會重抽 PDF 並用內建分類器重算 |
| 想系統性改變分類規則（譬如未來馬汝強都歸 數） | 改 `scripts/extract_school.py` 的 `classify_course_subject()`，重跑 extract |
| 想單筆覆蓋（譬如只有馬汝強要改 數） | 改 CSV 即可，但別再跑 extract |

### 設定型修改 vs 資料修改

不是所有規則都在 CSV 裡，有些藏在 .py 程式裡：

| 規則 | 位置 | 改動方式 |
|------|------|----------|
| 主授科目分類字典 | `scripts/extract_school.py` 的 `classify_course_subject()`（A 族群用） | 改 .py |
| 教師代號 prefix → 主授（其他族群用） | `scripts/extract_school.py` 的 `PREFIX_TO_SUBJECT` | 改 .py |
| 教師類別（IB/普通班）判斷 | `scripts/extract_school.py` 的 `IB_COURSE_PATTERNS` + `A_GROUP_IB_TEACHERS` | 改 .py |
| HTML 內 IB 課程偵測（決定走 4 階優先順序） | `scripts/build_web_school.py` 的 `IB_PATTERNS` | 改 .py |
| 連堂課判斷（探究／IPSS） | `scripts/build_web_school.py` 的 `isInquiryCourse()` JS | 改 .py |

「資料」型修改（單一老師主授不對、單筆教室寫錯）→ 改 CSV。
「規則」型修改（要把 BMSL 分到自不分到社、要把 ESS 也算 IB）→ 改 .py 重 extract。

## 自然科 vs 全校：兩個代課網頁的差異

| 項目 | 自然科版 | 全校版 |
|------|----------|---------|
| 來源 CSV | `課表_長表.csv`（含 主授科目／職務） | `全校課表_長表.csv`（含 主授科目／教師類別） |
| 老師數 | 16 | 130 |
| 候選分組 | 同科（物/化/生/地科） / 自然科其他 | 同科 → **同班** → 其他科（國/英/自/數/社/藝/體/特 拆組）；IB 課程例外 5 階優先；同科群組內**同細科**（如同為物理）排在前面並標 ★；群組內排序：該班導師 → 同細科 → **姓名筆劃 小→大** → 教師代號 |
| 老師選單 | 純 `<select>` | `<datalist>` 支援姓名 + 教師代號搜尋 |
| 連堂判斷 | 探究、IPSS | 同上 |
| UI 顯示 IB 標籤 | n/a | 否（避免階級觀感；內部仍用於 IB 候選分群） |
| 班級導師標記 | n/a | 任一群組內若是該班導師，姓名後加 `（導師）` 紅字並排在群組首位 |

## 修自然科課表資料

主資料嵌在 [scripts/build_schedule.py](scripts/build_schedule.py) 的 `RAW = [...]` 列表裡。

```python
RAW = [
    ("N01", 1, 1, "選修物理", "308", "T1409"),
    #  教師 星期 節次  課程     班級   教室
    ...
]
```

修改後跑 `python scripts/build_schedule.py && python scripts/build_web.py` 重生所有衍生檔。

## pdfplumber 抽取規則

直接讀 PDF 內部的「向量文字 + 繪圖指令」，不用 OCR。
對「電腦輸出的有邊框 PDF」幾乎 100% 準確。

### 後處理規則（在 [scripts/extract_v2.py](scripts/extract_v2.py)）

| 類型 | 問題 | 處理規則 |
|------|------|----------|
| 字型缺字 | `物理-探?`（「究」字 PDF 缺字） | `COURSE_RENAMES` 直接 mapping |
| 結尾括號截斷 | `T2106(ES` 沒有 `)` | 偵測 `^[A-Z]\d+\([A-Za-z]+$` 自動補回 |
| 多行課程名 | `選修地球科學` + `-大氣、海洋?` 換行 | 累積非「班級樣態」的行為課名延續 |

判斷規則：
- **班級樣態**：開頭數字（308、211A）或開頭「共計」（共計5班）
- **教室樣態**：T / A / S 開頭+數字、IB 開頭
- 都不是 → 視為課名延續

## 部署網頁

兩個 HTML 都是純靜態，**只需 1 個檔案**：

- 單獨上傳到 GitHub Pages、任何 Web Host、Google Drive 等
- 或直接 email/LINE 給同事，雙擊本地開啟也能用

不需 server、不需相依，所有資料嵌入在 HTML 中。

## 為什麼是這個架構

設計取捨：
- **資料嵌入 HTML 而非 fetch CSV**：要讓 HTML 雙擊就能離線開（fetch 在 file:// 被 CORS 擋）
- **build pipeline (Python)**：100+ 筆資料手抄不可能，CSV 變動時自動重生 HTML
- **CSV 為單一資料源**：所有 MD 視圖、HTML 都從這裡衍生，不會 drift
- **自然科與全校分離**：自然科有人工校對的 gold standard 與專屬視圖；全校以 pdfplumber 直接輸出，工具集較精簡
