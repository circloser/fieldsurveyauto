"""form_router / detect_form_words — 페이지 단어 기반 서식 판별 테스트(네트워크 불필요)."""
from core.extraction.form_detector import FORM_A, FORM_C, FORM_D, FORM_UNKNOWN
from core.form_router import route_page
from core.pdf_reader import PdfPage, Word


def _page(texts):
    words = [Word(0, i * 10, 40, i * 10 + 8, t) for i, t in enumerate(texts)]
    return PdfPage(page_no=0, width=600, height=800, words=words)


def test_route_form_a():
    # A 시그니처: 보길이/보마루폭/월류수심/물받이길이 등
    pg = _page(["인공 구조물", "보 길이", "보 마루폭", "월류수심", "물받이 길이"])
    assert route_page(pg).form_type == FORM_A


def test_route_form_c():
    # C 시그니처: 어도상태/평균경사도/계단식/아이스하버식
    pg = _page(["어도 현장", "어도 상태", "평균경사도", "아이스하버식", "계단식"])
    assert route_page(pg).form_type == FORM_C


def test_route_form_d():
    pg = _page(["어류 조사", "종명", "개체수", "전장"])
    assert route_page(pg).form_type == FORM_D


def test_route_unknown_when_no_signals():
    pg = _page(["안녕하세요", "무관한 문서", "표 아님"])
    assert route_page(pg).form_type == FORM_UNKNOWN


def test_title_change_does_not_break_routing():
    # 제목이 달라도(라벨 시그니처 기반) A로 판별되어야 함
    pg = _page(["○○시 특수 양식", "보 길이", "보 하단폭", "배사구 높이"])
    assert route_page(pg).form_type == FORM_A
