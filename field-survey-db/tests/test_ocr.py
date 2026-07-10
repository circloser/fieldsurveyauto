"""OCR 통합 검증 — 엔진 가용성, 스캔 페이지 OCR 채움.

OCR 엔진(easyocr 등)이 없으면 자동 skip. 있으면 렌더 이미지에서 한글을 읽는지 확인.
"""
import pytest

from core import ocr
from core.pdf_reader import render_page_png


@pytest.fixture(scope="module")
def sample_pdf(request):
    fx = request.path.parent / "fixtures" / "sample.pdf"
    if not fx.exists():
        pytest.skip("PDF 샘플 없음")
    return str(fx)


def test_ocr_reads_korean(sample_pdf):
    if not ocr.available():
        pytest.skip("OCR 엔진 미설치")
    dpi = 170
    png = render_page_png(sample_pdf, 0, dpi=dpi)
    words = ocr.ocr_image(png, scale=72.0 / dpi)
    joined = " ".join(w.text.replace(" ", "") for w in words)
    # 한글 주요 단어 일부가 인식되어야 한다(정확도 100%는 아니어도)
    hits = sum(1 for k in ["하천", "조사", "구조물", "해남"] if k in joined)
    assert hits >= 2, f"한글 인식 부족: {joined[:120]}"


def test_word_positions_present(sample_pdf):
    if not ocr.available():
        pytest.skip("OCR 엔진 미설치")
    png = render_page_png(sample_pdf, 0, dpi=150)
    words = ocr.ocr_image(png, scale=72.0 / 150)
    assert words
    w = words[0]
    assert w.x1 > w.x0 and w.y1 > w.y0  # 유효한 박스
