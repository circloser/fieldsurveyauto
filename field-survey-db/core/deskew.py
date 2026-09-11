"""스캔 쪽 기울기 바로잡기.

기울어진 스캔은 표 선이 비스듬해 칸 인식(이미지 격자)이 실패하고, 라벨을 따라가지 못해 좌표로만
읽게 되어 값이 한 줄씩 밀린다(실제 사례: 저어새 조사표 스캔 1쪽 1.5°·6쪽 0.5° → 칸 4·0개, 라벨 0/24).

업로드 단계(to_pdf)에서 한 번만 곧게 편 사본을 만들어, 이후 OCR·칸 인식·사진 자르기·잉크 판정이
모두 같은 곧은 쪽을 쓰게 한다. 대상은 글자 레이어가 없고 쪽 전체를 그림 한 장이 덮는 쪽(스캔)뿐.
각도 = 쪽 폭 45% 이상인 긴 가로선들의 기울기 중앙값. 0.3° 미만은 영향이 없어 그대로 두고, 7°를 넘는
선은 가로선이 아닐 수 있어 재지 않는다. 곧게 펼 쪽이 없으면 원본 경로를 그대로 돌려준다.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

MIN_DEG = 0.3
MAX_DEG = 7.0
_DONE: dict[tuple, str] = {}     # (경로, 수정시각, 크기) → 쓸 PDF 경로


def _is_scan_page(page) -> bool:
    """글자 레이어 없이 쪽 전체(90% 이상)를 그림 한 장이 덮는 쪽."""
    if page.rotation or page.get_text("words"):
        return False
    imgs = page.get_images(full=True)
    if len(imgs) != 1:
        return False
    rects = page.get_image_rects(imgs[0][0])
    pr = page.rect
    return len(rects) == 1 and rects[0].width * rects[0].height >= 0.9 * pr.width * pr.height


def estimate_skew(gray) -> float | None:
    """회색 쪽 그림의 기울기(도, 그림 좌표 기준 — 오른쪽으로 갈수록 내려가면 +).

    가는 가로 획(표 선)만 남기고 — 사진의 짙은 면처럼 두꺼운 덩어리는 뺀다 — 여러 각도로 눕혀 봤을 때
    가로 투영이 가장 뾰족해지는 각도를 찾는다(0.5° 간격으로 훑고 둘레를 0.05° 간격으로 다듬음).
    실측: 긴 선 검출(Hough)은 위로 기운 0.5~1.2°를 못 쟀는데 이 방식은 ±0.45~2° 합성 쪽과
    실제 스캔(1.45°·0.65°, 곧은 쪽 0.2° 이하)을 모두 맞혔다. 가는 가로 획이 선 3줄 분량보다 적으면 None."""
    import cv2
    import numpy as np

    h, w = gray.shape
    bw = (gray < 170).astype(np.uint8)
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 12), 1)))
    thick = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((5, 1), np.uint8))     # 세로로 5px 넘는 덩어리
    ys, xs = np.nonzero(horiz & (1 - thick))
    if len(ys) < 3 * w:
        return None
    if len(ys) > 80000:
        pick = np.random.default_rng(0).choice(len(ys), 80000, replace=False)
        ys, xs = ys[pick], xs[pick]
    ys = ys.astype(np.float64)
    xs = xs.astype(np.float64)

    def sharpness(a: float) -> float:
        t = np.radians(a)
        yy = np.round(ys * np.cos(t) - xs * np.sin(t)).astype(np.int64)
        hist = np.bincount(yy - yy.min()).astype(np.float64)
        return float((hist ** 2).sum())

    coarse = max(np.arange(-MAX_DEG, MAX_DEG + 1e-9, 0.5), key=sharpness)
    fine = max(np.arange(coarse - 0.5, coarse + 0.5 + 1e-9, 0.05), key=sharpness)
    return round(float(fine), 2)


def _gray(page, dpi: int):
    import fitz
    import numpy as np

    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _straightened_jpeg(page, angle: float) -> bytes:
    """스캔 원본 해상도(최대 300dpi)로 렌더해 angle 만큼 되돌리고 JPEG로."""
    import cv2
    import fitz
    import numpy as np

    px_w = page.get_images(full=True)[0][2]
    dpi = max(100, min(300, round(px_w / page.rect.width * 72)))
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    img = cv2.cvtColor(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3),
                       cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)   # 양수 = 반시계 — 오른쪽 아래로 처진 쪽을 들어 올림
    img = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError("JPEG 인코딩 실패")
    return buf.tobytes()


def deskew_pdf(pdf_path: str, cache_dir: str) -> str:
    """기울어진 스캔 쪽이 있으면 곧게 편 사본(cache_dir)의 경로, 없으면 원래 경로."""
    try:
        import cv2  # noqa: F401
        import fitz
        st = os.stat(pdf_path)
    except (ImportError, OSError):
        return pdf_path
    key = (os.path.abspath(pdf_path), st.st_mtime, st.st_size)
    if key in _DONE:
        return _DONE[key]
    result = pdf_path
    try:
        doc = fitz.open(pdf_path)
        try:
            angles: dict[int, float] = {}
            for i, page in enumerate(doc):
                if not _is_scan_page(page):
                    continue
                a = estimate_skew(_gray(page, 100))
                if a is not None and abs(a) >= MIN_DEG:
                    angles[i] = a
            if angles:
                tag = hashlib.md5(repr(key).encode("utf-8")).hexdigest()[:8]
                out = Path(cache_dir) / f"{Path(pdf_path).stem}_곧게_{tag}.pdf"
                if not out.exists():
                    out.parent.mkdir(parents=True, exist_ok=True)
                    new = fitz.open()
                    try:
                        for i, page in enumerate(doc):
                            if i not in angles:
                                new.insert_pdf(doc, from_page=i, to_page=i)
                                continue
                            np_page = new.new_page(width=page.rect.width, height=page.rect.height)
                            np_page.insert_image(np_page.rect, stream=_straightened_jpeg(page, angles[i]))
                        tmp = out.with_name(out.stem + ".part.pdf")
                        new.save(str(tmp), garbage=3, deflate=True)
                    finally:
                        new.close()
                    os.replace(tmp, out)
                result = str(out)
        finally:
            doc.close()
    except Exception:  # noqa: BLE001  (바로잡기 실패는 원본으로 계속)
        result = pdf_path
    _DONE[key] = result
    return result
