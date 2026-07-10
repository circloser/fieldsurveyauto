"""PDF 통합 파이프라인 — 입력(hwpx/pdf) → PDF → 위치 읽기 → 픽셀박스 추출.

디자이너는 PDF 페이지 이미지 위에 픽셀 박스를 그린다. 박스 좌표는 PDF 포인트 단위로
저장하므로 화면 배율과 무관하게 재현된다.
"""
from __future__ import annotations

import os

from core.normalize import has_check_mark, normalize, normalize_key
from core.pdf_reader import (
    Cell,
    PdfPage,
    detect_cells,
    read_pdf,
    text_in_bbox,
    value_by_label,
    value_words,
    words_in_bbox,
)

# 라벨스러운 단어 판정(자동 제안용)
import re as _re
_LABELISH = _re.compile(r"[가-힣]")


def _looks_like_label(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 10:
        return False
    if _re.match(r"^[\d(]", t):
        return False
    if not _LABELISH.search(t):
        return False
    if any(m in t for m in ("※", "붙임", "참고", "√", "■", "□")):
        return False
    # 제목/안내성 단어는 라벨(추출 항목) 아님
    if any(k in t for k in ("조사표", "현장", "제원", "측정", "기재", "방법")):
        return False
    return True


def to_pdf(src: str, cache_dir: str) -> str:
    """입력을 PDF로 만든다. pdf는 그대로, hwpx/hwp는 한글로 변환."""
    ext = os.path.splitext(src)[1].lower()
    if ext == ".pdf":
        return src
    if ext in (".hwpx", ".hwp"):
        from core.convert import hwpx_to_pdf
        base = os.path.splitext(os.path.basename(src))[0]
        out = os.path.join(cache_dir, base + ".pdf")
        return hwpx_to_pdf(src, out)
    raise ValueError(f"지원하지 않는 형식: {ext}")


# ---------- 자동 박스 제안 ----------

def _wkey(w) -> tuple:
    return (round(w.x0, 1), round(w.y0, 1), w.text)


def _same_line(a, b) -> bool:
    return abs(a.cy - b.cy) < max(a.y1 - a.y0, b.y1 - b.y0) * 0.6


def _value_right(page: PdfPage, lw, gap: float = 45.0) -> list:
    row = [w for w in page.words if w.x0 >= lw.x1 - 1 and _same_line(w, lw)]
    row.sort(key=lambda w: w.x0)
    picked, prev = [], None
    for w in row:
        if prev is not None and w.x0 - prev > gap:
            break
        picked.append(w)
        prev = w.x1
    return picked


def _value_below(page: PdfPage, lw) -> list:
    cands = [w for w in page.words
             if w.y0 >= lw.y1 - 1 and abs(w.cx - lw.cx) < 40]
    cands.sort(key=lambda w: (w.cy, w.cx))
    if not cands:
        return []
    base = cands[0].cy
    if base - lw.y1 > 30:  # 너무 멀면(다른 행) 값 아님
        return []
    return [w for w in cands if abs(w.cy - base) < 6]


# 값이 '명백한 데이터'인지: 숫자·좌표·체크·날짜 기호 포함
_DATAISH = _re.compile(r"[0-9√°′″㎜%]")


def _voverlap(a: Cell, b: Cell) -> bool:
    return a.y0 < b.y1 - 1 and a.y1 > b.y0 + 1


def _hoverlap(a: Cell, b: Cell) -> bool:
    return a.x0 < b.x1 - 1 and a.x1 > b.x0 + 1


def suggest_from_cells(pdf_path: str, page_no: int) -> list[dict]:
    """표 칸(테두리) 기반 자동 제안 — 라벨 칸의 인접 값 칸에 박스를 만든다.

    칸이 명확한 사각형이라 단어 위치 방식보다 훨씬 정확. 값 칸은 소비해 라벨로
    재사용하지 않아 과다 제안을 막는다.
    """
    cells = detect_cells(pdf_path, page_no)
    if not cells:
        return []
    order_cells = sorted(range(len(cells)), key=lambda i: (round(cells[i].y0), cells[i].x0))

    def right_of(c: Cell):
        best, bx = None, 1e9
        for d in cells:
            if d is c:
                continue
            if abs(d.x0 - c.x1) < 4 and _voverlap(c, d) and d.x0 < bx:
                best, bx = d, d.x0
        return best

    def below_of(c: Cell):
        best, by = None, 1e9
        for d in cells:
            if d is c:
                continue
            if abs(d.y0 - c.y1) < 4 and _hoverlap(c, d) and d.y0 < by:
                best, by = d, d.y0
        return best

    consumed: set[int] = set()
    used_targets: set[int] = set()   # 값 칸으로 이미 박스가 생긴 칸(중복 방지)
    idx_of = {id(cells[i]): i for i in range(len(cells))}
    boxes: list[dict] = []
    order = 0
    for i in order_cells:
        if i in consumed:
            continue
        c = cells[i]
        if not c.text or not _looks_like_label(c.text):
            continue
        r, b = right_of(c), below_of(c)
        value, rel = None, None
        if r is not None and not _looks_like_label(r.text):
            value, rel = r, "right"
        elif b is not None and not _looks_like_label(b.text):
            value, rel = b, "below"
        elif r is not None:
            value, rel = r, "right"
        elif b is not None:
            value, rel = b, "below"
        if value is None:
            continue
        vi = idx_of.get(id(value))
        if vi is not None:
            if vi in used_targets:
                continue   # 같은 칸에 이미 박스가 있으면 중복 생성 안 함
            used_targets.add(vi)
            consumed.add(vi)
        order += 1
        boxes.append({
            "order": order,
            "field": c.text.strip()[:20],
            "page": page_no,
            "x0": round(value.x0, 1), "y0": round(value.y0, 1),
            "x1": round(value.x1, 1), "y1": round(value.y1, 1),
            "mode": "text",
            "anchor": {"label": c.text.strip(), "relation": rel},
            "use_anchor": False,   # 칸 사각형이 정확 → 위치(칸) 기준 기본, 앵커는 선택
            "suggested": True,
            "from_cell": True,
        })
    # 문서 위치 순서로 order 재부여
    for n, bx in enumerate(sorted(boxes, key=lambda z: (z["y0"], z["x0"])), start=1):
        bx["order"] = n
    return boxes


def suggest_cells_maximal(pdf_path: str, page_no: int) -> list[dict]:
    """모든 표 칸에 박스를 만든다(최대 생성 → 사용자가 삭제).

    각 칸의 왼쪽/위 라벨을 이름으로 쓰고, 빈 여백 칸(텍스트도 라벨이웃도 없음)만 제외.
    """
    cells = detect_cells(pdf_path, page_no)
    if not cells:
        return []

    def left_of(c: Cell):
        best, bx = None, -1
        for d in cells:
            if d is c:
                continue
            if abs(d.x1 - c.x0) < 4 and _voverlap(c, d) and d.x1 > bx:
                best, bx = d, d.x1
        return best

    def top_of(c: Cell):
        best, by = None, -1
        for d in cells:
            if d is c:
                continue
            if abs(d.y1 - c.y0) < 4 and _hoverlap(c, d) and d.y1 > by:
                best, by = d, d.y1
        return best

    boxes: list[dict] = []
    seen: set[tuple] = set()
    for c in cells:
        left, top = left_of(c), top_of(c)
        label, rel = "", "right"
        if left is not None and _looks_like_label(left.text):
            label, rel = left.text.strip(), "right"
        elif top is not None and _looks_like_label(top.text):
            label, rel = top.text.strip(), "below"
        # 내용이 없는 칸도 박스로 만든다(다른 양식에선 채워질 수 있음).
        field = (label or c.text or "칸").strip()[:20]
        key = (round(c.x0), round(c.y0))
        if key in seen:
            continue
        seen.add(key)
        box = {
            "field": field, "page": page_no,
            "x0": round(c.x0, 1), "y0": round(c.y0, 1),
            "x1": round(c.x1, 1), "y1": round(c.y1, 1),
            "mode": "text", "use_anchor": False, "suggested": True, "from_cell": True,
            "anchor": {"label": label, "relation": rel} if label else None,
        }
        boxes.append(box)
    for n, b in enumerate(sorted(boxes, key=lambda z: (z["y0"], z["x0"])), start=1):
        b["order"] = n
    return boxes


def suggest_pixel_boxes(page: PdfPage) -> list[dict]:
    """보수적 자동 제안 — '라벨 오른쪽에 명백한 데이터(숫자·좌표·체크)'인 경우만.

    순수 한글 값(하천명→해남천 등)은 라벨/값 구분이 애매해 오검출이 잦으므로
    자동 제안하지 않고, 사용자가 실제 문서 위에 직접 그리도록 둔다(깨끗한 소수 제안).
    """
    words = sorted(page.words, key=lambda w: (round(w.cy / 4), w.x0))
    consumed: set[tuple] = set()
    placed: list[tuple[float, float, float, float]] = []
    boxes: list[dict] = []

    def overlaps(x0, y0, x1, y1) -> bool:
        for px0, py0, px1, py1 in placed:
            ix = min(x1, px1) - max(x0, px0)
            iy = min(y1, py1) - max(y0, py0)
            if ix > 0 and iy > 0 and (x1 - x0):
                if (ix * iy) / ((x1 - x0) * (y1 - y0)) > 0.4:
                    return True
        return False

    order = 0
    for lw in words:
        if _wkey(lw) in consumed or not _looks_like_label(lw.text):
            continue
        picked = _value_right(page, lw)
        if not picked:
            continue
        joined = " ".join(w.text for w in picked)
        # 명백한 데이터 값만 제안(오검출 최소화)
        if not _DATAISH.search(joined):
            continue
        span = max(w.x1 for w in picked) - min(w.x0 for w in picked)
        if span > 170 or len(picked) > 5:
            continue
        for w in picked:
            consumed.add(_wkey(w))
        x0 = min(w.x0 for w in picked) - 2
        y0 = min(w.y0 for w in picked) - 2
        x1 = max(w.x1 for w in picked) + 2
        y1 = max(w.y1 for w in picked) + 2
        if overlaps(x0, y0, x1, y1):
            continue
        placed.append((x0, y0, x1, y1))
        order += 1
        boxes.append({
            "order": order,
            "field": lw.text.strip(),
            "page": page.page_no,
            "x0": round(x0, 1), "y0": round(y0, 1), "x1": round(x1, 1), "y1": round(y1, 1),
            "mode": "text",
            "anchor": {"label": lw.text.strip(), "relation": "right"},
            "use_anchor": True,
            "suggested": True,
        })
    return boxes


# ---------- 픽셀박스 추출 ----------

def _box_value(page: PdfPage, box: dict) -> str:
    mode = box.get("mode", "text")
    bbox = {"x0": box["x0"], "y0": box["y0"], "x1": box["x1"], "y1": box["y1"]}

    # 라벨 앵커 우선(text/bold) — 못 찾으면 박스 좌표로 폴백
    anchor = box.get("anchor")
    if anchor and box.get("use_anchor", True) and anchor.get("label") and mode in ("text", "bold"):
        v = value_by_label(page, anchor["label"], anchor.get("relation", "right"),
                           bold_only=(mode == "bold"))
        if v:
            return v

    if mode == "check":
        ws = words_in_bbox(page, bbox)
        if not any(has_check_mark(w.text) for w in ws):
            return ""  # 체크 없으면 빈 값
        return normalize(" ".join(w.text for w in ws if not has_check_mark(w.text)))

    return text_in_bbox(page, bbox, bold_only=(mode == "bold"))


def match_pages(boxes: list[dict], pages: list[PdfPage], threshold: float = 0.35) -> dict[int, int]:
    """템플릿 페이지 ↔ 입력 페이지를 라벨 지문 유사도로 매칭.

    반환: {템플릿_페이지: 입력_페이지}. 매칭 못 하면 그 템플릿 페이지는 빠짐.
    9장 중 3장만 있어도, 순서가 달라도 서식이 비슷한 페이지를 찾아 연결한다.
    """
    tmpl: dict[int, set[str]] = {}
    for b in boxes:
        lbl = ((b.get("anchor") or {}).get("label")) or b.get("field") or ""
        k = normalize_key(lbl)
        if k and k != "칸":
            tmpl.setdefault(int(b["page"]), set()).add(k)
    # 입력 페이지 본문(단어 이어붙인 정규화 문자열) — 여러 단어 라벨도 부분포함으로 매칭
    inp_text = {p.page_no: normalize_key("".join(w.text for w in p.words)) for p in pages}

    pairs = []
    for tp, labels in tmpl.items():
        if not labels:
            continue
        for ip, text in inp_text.items():
            hit = sum(1 for l in labels if l in text)
            pairs.append((hit / len(labels), tp, ip))
    pairs.sort(key=lambda x: -x[0])

    mapping: dict[int, int] = {}
    used: set[int] = set()
    for score, tp, ip in pairs:
        if tp in mapping or ip in used or score < threshold:
            continue
        mapping[tp] = ip
        used.add(ip)
    return mapping


def apply_pixel_template(pages: list[PdfPage], boxes: list[dict],
                         page_map: dict[int, int] | None = None) -> dict[str, str]:
    """박스를 적용해 {field: value}. page_map 이 있으면 템플릿 페이지를 입력 페이지로 치환."""
    ordered = sorted(boxes, key=lambda b: b.get("order", 0))
    by_page = {p.page_no: p for p in pages}
    out: dict[str, str] = {}
    for b in ordered:
        tpage = int(b.get("page", 0))
        if page_map is not None:
            ipage = page_map.get(tpage)
            page = by_page.get(ipage) if ipage is not None else None
        else:
            page = by_page.get(tpage)
        out[b["field"]] = _box_value(page, b) if page else ""
    return out


def field_order(boxes: list[dict]) -> list[str]:
    return [b["field"] for b in sorted(boxes, key=lambda b: b.get("order", 0))]
