"""레이아웃 지문 — 양식의 정체성을 '제목'이 아니라 '라벨들의 전체 공간 배치'로 정의.

경진대회 계획 Phase 1-나 (제목 바뀌면 다른 양식 문제):
  제목/사무실명이 달라도 배치가 같으면 같은 양식으로 인식하게 한다.

지문 = 라벨 텍스트 + 정규화 위치. 위치는 '라벨 집합의 바운딩박스' 기준 0..1 로 정규화하므로,
페이지가 밀리거나(스캔 여백차) 배율이 달라도 배치(위상)만 같으면 높은 유사도가 나온다.
제목·안내성 토큰은 지문에서 제외해 '제목 의존성'을 없앤다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from core.normalize import normalize_key
from core.pdf_reader import PdfPage

# 제목/안내성 토큰 — 지문에서 제외(양식 정체성이 아님)
_TITLEISH = ("조사표", "현장", "제원", "측정", "기재", "방법", "붙임", "참고", "지침", "작성")


def _is_labelish(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 12:
        return False
    if any(k in t for k in _TITLEISH):
        return False
    # 한글이 있어야 라벨로 간주(숫자·기호 값은 제외)
    return any("가" <= ch <= "힣" for ch in t)


@dataclass
class Fingerprint:
    labels: list[tuple[str, float, float]] = field(default_factory=list)  # (키, nx, ny)

    def keys(self) -> set[str]:
        return {k for k, _, _ in self.labels}


def _normalize_positions(items: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    """라벨 위치들을 그 바운딩박스 기준 0..1 로 정규화(밀림·배율 불변)."""
    if not items:
        return []
    xs = [x for _, x, _ in items]
    ys = [y for _, _, y in items]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = (maxx - minx) or 1.0
    h = (maxy - miny) or 1.0
    return [(k, (x - minx) / w, (y - miny) / h) for k, x, y in items]


def _dedup(items: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    seen: set[str] = set()
    out = []
    for k, x, y in items:
        if k and k not in seen:
            seen.add(k)
            out.append((k, x, y))
    return out


def from_words(page: PdfPage) -> Fingerprint:
    """입력 페이지 단어에서 라벨스러운 것만 골라 지문 생성."""
    items = [(normalize_key(w.text), w.cx, w.cy) for w in page.words if _is_labelish(w.text)]
    return Fingerprint(_normalize_positions(_dedup(items)))


def from_boxes(boxes: list[dict]) -> Fingerprint:
    """템플릿(박스 정의)에서 지문 생성 — 박스 앵커 라벨/필드명과 박스 중심 위치 사용."""
    items = []
    for b in boxes:
        lbl = ((b.get("anchor") or {}).get("label")) or b.get("field") or ""
        k = normalize_key(lbl)
        if not k or k == "칸":
            continue
        cx = (float(b["x0"]) + float(b["x1"])) / 2
        cy = (float(b["y0"]) + float(b["y1"])) / 2
        items.append((k, cx, cy))
    return Fingerprint(_normalize_positions(_dedup(items)))


def _key_match(a: str, b: str) -> bool:
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def match(template: Fingerprint, page: Fingerprint) -> float:
    """0..1 배치 유사도 = 라벨 존재율 × 위치 일치도.

    - 라벨 존재율: 템플릿 라벨 중 입력에서 (퍼지로) 발견된 비율.
    - 위치 일치도: 발견된 라벨쌍의 정규화 좌표 평균거리로 산출.
    제목이 달라도(지문 제외) 배치가 같으면 높게 나온다.
    """
    if not template.labels:
        return 0.0
    used: set[int] = set()
    pairs: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for tk, tx, ty in template.labels:
        for i, (pk, px, py) in enumerate(page.labels):
            if i in used:
                continue
            if _key_match(tk, pk):
                pairs.append(((tx, ty), (px, py)))
                used.add(i)
                break
    if not pairs:
        return 0.0
    presence = len(pairs) / len(template.labels)
    dist = sum(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
               for (ax, ay), (bx, by) in pairs) / len(pairs)
    spatial = max(0.0, 1.0 - dist)          # 정규화 좌표라 거리≈0 이면 1.0
    return round(presence * (0.5 + 0.5 * spatial), 3)


def best_match(template: Fingerprint, pages: list[PdfPage],
               threshold: float = 0.4) -> int | None:
    """여러 입력 페이지 중 템플릿 배치와 가장 잘 맞는 페이지 번호. 임계 미만이면 None."""
    best_pno, best_score = None, threshold
    for p in pages:
        s = match(template, from_words(p))
        if s > best_score:
            best_score, best_pno = s, p.page_no
    return best_pno
