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


def detect_title(pdf_path: str, page_no: int) -> dict | None:
    """페이지 상단의 '큰 글씨'(제목)를 찾는다 → {text, x0,y0,x1,y1} 또는 None.

    기준: 글꼴 크기가 본문 중앙값보다 확실히 크고(≥1.25배), 페이지 위쪽 30% 안.
    같은 줄의 큰 글씨 span 들을 이어붙여 한 줄 제목으로 만든다.
    """
    import statistics

    import fitz

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no]
        h = page.rect.height
        spans = []
        for b in page.get_text("dict").get("blocks", []):
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    t = (s.get("text") or "").strip()
                    if t:
                        spans.append((s["bbox"], float(s.get("size", 0)), t))
    finally:
        doc.close()
    if len(spans) < 3:
        return None
    med = statistics.median(sz for _, sz, _ in spans)
    big = [s for s in spans if s[1] >= max(med * 1.25, med + 2) and s[0][1] < h * 0.30]
    if not big:
        return None
    # 줄 단위로 묶어 가장 큰(동률이면 가장 위) 줄을 제목으로
    lines: dict[int, list] = {}
    for s in big:
        lines.setdefault(round(s[0][1] / 6), []).append(s)
    best = max(lines.values(), key=lambda row: (max(x[1] for x in row), -min(x[0][1] for x in row)))
    best.sort(key=lambda x: x[0][0])
    text = normalize(" ".join(x[2] for x in best))
    if len(text) < 2:
        return None
    x0 = min(x[0][0] for x in best) - 2
    y0 = min(x[0][1] for x in best) - 2
    x1 = max(x[0][2] for x in best) + 2
    y1 = max(x[0][3] for x in best) + 2
    return {"text": text, "x0": round(x0, 1), "y0": round(y0, 1),
            "x1": round(x1, 1), "y1": round(y1, 1)}


# ---------- 픽셀박스 추출 ----------

def _cell_anchor_value(cells: list[Cell], box: dict,
                       return_cell: bool = False):
    """유기적 추출 — 입력 페이지의 표 칸에서 라벨 칸을 찾아 인접 값 칸을 읽는다.

    조사표에 줄이 추가되거나 위치가 밀려도 라벨을 따라가므로 값이 어긋나지 않는다.
    같은 라벨이 여러 개면 템플릿 박스 위치에 가장 가까운 것을 고른다.
    라벨 칸을 못 찾으면 None(호출부에서 좌표 방식으로 폴백).
    """
    anchor = box.get("anchor") or {}
    want = normalize_key(anchor.get("label") or "")
    if not want or not cells:
        return None
    cands = [c for c in cells if normalize_key(c.text) == want]
    if not cands:
        cands = [c for c in cells if want and want in normalize_key(c.text)]
    if not cands:
        return None
    bx, by = float(box["x0"]), float(box["y0"])
    lab = min(cands, key=lambda c: (c.x0 - bx) ** 2 + (c.y0 - by) ** 2)
    rel = anchor.get("relation", "right")
    if rel == "below":
        nxt = [c for c in cells if abs(c.y0 - lab.y1) < 4 and _hoverlap(lab, c)]
        nxt.sort(key=lambda c: c.y0)
    else:
        nxt = [c for c in cells if abs(c.x0 - lab.x1) < 4 and _voverlap(lab, c)]
        nxt.sort(key=lambda c: c.x0)
    if not nxt:
        return None
    val = normalize(nxt[0].text)
    return (val, nxt[0]) if return_cell else val


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


def match_bundles(boxes: list[dict], pages: list[PdfPage],
                  threshold: float = 0.35, max_bundles: int = 200) -> list[dict[int, int]]:
    """한 파일 안에 같은 서식이 여러 묶음 반복될 때, 묶음마다 페이지 매핑을 찾는다.

    match_pages 를 반복 적용: 매칭된 입력 페이지를 제외하고 다시 매칭 → 다음 묶음.
    반환: [ {템플릿_페이지: 입력_페이지}, ... ] (묶음 순서 = 입력 페이지 순서).
    안전장치: 두 번째 묶음부터는 첫 묶음 매칭 페이지 수의 절반 이상 매칭돼야
    묶음으로 인정(꼬리 페이지의 우연한 약한 매칭으로 헛 행이 생기지 않게).
    """
    remaining = list(pages)
    bundles: list[dict[int, int]] = []
    first_n = 0
    while remaining and len(bundles) < max_bundles:
        m = match_pages(boxes, remaining, threshold)
        if not m:
            break
        if bundles and len(m) < max(1, round(first_n * 0.5)):
            break  # 첫 묶음보다 훨씬 부실한 매칭 → 진짜 묶음 아님
        if not bundles:
            first_n = len(m)
        bundles.append(m)
        used = set(m.values())
        remaining = [p for p in remaining if p.page_no not in used]
    # 묶음을 문서 순서(첫 매칭 페이지 기준)로 정렬해 행 순서를 자연스럽게
    bundles.sort(key=lambda mm: min(mm.values()))
    return bundles


