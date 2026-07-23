# src/image_metadata.py
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ExifTags

# 支援的圖片副檔名，對應 .gitignore 中排除版控的圖片格式
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}

# 使用者為台北時區，分析時間一律記錄本地時間，不用 UTC，方便直接對照查看
LOCAL_TIMEZONE = ZoneInfo("Asia/Taipei")

# 常見攝影長寬比，用來把實際像素比例正規化分類（對應 docs/roadmap.md 的 aspect_ratio_group）
KNOWN_ASPECT_RATIOS = {
    "3:2": 3 / 2, "4:3": 4 / 3, "1:1": 1 / 1,
    "16:9": 16 / 9, "2:3": 2 / 3, "3:4": 3 / 4, "9:16": 9 / 16,
}


def _sanitize_text(value: str) -> str:
    # 部分相機／後製軟體寫入的 EXIF 字串會夾雜 NUL byte 等非印刷字元（曾在實測素材中發現），
    # 直接輸出會讓 Markdown／JSON 等文字檔案損毀，故一律過濾掉
    return "".join(ch for ch in value if ch.isprintable()).strip()


def _extract_exif(image: Image.Image) -> dict:
    # EXIF 標籤原始格式是數字代碼，轉成人類看得懂的欄位名稱，方便日後在文件與資料庫中檢視
    raw_exif = image.getexif()
    if not raw_exif:
        return {}
    exif_data = {}
    for tag_id, value in raw_exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        # bytes 與部分 EXIF 專用型別（如 IFDRational）無法直接存成 JSON，一律轉字串避免輸出失敗
        if isinstance(value, bytes):
            value = _sanitize_text(value.decode(errors="ignore"))
        elif isinstance(value, str):
            value = _sanitize_text(value)
        elif not isinstance(value, (int, float, bool)):
            value = _sanitize_text(str(value))
        exif_data[tag_name] = value
    return exif_data


def _aspect_ratio_group(width: int, height: int) -> str:
    # 實際像素比例不會剛好整除（例如 6000x4000），取最接近的常見比例分類
    actual_ratio = width / height
    return min(KNOWN_ASPECT_RATIOS, key=lambda name: abs(KNOWN_ASPECT_RATIOS[name] - actual_ratio))


