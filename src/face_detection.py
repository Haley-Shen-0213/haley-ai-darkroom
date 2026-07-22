# src/face_detection.py
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

# 模組層級快取：InsightFace 模型載入一次要價約 30 秒，若每張圖片都重新載入會拖垮整個批次流程
_APP: FaceAnalysis | None = None


def _get_app() -> FaceAnalysis:
    global _APP
    if _APP is None:
        # buffalo_l 套件同時包含 RetinaFace 偵測與 ArcFace 辨識模型，對應 docs/roadmap.md 3.4 節的準確度優先選型
        # ctx_id=-1 使用 CPU：目前環境的 onnxruntime 未裝 GPU 版本，Phase 1 屬離線批次分析，可接受較慢的速度換取準確度
        _APP = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _APP.prepare(ctx_id=-1, det_size=(640, 640))
    return _APP


def _imread_unicode(file_path: Path) -> np.ndarray:
    # cv2.imread 在 Windows 上無法正確處理含中文的路徑（實測會回傳 None），改用 np.fromfile + cv2.imdecode 繞過
    file_bytes = np.fromfile(str(file_path), dtype=np.uint8)
    return cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)


def detect_faces(file_path: Path) -> list[dict]:
    # 對應 docs/roadmap.md Phase 1「②人臉、主體位置與占比」的人臉部分
    # 目前只取 bbox/信心分數，暫不輸出 512 維人臉特徵向量（embedding）：
    # 那是 Phase 2 人臉比對辨識才需要的欄位，資料庫表也尚未設計對應欄位，先不做用不到的事
    image = _imread_unicode(file_path)
    height, width = image.shape[:2]
    faces = _get_app().get(image)

    results = []
    for face in faces:
        x1, y1, x2, y2 = face.bbox
        bbox_w, bbox_h = x2 - x1, y2 - y1
        results.append({
            "bbox_x": round(float(x1), 1),
            "bbox_y": round(float(y1), 1),
            "bbox_w": round(float(bbox_w), 1),
            "bbox_h": round(float(bbox_h), 1),
            "center_x_norm": round(float((x1 + bbox_w / 2) / width), 5),
            "center_y_norm": round(float((y1 + bbox_h / 2) / height), 5),
            "area_ratio": round(float(bbox_w * bbox_h) / (width * height), 5),
            "confidence": round(float(face.det_score), 4),
            "model_version": "insightface-buffalo_l",
        })
    # 由左至右排序，方便報告閱讀與之後人工比對
    results.sort(key=lambda f: f["bbox_x"])
    return results
