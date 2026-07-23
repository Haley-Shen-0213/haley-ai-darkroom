# src/grid_analysis.py
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from image_io import imread_unicode
from image_metadata import dominant_colors, rgb_to_hsl

# 對應 docs/roadmap.md 3.2③「九宮格分析」：grid_index 1~9，左上到右下編號（列優先），
# 與 db/schema 草案（docs/roadmap.md 3.3 節 grid_analysis 表）的編號規則一致，第 5 格固定是中央格
_GRID_ROWS = 3
_GRID_COLS = 3
_CENTER_GRID_INDEX = 5


def _get_split_ratio(aspect_ratio_group: str, grid_settings: dict) -> tuple[float, float]:
    # 依長寬比分組取切分比例：優先用 per_aspect_ratio_group 的覆寫值，沒有才退回 default_split_ratio
    # 覆寫值目前（2026-07-23）尚未累積任何分組統計，per_aspect_ratio_group 恆為空字典，
    # 若之後填入，需同時提供 edge、center 兩個鍵（config/settings.yaml 已註記此限制，不在程式中額外檢查）
    overrides = grid_settings.get("per_aspect_ratio_group", {})
    ratios = overrides.get(aspect_ratio_group, grid_settings["default_split_ratio"])
    return ratios["edge"], ratios["center"]


def _cell_bounds(width: int, height: int, edge_ratio: float, center_ratio: float) -> list[dict]:
    # 依「邊緣格佔比 edge / 中央格佔比 center」把長寬各切成三段，組出 9 個格子的像素邊界
    # 用累加後的比例（而非各自獨立四捨五入）換算像素座標，確保邊界單調遞增、格子之間不重疊也不留縫隙
    col_fracs = [0.0, edge_ratio, edge_ratio + center_ratio, 1.0]
    row_fracs = [0.0, edge_ratio, edge_ratio + center_ratio, 1.0]
    col_px = [round(f * width) for f in col_fracs]
    row_px = [round(f * height) for f in row_fracs]

    cells = []
    grid_index = 1
    for row in range(_GRID_ROWS):
        for col in range(_GRID_COLS):
            cells.append({
                "grid_index": grid_index,
                "x0": col_px[col], "x1": col_px[col + 1],
                "y0": row_px[row], "y1": row_px[row + 1],
            })
            grid_index += 1
    return cells


def _bbox_overlap_ratio(bbox: dict, region: dict) -> float:
    # 計算 bbox（人臉／主體偵測結果，像素座標）與九宮格某一格區域的重疊面積，占 bbox 自身面積的比例
    # 用於「主體 bbox 有多少比例落在第 5 格」這個驗證指標，見 docs/roadmap.md 3.2③ 節
    bx0, by0 = bbox["bbox_x"], bbox["bbox_y"]
    bx1, by1 = bx0 + bbox["bbox_w"], by0 + bbox["bbox_h"]

    inter_x0, inter_y0 = max(bx0, region["x0"]), max(by0, region["y0"])
    inter_x1, inter_y1 = min(bx1, region["x1"]), min(by1, region["y1"])
    inter_area = max(0.0, inter_x1 - inter_x0) * max(0.0, inter_y1 - inter_y0)

    bbox_area = bbox["bbox_w"] * bbox["bbox_h"]
    if bbox_area <= 0:
        return 0.0
    return round(inter_area / bbox_area, 5)


def analyze_grid(file_path: Path, subject: dict | None, aspect_ratio_group: str, settings: dict) -> dict:
    # 對應 docs/roadmap.md Phase 1「③九宮格分析」
    # 亮度／飽和度／邊緣偵測都先在「整張圖」算好，再依格子邊界切片統計，而不是先裁切各格再各自運算：
    # Canny 邊緣偵測需要格子邊界外的鄰近像素當上下文，先裁切再算會在格子邊緣附近多算出假邊緣
    grid_settings = settings["grid_analysis"]
    edge_ratio, center_ratio = _get_split_ratio(aspect_ratio_group, grid_settings)

    image_bgr = imread_unicode(file_path)
    height, width = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    hue, saturation, lightness = rgb_to_hsl(image_rgb)

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    canny_cfg = grid_settings["edge_detection"]
    edges = cv2.Canny(gray, canny_cfg["canny_threshold1"], canny_cfg["canny_threshold2"])

    cells_bounds = _cell_bounds(width, height, edge_ratio, center_ratio)
    cells = []
    for cell in cells_bounds:
        x0, x1, y0, y1 = cell["x0"], cell["x1"], cell["y0"], cell["y1"]
        cell_rgb = image_rgb[y0:y1, x0:x1]
        cell_edges = edges[y0:y1, x0:x1]

        cells.append({
            "grid_index": cell["grid_index"],
            "avg_brightness": round(float(lightness[y0:y1, x0:x1].mean()) * 100, 3),
            "avg_saturation": round(float(saturation[y0:y1, x0:x1].mean()) * 100, 3),
            "dominant_color": dominant_colors(Image.fromarray(cell_rgb), top_n=1)[0],
            # 邊緣密度：該格內邊緣像素占全格像素的比例，粗略反映該區塊資訊量／是否為主體所在
            "edge_density": round(float(np.count_nonzero(cell_edges)) / cell_edges.size, 4),
        })

    # 第 5 格（中央格）主體占比：驗證「中央格是否真的涵蓋大部分主體」這個九宮格設計目標是否達成，
    # 沒有偵測到主體時（subject 為 None）沒有基準可算，回傳 None，對應 images.center_cell_subject_coverage 允許為 NULL
    center_cell = next(c for c in cells_bounds if c["grid_index"] == _CENTER_GRID_INDEX)
    center_cell_subject_coverage = _bbox_overlap_ratio(subject, center_cell) if subject else None

    return {
        "cells": cells,
        "center_cell_subject_coverage": center_cell_subject_coverage,
        "split_ratio": {"edge": edge_ratio, "center": center_ratio},
        "model_version": "grid-analysis-v1",
    }
