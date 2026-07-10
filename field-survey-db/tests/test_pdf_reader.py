"""PDF 통합 경로 검증 — 텍스트/위치 추출, 라벨 앵커, 굵게, 박스, 렌더."""
import pytest

from core.pdf_reader import (
    find_label_word,
    read_pdf,
    render_page_png,
    text_in_bbox,
    value_by_label,
)


@pytest.fixture(scope="module")
def page0(request):
    fx = request.path.parent / "fixtures" / "sample.pdf"
    if not fx.exists():
        pytest.skip("PDF 샘플 없음(한글 변환 필요)")
    return read_pdf(str(fx)).pages[0], str(fx)


def test_pdf_has_text_words(page0):
    p, _ = page0
    assert len(p.words) > 50
    assert not p.needs_ocr  # 타이핑 PDF는 텍스트 있음


def test_label_anchor_right(page0):
    p, _ = page0
    assert value_by_label(p, "하천명", "right") == "해남천"
    assert "34" in value_by_label(p, "위도", "right")
    assert value_by_label(p, "관리 기관", "right") == "전남 해남군"  # 여러 단어 라벨+값
    assert value_by_label(p, "조사자 1", "right") == "나긍환"


def test_bold_only_extraction(page0):
    p, _ = page0
    # 기상상태: 선택된 날씨(흐림)만 굵게
    assert value_by_label(p, "기상상태", "right", bold_only=True) == "흐림"


def test_box_extraction(page0):
    p, _ = page0
    lw = find_label_word(p, "해남천")
    assert lw is not None
    bbox = {"x0": lw.x0 - 5, "y0": lw.y0 - 3, "x1": lw.x1 + 5, "y1": lw.y1 + 3}
    assert text_in_bbox(p, bbox) == "해남천"


def test_render_page(page0):
    _, path = page0
    png = render_page_png(path, 0, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 시그니처
    assert len(png) > 10000
