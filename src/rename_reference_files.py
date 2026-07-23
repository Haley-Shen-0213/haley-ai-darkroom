# src/rename_reference_files.py
import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import load_settings, resolve_path
from image_metadata import SUPPORTED_EXTENSIONS

LOCAL_TIMEZONE = ZoneInfo("Asia/Taipei")

# 已重新命名過的檔案會符合這個樣式（例如 advanced_001.jpg），重跑時用來判斷「這張已經改過名了」而跳過，
# 讓這支腳本可以重複執行：使用者會持續放新照片進 reference/ 資料夾，每次只處理還沒改過名的新檔案
_RENAMED_PATTERN = re.compile(r"^(?P<folder>[a-z]+)_(?P<seq>\d{3})$")


def _list_images(folder_path: Path) -> list[Path]:
    # 依修改時間排序：原始檔名一部分是純數字 ID、一部分是中文開頭，字面排序沒有實際意義，
    # 用 mtime 排序至少能反映「照片是依什麼順序被放進資料夾」，作為流水號先後的合理依據
    return sorted(
        (p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: p.stat().st_mtime,
    )


def _existing_max_seq(folder_name: str, files: list[Path]) -> int:
    # 掃描該資料夾內已經是「資料夾_流水號」格式的檔名，取目前最大流水號，讓新檔案接續編號
    max_seq = 0
    for f in files:
        match = _RENAMED_PATTERN.match(f.stem)
        if match and match.group("folder") == folder_name:
            max_seq = max(max_seq, int(match.group("seq")))
    return max_seq


def rename_folder(folder_name: str, folder_path: Path) -> list[dict]:
    # 對應使用者需求：reference 底下依資料夾分類重新命名為「資料夾_流水號」（例如 advanced_001），
    # 方便事後在檔案總管／CSV 之間快速對應圖片
    files = _list_images(folder_path)
    already_renamed = [p for p in files if _RENAMED_PATTERN.match(p.stem)]
    to_rename = [p for p in files if not _RENAMED_PATTERN.match(p.stem)]

    next_seq = _existing_max_seq(folder_name, already_renamed) + 1
    mapping_rows = []
    for old_path in to_rename:
        new_name = f"{folder_name}_{next_seq:03d}{old_path.suffix}"
        new_path = old_path.with_name(new_name)
        old_filename = old_path.name
        old_path.rename(new_path)
        mapping_rows.append({
            "folder": folder_name,
            "old_filename": old_filename,
            "new_filename": new_name,
            "renamed_at": datetime.now(LOCAL_TIMEZONE).isoformat(),
        })
        next_seq += 1
    return mapping_rows


def main() -> None:
    settings = load_settings()
    reference_paths = settings["paths"]["reference"]

    # 對照表持續累加寫入（不覆蓋舊紀錄），因為這支腳本設計為每次只處理新檔案、可重複執行
    mapping_csv = resolve_path("data/analysis_output/reference_rename_mapping.csv")
    mapping_csv.parent.mkdir(parents=True, exist_ok=True)
    file_exists = mapping_csv.exists()

    all_rows = []
    for folder_name in ("basic", "intermediate", "advanced"):
        folder_path = resolve_path(reference_paths[folder_name])
        rows = rename_folder(folder_name, folder_path)
        all_rows.extend(rows)
        print(f"{folder_name}：重新命名 {len(rows)} 個檔案")

    if all_rows:
        # utf-8-sig：對照表的原始檔名可能含中文（例如「安娜_DSC7292_20260417.jpg」），
        # 加 BOM 讓 Windows 版 Excel 開啟時不會亂碼
        with open(mapping_csv, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["folder", "old_filename", "new_filename", "renamed_at"])
            if not file_exists:
                writer.writeheader()
            writer.writerows(all_rows)
        print(f"共重新命名 {len(all_rows)} 個檔案，對照表已寫入：{mapping_csv}")
    else:
        print("沒有需要重新命名的檔案（可能都已經是「資料夾_流水號」格式）")


if __name__ == "__main__":
    main()
