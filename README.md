# haley-ai-darkroom

一套 AI 輔助修圖／暗房系統。依據已建立的人臉資料自動辨識照片人物、判定人臉與主體範圍，並根據分析結果提供修圖／裁切建議、圖片參數自動調整建議，再依成品評分結果持續學習並優化調色風格。完整的人臉、主體、參數與評分紀錄都會存入資料庫。

- 資料庫：MySQL
- 詳細規劃與時程：[docs/roadmap.md](docs/roadmap.md)
- 開發規範（檔頭註解、繁中設計註解、參數抽離等）：[CLAUDE.md](CLAUDE.md)
- 版本異動紀錄：[CHANGELOG.md](CHANGELOG.md)

## 目前進度

專案分六大核心功能推進，目前實際開發順序（詳見 `docs/roadmap.md`）：

| Phase | 內容 | 狀態 |
|---|---|---|
| 1 | 圖片分析測試＋資料庫建立 | 進行中：①圖片基本資料分析、②人臉/主體偵測已完成；③九宮格分析、④寫入 MySQL 尚未開始 |
| 2 | 人臉辨識比對 | 未開始 |
| 3 | 修圖必要性＋裁切建議 | 未開始 |
| 4 | 參數自動調整建議 | 未開始 |
| 5 | 評分系統與風格學習 | 未開始 |
| 6 | 系統整合與資料庫完善 | 未開始 |

## 目錄結構

```
config/settings.yaml     # 可調整參數（路徑、九宮格切分比例、色相區間定義等）
.env.example             # 機密參數欄位範本（實際數值放 .env，不進版控）
data/images/              # 圖片資料（reference 三級／pending／completed，實際圖檔不進版控）
data/analysis_output/    # 分析結果輸出（不進版控，執行腳本後產生）
src/                      # 分析程式
docs/roadmap.md           # 技術文件與時程規劃
```

## 環境設定

採用現有系統 Python 環境（3.13.7），不使用虛擬環境。

```
pip install -r requirements.txt
cp .env.example .env   # 依需要填入 MySQL 連線資訊
```

## 執行分析

```
cd src
python run_image_analysis.py
```

會掃描 `data/images/` 底下所有圖片，執行①圖片基本資料分析（尺寸、色彩、HSL 色相區間）與②人臉／主體偵測，結果輸出至 `data/analysis_output/image_analysis_preview.md` 供人工檢視。
