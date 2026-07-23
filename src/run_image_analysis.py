# src/run_image_analysis.py
from pathlib import Path

from config import load_settings, resolve_path
from face_detection import detect_faces
from grid_analysis import analyze_grid
from image_metadata import SUPPORTED_EXTENSIONS, analyze_image_basic
from subject_detection import detect_subject

# 中文對照表，讓報告內的色相區間名稱對使用者更直覺（對應 config/settings.yaml 的 hue_bands 鍵值）
HUE_BAND_LABELS = {
    "red": "紅色", "orange": "橘黃色", "yellow": "黃色", "green": "綠色",
    "aqua": "水綠色", "blue": "藍色", "purple": "紫色", "magenta": "洋紅色",
}


def find_images(root: Path) -> list[Path]:
    # 遞迴掃描目錄下所有圖片檔案，.gitkeep 等非圖片檔會被副檔名過濾掉
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)


def _format_size(num_bytes: int) -> str:
    # 位元組換算成 KB，方便人工閱讀
    return f"{num_bytes / 1024:.1f} KB"


def _format_hue_band_table(hue_bands: dict) -> list[str]:
    # 對應 Lightroom HSL 面板：每個色相區間各自的占比／色相／飽和度／明度，無像素落在該區間時顯示 "-"
    lines = ["| 色相區間 | 像素占比 | 平均色相 | 平均飽和度 | 平均明度 |", "|---|---|---|---|---|"]
    for band_name, stats in hue_bands.items():
        label = HUE_BAND_LABELS.get(band_name, band_name)
        if stats["pixel_ratio"] == 0.0:
            lines.append(f"| {label} | 0% | - | - | - |")
        else:
            lines.append(
                f"| {label} | {stats['pixel_ratio']}% | {stats['avg_hue']}° "
                f"| {stats['avg_saturation']} | {stats['avg_luminance']} |"
            )
    return lines


# 中央格固定是第 5 格（grid_analysis._CENTER_GRID_INDEX），對應 docs/roadmap.md 3.2③ 節「第5格(中央格)」的編號規則
_CENTER_GRID_INDEX = 5


def _format_grid_table(grid: dict) -> list[str]:
    # 九宮格 3x3 逐格明細：grid_index 1~9 依左上到右下編號，第 5 格額外標註主體占比供人工核對
    edge, center = grid["split_ratio"]["edge"], grid["split_ratio"]["center"]
    lines = [
        f"切分比例：邊緣格 {edge*100:.0f}% ／ 中央格 {center*100:.0f}%（依長寬比分組，見 `config/settings.yaml`）",
        "",
        "| 格號 | 平均明度 | 平均飽和度 | 主色 | 邊緣密度 | 主體占比(僅第5格) |",
        "|---|---|---|---|---|---|",
    ]
    for cell in grid["cells"]:
        coverage = grid["center_cell_subject_coverage"]
        is_center = cell["grid_index"] == _CENTER_GRID_INDEX
        coverage_display = f"{coverage * 100:.1f}%" if (is_center and coverage is not None) else "-"
        lines.append(
            f"| {cell['grid_index']} | {cell['avg_brightness']} | {cell['avg_saturation']} "
            f"| `{cell['dominant_color']}` | {cell['edge_density']} | {coverage_display} |"
        )
    return lines


