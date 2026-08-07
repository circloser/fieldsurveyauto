"""유기적(내용 기준) 정렬 레이어 — 표 선(벡터 칸)에 의존하지 않고
라벨을 '단어+위치'로 찾아 값을 읽는다. 텍스트 PDF와 OCR(스캔·손글씨)을 동일 처리.

경진대회 계획 Phase 1-가 (양식 틀어짐 대응):
  1) 라벨 퍼지 매칭 — OCR 오타/띄어쓰기 편차('하천명'→'하천멍')를 견딘다.
  2) 상대 앵커(offset) — 값 위치를 '라벨 기준 상대 좌표'로 잡아, 페이지가 통째로
     밀리거나 배율이 달라도 값이 라벨을 따라가게 한다(절대좌표 폴백 최소화).

page.words 는 core.pdf_reader 에서 이미 벡터·OCR을 통합하므로, 이 레이어는 그 위에서
표 선 감지 없이 동작한다. (스캔본도 동일 경로)
"""
from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

from core.normalize import normalize, normalize_key
from core.pdf_reader import PdfPage, Word, words_in_bbox


def source_of(page: PdfPage) -> str:
    """이 페이지 단어의 출처: 'ocr'(스캔/손글씨) 또는 'vector'(텍스트 PDF)."""
    return "ocr" if page.ocr else "vector"


def _ratio(a: str, b: str) -> float:
    """한글은 자모(NFD) 단위로 비교 — OCR 오타('명'→'멍', 종성 1개 차이)에 관대."""
    if not a or not b:
        return 0.0
    ja = unicodedata.normalize("NFD", a)
    jb = unicodedata.normalize("NFD", b)
    return SequenceMatcher(None, ja, jb).ratio()


def _line_runs(page: PdfPage, max_run: int = 5):
    """같은 줄 연속 단어 결합 후보를 (결합키, 시작단어, 끝단어)로 생성.

    라벨이 여러 단어로 쪼개져 있어도('관리'+'기관') 결합해 매칭할 수 있게 한다.
    """
    lines: dict[int, list[Word]] = {}
    for w in page.words:
        lines.setdefault(round(w.cy / 4), []).append(w)
    for row in lines.values():
        row.sort(key=lambda w: w.x0)
        for i in range(len(row)):
            acc = ""
            for j in range(i, min(i + max_run, len(row))):
                acc += normalize_key(row[j].text)
                yield acc, row[i], row[j]


def find_label_fuzzy(page: PdfPage, label: str, min_ratio: float = 0.82) -> Word | None:
    """라벨과 가장 잘 맞는 단어(또는 같은 줄 결합)를 찾는다.

    우선순위: 완전일치 → 부분포함 → 퍼지(유사도 ≥ min_ratio). 못 찾으면 None.
    """
    want = normalize_key(label)
    if not want:
        return None

    exact: Word | None = None
    fuzzy: Word | None = None
    fuzzy_score = min_ratio
    for key, a, b in _line_runs(page):
        if not key:
            continue
        cand = Word(a.x0, min(a.y0, b.y0), b.x1, max(a.y1, b.y1), label)
        if key == want:
            # 가장 짧게 정확히 맞는 결합 우선(불필요한 확장 방지)
            if exact is None or (b.x1 - a.x0) < (exact.x1 - exact.x0):
                exact = cand
        elif len(key) <= len(want) + 3:
            s = _ratio(want, key)
            if s > fuzzy_score:
                fuzzy_score, fuzzy = s, cand
    if exact is not None:
        return exact

    # 부분 포함(라벨이 값과 한 셀에 붙어 들어간 경우 등)
    for w in page.words:
        if want in normalize_key(w.text):
            return w
    return fuzzy


def label_relative_offset(label_word: Word, box: dict) -> dict:
    """설계 시점: 값 박스를 '라벨 기준 상대 오프셋'으로 변환(저장용).

    이렇게 저장하면 추출 시 라벨만 찾으면 값 영역을 상대적으로 재구성할 수 있어
    페이지 전체가 밀려도 값이 어긋나지 않는다.
    """
    return {
        "dx0": round(float(box["x0"]) - label_word.x0, 1),
        "dy0": round(float(box["y0"]) - label_word.y0, 1),
        "dx1": round(float(box["x1"]) - label_word.x0, 1),
        "dy1": round(float(box["y1"]) - label_word.y0, 1),
    }


def _read_region(page: PdfPage, region: dict) -> str:
    ws = words_in_bbox(page, region)
    return normalize(" ".join(w.text for w in ws))


def _same_line(a: Word, b: Word) -> bool:
    return abs(a.cy - b.cy) < max(a.y1 - a.y0, b.y1 - b.y0) * 0.6


def _read_relation(page: PdfPage, lw: Word, rel: str, gap: float = 45.0) -> str:
    if rel == "self":
        return normalize(lw.text)
    if rel == "below":
        cands = [w for w in page.words
                 if w.y0 >= lw.y1 - 1 and abs(w.cx - lw.cx) < (lw.x1 - lw.x0) + 30]
        cands.sort(key=lambda w: (w.cy, w.cx))
        if not cands:
            return ""
        base = cands[0].cy
        return normalize(" ".join(w.text for w in cands if abs(w.cy - base) < 6))
    # right
    row = [w for w in page.words if w.x0 >= lw.x1 - 1 and _same_line(w, lw)]
    row.sort(key=lambda w: w.x0)
    picked, prev = [], None
    for w in row:
        if prev is not None and w.x0 - prev > gap:
            break
        picked.append(w)
        prev = w.x1
    return normalize(" ".join(w.text for w in picked))


def value_by_anchor(page: PdfPage, anchor: dict, min_ratio: float = 0.82) -> str | None:
    """라벨 앵커로 값을 읽는다.

    - offset 이 있으면 상대영역으로 읽어 '밀림'에 강함(권장, 설계 시 저장).
    - 없으면 relation(right/below/self) 방향으로 읽음(기존 호환).
    라벨을 못 찾으면 None → 호출부에서 좌표 방식으로 폴백하게 한다.
    """
    label = anchor.get("label") or ""
    lw = find_label_fuzzy(page, label, min_ratio)
    if lw is None:
        return None
    offset = anchor.get("offset")
    if offset:
        region = {
            "x0": lw.x0 + offset["dx0"], "y0": lw.y0 + offset["dy0"],
            "x1": lw.x0 + offset["dx1"], "y1": lw.y0 + offset["dy1"],
        }
        return _read_region(page, region)
    return _read_relation(page, lw, anchor.get("relation", "right"))
