# src/subject_detection.py
from pathlib import Path

import cv2
import numpy as np
from rembg import new_session, remove

# 模組層級快取：避免每張圖片都重新建立一次 onnxruntime session
_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None:
        # isnet-general-use 是 rembg 內建模型中，針對一般場景（非特定人像/物件）顯著主體分割效果較好的一款
        # 選它而非泛用型的 SAM，是因為這裡要的是「單一顯著主體」的遮罩，SAM 是通用分割工具，
        # 得額外處理「從一堆候選遮罩中挑出主體」的邏輯，且 SAM 對 4GB VRAM 較吃緊；isnet 直接輸出單一顯著度遮罩，更貼合這裡的需求
        _SESSION = new_session("isnet-general-use")
    return _SESSION


def _imread_unicode(file_path: Path) -> np.ndarray:
    # cv2.imread 在 Windows 上無法正確處理含中文的路徑，改用 np.fromfile + cv2.imdecode 繞過
    file_bytes = np.fromfile(str(file_path), dtype=np.uint8)
    return cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)


def detect_subject(file_path: Path, mask_threshold: int = 128) -> dict | None:
    # 對應 docs/roadmap.md Phase 1「②人臉、主體位置與占比」的主體部分
    # 用顯著性物件分割取得前景遮罩，再取「面積最大的連通區域」當作主體範圍，避免雜訊小區塊干擾 bounding box
    image_bgr = _imread_unicode(file_path)
    height, width = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    mask = remove(image_rgb, session=_get_session(), only_mask=True)
    binary_mask = (mask > mask_threshold).astype(np.uint8)

    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary_mask, connectivity=8)
    if num_labels <= 1:
        return None  # 沒有偵測到明顯前景主體（例如全圖都是背景/風景，沒有單一顯著物件）

    # label 0 固定是背景，取面積最大的前景連通區域視為主體
    largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[largest_label]

    return {
        "bbox_x": int(x),
        "bbox_y": int(y),
        "bbox_w": int(w),
        "bbox_h": int(h),
        "center_x_norm": round(float(x + w / 2) / width, 5),
        "center_y_norm": round(float(y + h / 2) / height, 5),
        "area_ratio": round(float(area) / (width * height), 5),
        "subject_type": "salient_object",
        "model_version": "rembg-isnet-general-use",
    }
