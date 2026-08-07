"""layout_fingerprint.py — 배치 기반 양식 매칭 단위 테스트.

핵심 검증:
  1) 같은 배치인데 통째로 밀리거나 배율이 달라도 높은 유사도(밀림/스케일 불변).
  2) 제목/사무실명이 달라도 매칭됨(제목은 지문에서 제외).
  3) 라벨은 같아도 배치가 흐트러지면 유사도 하락.
"""
from core.layout_fingerprint import from_words, match
from core.pdf_reader import PdfPage, Word


def _page(words):
    return PdfPage(page_no=0, width=600, height=800, words=words)


def _w(text, x0, y0, w=40, h=12):
    return Word(x0, y0, x0 + w, y0 + h, text)


# 표준 양식: 라벨 4개가 특정 배치
def _standard():
    return _page([
        _w("하천명", 100, 100),
        _w("대권역", 300, 100),
        _w("위도", 100, 200),
        _w("경도", 300, 200),
    ])


def test_same_layout_shifted_and_scaled_matches_high():
    tmpl = from_words(_standard())
    # 모든 라벨 +80,+60 밀고 1.2배 확대 — 배치(위상)는 동일
    shifted = _page([
        _w("하천명", 100 * 1.2 + 80, 100 * 1.2 + 60),
        _w("대권역", 300 * 1.2 + 80, 100 * 1.2 + 60),
        _w("위도", 100 * 1.2 + 80, 200 * 1.2 + 60),
        _w("경도", 300 * 1.2 + 80, 200 * 1.2 + 60),
    ])
    assert match(tmpl, from_words(shifted)) > 0.9


def test_different_title_still_matches():
    tmpl = from_words(_standard())
    # 제목 토큰('...현장조사표')이 붙어도 지문에서 제외되므로 영향 없음
    with_title = _page([
        _w("인공구조물현장조사표", 100, 40),   # 제목 — 제외 대상
        _w("하천명", 100, 100),
        _w("대권역", 300, 100),
        _w("위도", 100, 200),
        _w("경도", 300, 200),
    ])
    assert match(tmpl, from_words(with_title)) > 0.9


def test_scrambled_layout_scores_lower():
    tmpl = from_words(_standard())
    # 라벨은 같은데 배치가 뒤섞임 → 위치 일치도 하락
    scrambled = _page([
        _w("경도", 100, 100),
        _w("위도", 300, 100),
        _w("대권역", 100, 200),
        _w("하천명", 300, 200),
    ])
    high = match(tmpl, from_words(_standard()))
    low = match(tmpl, from_words(scrambled))
    assert low < high


def test_unrelated_page_scores_low():
    tmpl = from_words(_standard())
    other = _page([_w("종명", 100, 100), _w("개체수", 300, 100), _w("전장", 100, 200)])
    assert match(tmpl, from_words(other)) < 0.4
