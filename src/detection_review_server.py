# src/detection_review_server.py
import csv
import json
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from config import load_settings, resolve_path
from face_detection import detect_faces
from image_metadata import SUPPORTED_EXTENSIONS
from subject_detection import detect_subject

# 對應 docs/roadmap.md 待辦「人臉／主體偵測結果的視覺化核對頁面」：本機小型網頁伺服器，
# 讓使用者疊圖核對偵測框準不準，人臉框、主體框分開評分（不準確／普通／準確），結果寫入 CSV
LOCAL_TIMEZONE = ZoneInfo("Asia/Taipei")
RATING_LABELS = ["不準確", "普通", "準確"]

CSV_FIELDNAMES = [
    "filename", "folder", "face_count", "face_rating", "face_rating_min", "face_rating_max",
    "subject_detected", "subject_area_ratio", "subject_rating", "subject_rating_min", "subject_rating_max",
    "rated_at",
]


def _list_reference_images(settings: dict) -> list[dict]:
    # 掃描 reference 三個資料夾，只納入 reference（不含 pending/completed，範圍對應這次的重新命名作業）
    # 檔名已在 src/rename_reference_files.py 統一改成「資料夾_流水號」格式，依檔名排序即等同依流水號依序瀏覽
    reference_paths = settings["paths"]["reference"]
    images = []
    for folder_name in ("basic", "intermediate", "advanced"):
        folder_path = resolve_path(reference_paths[folder_name])
        for p in sorted(folder_path.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append({"filename": p.name, "folder": folder_name, "path": p})
    return images


def _load_detection_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return {}


def _save_detection_cache(cache_path: Path, cache: dict) -> None:
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_detection(image_info: dict, cache: dict) -> dict:
    # 人臉／主體偵測結果快取到磁碟：這個伺服器可能被重複啟動來查看評分進度，
    # 若每次啟動都重跑一次 InsightFace／rembg（光模型載入就要約 50 秒），使用體驗會很差
    # 用檔案 mtime + 大小當快取失效依據：檔案沒變就沿用快取，變了（例如同名覆蓋）才重新偵測
    path = image_info["path"]
    stat = path.stat()
    cache_key = image_info["filename"]
    cached = cache.get(cache_key)
    if cached and cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
        return cached

    result = {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "faces": detect_faces(path),
        "subject": detect_subject(path),
    }
    cache[cache_key] = result
    return result


# Windows 內建的正體中文字型：標籤文字含「主體」等中文字，PIL 的預設字型（ImageFont.load_default）
# 不支援 CJK，中文字元會變成方框亂碼（實測 advanced_001.jpg 的「主體」標籤才發現這個問題），必須指定中文字型
_CJK_FONT_PATH = Path("C:/Windows/Fonts/msjh.ttc")


def _load_label_font(font_size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(_CJK_FONT_PATH), font_size)
    except OSError:
        # 萬一系統上找不到這個字型檔（例如非 Windows 環境），退回預設字型，至少英數字部分能正常顯示
        return ImageFont.load_default()


def _draw_label(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: tuple, font: ImageFont.ImageFont) -> None:
    # 標籤文字加實心背景色塊，避免疊在複雜背景上難以辨識
    # 框的頂邊離圖片上緣太近時（實測全身主體框常見，人物頭頂本來就靠近畫面頂端），
    # 標在框上方會被邊緣裁掉，改標在框內側緊貼頂邊，兩種情況都能完整顯示
    label_y = y - font.size - 4 if y >= font.size + 4 else y + 2
    text_bbox = draw.textbbox((x + 2, label_y), text, font=font)
    draw.rectangle(text_bbox, fill=color)
    draw.text((x + 2, label_y), text, fill="white", font=font)


def _render_annotated_jpeg(path: Path, faces: list[dict], subject: dict | None, review_settings: dict) -> bytes:
    # 疊圖規則：人臉框、主體框用不同顏色區分（顏色設定見 config/settings.yaml detection_review），
    # 線寬依圖片短邊比例縮放，避免小圖線太粗糊掉細節、大圖（實測素材中有 6000x4000）線太細看不清楚
    # 每次請求即時繪製（不落地存檔）：偵測結果已經有磁碟快取，繪圖本身很快，不需要再多一層檔案快取
    face_color = tuple(review_settings["face_box_color_rgb"])
    subject_color = tuple(review_settings["subject_box_color_rgb"])

    with Image.open(path) as raw:
        image = raw.convert("RGB").copy()
    width, height = image.size
    line_width = max(3, round(min(width, height) / 200))
    font = _load_label_font(max(16, round(min(width, height) / 40)))
    draw = ImageDraw.Draw(image)

    if subject:
        x0, y0 = subject["bbox_x"], subject["bbox_y"]
        x1, y1 = x0 + subject["bbox_w"], y0 + subject["bbox_h"]
        draw.rectangle([x0, y0, x1, y1], outline=subject_color, width=line_width)
        _draw_label(draw, x0, y0, f"主體 {subject['area_ratio'] * 100:.1f}%", subject_color, font)

    for idx, face in enumerate(faces, start=1):
        # InsightFace 的 bbox 是模型輸出、不是系統內部保證乾淨的資料，畫圖前裁到圖片範圍內，
        # 避免極少數退化框（超出邊界或寬高為 0）讓 PIL 丟例外中斷整個伺服器
        x0 = int(max(0, min(width - 1, face["bbox_x"])))
        y0 = int(max(0, min(height - 1, face["bbox_y"])))
        x1 = int(max(0, min(width, face["bbox_x"] + face["bbox_w"])))
        y1 = int(max(0, min(height, face["bbox_y"] + face["bbox_h"])))
        if x1 <= x0 or y1 <= y0:
            continue
        draw.rectangle([x0, y0, x1, y1], outline=face_color, width=line_width)
        _draw_label(draw, x0, y0, f"F{idx}", face_color, font)

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def _load_ratings(csv_path: Path) -> dict:
    rows = {}
    if csv_path.exists():
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows[row["filename"]] = row
    return rows


def _save_ratings(csv_path: Path, rows: dict) -> None:
    # 每次評分都整份重寫：資料量小（幾十張圖片等級），重寫比處理「同一張圖重複評分要更新哪一列」簡單可靠
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for filename in sorted(rows):
            writer.writerow(rows[filename])


def _is_fully_rated(row: dict | None) -> bool:
    return bool(row and row.get("face_rating") and row.get("subject_rating"))


def _count_done(images: list[dict], ratings: dict) -> int:
    return sum(1 for img in images if _is_fully_rated(ratings.get(img["filename"])))


def _button_group(target: str, filename: str, current_rating: str) -> str:
    buttons = []
    for label in RATING_LABELS:
        css_class = "rate-btn selected" if label == current_rating else "rate-btn"
        buttons.append(
            f'<form method="post" action="/rate" style="display:inline">'
            f'<input type="hidden" name="filename" value="{filename}">'
            f'<input type="hidden" name="target" value="{target}">'
            f'<input type="hidden" name="rating" value="{label}">'
            f'<button type="submit" class="{css_class}">{label}</button>'
            f'</form>'
        )
    return "".join(buttons)


def _render_review_page(img_info: dict, detection: dict, row: dict | None,
                         images: list[dict], ratings: dict, review_settings: dict) -> str:
    filename = img_info["filename"]
    names = [i["filename"] for i in images]
    idx = names.index(filename)
    prev_link = f'<a href="/review/{names[idx - 1]}">← 上一張</a>' if idx > 0 else "（第一張）"
    next_link = f'<a href="/review/{names[idx + 1]}">下一張 →</a>' if idx < len(names) - 1 else "（最後一張）"

    faces, subject = detection["faces"], detection["subject"]
    face_info = f"偵測到 {len(faces)} 張人臉" if faces else "未偵測到人臉"
    subject_info = f"主體占比：{subject['area_ratio'] * 100:.1f}%" if subject else "未偵測到明顯主體"

    face_color_css = f"rgb({','.join(str(c) for c in review_settings['face_box_color_rgb'])})"
    subject_color_css = f"rgb({','.join(str(c) for c in review_settings['subject_box_color_rgb'])})"

    row = row or {}
    done_count = _count_done(images, ratings)

    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<title>偵測結果核對 - {filename}</title>
<style>
body {{ font-family: "Microsoft JhengHei", -apple-system, sans-serif; max-width: 900px; margin: 20px auto; padding: 0 16px; }}
.progress {{ color: #666; }}
.nav {{ display: flex; justify-content: space-between; margin: 8px 0 16px; }}
img.preview {{ max-width: 100%; max-height: 70vh; display: block; margin: 0 auto; border: 1px solid #ccc; }}
.info {{ background: #f5f5f5; padding: 12px; border-radius: 6px; margin: 16px 0; line-height: 1.8; }}
.rate-group {{ margin: 16px 0; }}
.rate-btn {{ padding: 8px 20px; margin-right: 8px; border: 1px solid #999; border-radius: 4px; background: white; cursor: pointer; font-size: 14px; }}
.rate-btn.selected {{ background: #333; color: white; border-color: #333; }}
.legend-face {{ color: {face_color_css}; font-weight: bold; }}
.legend-subject {{ color: {subject_color_css}; font-weight: bold; }}
</style></head>
<body>
<div class="progress">進度：{done_count} / {len(images)} 張已完成兩項評分　｜　<a href="/done">查看總覽</a></div>
<div class="nav">{prev_link}　　{filename}（{img_info['folder']}）　　{next_link}</div>
<img class="preview" src="/image/{filename}" alt="{filename}">
<div class="info">
  <span class="legend-face">■</span> 人臉框　　<span class="legend-subject">■</span> 主體框<br>
  {face_info}<br>
  {subject_info}
</div>
<div class="rate-group">
  <h3>人臉框準確度</h3>
  {_button_group('face', filename, row.get('face_rating', ''))}
</div>
<div class="rate-group">
  <h3>主體框準確度</h3>
  {_button_group('subject', filename, row.get('subject_rating', ''))}
</div>
</body></html>"""


def _render_done_page(images: list[dict], ratings: dict) -> str:
    tally = {"face": {}, "subject": {}}
    for label in RATING_LABELS:
        tally["face"][label] = 0
        tally["subject"][label] = 0
    for img in images:
        row = ratings.get(img["filename"])
        if not row:
            continue
        if row.get("face_rating") in RATING_LABELS:
            tally["face"][row["face_rating"]] += 1
        if row.get("subject_rating") in RATING_LABELS:
            tally["subject"][row["subject_rating"]] += 1

    done_count = _count_done(images, ratings)
    first_filename = images[0]["filename"] if images else ""
    rows_html = "".join(
        f"<tr><td>{label}</td><td>{tally['face'][label]}</td><td>{tally['subject'][label]}</td></tr>"
        for label in RATING_LABELS
    )
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>評分總覽</title>
<style>body {{ font-family: "Microsoft JhengHei", sans-serif; max-width: 700px; margin: 40px auto; padding: 0 16px; }}
table {{ border-collapse: collapse; margin-top: 12px; }}
td, th {{ border: 1px solid #ccc; padding: 6px 16px; text-align: center; }}</style></head>
<body>
<h2>評分總覽</h2>
<p>{done_count} / {len(images)} 張已完成兩項評分</p>
<table><tr><th>評分</th><th>人臉框</th><th>主體框</th></tr>{rows_html}</table>
<p style="margin-top:20px"><a href="/review/{first_filename}">回到第一張（可修改已評分結果）</a></p>
</body></html>"""


class ReviewHandler(BaseHTTPRequestHandler):
    # 共用狀態由 main() 在啟動伺服器前設定好，同一支腳本只服務單一使用者、單一瀏覽階段，
    # 用類別屬性簡單共享狀態即可，不需要引入 session 或資料庫等級的機制
    images: list[dict] = []
    detections: dict = {}
    ratings: dict = {}
    review_settings: dict = {}
    csv_path: Path | None = None

    def log_message(self, format, *args):
        pass  # 不印出預設的 HTTP access log，減少終端機雜訊

    def _by_filename(self) -> dict:
        return {img["filename"]: img for img in self.images}

    def _next_unrated(self, after: str | None = None) -> str:
        names = [img["filename"] for img in self.images]
        if after is not None:
            start = names.index(after) + 1
            ordered = names[start:] + names[:start]
        else:
            ordered = names
        for name in ordered:
            if not _is_fully_rated(self.ratings.get(name)):
                return f"/review/{name}"
        return "/done"

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._redirect(self._next_unrated())
        elif parsed.path == "/done":
            body = _render_done_page(self.images, self.ratings).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/review/"):
            filename = parsed.path[len("/review/"):]
            img_info = self._by_filename().get(filename)
            if img_info is None:
                self.send_error(404, "找不到這張圖片")
                return
            html = _render_review_page(
                img_info, self.detections[filename], self.ratings.get(filename),
                self.images, self.ratings, self.review_settings,
            )
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/image/"):
            filename = parsed.path[len("/image/"):]
            img_info = self._by_filename().get(filename)
            if img_info is None:
                self.send_error(404, "找不到這張圖片")
                return
            detection = self.detections[filename]
            body = _render_annotated_jpeg(img_info["path"], detection["faces"], detection["subject"], self.review_settings)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/rate":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        filename = fields.get("filename", [""])[0]
        target = fields.get("target", [""])[0]
        rating = fields.get("rating", [""])[0]

        img_info = self._by_filename().get(filename)
        if img_info is None or target not in ("face", "subject") or rating not in RATING_LABELS:
            self.send_error(400, "評分參數不正確")
            return

        rating_min, rating_max = self.review_settings["rating_ranges"][rating]
        detection = self.detections[filename]
        row = self.ratings.setdefault(filename, {"filename": filename})
        row["folder"] = img_info["folder"]
        row["face_count"] = len(detection["faces"])
        row["subject_detected"] = bool(detection["subject"])
        row["subject_area_ratio"] = detection["subject"]["area_ratio"] if detection["subject"] else ""

        if target == "face":
            row["face_rating"], row["face_rating_min"], row["face_rating_max"] = rating, rating_min, rating_max
        else:
            row["subject_rating"], row["subject_rating_min"], row["subject_rating_max"] = rating, rating_min, rating_max
        row["rated_at"] = datetime.now(LOCAL_TIMEZONE).isoformat()

        _save_ratings(self.csv_path, self.ratings)

        next_url = self._next_unrated(after=filename) if _is_fully_rated(row) else f"/review/{filename}"
        self._redirect(next_url)


def main() -> None:
    settings = load_settings()
    review_settings = settings["detection_review"]

    images = _list_reference_images(settings)
    if not images:
        print("data/images/reference 底下沒有找到圖片，請先放入圖片再啟動。")
        return

    cache_path = resolve_path("data/analysis_output/detection_cache.json")
    cache = _load_detection_cache(cache_path)

    print(f"共 {len(images)} 張圖片，準備人臉／主體偵測結果（已有快取的圖片會直接沿用，不重新跑模型）...")
    detections = {img["filename"]: _get_detection(img, cache) for img in images}
    _save_detection_cache(cache_path, cache)

    csv_path = resolve_path("data/analysis_output/detection_accuracy_review.csv")
    ratings = _load_ratings(csv_path)

    ReviewHandler.images = images
    ReviewHandler.detections = detections
    ReviewHandler.ratings = ratings
    ReviewHandler.review_settings = review_settings
    ReviewHandler.csv_path = csv_path

    port = review_settings["server_port"]
    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"核對頁面已啟動：{url}（Ctrl+C 或關閉終端機即可停止）")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止伺服器")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
