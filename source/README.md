# source/ — 原始課表 PDF

本資料夾存放每學期的原始課表 PDF，供各 `scripts/extract_*.py` 讀取。

**這個資料夾的所有內容都被 `.gitignore` 排除，不會上傳到 GitHub。**

---

## 放什麼檔案

| 檔名 | 來源 | 供哪支腳本使用 |
|------|------|----------------|
| `全校課表.pdf` | 學校行政系統匯出的全校版課表 | `scripts/extract_school.py` |
| `課表.pdf` | 自然科版課表（人工 OCR 校對用） | `scripts/extract_v2.py` |

> 舊學期課表建議另存為 `全校課表_113-2.pdf` 等帶學期的名稱，避免覆蓋。

---

## PDF 格式要求

- **向量文字**（pdfplumber 可抽出文字），非掃描圖片
- 每頁 header 含「班級 導師」格式（供 `extract_homeroom_class()` 偵測導師班號）
- 教室代碼格式：`T/A/IB/S` 開頭（例如 `T101`、`IB04`、`S1304`）

---

## 新學期更新流程

1. 將新課表 PDF 放入本資料夾，命名為 `全校課表.pdf`
2. 執行資料抽取：
   ```powershell
   python scripts/extract_school.py
   ```
   → 產出 `school_wide/全校課表_長表.csv`

3. 執行分類審查（人工確認分類是否正確）：
   ```powershell
   python scripts/audit_categories.py
   ```
   → 產出 `school_wide/分類確認表.md`，開啟確認後再進下一步

4. 產生代課查詢網頁：
   ```powershell
   python scripts/build_web_school.py
   ```
   → 產出 `school_wide/全校代課查詢.html`，雙擊即可離線使用

> 詳細說明與常見問題見 [維護說明.md](../維護說明.md)

---

## 範例資料

`sample_data/` 資料夾（在專案根目錄，有上傳 GitHub）含有**匿名化的範例課表**，可用於：
- 測試腳本是否正常運作
- 了解 CSV 欄位結構
- 練習操作流程（不含真實課表資料）
