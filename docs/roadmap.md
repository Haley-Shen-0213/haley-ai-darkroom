<!-- docs/roadmap.md -->

# haley-ai-darkroom 技術文件：專案推進時程規劃

> 本文件依 [CLAUDE.md](../CLAUDE.md) 規範撰寫，所有內容為繁體中文。此文件會隨專案進展持續更新，每次調整範圍或時程時應同步修訂。

## 1. 前提假設

| 項目 | 內容 |
|---|---|
| 開發人力 | 僅 Haley 一人，獨立開發 |
| 投入型態 | 業餘／副業，預估每週約 5～10 小時 |
| 資料庫 | MySQL |
| 開發機 | HALEYPC（i9-14900K / 128GB RAM / RTX 4060 8GB VRAM） |
| Python 環境 | 直接使用現有系統環境（系統預設 Python 3.13.7），**不額外建立虛擬環境**（不使用 venv／poetry／conda） |
| 辨識準確度優先級 | 人臉／主體辨識以**最高準確度**為選型優先考量，速度與資源消耗為次要（見 3.4 節） |

因為是業餘、單人開發，時程估算採**保守抓法**，並以「先求資料與流程跑通，再談優化」為原則，避免一開始就陷入模型調校或介面美化的無底洞。

## 2. 整體階段總覽

專案原本規劃的六大核心功能，經討論後調整為以下推進順序：**先建立資料分析與資料庫基礎，之後的修圖建議、參數調整、風格學習，全部都要依賴這個基礎資料**，所以優先做這塊是合理的。

| 階段 | 內容 | 對應原始功能編號 | 粗估時數 | 粗估週數（業餘） |
|---|---|---|---:|---:|
| Phase 1 | 圖片分析測試 + 資料庫建立（本文件重點） | 2, 6（部分） | 35～55 小時 | 約 5～7 週 |
| Phase 2 | 人臉辨識比對 + 人物身份資料庫 | 1 | 20～35 小時 | 約 3～5 週 |
| Phase 3 | 修圖必要性判定 + 裁切格式建議 | 3 | 25～40 小時 | 約 4～6 週 |
| Phase 4 | 圖片參數自動調整建議 | 4 | 25～40 小時 | 約 4～6 週 |
| Phase 5 | 評分系統 + 風格學習優化 | 5 | 30～50 小時 | 約 5～8 週 |
| Phase 6 | 系統整合、資料庫完善、（視需要）操作介面 | 6（完整） | 20～35 小時 | 約 3～5 週 |

> Phase 2～6 的時數會依 Phase 1 實際跑出來的資料型態與難點做調整，目前僅為概估，等 Phase 1 完成後應回頭修正此表。

---

## 3. Phase 1 詳細規劃：圖片分析測試 + 資料庫建立

### 3.1 目標

匯入一批參考作品（既有的修圖成品／原始照片），針對每張圖片自動跑出以下四類分析資料，並完整寫入 MySQL，作為後續所有功能（修圖建議、參數調整、風格學習）的資料基礎。

### 3.2 分析內容拆解

**① 圖片基本資料分析**
- 檔案層級：檔案大小、格式、色彩深度、EXIF 基本資訊（拍攝參數若有）
- 尺寸層級：寬、高、長寬比（例如 3:2、4:3、1:1、16:9 等，需分類歸一化，因為實際像素比不會剛好整除）
- 色彩層級：整體平均亮度、對比度、飽和度、色溫傾向、主色調（dominant colors，建議取前 3～5 色）

**② 人臉、主體位置與占比**
- 人臉：偵測所有人臉的 bounding box（位置＋寬高），計算每張人臉面積占整體圖片面積的比例
- 主體：偵測主要拍攝主體範圍（可先以「顯著性偵測 / saliency detection」或現成的 object detection 模型抓最大前景物件作為起點，不必一開始就做到語意分割等級）
- 兩者都需記錄：中心點座標（正規化為 0～1，不受實際解析度影響）、占比、與圖片邊界的相對關係（是否置中、偏左右上下等）

**③ 九宮格分析**
- 依照 3.2① 已分類好的長寬比群組，將圖片等分為 3×3 共 9 個區塊
- 每個區塊需計算：平均亮度、平均飽和度、主色、邊緣密度（可作為「該區塊資訊量／是否為主體所在」的粗略指標）
- **第 5 格（中央格）主體占比**：需額外計算「②主體偵測結果的 bounding box 面積，有多少比例落在第 5 格範圍內」（= 主體 bbox 與第 5 格區域的重疊面積 ÷ 主體 bbox 總面積），這是驗證「中央格是否真的涵蓋大部分主體」這個設計目標是否達成的關鍵指標，之後每一份分析報告都要包含這個數字，不只是內部設計時的假設
- 用途：之後可分析「主體、人臉常落在哪個九宮格區塊」「不同構圖偏好下各區塊的色彩傾向」，作為修圖建議、裁切建議的判斷依據

