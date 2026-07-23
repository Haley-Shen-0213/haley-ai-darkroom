<!-- CHANGELOG.md -->

# 異動紀錄

本檔案記錄專案版本間的實際異動內容。時間戳記為台北時區（UTC+8），精確到分鐘；若同一檔案在同一開發階段內經過多次修改，時間戳記取該檔案最後一次修改的時間。

## [0.3.0] - 2026-07-23

### 新增

- **18:40** 新增 `src/rename_reference_files.py`：把 `data/images/reference/{basic,intermediate,advanced}` 底下的檔案統一改名為「資料夾_流水號」格式（例如 `advanced_001.jpg`），方便日後跨 CSV／檔案總管快速對應圖片；依檔案 mtime 排序決定流水號先後、已改過名的檔案會跳過，可重複執行；原始檔名對照表寫入 `data/analysis_output/reference_rename_mapping.csv`；已執行過一次，29 個檔案（basic 5／intermediate 12／advanced 12）全部重新命名完成
- **18:54** 新增 `src/detection_review_server.py`：人臉／主體偵測結果的視覺化核對頁面，本機小型網頁伺服器（Python 內建 `http.server`，不引入 Flask 等額外依賴），瀏覽器開啟後逐張顯示疊了偵測框的圖片（人臉框紅色、主體框天藍色，顏色見 `config/settings.yaml`），人臉框與主體框分開評分（不準確／普通／準確），評分結果即時寫入 `data/analysis_output/detection_accuracy_review.csv`；人臉／主體偵測結果快取到 `data/analysis_output/detection_cache.json`（用檔案 mtime＋大小判斷是否過期），避免每次重啟伺服器都要重跑一次模型；已在 29 張參考圖片上實測，並由使用者實際操作完成一輪評分（人臉框 1 張不準確／2 張普通／26 張準確，主體框 1 張不準確／28 張準確）

### 修正

- **18:54** `src/detection_review_server.py`：疊圖標籤文字（如「主體 50.0%」）原本用 PIL 預設字型繪製，不支援中文會顯示成方框亂碼，改用 Windows 內建的微軟正黑體（`msjh.ttc`）繪製中文標籤，找不到字型檔時退回預設字型

### 變更

- **19:18** 更新 `README.md`：目前進度表反映③九宮格分析與視覺化核對頁面已完成，目錄結構補上 `src/` 各腳本用途說明，新增「重新命名參考圖片」「偵測結果視覺化核對」兩節執行說明

## [0.2.0] - 2026-07-23

### 新增

- **18:21～18:24** 新增 `src/grid_analysis.py`：對應 Phase 1「③九宮格分析」，依 `config/settings.yaml` 的 `grid_analysis` 切分比例將圖片切成 3×3 共 9 格，計算各格平均明度／飽和度／主色／邊緣密度，並算出主體 bbox 落在第 5 格（中央格）的面積占比 `center_cell_subject_coverage`；亮度／飽和度／邊緣偵測皆先在整張圖算好再依格子邊界切片，避免先裁切再各自算 Canny 邊緣偵測，導致格子邊界附近因缺少鄰近像素上下文而產生假邊緣
- **18:22** 新增 `src/image_io.py`：把 `face_detection.py`／`subject_detection.py` 原本各自複製一份的 Windows 中文路徑讀圖 workaround（`imread_unicode`）抽成共用模組，`grid_analysis.py` 為第三個使用處
- **18:23** 更新 `src/run_image_analysis.py`：整合九宮格分析進批次流程與報告，總覽表新增「第5格主體占比」欄位，詳細區塊新增九宮格逐格明細表

### 變更

- **18:21** `config/settings.yaml`：`grid_analysis` 新增 `edge_detection`（Canny 邊緣偵測門檻值 `canny_threshold1`／`canny_threshold2`）
- **18:21～18:22** `src/image_metadata.py`：`rgb_to_hsl`、`dominant_colors` 由私有函式改為對外公開（拿掉底線前綴），供 `grid_analysis.py` 重用
- **18:22** `src/face_detection.py`、`src/subject_detection.py`：改用 `src/image_io.py` 的共用 `imread_unicode`，移除各自重複的實作；`face_detection.py` 同時移除因此變為未使用的 `cv2`／`numpy` import

### 修正

- **06:38** `CHANGELOG.md`：移除「尚未完成／待開發項目清單」段落，待辦事項統一移至 `docs/roadmap.md`，避免同一份待辦內容分散在兩個檔案、各自維護不同步
- **06:47** `CLAUDE.md`、`src/subject_detection.py`：修正硬體規格文件中 GPU VRAM 描述，從「約 4GB」更正為「約 8GB」，並放寬模型選型的保守假設描述

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