def apply_pixel_template(pages: list[PdfPage], boxes: list[dict],
                         page_map: dict[int, int] | None = None,
                         pdf_path: str | None = None) -> dict[str, str]:
    """박스를 적용해 {field: value}. page_map 이 있으면 템플릿 페이지를 입력 페이지로 치환.

    pdf_path 를 주면 유기적 추출: 입력 페이지의 표 칸을 감지해 라벨 칸 기준으로 값을
    읽는다(줄 추가·위치 밀림에 강함). 라벨을 못 찾은 박스만 좌표 방식으로 폴백.
    """
    import statistics

    ordered = sorted(boxes, key=lambda b: b.get("order", 0))
    by_page = {p.page_no: p for p in pages}
    cells_cache: dict[int, list[Cell]] = {}
    title_cache: dict[int, dict | None] = {}

    def cells_for(pno: int) -> list[Cell]:
        if pno not in cells_cache:
            try:
                cells_cache[pno] = detect_cells(pdf_path, pno)
            except Exception:  # noqa: BLE001
                cells_cache[pno] = []
        return cells_cache[pno]

    def title_for(pno: int) -> dict | None:
        if pno not in title_cache:
            try:
                title_cache[pno] = detect_title(pdf_path, pno)
            except Exception:  # noqa: BLE001
                title_cache[pno] = None
        return title_cache[pno]

    # 1차: 라벨(칸-앵커)로 읽고, 성공한 박스의 '이동량'을 페이지별로 수집
    results: dict[int, str] = {}
    resolved: dict[int, PdfPage | None] = {}
    deltas: dict[int, list[tuple[float, float]]] = {}
    for i, b in enumerate(ordered):
        tpage = int(b.get("page", 0))
        if page_map is not None:
            ipage = page_map.get(tpage)
            page = by_page.get(ipage) if ipage is not None else None
        else:
            page = by_page.get(tpage)
        resolved[i] = page
        if page is None:
            results[i] = ""
            continue
        if pdf_path and b.get("mode", "text") == "text" and (b.get("anchor") or {}).get("label"):
            cells = cells_for(page.page_no)
            if cells:
                r = _cell_anchor_value(cells, b, return_cell=True)
                if r is not None:
                    val, vcell = r
                    results[i] = val
                    deltas.setdefault(page.page_no, []).append(
                        (vcell.x0 - float(b["x0"]), vcell.y0 - float(b["y0"])))
                    continue
        # 미해결 → 2차에서 처리

    # 페이지별 오프셋(중앙값) — 라벨 성공 3개 이상일 때만 신뢰
    offset: dict[int, tuple[float, float]] = {}
    for pno, ds in deltas.items():
        if len(ds) >= 3:
            dx = statistics.median(d[0] for d in ds)
            dy = statistics.median(d[1] for d in ds)
            if abs(dx) > 2 or abs(dy) > 2:
                offset[pno] = (dx, dy)

    # 2차: 라벨이 없거나 못 찾은 박스 — 제목은 페이지의 큰 글씨로, 나머지는
    # 오프셋 보정된 좌표로 읽는다(양식이 통째로 밀린 경우 같이 따라감).
    for i, b in enumerate(ordered):
        if i in results:
            continue
        page = resolved[i]
        if page is None:
            results[i] = ""
            continue
        if b.get("mode") == "title" and pdf_path is not None:
            t = title_for(page.page_no)
            if t and t.get("text"):
                results[i] = t["text"]
                continue
        bb = b
        d = offset.get(page.page_no)
        if d:
            bb = dict(b)
            bb["x0"] = float(b["x0"]) + d[0]
            bb["x1"] = float(b["x1"]) + d[0]
            bb["y0"] = float(b["y0"]) + d[1]
            bb["y1"] = float(b["y1"]) + d[1]
        results[i] = _box_value(page, bb)

    return {b["field"]: results[i] for i, b in enumerate(ordered)}


def field_order(boxes: list[dict]) -> list[str]:
    return [b["field"] for b in sorted(boxes, key=lambda b: b.get("order", 0))]
