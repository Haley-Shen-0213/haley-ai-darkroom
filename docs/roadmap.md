<!-- docs/roadmap.md -->

# haley-ai-darkroom 技術文件：專案推進時程規劃

> 本文件依 [CLAUDE.md](../CLAUDE.md) 規範撰寫，所有內容為繁體中文。此文件會隨專案進展持續更新，每次調整範圍或時程時應同步修訂。

## 1. 前提假設

| 項目 | 內容 |
|---|---|
| 開發人力 | 僅 Haley 一人，獨立開發 |
| 投入型態 | 業餘／副業，預估每週約 5～10 小時 |
| 資料庫 | MySQL |
| 開發機 | HALEYPC（i9-14900K / 128GB RAM / RTX 4060 4GB VRAM） |
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
- 用途：之後可分析「主體、人臉常落在哪個九宮格區塊」「不同構圖偏好下各區塊的色彩傾向」，作為修圖建議、裁切建議的判斷依據

**九宮格切分比例設計（重點：中央第 5 格需涵蓋大部分主體）**

先查了兩個攝影構圖界最常見的九宮格理論，兩者的切法都跟這次需求的方向相反，先說明清楚再給建議：

- **三分法（Rule of Thirds）**：長寬各切三等分（約 33.3% / 33.3% / 33.3%），中央格只占整體面積約 1/9。這是最基本的參考網格，但中央格明顯偏小。
- **黃金比例網格（Phi Grid）**：分割線落在約 38.2% 與 61.8% 處（即 38.2% / 23.6% / 38.2%），中央格反而**比三分法更小**（約 23.6% 的邊長）。這套理論的目的是刻意把主體推離中心，讓構圖更有張力，並非用來「涵蓋主體」。

也就是說，這兩套經典理論都是「構圖建議用的美學網格」，目的是引導拍攝者把主體擺在格線交叉點附近（偏離中心），跟這裡「分析用網格、第 5 格要涵蓋大部分主體」的目的是相反的，不能直接套用。

比較支持這次需求方向的，反而是視覺注意力研究中的「中央偏誤（center bias）」：Tatler (2007) 的眼動追蹤研究顯示，觀察者的視線落點有強烈的中央集中傾向，且此偏誤與畫面內容、拍攝構圖無關；Judd et al. (2009) 的視覺顯著性模型也發現，加入一個「以畫面中心為峰值的高斯分布」能大幅提升預測人眼會看向哪裡的準確度。這代表無論攝影師怎麼構圖，主體或視覺焦點本來就有很高機率落在畫面中央區域附近，這與「第 5 格要涵蓋大部分主體」的直覺是一致的。

**建議做法：不要照搬三分法或黃金比例的切法，改用「資料驅動」的方式決定切分比例**：
1. Phase 1 初期先用一組**可調的預設比例**起步：中央格邊長占比 50%（即長寬各切 25% / 50% / 25%），中央格面積約占整體 25%，明顯大於三分法與黃金比例網格，作為起始安全值
2. 待累積一批參考圖片與主體偵測結果後，實際統計「主體 bounding box 的邊長、面積分布」（依 3.2① 的長寬比分組分開統計），用統計出的百分位數（例如涵蓋 80% 主體所需的中央區域大小）反推每個長寬比群組各自的最佳切分比例
3. 三分法、黃金比例網格可以額外記錄一份對照欄位（供之後分析「哪些構圖偏好接近經典理論」用），但**主要拿來做主體涵蓋率判斷的網格，用第 2 步資料驅動出來的比例**，不是直接套書上的比例
4. 切分比例（中央格占比等）需寫入 `config/settings.yaml`，不要寫死在程式碼中，方便依統計結果隨時調整

