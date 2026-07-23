# src/image_io.py
from pathlib import Path

import cv2
import numpy as np


def imread_unicode(file_path: Path) -> np.ndarray:
    # cv2.imread 在 Windows 上無法正確處理含中文的路徑（實測會回傳 None），改用 np.fromfile + cv2.imdecode 繞過
    # 原本 face_detection.py、subject_detection.py 各自複製一份，grid_analysis.py 是第三個需要的地方，
    # 三處重複且是修 Windows 路徑 bug 才會用到的 workaround，故抽出共用，避免之後修正時漏改
    file_bytes = np.fromfile(str(file_path), dtype=np.uint8)
    return cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