**九宮格切分比例設計（重點：中央第 5 格需涵蓋大部分主體）**

先查了兩個攝影構圖界最常見的九宮格理論，兩者的切法都跟這次需求的方向相反，先說明清楚再給建議：

- **三分法（Rule of Thirds）**：長寬各切三等分（約 33.3% / 33.3% / 33.3%），中央格只占整體面積約 1/9。這是最基本的參考網格，但中央格明顯偏小。
- **黃金比例網格（Phi Grid）**：分割線落在約 38.2% 與 61.8% 處（即 38.2% / 23.6% / 38.2%），中央格反而**比三分法更小**（約 23.6% 的邊長）。這套理論的目的是刻意把主體推離中心，讓構圖更有張力，並非用來「涵蓋主體」。

也就是說，這兩套經典理論都是「構圖建議用的美學網格」，目的是引導拍攝者把主體擺在格線交叉點附近（偏離中心），跟這裡「分析用網格、第 5 格要涵蓋大部分主體」的目的是相反的，不能直接套用。

比較支持這次需求方向的，反而是視覺注意力研究中的「中央偏誤（center bias）」：Tatler (2007) 的眼動追蹤研究顯示，觀察者的視線落點有強烈的中央集中傾向，且此偏誤與畫面內容、拍攝構圖無關；Judd et al. (2009) 的視覺顯著性模型也發現，加入一個「以畫面中心為峰值的高斯分布」能大幅提升預測人眼會看向哪裡的準確度。這代表無論攝影師怎麼構圖，主體或視覺焦點本來就有很高機率落在畫面中央區域附近，這與「第 5 格要涵蓋大部分主體」的直覺是一致的。

**針對人像／全身拍攝的專屬構圖知識（比通用構圖理論更貼近本專案實際素材）**

上面兩套理論（三分法、黃金比例）是任何題材通用的美學構圖網格，不是針對人像設計的。考量到本專案實際參考照片以人像為主、且以全身為主要目標，另外查了人像／全身攝影專屬的構圖慣例，發現的數字對九宮格設計影響更大：

- **直式構圖是全身人像標準**：直式比例天生貼合人體站姿比例，這也對應到目前參考照片多為 3:4、9:16 直式的實況
- **頭部留白（headroom）**：慣例把眼睛放在畫面上方約 1/3 處，代表頭頂大約在畫面上緣往下 10~20% 位置，不會貼齊頂端
- **腳部留白（footroom）不能大於頭部留白**：業界慣例「頭頂上方留白 ≥ 腳下留白」，若腳下空間比頭頂還多，畫面會顯得侷促、留白浪費
- **絕對不能在關節處裁切**：膝蓋、手肘、頸部、腳踝等關節位置被裁掉會很不自然

把這些數字兜起來：頭頂約在畫面 10~20% 處，腳底通常落在 90~95% 附近，代表**全身人像主體在垂直方向上會占據畫面高度的 70~85%**——遠超過三分法的中央列（33%）、黃金比例的中央列（23.6%），甚至比原本設想的「中央格 50%」都大得多。這代表若以全身人像為主要分析對象，**光是放大中央那一格可能還不夠**，主體實際上會從中央格一路延伸到下方格子（因為腿部會延伸到接近畫面底部），單一「中央格」的概念可能無法完整涵蓋全身主體，九宮格的「涵蓋率」判斷可能需要看「中央欄＋中下欄」合計，而不只是第 5 格單一格子。

**建議做法：不要照搬三分法或黃金比例的切法，改用「資料驅動」的方式決定切分比例，且需分別驗證全身／半身等不同拍攝類型**：
1. Phase 1 初期先用一組**可調的預設比例**起步：中央格邊長占比 50%（即長寬各切 25% / 50% / 25%），中央格面積約占整體 25%，明顯大於三分法與黃金比例網格，作為起始安全值
2. 待累積一批參考圖片與主體偵測結果後，實際統計「主體 bounding box 的邊長、面積分布」（依 3.2① 的長寬比分組分開統計），用統計出的百分位數反推每個長寬比群組各自的最佳切分比例；**全身人像因主體垂直占比明顯偏高，統計時應留意「中央格是否足夠、或需要中央欄橫跨中列+下列」這個問題**，不要假設所有題材都適用同一種切法
3. 三分法、黃金比例網格可以額外記錄一份對照欄位（供之後分析「哪些構圖偏好接近經典理論」用），但**主要拿來做主體涵蓋率判斷的網格，用第 2 步資料驅動出來的比例**，不是直接套書上的比例
4. 切分比例（中央格占比等）需寫入 `config/settings.yaml`，不要寫死在程式碼中，方便依統計結果隨時調整

