# src/config.py
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 專案根目錄：以本檔案位置往上推算，避免依賴「執行程式時所在的工作目錄」而找錯路徑
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> dict:
    # 讀取 config/settings.yaml 的可調參數（路徑、九宮格切分比例等）
    # 依 CLAUDE.md 規範，這些會變動的一般數值不寫死在程式碼中，統一從這裡讀取
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    with open(settings_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env() -> None:
    # 讀取 .env 內的機密參數（如資料庫帳密）。本次「輸出成文件」的步驟用不到，
    # 但先備妥給後續 Phase 1 寫入 MySQL 的程式使用，避免每個腳本各自處理一次
    load_dotenv(PROJECT_ROOT / ".env")


def resolve_path(relative_path: str) -> Path:
    # 把 settings.yaml 中的相對路徑轉成絕對路徑
    return PROJECT_ROOT / relative_path