def build_markdown_report(results: list[dict]) -> str:
    # 產出人工可直接閱讀的 Markdown 報告：上半部用表格快速比較，下半部用可摺疊區塊保留完整原始資料
    # （含 EXIF、色相區間分析、人臉/主體偵測結果）
    lines = [
        "<!-- data/analysis_output/image_analysis_preview.md -->",
        "",
        "# 圖片分析結果",
        "",
        f"共 {len(results)} 張圖片，對應 `docs/roadmap.md` Phase 1「①圖片基本資料分析」「②人臉、主體位置與占比」「③九宮格分析」，"
        f"本檔案由 `src/run_image_analysis.py` 自動產生，僅供人工檢視參考，不進版控。",
        "",
        "## 總覽",
        "",
        "| 檔名 | 尺寸 | 長寬比 | 平均色相 | 平均飽和度 | 平均明度 | 人臉數 | 主體占比 | 第5格主體占比 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in results:
        name = Path(item["file_path"]).name
        subject = item["subject"]
        subject_ratio = f"{subject['area_ratio'] * 100:.1f}%" if subject else "-"
        # 第 5 格（中央格）主體占比：驗證九宮格「中央格涵蓋大部分主體」設計目標的關鍵指標，
        # docs/roadmap.md 3.2③ 節要求每一份分析報告都要包含這個數字，故放進總覽表而非只留在詳細區塊
        coverage = item["grid"]["center_cell_subject_coverage"]
        coverage_display = f"{coverage * 100:.1f}%" if coverage is not None else "-"
        lines.append(
            f"| {name} | {item['width_px']}x{item['height_px']} | {item['aspect_ratio_group']} "
            f"| {item['avg_hue']}° | {item['avg_saturation']} | {item['avg_brightness']} "
            f"| {len(item['faces'])} | {subject_ratio} | {coverage_display} |"
        )

    lines += ["", "## 詳細資料（色相區間、人臉/主體偵測、EXIF）", ""]
    for item in results:
        name = Path(item["file_path"]).name
        lines.append(f"<details><summary>{name}</summary>")
        lines.append("")
        lines.append(f"- 完整路徑：`{item['file_path']}`")
        lines.append(f"- 檔案大小：{_format_size(item['file_size_bytes'])}")
        lines.append(f"- 格式：{item['format']}")
        lines.append(f"- 分析模型版本：{item['analysis_model_version']}")
        lines.append(f"- 分析時間：{item['analyzed_at']}")
        lines.append("")

        lines.append("**色相區間分析（仿 Lightroom HSL 面板）**")
        lines.append("")
        lines += _format_hue_band_table(item["hue_bands"])
        lines.append("")

        lines.append("**人臉偵測**")
        lines.append("")
        if item["faces"]:
            lines.append("| # | 位置(x,y,w,h) | 面積占比 | 信心分數 |")
            lines.append("|---|---|---|---|")
            for idx, face in enumerate(item["faces"], start=1):
                lines.append(
                    f"| {idx} | ({face['bbox_x']}, {face['bbox_y']}, {face['bbox_w']}, {face['bbox_h']}) "
                    f"| {face['area_ratio'] * 100:.2f}% | {face['confidence']} |"
                )
        else:
            lines.append("（未偵測到人臉）")
        lines.append("")

        lines.append("**主體偵測**")
        lines.append("")
        subject = item["subject"]
        if subject:
            lines.append(
                f"- 位置(x,y,w,h)：({subject['bbox_x']}, {subject['bbox_y']}, {subject['bbox_w']}, {subject['bbox_h']})"
            )
            lines.append(f"- 面積占比：{subject['area_ratio'] * 100:.2f}%")
            lines.append(f"- 類型：{subject['subject_type']}")
        else:
            lines.append("（未偵測到明顯主體）")
        lines.append("")

        lines.append("**九宮格分析**")
        lines.append("")
        lines += _format_grid_table(item["grid"])
        lines.append("")

        if item["exif"]:
            lines.append("**EXIF**")
            lines.append("")
            for key, value in item["exif"].items():
                lines.append(f"- {key}：{value}")
        else:
            lines.append("**EXIF**：無")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    settings = load_settings()
    data_root = resolve_path(settings["paths"]["data_root"])
    hue_bands = settings["color_analysis"]["hue_bands"]
    saturation_threshold = settings["color_analysis"]["saturation_threshold"]

    image_paths = find_images(data_root)
    results = []
    for path in image_paths:
        item = analyze_image_basic(path, hue_bands, saturation_threshold)
        item["faces"] = detect_faces(path)
        item["subject"] = detect_subject(path)
        item["grid"] = analyze_grid(path, item["subject"], item["aspect_ratio_group"], settings)
        results.append(item)
        print(f"已分析：{path.name}（人臉 {len(item['faces'])} 張）")

    output_dir = resolve_path("data/analysis_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "image_analysis_preview.md"

    # 先輸出成文件供人工檢視格式是否合理，等確認沒問題後，Phase 1 才會把這份資料改成寫入 MySQL
    output_file.write_text(build_markdown_report(results), encoding="utf-8")

    print(f"已分析 {len(results)} 張圖片，結果輸出至：{output_file}")


if __name__ == "__main__":
    main()
