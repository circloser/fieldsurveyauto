"""스캔(이미지) PDF용 OCR — 렌더 이미지에서 글자+위치를 얻는다.

엔진은 교체 가능(pluggable). 우선순위: rapidocr(설치 쉬움, 한국어) → pytesseract(별도 설치).
어느 것도 없으면 available()=False 이고, 호출 시 명확한 안내 오류를 던진다.
텍스트 PDF는 OCR이 필요 없으므로, needs_ocr 페이지에만 사용한다.
"""
from __future__ import annotations

from dataclasses import dataclass

_ENGINE = None          # 로드된 엔진 객체
_ENGINE_KIND = None     # "rapidocr" | "tesseract" | None
_TRIED = False


@dataclass
class OcrWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def _load_engine():
    global _ENGINE, _ENGINE_KIND, _TRIED
    if _TRIED:
        return _ENGINE_KIND
    _TRIED = True
    # 1) EasyOCR (한국어 정식 지원, pip만으로 설치)
    try:
        import easyocr
        _ENGINE = easyocr.Reader(["ko", "en"], gpu=False)
        _ENGINE_KIND = "easyocr"
        return _ENGINE_KIND
    except Exception:  # noqa: BLE001
        pass
    # 2) pytesseract (Tesseract 바이너리 별도 설치 필요, 한국어 kor)
    try:
        import pytesseract  # noqa: F401
        _ENGINE = "tesseract"
        _ENGINE_KIND = "tesseract"
        return _ENGINE_KIND
    except Exception:  # noqa: BLE001
        pass
    _ENGINE_KIND = None
    return None


def available() -> bool:
    return _load_engine() is not None


def ocr_image(png_bytes: bytes, scale: float = 1.0) -> list[OcrWord]:
    """PNG 이미지 바이트에서 (단어, 위치) 목록을 얻는다.

    scale: 이미지 픽셀 → PDF 포인트 변환 계수(= 72/dpi). 결과 좌표를 포인트로 맞춘다.
    """
    kind = _load_engine()
    if kind is None:
        raise RuntimeError(
            "OCR 엔진이 없습니다. 스캔(이미지) PDF를 읽으려면 rapidocr-onnxruntime "
            "설치가 필요합니다: pip install rapidocr-onnxruntime"
        )
    if kind == "easyocr":
        return _ocr_easy(png_bytes, scale)
    return _ocr_tesseract(png_bytes, scale)


def _ocr_easy(png_bytes: bytes, scale: float) -> list[OcrWord]:
    import io

    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    arr = np.array(img)
    # detail=1: [ (box[4pt], text, conf), ... ]
    result = _ENGINE.readtext(arr, detail=1, paragraph=False)
    words: list[OcrWord] = []
    for box, text, _conf in result:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        words.append(OcrWord(min(xs) * scale, min(ys) * scale,
                             max(xs) * scale, max(ys) * scale, str(text)))
    return words


def _ocr_tesseract(png_bytes: bytes, scale: float) -> list[OcrWord]:
    import io

    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes))
    data = pytesseract.image_to_data(img, lang="kor+eng",
                                     output_type=pytesseract.Output.DICT)
    words: list[OcrWord] = []
    n = len(data["text"])
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(OcrWord(x * scale, y * scale, (x + w) * scale, (y + h) * scale, txt))
    return words