> 參考來源：
> - [The Golden Ratio vs. The Rule of Thirds In Photography](https://skylum.com/blog/the-golden-ratio-vs-the-rule-of-thirds-in-photography)
> - [Golden Ratio Composition vs Rule of Thirds](https://expertphotography.com/golden-ratio-vs-rule-of-thirds)
> - [Golden ratio generator: phi grid and spiral overlays](https://gridmakerpro.com/tools/golden-ratio/)
> - Tatler, B.W. (2007). *The central fixation bias in scene viewing* — [Overt Fixations Reflect a Natural Central Bias](https://www.researchgate.net/publication/266158154_Overt_Fixations_Reflect_a_Natural_Central_Bias)
> - Judd et al. (2009) *Learning to Predict Where Humans Look* — 相關綜述見 [Center bias outperforms image salience but not semantics](https://pmc.ncbi.nlm.nih.gov/articles/PMC11149060/)

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
    analysis_model_version VARCHAR(50),     -- 記錄本次分析用的模型/演算法版本
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
| 主體偵測 | **rembg（isnet-general-use 模型）** 做顯著主體分割 | 原規劃是 SAM 或 U2-Net；實際評估後選 rembg 的 isnet-general-use：SAM 是通用分割工具，要另外處理「從多個候選遮罩挑出主體」的邏輯且對 4GB VRAM 較吃緊，isnet 直接輸出單一顯著度遮罩，更貼合「找出主體」這個具體需求。**已實作並測試**：`src/subject_detection.py`，實測單張推論僅約 0.4 秒（CPU） |
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
- `src/subject_detection.py`：對應「②主體」，改用 **rembg 的 isnet-general-use** 模型做顯著主體分割，取最大連通前景區域的 bbox／面積占比。原規劃寫的 SAM 是通用分割工具，還得額外處理「從多個候選遮罩挑出主體」的邏輯且對 4GB VRAM 較吃緊；isnet 直接輸出單一顯著度遮罩，更貼合「找出主體」這個具體需求，故改用此方案
- `src/run_image_analysis.py`（原 `run_basic_analysis.py`，隨功能擴充重新命名）：掃描 `data/images/` 底下所有圖片，執行①②分析後輸出至 `data/analysis_output/image_analysis_preview.md`

**實測結果**：目前 `data/images/` 下 18 張參考圖片（涵蓋 9:16、3:2、3:4 三種長寬比）全部跑過一輪，人臉偵測到 0～2 張不等、主體面積占比在 13%～50% 之間，數值皆合理。目前環境的 onnxruntime 只有 CPU 執行提供者（未裝 GPU 版本），全部跑完（含兩個模型第一次載入約 30 秒＋18 秒）總耗時約 56 秒，之後每張圖片實際推論約 1～2 秒，對離線批次分析而言可接受。

尚未開始：③九宮格分析（需要②的主體 bbox 結果才能判斷「中央格是否涵蓋主體」，現在資料齊了，可以接著做）、④寫入 MySQL。

---

## 4. Phase 2～6 概述（待 Phase 1 完成後細化）

- **Phase 2｜人臉辨識比對**：在 Phase 1 已有的人臉 bounding box 基礎上，加入人臉 embedding 比對，建立「已知人物」資料庫，讓系統能認出同一人出現在不同照片中。
- **Phase 3｜修圖必要性 + 裁切建議**：依 Phase 1 累積的九宮格與主體占比資料，訂出規則或簡易模型，判斷「是否需要修圖」與「建議裁切比例／構圖」。
- **Phase 4｜參數自動調整建議**：依色彩分析資料（亮度、飽和度、色溫等），對照理想範圍或使用者過去偏好，產出曝光、白平衡等調整建議。
- **Phase 5｜評分系統與風格學習**：需要先有「成品評分」的輸入管道（可能是使用者手動評分，或依修圖前後對比），再讓系統從高分作品中學習調色風格傾向。
- **Phase 6｜系統整合與資料庫完善**：把前面各階段串起來，補齊資料庫中仍缺的關聯與索引，視情況決定是否需要操作介面（CLI 工具即可，或要簡易 Web 介面）。

## 5. 待確認事項

- [x] 圖片存放路徑已建立：`data/images/{reference/{basic,intermediate,advanced}, pending, completed}`，詳見 `data/images/IMAGE_DATA_GUIDE.md`；路徑已抽離至 `config/settings.yaml`
- [x] `reference/` 三級（基本／中級／高級）為使用者主觀手動分級，非系統演算法評分；`completed/` 檔案的評分改以資料庫評分系統記錄（對應 Phase 5）
- [x] 參考圖片的取得方式：使用者會陸續手動放入對應等級資料夾，目前 `data/images/reference/advanced/` 已有 1 張（`S__57589785.jpg`），無固定張數或截止時間
- [x] 人臉／主體偵測模型選型：改以**準確度優先**，選定 InsightFace（RetinaFace+ArcFace）與 SAM/U2-Net，見 3.4 節；VRAM 若不足以跑最大版本，優先降模型版本、其次才降到 CPU 推論
- [x] 九宮格切分比例：不採用三分法／黃金比例（兩者中央格都偏小，與需求相反），改採「中央第 5 格需涵蓋大部分主體」的資料驅動設計，初始安全值為 25/50/25，待資料累積後依長寬比分組微調，見 3.2③ 節
- [ ] 九宮格資料驅動微調，需等 Phase 1 累積一定數量的參考／待處理圖片與主體偵測結果後才能實際統計出各長寬比分組的最佳比例
- [ ] MySQL 實際連線資訊（host／port／帳密）尚未填入，`.env` 已建立參數名稱但數值留空，待使用者自行填寫或提供
- [ ] InsightFace／SAM 等模型的實際 pip 套件安裝與跑通測試，尚未執行（僅完成技術選型，未寫程式碼）
