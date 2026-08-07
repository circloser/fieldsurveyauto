"""layout.py — 유기적 정렬(퍼지 라벨 + 상대 앵커) 단위 테스트.

실제 PDF 없이 합성 단어(Word)로 '틀어짐/OCR 오타' 상황을 재현해 강건성을 검증한다.
"""
from core.layout import (
    find_label_fuzzy,
    label_relative_offset,
    value_by_anchor,
)
from core.pdf_reader import PdfPage, Word


def _page(words, ocr=False):
    pg = PdfPage(page_no=0, width=600, height=800, words=words)
    pg.ocr = ocr
    return pg


def _w(text, x0, y0, w=40, h=12):
    return Word(x0, y0, x0 + w, y0 + h, text)


def test_find_label_exact():
    pg = _page([_w("하천명", 100, 100), _w("해남천", 150, 100)])
    lw = find_label_fuzzy(pg, "하천명")
    assert lw is not None and abs(lw.x0 - 100) < 1


def test_find_label_fuzzy_ocr_typo():
    # OCR 오타: '하천명' → '하천멍' 도 찾아야 한다
    pg = _page([_w("하천멍", 100, 100), _w("해남천", 150, 100)], ocr=True)
    lw = find_label_fuzzy(pg, "하천명")
    assert lw is not None and abs(lw.x0 - 100) < 1


def test_find_label_combined_words():
    # '관리'+'기관' 결합 라벨 매칭
    pg = _page([_w("관리", 100, 100, w=30), _w("기관", 132, 100, w=30)])
    lw = find_label_fuzzy(pg, "관리기관")
    assert lw is not None and abs(lw.x0 - 100) < 1


def test_value_by_anchor_relation_right():
    pg = _page([_w("위도", 100, 100), _w("37.5124", 150, 100, w=60)])
    v = value_by_anchor(pg, {"label": "위도", "relation": "right"})
    assert v == "37.5124"


def test_value_by_anchor_relation_below():
    pg = _page([_w("보길이", 100, 100), _w("12.3", 100, 120, w=40)])
    v = value_by_anchor(pg, {"label": "보길이", "relation": "below"})
    assert v == "12.3"


def test_offset_is_shift_invariant():
    """핵심: 라벨 기준 offset 으로 저장하면 페이지가 통째로 밀려도 값이 따라온다."""
    # 설계 페이지: 라벨(100,100), 값 박스(150,100)-(210,112)
    label = _w("하천명", 100, 100)
    box = {"x0": 150, "y0": 100, "x1": 210, "y1": 112}
    offset = label_relative_offset(label, box)

    # 추출 페이지: 모든 것이 +50, +30 밀림 (양식 틀어짐 재현)
    shifted = _page([_w("하천명", 150, 130), _w("해남천", 200, 130, w=50)])
    v = value_by_anchor(shifted, {"label": "하천명", "offset": offset})
    assert v == "해남천"


def test_anchor_missing_returns_none():
    pg = _page([_w("무관한", 100, 100)])
    assert value_by_anchor(pg, {"label": "하천명", "relation": "right"}) is None