def rgb_to_hsl(rgb_array: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # 手動實作 RGB→HSL 向量化轉換（Pillow 沒有內建 HSL 模式，只有 HSV）
    # 回傳色相 hue（0~360 度）、飽和度 saturation（0~1）、明度 lightness（0~1）三個陣列，
    # 選用 HSL 而非 HSV，是為了跟 Lightroom HSL 面板（色相/飽和度/明度）的術語與數值意義一致
    # 對外公開（無底線前綴）：grid_analysis.py 的九宮格色彩統計也需要同一套轉換，避免另寫一份邏輯
    rgb = rgb_array.astype(np.float32) / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    max_c = np.max(rgb, axis=-1)
    min_c = np.min(rgb, axis=-1)
    delta = max_c - min_c
    lightness = (max_c + min_c) / 2

    with np.errstate(divide="ignore", invalid="ignore"):
        saturation = np.where(delta == 0, 0.0, delta / (1 - np.abs(2 * lightness - 1)))
    saturation = np.nan_to_num(saturation, nan=0.0)

    hue = np.zeros_like(max_c)
    has_color = delta != 0
    r_is_max = has_color & (max_c == r)
    g_is_max = has_color & (max_c == g) & ~r_is_max
    b_is_max = has_color & (max_c == b) & ~r_is_max & ~g_is_max

    hue[r_is_max] = (60 * ((g[r_is_max] - b[r_is_max]) / delta[r_is_max]) + 360) % 360
    hue[g_is_max] = (60 * ((b[g_is_max] - r[g_is_max]) / delta[g_is_max]) + 120) % 360
    hue[b_is_max] = (60 * ((r[b_is_max] - g[b_is_max]) / delta[b_is_max]) + 240) % 360

    return hue, saturation, lightness


def _circular_mean_degrees(hue_values: np.ndarray) -> float:
    # 色相是 0~360 度的循環量，不能直接用算術平均：350 度跟 5 度這種橫跨 0 度的值，
    # 一般平均會算出 177.5 度（完全錯誤），必須把角度轉成單位圓座標平均後再轉回角度
    radians = np.deg2rad(hue_values)
    mean_angle = np.degrees(np.arctan2(np.sin(radians).mean(), np.cos(radians).mean()))
    return float(mean_angle % 360)


def _color_stats(image: Image.Image) -> dict:
    # 整張圖的色相／飽和度／明度／對比度平均值，作為「該圖整體色調」的摘要指標
    hue, saturation, lightness = rgb_to_hsl(np.asarray(image.convert("RGB")))
    return {
        "avg_hue": round(_circular_mean_degrees(hue), 2),
        "avg_saturation": round(float(saturation.mean()) * 100, 3),
        "avg_brightness": round(float(lightness.mean()) * 100, 3),
        # 對比度用明度的標準差近似：數值越大代表畫面明暗差異越大
        "avg_contrast": round(float(lightness.std()) * 100, 3),
    }


def _hue_in_band(hue: np.ndarray, band_range: list[float]) -> np.ndarray:
    low, high = band_range
    if low <= high:
        return (hue >= low) & (hue < high)
    # 色相是 0~360 度循環的，「紅色」這類色相會橫跨 345→360→0→15，需處理環繞情況
    return (hue >= low) | (hue < high)


def analyze_hue_bands(image: Image.Image, hue_bands: dict, saturation_threshold: float) -> dict:
    # 對應 Lightroom HSL 面板的做法：把畫面依色相分成幾個色彩區間（紅/橘黃/黃/綠/水綠/藍/紫/洋紅等，
    # 區間定義來自 config/settings.yaml），分別統計每個區間的色相/飽和度/明度平均值與像素占比
    # 濾掉飽和度過低（接近灰階、無明確色相意義）的像素，避免灰階雜訊拉低各色相區間統計的代表性
    hue, saturation, lightness = rgb_to_hsl(np.asarray(image.convert("RGB")))
    colorful_mask = saturation >= saturation_threshold
    total_pixels = hue.size

    bands_result = {}
    for band_name, band_range in hue_bands.items():
        band_mask = colorful_mask & _hue_in_band(hue, band_range)
        pixel_count = int(band_mask.sum())
        if pixel_count == 0:
            bands_result[band_name] = {"pixel_ratio": 0.0, "avg_hue": None, "avg_saturation": None, "avg_luminance": None}
            continue
        bands_result[band_name] = {
            "pixel_ratio": round(pixel_count / total_pixels * 100, 3),
            "avg_hue": round(_circular_mean_degrees(hue[band_mask]), 2),
            "avg_saturation": round(float(saturation[band_mask].mean()) * 100, 3),
            "avg_luminance": round(float(lightness[band_mask].mean()) * 100, 3),
        }
    return bands_result


def dominant_colors(image: Image.Image, top_n: int = 5) -> list[str]:
    # 用 Pillow 內建色彩量化取代自己寫 k-means，先求堪用；之後若準確度不夠再換更精準的演算法
    # 對外公開（無底線前綴）：grid_analysis.py 算各格主色時也需要這個函式，top_n=1 即可
    quantized = image.convert("RGB").quantize(colors=64)
    palette = quantized.getpalette()
    color_counts = sorted(quantized.getcolors(), reverse=True, key=lambda item: item[0])
    dominant = []
    for _, palette_index in color_counts[:top_n]:
        r, g, b = palette[palette_index * 3: palette_index * 3 + 3]
        dominant.append(f"#{r:02x}{g:02x}{b:02x}")
    return dominant


def analyze_image_basic(file_path: Path, hue_bands: dict, hue_saturation_threshold: float) -> dict:
    # 對應 docs/roadmap.md Phase 1「①圖片基本資料分析」：檔案層級、尺寸層級、色彩層級資料
    # hue_bands、hue_saturation_threshold 由呼叫端從 config/settings.yaml 讀取傳入，
    # 依 CLAUDE.md 規範不把這些可調參數寫死在程式碼中
    with Image.open(file_path) as image:
        width, height = image.size
        result = {
            "file_path": str(file_path),
            "file_size_bytes": file_path.stat().st_size,
            "format": image.format,
            "width_px": width,
            "height_px": height,
            "aspect_ratio_raw": round(width / height, 6),
            "aspect_ratio_group": _aspect_ratio_group(width, height),
            **_color_stats(image),
            "dominant_colors": dominant_colors(image),
            "hue_bands": analyze_hue_bands(image, hue_bands, hue_saturation_threshold),
            "exif": _extract_exif(image),
            "analysis_model_version": "basic-metadata-v1",
            "analyzed_at": datetime.now(LOCAL_TIMEZONE).isoformat(),
        }
    return result