> 參考來源（通用構圖理論）：
> - [The Golden Ratio vs. The Rule of Thirds In Photography](https://skylum.com/blog/the-golden-ratio-vs-the-rule-of-thirds-in-photography)
> - [Golden Ratio Composition vs Rule of Thirds](https://expertphotography.com/golden-ratio-vs-rule-of-thirds)
> - [Golden ratio generator: phi grid and spiral overlays](https://gridmakerpro.com/tools/golden-ratio/)
> - Tatler, B.W. (2007). *The central fixation bias in scene viewing* — [Overt Fixations Reflect a Natural Central Bias](https://www.researchgate.net/publication/266158154_Overt_Fixations_Reflect_a_Natural_Central_Bias)
> - Judd et al. (2009) *Learning to Predict Where Humans Look* — 相關綜述見 [Center bias outperforms image salience but not semantics](https://pmc.ncbi.nlm.nih.gov/articles/PMC11149060/)
>
> 參考來源（人像／全身拍攝專屬）：
> - [Essential Tips to Frame and Compose Better Portraits - Fstoppers](https://fstoppers.com/portraits/essential-tips-frame-and-compose-better-portraits-686817)
> - [How to Shoot Full-Body Portraits: The Complete Guide - PhotoWorkout](https://www.photoworkout.com/make-full-body-portraits/)
> - [Headroom (photographic framing) - Wikipedia](https://en.wikipedia.org/wiki/Headroom_(photographic_framing))
> - [Foundations of Portrait Composition Part I: Framing Your Model - Zoner](https://learn.zoner.com/foundations-of-portrait-composition-part-i-framing-your-model/)
> - [Full Body Portrait Posing | 19 Secret Tips - PhotoWhoa](https://www.photowhoa.com/blog/full-body-portrait/)

**④ 完整數據紀錄**
- 上述①②③的結果需完整寫入資料庫，且要保留「原始量測值」與「正規化後的值」兩種，方便日後不同分析情境調用
- 需記錄分析當下所使用的演算法／模型版本（例如人臉偵測用哪個模型、哪個版本），避免日後模型更新後資料混雜、難以追溯

### 3.3 資料庫 Schema 草案（MySQL）

以下為初版草案，供後續實作時參考，正式建表時仍需依實際測試結果微調：

```sql
-- db/schema/001_phase1_core.sql
-- 說明：Phase 1 圖片分析所需的核心資料表，先求可用，欄位設計保留擴充彈性

-- 圖片基本資料表：對應「①圖片基本資料分析」
CREATE TABLE images (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(500) NOT NULL,        -- 圖片實體路徑，日後可能改存物件儲存位置
    file_size_bytes BIGINT,
    format VARCHAR(20),                     -- JPEG / PNG / RAW 等
    width_px INT,
    height_px INT,
    aspect_ratio_raw DECIMAL(10,6),         -- width/height 原始值
    aspect_ratio_group VARCHAR(20),         -- 歸一化後的分類，例如 '3:2'、'4:3'、'1:1'
    avg_brightness DECIMAL(6,3),
    avg_contrast DECIMAL(6,3),
    avg_saturation DECIMAL(6,3),
    color_temperature_k INT,                -- 估算色溫，允許為 NULL（非必然算得出）
    dominant_colors JSON,                   -- 存前 3~5 個主色的 RGB/HEX 陣列
    exif_json JSON,                         -- 原始 EXIF 資訊，結構不固定故用 JSON
    center_cell_subject_coverage DECIMAL(6,5),  -- 主體 bbox 落在九宮格第5格(中央格)的面積比例，見 3.2③
    analysis_model_version VARCHAR(50),     -- 記錄本次分析用的模型/演算法版本

    -- 評等相關欄位：見 3.7「評等機制設計」
    reference_level VARCHAR(20),            -- 'basic'/'intermediate'/'advanced'，僅參考檔案有值，來自匯入時的資料夾分類
    user_rating DECIMAL(4,2),               -- 使用者對 completed 圖片的評分，非參考檔案才會填
    rated_at DATETIME,                      -- 使用者評分的時間（台北時區）

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 人臉偵測結果：對應「②人臉、主體位置」的人臉部分
CREATE TABLE detected_faces (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    image_id BIGINT NOT NULL,
    bbox_x INT, bbox_y INT, bbox_w INT, bbox_h INT,   -- 原始像素座標
    center_x_norm DECIMAL(6,5),             -- 正規化中心點 X (0~1)
    center_y_norm DECIMAL(6,5),
    area_ratio DECIMAL(6,5),                -- 人臉面積 / 圖片面積
    confidence DECIMAL(5,4),
    person_id BIGINT NULL,                  -- 對應到 Phase 2 的人物身份表，Phase 1 階段可先留空
    model_version VARCHAR(50),
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
);

-- 主體偵測結果：對應「②人臉、主體位置」的主體部分
CREATE TABLE detected_subjects (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    image_id BIGINT NOT NULL,
    bbox_x INT, bbox_y INT, bbox_w INT, bbox_h INT,
    center_x_norm DECIMAL(6,5),
    center_y_norm DECIMAL(6,5),
    area_ratio DECIMAL(6,5),
    subject_type VARCHAR(50),               -- 目前先粗略分類，例如 'person' / 'object' / 'unknown'
    confidence DECIMAL(5,4),
    model_version VARCHAR(50),
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
);

-- 九宮格分析結果：對應「③九宮格分析」
CREATE TABLE grid_analysis (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    image_id BIGINT NOT NULL,
    grid_index TINYINT NOT NULL,            -- 1~9，左上到右下編號
    avg_brightness DECIMAL(6,3),
    avg_saturation DECIMAL(6,3),
    dominant_color VARCHAR(7),              -- HEX 色碼
    edge_density DECIMAL(6,4),              -- 邊緣密度，粗略反映該區塊資訊量
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    UNIQUE KEY uq_image_grid (image_id, grid_index)
);
```

> `person_id`、`subject_type` 等欄位是預留給 Phase 2、Phase 3 使用，Phase 1 階段先建表結構，不強求馬上填滿。

### 3.4 技術棧建議

> 使用者要求人臉／主體辨識準確度以最高為主，因此以下不再以「輕量、省資源」為第一考量，改以**準確度優先**，VRAM 限制以「可容忍較慢的批次處理速度」來緩解（Phase 1 是離線批次分析，不是即時系統，犧牲速度換準確度是合理取捨）。

| 用途 | 建議工具 | 原因 |
|---|---|---|
| 語言 | Python | 影像處理／CV 生態最完整，且開發機已裝 Python 3.13.7 |
| 影像基本處理 | OpenCV (`cv2`) | 業界標準，讀取、色彩空間轉換、邊緣偵測都直接可用 |
| 人臉偵測＋辨識 | **InsightFace**（buffalo_l：RetinaFace 偵測 + ArcFace 特徵嵌入） | 目前開源方案中準確度數一數二，RetinaFace 對小臉、側臉、遮擋的偵測能力明顯優於 mediapipe/dlib；ArcFace 的人臉嵌入也是 Phase 2 人臉比對辨識的主流高準確度選擇，兩者銜接一致。**已實作並測試**：`src/face_detection.py` |
| 主體偵測 | **rembg（isnet-general-use 模型）** 做顯著主體分割 | 原規劃是 SAM 或 U2-Net；實際評估後選 rembg 的 isnet-general-use：SAM 是通用分割工具，要另外處理「從多個候選遮罩挑出主體」的邏輯，isnet 直接輸出單一顯著度遮罩，更貼合「找出主體」這個具體需求。**已實作並測試**：`src/subject_detection.py`，實測單張推論僅約 0.4 秒（CPU） |
| 色彩分析 | OpenCV + numpy 手算統計值 | 不需額外框架，直接算直方圖、平均值即可。**已實作**：`src/image_metadata.py` |
| 資料庫存取 | `mysql-connector-python` 或 SQLAlchemy | 依團隊熟悉度選一即可，單人專案建議先用較輕量的 connector，日後有需要再導入 ORM |
| 參數管理 | `.env`（機密）＋ YAML（可調參數，如信心門檻、九宮格切法） | 依 CLAUDE.md 規範 |

> 準確度優先的取捨：InsightFace 與 isnet 都比先前建議的 mediapipe/dlib/YOLOv8n 更吃資源、推論較慢，但由於 Phase 1 是批次離線處理（不需要即時反應），這個取捨是合理的。**實測結果**：目前環境的 onnxruntime 只裝了 CPU 版本（未裝 onnxruntime-gpu），兩個模型都能在 CPU 上順利跑完 18 張測試圖片，沒有遇到 VRAM 不足的問題；若之後圖片量變大需要加速，可評估安裝 onnxruntime-gpu 搭配 CUDA。

### 3.5 完成定義（Definition of Done）

Phase 1 視為完成，需滿足：
1. 可批次匯入一個資料夾內的參考圖片
2. 每張圖片都能自動產出①②③三類分析結果，且無需人工介入
3. 所有結果正確寫入 MySQL 對應資料表，欄位無明顯遺漏或型別錯誤
4. 能針對至少一批真實參考圖（建議 20～50 張、涵蓋不同比例／構圖）跑過一輪，並人工抽查幾筆資料的正確性（例如人臉框、九宮格切法是否合理）
5. 分析流程與參數（門檻值等）已抽離至 YAML，機密資訊（DB 帳密）已抽離至 `.env`

### 3.6 目前進度：①②已完成最小可行腳本（尚未寫入 MySQL）

在正式寫入 MySQL 之前，先做一版**只輸出文件、不寫資料庫**的最小可行腳本，用來確認分析格式是否合理：

- `src/config.py`：讀取 `config/settings.yaml` 與 `.env`
- `src/image_metadata.py`：對應「①圖片基本資料分析」，計算檔案/尺寸/色彩層級資料，包含：
  - 整體平均色相／飽和度／明度／對比（自行實作 RGB→HSL 向量化轉換，色相平均值採循環平均 circular mean，避免橫跨 0/360 度時算術平均出錯）
  - 仿 Lightroom HSL 面板的 8 色相區間分析（紅/橘黃/黃/綠/水綠/藍/紫/洋紅），各區間的像素占比、平均色相/飽和度/明度
  - 前 5 個主色（dominant colors）、EXIF（含防止 NUL byte 等非印刷字元污染輸出的清洗）
- `src/face_detection.py`：對應「②人臉」，用 InsightFace（buffalo_l：RetinaFace 偵測＋ArcFace 辨識模型包）偵測人臉 bbox、面積占比、信心分數。目前僅取偵測結果，暫不輸出 512 維人臉特徵向量（embedding 是 Phase 2 人臉比對辨識才需要，資料庫表也還沒設計對應欄位）
- `src/subject_detection.py`：對應「②主體」，改用 **rembg 的 isnet-general-use** 模型做顯著主體分割，取最大連通前景區域的 bbox／面積占比。原規劃寫的 SAM 是通用分割工具，還得額外處理「從多個候選遮罩挑出主體」的邏輯；isnet 直接輸出單一顯著度遮罩，更貼合「找出主體」這個具體需求，故改用此方案
- `src/run_image_analysis.py`（原 `run_basic_analysis.py`，隨功能擴充重新命名）：掃描 `data/images/` 底下所有圖片，執行①②分析後輸出至 `data/analysis_output/image_analysis_preview.md`

**實測結果**：目前 `data/images/` 下 18 張參考圖片（涵蓋 9:16、3:2、3:4 三種長寬比）全部跑過一輪，人臉偵測到 0～2 張不等、主體面積占比在 13%～50% 之間，數值皆合理。目前環境的 onnxruntime 只有 CPU 執行提供者（未裝 GPU 版本），全部跑完（含兩個模型第一次載入約 30 秒＋18 秒）總耗時約 56 秒，之後每張圖片實際推論約 1～2 秒，對離線批次分析而言可接受。

- `src/grid_analysis.py`：對應「③九宮格分析」，依 3.2③ 節「中央格需涵蓋大部分主體」設計，把圖片依長寬比分組取得的切分比例（`config/settings.yaml` 的 `grid_analysis.default_split_ratio`／`per_aspect_ratio_group`）切成 3×3 共 9 格，每格計算平均明度／飽和度／主色／邊緣密度，並算出主體 bbox 落在第 5 格（中央格）的面積占比 `center_cell_subject_coverage`。亮度／飽和度／邊緣偵測皆先在整張圖算好再依格子邊界切片，避免裁切後單獨算 Canny 邊緣偵測在格子邊界產生假邊緣。`src/image_metadata.py` 的 `rgb_to_hsl`／`dominant_colors` 改為對外公開（拿掉底線前綴）供此模組重用；另外把 `face_detection.py`／`subject_detection.py` 重複各一份的 Windows 中文路徑讀圖 workaround 抽成共用的 `src/image_io.py`（`imread_unicode`）

**實測結果**：測試當下 29 張參考圖片（使用者手動持續放入 `reference/advanced/` 增加訓練量中，張數仍會持續變動，此為某次執行的快照）全部跑過九宮格分析，含 1 張 6000×4000 大解析度、9:16／3:2／3:4 多種長寬比，第 5 格主體占比落在 26.6%～60.2% 之間，人工抽查第 1 張與極端案例（9:16 直式、6000×4000 大圖）數值皆合理、報告總覽表與詳細表的第 5 格數字一致。

尚未開始：④寫入 MySQL。

**待辦註記（2026-07-22 21:35，已於 2026-07-23 定案，見 3.7 節）**：圖片分析報告未來要加上等級評分機制，設計已於 3.7 節確認。

### 3.7 評等機制設計（2026-07-23 定案）

圖片的「評等」分兩種來源，不是同一套邏輯：

1. **`reference/` 底下的參考檔案**：評等 = 匯入時所在的資料夾分類（`basic`／`intermediate`／`advanced`），使用者手動把圖片放進哪一級資料夾，那一級就是評等，**不需要另外的評分動作或介面**。對應 `images.reference_level` 欄位，匯入程式讀取檔案所在資料夾路徑即可寫入，不需人工再次輸入。
2. **其餘圖片（`pending/` → `completed/` 流程中的圖片）**：沒有資料夾分級可用，評等 = **使用者事後評分**，評分結果記錄到資料庫的 `images.user_rating`（＋`rated_at` 記錄評分時間，用台北時區）。這批評分之後會是 Phase 5「評分系統與風格學習」的主要資料來源。

**這對報告與資料庫的影響**：
- `image_analysis_preview.md` 之後對 `reference/` 圖片要顯示「所屬等級」（直接讀資料夾名稱），對 `completed/` 圖片則顯示「使用者評分」欄位（尚未評分則顯示「未評分」）
- MySQL `images` 表已在 3.3 節加入 `reference_level`、`user_rating`、`rated_at` 三個欄位（互斥使用：參考圖只填 `reference_level`，其餘圖片只填 `user_rating`/`rated_at`，兩者不會同時有值）
- 使用者評分介面本身怎麼做（CLI 輸入、還是後續的視覺化核對頁面一併加上評分功能）尚未設計，待①②③④跑通後再規劃

---

## 4. Phase 2～6 概述（待 Phase 1 完成後細化）

- **Phase 2｜人臉辨識比對**：在 Phase 1 已有的人臉 bounding box 基礎上，加入人臉 embedding 比對，建立「已知人物」資料庫，讓系統能認出同一人出現在不同照片中。
- **Phase 3｜修圖必要性 + 裁切建議**：依 Phase 1 累積的九宮格與主體占比資料，訂出規則或簡易模型，判斷「是否需要修圖」與「建議裁切比例／構圖」。
- **Phase 4｜參數自動調整建議**：依色彩分析資料（亮度、飽和度、色溫等），對照理想範圍或使用者過去偏好，產出曝光、白平衡等調整建議。
- **Phase 5｜評分系統與風格學習**：需要先有「成品評分」的輸入管道（`images.user_rating`，見 3.7 節），再讓系統從評分資料中學習調色風格傾向。技術路線與本機技術棧建議見 4.1 節。
- **Phase 6｜系統整合與資料庫完善**：把前面各階段串起來，補齊資料庫中仍缺的關聯與索引，視情況決定是否需要操作介面（CLI 工具即可，或要簡易 Web 介面）。

### 4.1 Phase 5 技術路線：不接 LLM API，改用本機古典機器學習

**為什麼不用 LLM API 當核心學習機制**：LLM 每次呼叫是無狀態的，不會因為累積了 N 筆評分就內化使用者偏好（除非每次都把全部歷史塞進 prompt，這既不是「訓練」也無法隨資料量增加而變準）；這裡要學的是「圖片特徵 → 調色參數／分數」的**數值迴歸問題**，LLM 不擅長穩定輸出精確數值。且評分資料量預期只有幾十到幾百筆，用本機古典 ML 已經足夠，還能離線跑、不必付 API 費用、結果可重現。

**建議的本機技術棧**：

| 環節 | 建議工具 | 說明 |
|---|---|---|
| 特徵輸入 | 沿用 Phase 1①②③已抽出的結構化特徵（色相區間、亮度/飽和度、人臉/主體占比、九宮格第 5 格占比等） | 不需要重新設計特徵，Phase 1 的分析結果直接當迴歸模型的輸入欄位 |
| （可選）語意特徵加值 | CLIP 之類的預訓練視覺 embedding，本機跑（不呼叫 API） | 若覺得純色彩統計不夠捕捉「風格」，可加這層；只是額外加分項，非必要，且需額外安裝 PyTorch 或找 ONNX 轉換版本以維持跟現有 onnxruntime 環境一致 |
| 學習/迴歸模型 | **LightGBM 或 XGBoost**（或更簡單的 scikit-learn `GradientBoostingRegressor`） | 純 CPU 運算、對小樣本表格資料效果好，i9-14900K 24 核心資源綽綽有餘，也不需要用到 GPU |
| 模型版本管理 | 存成檔案（`joblib`/`pickle`）到本機 `models/` 目錄，比照 Phase 1 的 `model_version` 做法記錄訓練時間與版本 | 方便追蹤模型是否越訓練越準，出問題可回滾舊版本 |
| 訓練觸發時機 | 不需即時訓練；累積一定新增評分數（例如每新增 10～20 筆）才重新訓練一次即可 | 訓練成本低（小樣本資料通常幾秒到幾十秒），沒必要每筆評分都重跑 |
| 冷啟動處理 | 評分數不足門檻值前，先用寫死的規則式建議（例如與歷史平均值比對），資料夠了才切換成模型預測 | 門檻值放 `config/settings.yaml`，不寫死在程式碼 |

### 4.2 精準的「為什麼」解釋機制：LLM 只做翻譯，不做判斷

使用者要求解釋要**精準**、不需要語氣風格化，因此明確排除「LLM 自己看照片憑感覺講評語」這種做法（容易產生講得好聽但不對應實際數據的內容，即幻覺），改採以下架構：

1. **判斷交給已訓練的迴歸模型**：4.1 節的 LightGBM/XGBoost 模型根據使用者實際評分學出來的權重，對每張照片給出分數
2. **用 SHAP（SHapley Additive exPlanations）算出精確歸因**：針對這張照片的分數，具體是被哪些特徵拉高或拉低、貢獻多少，數字直接來自模型內部計算，可追溯、非模型憑空生成。`shap` 套件對 LightGBM/XGBoost 有專門優化的 TreeExplainer，純本機運算，不需要額外 GPU 資源
3. **本地 LLM 的角色縮小為「翻譯」**：只負責把 SHAP 算出的數字翻成一句話（例如「這張分數偏低，主要是主體只有 60% 落在第5格，低於您高分作品平均的 85%」），**不負責自己判斷照片美不美**，避免脫離實際數據的自由發揮
4. **RAG（檢索增強）作為佐證，不是風格聯想**：把過去照片的 SHAP 特徵組合存進本機向量資料庫，解釋新照片時檢索「SHAP 特徵組合最相近的過去高分作品」附上當對照，一樣是精準可追溯的資訊
5. **不做語氣／說話風格微調**：使用者明確表示不需要，故不考慮用 LoRA/QLoRA 讓 LLM 講話像使用者本人；本機 LLM 部署工具建議 Ollama＋Qwen2.5 系列（中文能力佳），僅用於上述第 3 點的翻譯工作

### 4.3 連結美學理論的量化特徵（Computational Aesthetics）

要讓評分與解釋「連結美學理論」而非純粹統計數字，可以參考學術上「計算美學（Computational Aesthetics）」領域的做法——Datta et al. (2006) 的奠基性論文，就是把三分法、色彩協調、景深等美學概念轉換成可精確計算的數學特徵。以下 5 項建議加入的特徵，多數可以直接沿用 Phase 1 既有分析基礎，不需要重新蒐集資料：

| 特徵 | 計算方式 | 沿用現有基礎 |
|---|---|---|
| **色彩協調度** | Cohen-Or et al. (2006, SIGGRAPH)「調和樣板」演算法：色相圈上定義互補/類比/三角等標準協調樣板，比對照片色相分布與哪個樣板最吻合、吻合程度多少 | 直接用 `image_metadata.py` 已算好的 8 色相區間直方圖，零額外分析成本 |
| **構圖法則吻合度** | Datta et al. (2006)：人臉/主體 bbox 中心點到三分法／黃金比例網格交叉點的正規化距離，距離越小越貼近經典構圖 | 直接用 `face_detection.py`／`subject_detection.py` 已算出的 bbox |
| **色彩豐富度（Colorfulness）** | Hasler & Süsstrunk (2003) 封閉公式，從 RGB 通道統計值直接算出色彩鮮活程度 | 計算成本低，可與現有飽和度統計互補 |
| **視覺平衡／對稱** | 用③九宮格各格的亮度／邊緣密度，計算左右或對角的視覺重量是否平衡 | 需等③九宮格分析實作後才能算 |
| **主體與背景複雜度對比** | 比較主體遮罩內外的邊緣密度差異，數值越大代表主體從背景中「跳出來」的程度越高（類似淺景深效果） | 直接用 `subject_detection.py` 已算出的主體遮罩 |

這些特徵會跟既有的色相/亮度等原始統計值一起，變成迴歸模型的輸入欄位；如此一來 4.2 節的 SHAP 解釋就能講出「色彩協調度貢獻 +0.3」「構圖偏離三分法交叉點較遠，貢獻 -0.2」這類話——同時具備美學理論的命名、又是模型精確算出的歸因，不是 LLM 自行判斷或美化的說法。

> 參考來源：
> - Datta, R. et al. (2006). *Studying Aesthetics in Photographic Images Using a Computational Approach* — [ResearchGate](https://www.researchgate.net/publication/221304720_Studying_Aesthetics_in_Photographic_Images_Using_a_Computational_Approach)
> - Cohen-Or, D. et al. (2006). *Color Harmonization*, ACM SIGGRAPH / TOG 25(3) — [PDF](https://igl.ethz.ch/projects/color-harmonization/harmonization.pdf)
> - Nishiyama, M. et al. *Aesthetic quality classification of photographs based on color harmony* — [ResearchGate](https://www.researchgate.net/publication/221361802_Aesthetic_quality_classification_of_photographs_based_on_color_harmony)
> - Hasler, D. & Süsstrunk, S. (2003). *Measuring colourfulness in natural images*

### 4.4 待討論註記：「AI 攝影助理」範例（2026-07-23，使用者提供，待展開討論）

使用者提出一個編號「2. AI 攝影助理」的概念範例，尚未展開細談，先原樣記錄：

> 系統分析照片後，LLM 產出自然語言建議：
> 「這張照片的主體位於畫面偏左下方，接近三分線交點。不過背景右上角有高亮干擾物，會分散注意力。建議降低高光、裁切右側 8%，並增加主體局部對比。」
>
> 這種就很適合 LLM。

初步觀察（不代表定案，待後續討論）：這個範例同時包含「客觀分析陳述」（主體位置、背景干擾物）與「具體建議」（降高光、裁切比例、局部對比），性質上跟 4.2 節「LLM 只做翻譯不做判斷」的原則一致——如果「背景干擾物偵測」「裁切比例建議」等判斷本身也能量化（例如干擾物用顯著度/邊緣密度找出主體以外的高亮區域、裁切比例用既有的九宮格與構圖法則吻合度資料反推），一樣可以讓 LLM 只負責把這些量化判斷轉成一段通順的說明，維持精準的原則。使用者提到這是編號「2.」的項目，暗示可能還有其他編號項目尚未提供，之後有空再繼續討論、確認完整清單與各項目的設計方向。

- [x] 圖片存放路徑已建立：`data/images/{reference/{basic,intermediate,advanced}, pending, completed}`，詳見 `data/images/IMAGE_DATA_GUIDE.md`；路徑已抽離至 `config/settings.yaml`
- [x] 評等機制已定案：`reference/` 三級＝匯入時的資料夾分類（使用者手動分級，無需另外評分）；`completed/` 圖片＝使用者事後評分，記錄到 `images.user_rating`（見 3.7 節）
- [x] 參考圖片的取得方式：使用者會陸續手動放入對應等級資料夾，持續累積中（無固定張數或截止時間）
- [x] 人臉／主體偵測模型選型與安裝測試：InsightFace（buffalo_l：RetinaFace+ArcFace）與 rembg（isnet-general-use，取代原規劃的 SAM）皆已安裝並在 18 張參考圖片上測試通過，見 3.4／3.6 節
- [x] 九宮格切分比例：不採用三分法／黃金比例（兩者中央格都偏小，與需求相反），改採「中央第 5 格需涵蓋大部分主體」的資料驅動設計，初始安全值為 25/50/25，並已補充人像/全身拍攝專屬構圖知識，待資料累積後依長寬比分組微調，見 3.2③ 節
- [x] ③九宮格分析已實作（含第 5 格主體占比 `center_cell_subject_coverage`），見 3.6 節；`src/grid_analysis.py`，已在 29 張參考圖片上測試通過
- [ ] ④分析結果尚未寫入 MySQL（`images` 表 schema 已就緒，含評等與第 5 格占比欄位，尚未實作寫入程式）
- [ ] 九宮格資料驅動微調，需等 Phase 1 累積一定數量的參考／待處理圖片與主體偵測結果後才能實際統計出各長寬比分組的最佳比例
- [x] 人臉／主體偵測結果的視覺化核對頁面已實作：`src/detection_review_server.py`（本機小型網頁伺服器，`http.server` 標準庫，無額外依賴），人臉框（紅）／主體框（天藍）疊圖＋主體占比文字標示，人臉框與主體框分開評分（不準確／普通／準確，對應 0~30%／30~60%／60~100%），評分寫入 `data/analysis_output/detection_accuracy_review.csv`；配套完成 `src/rename_reference_files.py`，把 `data/images/reference/{basic,intermediate,advanced}` 底下檔案統一改名為「資料夾_流水號」（例如 `advanced_001.jpg`），方便跨 CSV／檔案總管對應，並保留原檔名對照表 `data/analysis_output/reference_rename_mapping.csv`；已在 29 張參考圖片上實測，使用者已實際使用過一輪（人臉框 1 張不準確／2 張普通／26 張準確，主體框 1 張不準確／28 張準確）
- [ ] 使用者評分（`user_rating`）的實際操作介面尚未設計（CLI 輸入？還是併入視覺化核對頁面？）——注意這跟上面「偵測準確度評分」CSV 是兩件不同的事：`user_rating` 是完成品照片的**美學評分**（3.7 節，供 Phase 5 風格學習用），`detection_accuracy_review.csv` 是**偵測框準不準**的人工核對（供這裡的模型/門檻值調校參考），兩者資料表與用途都不同，不要混用
- [ ] 既有的人臉／主體偵測 bbox（含這次的視覺化核對頁面）都沒有套用 EXIF 方向校正，若照片 EXIF 標記需要旋轉，算出的座標會跟人眼看到的實際畫面方向不一致；核對頁面因為是疊圖顯示、跟偵測用的是同一份原始像素座標，暫時不影響核對本身，但要留意這是全流程共通的既有限制
- [ ] MySQL 實際連線資訊（host／port／帳密）尚未填入，`.env` 已建立參數名稱但數值留空，待使用者自行填寫或提供
- [ ] onnxruntime 目前僅裝 CPU 版本，未評估 GPU（onnxruntime-gpu）加速的必要性
