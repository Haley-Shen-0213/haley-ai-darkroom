<!-- CHANGELOG.md -->

# 異動紀錄

本檔案記錄專案版本間的實際異動內容。時間戳記為台北時區（UTC+8），精確到分鐘；若同一檔案在同一開發階段內經過多次修改，時間戳記取該檔案最後一次修改的時間。

## [0.1.0] - 2026-07-22（初始版本）

### 新增

- **19:37** 初始化專案：`README.md` 佔位、`.gitignore` 套用 Python 專案樣板
- **20:04** 建立圖片資料目錄骨架：`data/images/reference/{basic,intermediate,advanced}`、`data/images/pending`、`data/images/completed`（各目錄以 `.gitkeep` 保留結構）
- **20:11** 新增 `data/images/IMAGE_DATA_GUIDE.md`：圖片目錄用途、參考檔案三級分類（使用者主觀手動分級）、完成檔案評分改記錄於資料庫等說明
- **20:23** 新增 `.env.example`（機密參數欄位範本，數值留空）與本機 `.env`；MySQL 連線參數（`DB_HOST`／`DB_PORT`／`DB_NAME`／`DB_USER`／`DB_PASSWORD`）
- **20:30～20:35** 新增 `src/config.py`（讀取 `config/settings.yaml` 與 `.env` 的共用工具）；更新 `.gitignore`，排除圖片二進位檔與分析輸出目錄內容
- **20:43** 完成 `CLAUDE.md` 專案守則：檔頭路徑註解、繁體中文設計註解、參數抽離（`.env`／YAML）、檔名唯一性、時區（Asia/Taipei）等規則
- **20:54** 新增 `config/settings.yaml`：圖片路徑參數、九宮格切分比例（中央格 25/50/25 起始值）、色相區間分析參數（8 色相區間邊界、飽和度門檻）
- **20:57** 新增 `src/image_metadata.py`：對應 Phase 1「①圖片基本資料分析」——尺寸／長寬比分類、自行實作 RGB→HSL 向量化轉換、整體色相／飽和度／明度／對比統計（色相採循環平均）、仿 Lightroom HSL 面板的 8 色相區間分析、前 5 主色、EXIF 擷取（含非印刷字元清洗）
- **21:11** 新增 `requirements.txt`（Pillow、numpy、PyYAML、python-dotenv、insightface、onnxruntime、opencv-python、rembg）
- **21:14～21:17** 新增 `src/face_detection.py`（InsightFace buffalo_l：人臉 bbox／面積占比／信心分數）、`src/subject_detection.py`（rembg isnet-general-use：主體 bbox／面積占比，取最大連通前景區域）、`src/run_image_analysis.py`（整合①②並輸出 `data/analysis_output/image_analysis_preview.md`，18 張參考圖片實測通過）
- **21:19** 完成 `docs/roadmap.md`：Phase 1～6 技術文件與時程規劃、九宮格切分比例設計（含 Tatler 2007／Judd et al. 2009 中央偏誤研究依據）、技術棧選型與實測結果
- **21:28** 新增 `README.md`（專案說明、目前進度、環境設定與執行方式）、`CHANGELOG.md`（本檔案）

### 修正

- `src/image_metadata.py`：修正色相區間統計的循環平均（circular mean）錯誤——原本用算術平均計算「紅色」區間（橫跨 345°→360°→0°→15°）的平均色相，導致算出錯誤的 153° 而非正確的接近 0°
- `src/image_metadata.py`：修正 EXIF 擷取時未過濾非印刷字元（含 NUL byte）的問題，避免個別相機/後製軟體寫入的損毀 EXIF 資料污染輸出文件

## 尚未完成／待開發項目清單

- **Phase 1**
  - ③九宮格分析尚未實作（②已有主體 bbox 資料，可接續進行）
  - ④分析結果尚未寫入 MySQL（僅輸出 Markdown 文件供人工檢視）
  - 人臉／主體偵測結果的視覺化核對頁面（在圖片上疊加不同顏色標示框，供人工評分準確度）尚未實作
  - `reference/` 三級（基本／中級／高級）目前僅為使用者主觀手動分級，無量化標準
  - `.env` 的 MySQL 實際連線資訊尚未填入
  - onnxruntime 目前僅裝 CPU 版本，未評估 GPU（onnxruntime-gpu）加速的必要性
- **Phase 2～6**：人臉辨識比對、修圖必要性與裁切建議、參數自動調整建議、評分系統與風格學習、系統整合與資料庫完善，均尚未開始
