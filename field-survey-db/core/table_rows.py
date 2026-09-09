"""표(여러 행) 추출 — 머리글 한 줄 + 데이터 여러 줄인 표를 '데이터 행마다 한 건'으로 뽑는다.

예) 담당자 현황 제출서: [기관명 | 관리 하천명 | 담당부서 | 직위 | 성명 | 연락처 | 이메일] 아래 3~4줄.
    → 줄마다 엑셀 한 행(열 = 머리글). 세로로 합쳐진 칸(기관명이 여러 줄에 걸침)은 걸친 줄마다 채운다.

격자(칸) 찾기:
· 글자 PDF: 표 선(pdfplumber) → 칸 사각형(합쳐진 칸은 큰 사각형 하나)
· 스캔본:   이미지에서 긴 가로·세로 선을 찾아 격자를 만들고, 칸 사이에 선이 없으면 합쳐진 칸으로 본다
칸 글자는 페이지 단어(OCR 포함) 가운데 칸 안에 중심이 든 것들.
"""
from __future__ import annotations

import re

from core.normalize import normalize
from core.pdf_reader import Cell, PdfPage, detect_cells

TABLE_MARK = "__table__"        # 추출 결과에서 표 값을 구분하는 표시


# ---------- 격자(칸) 찾기 ----------

def _cluster(vals: list[float], tol: float) -> list[float]:
    """가까운 값들을 하나로(중앙값) — 선·칸 경계 좌표 정리."""
    out: list[list[float]] = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sorted(g)[len(g) // 2] for g in out]


def _line_positions(mask, axis: int, min_frac: float, tol_px: int = 3) -> list[int]:
    """선 마스크에서 긴 선의 위치들(px). axis=1: 가로선(행 방향 합산), axis=0: 세로선."""
    import numpy as np
    prof = mask.sum(axis=axis)
    need = min_frac * mask.shape[axis]
    idx = np.where(prof >= need)[0].tolist()
    if not idx:
        return []
    return [int(v) for v in _cluster([float(i) for i in idx], tol_px)]


def _trim_rows(ys: list[int], xs: list[int], vb) -> list[int]:
    """표 위·아래에 붙은 '표가 아닌 가로선'(제목 밑줄 등)을 뗀다 —
    첫/끝 줄 띠에 세로선이 거의 없으면 그 경계선은 표 밖이다."""
    def has_cols(y0: int, y1: int) -> bool:
        if y1 - y0 < 4:
            return False
        hit = 0
        for x in xs:
            band = vb[y0 + 1:y1 - 1, max(0, x - 3):x + 4]
            if band.size and band.any(axis=1).mean() >= 0.5:
                hit += 1
        return hit >= max(2, int(0.3 * len(xs)))
    ys = list(ys)
    while len(ys) >= 2 and not has_cols(ys[0], ys[1]):
        ys.pop(0)
    while len(ys) >= 2 and not has_cols(ys[-2], ys[-1]):
        ys.pop()
    return ys


def image_grid(pdf_path: str, page_no: int, region: tuple[float, float, float, float] | None = None,
               dpi: int = 150, min_frac: float = 0.2) -> list[Cell]:
    """이미지(스캔)에서 표 격자 → 칸 사각형들(pt, 글자 없음). 선이 2×2 미만이면 [].
    가로선은 영역 너비의 20%만 넘으면 줄 경계로 본다(합쳐진 칸 옆의 짧은 구분선도 줄) —
    칸 사이에 선이 없는 곳은 합쳐진 칸으로 묶이므로 짧은 선이 많아도 안전하다."""
    import cv2
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no]
        clip = fitz.Rect(*region) if region else page.rect
        pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
    finally:
        doc.close()
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    if gray.size == 0:
        return []
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    H, W = bw.shape
    kh = max(15, W // 20)
    kv = max(15, H // 20)
    hmask = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (kh, 1)))
    vmask = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, kv)))
    hb = hmask > 0
    vb = vmask > 0
    ys = _line_positions(hb, axis=1, min_frac=min_frac)
    xs = _line_positions(vb, axis=0, min_frac=max(min_frac, 0.3))
    if len(ys) < 2 or len(xs) < 2:
        return []
    ys = _trim_rows(ys, xs, vb)
    if len(ys) < 2:
        return []
    s = 72.0 / dpi
    ox, oy = (clip.x0, clip.y0)
    nr, nc = len(ys) - 1, len(xs) - 1

    def has_hline(y: int, xa: int, xb: int) -> bool:      # (xa..xb) 구간에 가로선이 있나
        band = hb[max(0, y - 3):y + 4, xa:xb]
        return band.any(axis=0).mean() >= 0.5 if band.size else False

    def has_vline(x: int, ya: int, yb: int) -> bool:
        band = vb[ya:yb, max(0, x - 3):x + 4]
        return band.any(axis=1).mean() >= 0.5 if band.size else False

    # 합쳐진 칸: 사이에 선이 없으면 같은 묶음(union-find)
    parent = list(range(nr * nc))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for r in range(nr):
        for c in range(nc):
            if r + 1 < nr and not has_hline(ys[r + 1], xs[c] + 2, xs[c + 1] - 2):
                union(r * nc + c, (r + 1) * nc + c)
            if c + 1 < nc and not has_vline(xs[c + 1], ys[r] + 2, ys[r + 1] - 2):
                union(r * nc + c, r * nc + c + 1)
    groups: dict[int, list[tuple[int, int]]] = {}
    for r in range(nr):
        for c in range(nc):
            groups.setdefault(find(r * nc + c), []).append((r, c))
    cells: list[Cell] = []
    for members in groups.values():
        r0 = min(m[0] for m in members)
        r1 = max(m[0] for m in members)
        c0 = min(m[1] for m in members)
        c1 = max(m[1] for m in members)
        cells.append(Cell(ox + xs[c0] * s, oy + ys[r0] * s, ox + xs[c1 + 1] * s, oy + ys[r1 + 1] * s))
    return cells


def _cell_text(page: PdfPage, cell: Cell) -> str:
    """칸 안 단어들을 읽기 순서로 — 줄이 바뀌어도 이어 붙이되 이메일(@)은 띄지 않는다."""
    ws = [w for w in page.words if cell.x0 <= w.cx <= cell.x1 and cell.y0 <= w.cy <= cell.y1
          and (w.text or "").strip()]
    if not ws:
        return ""
    ws.sort(key=lambda w: (round(w.cy / 5), w.cx))
    out = ""
    for w in ws:
        t = w.text.strip()
        if not out:
            out = t
        elif out.endswith("@") or t.startswith("@") or (("@" in out) and re.match(r"^[\w.]+$", t)):
            out += t
        else:
            out += " " + t
    return normalize(out)


def cells_in_region(pdf_path: str, page: PdfPage, region: tuple[float, float, float, float] | None,
                    ) -> list[Cell]:
    """영역 안의 표 칸들(글자 포함). 글자 PDF는 표 선으로, 없으면(스캔) 이미지 격자로."""
    x0, y0, x1, y1 = region if region else (0, 0, page.width, page.height)
    # 이미지 격자를 먼저 쓴다 — 글자 PDF도 선을 그대로 렌더하므로 정확하고,
    # pdfplumber 는 세로로 합쳐진 칸(기관명이 여러 줄에 걸침)을 빠뜨린다.
    cells: list[Cell] = []
    try:
        cells = image_grid(pdf_path, page.page_no, region)
    except Exception:  # noqa: BLE001
        cells = []
    if not cells and not getattr(page, "ocr", False):
        try:
            cells = [c for c in detect_cells(pdf_path, page.page_no)
                     if c.x0 >= x0 - 3 and c.y0 >= y0 - 3 and c.x1 <= x1 + 3 and c.y1 <= y1 + 3]
        except Exception:  # noqa: BLE001
            cells = []
    for c in cells:
        c.text = _cell_text(page, c)
    return cells


# ---------- 칸 → 머리글·행 ----------

def table_rows(cells: list[Cell], header_rows: int = 1, tol: float = 3.0,
               ) -> tuple[list[str], list[dict]]:
    """칸들 → (열 이름들, 데이터 행들). 첫 header_rows 줄이 머리글.
    세로로 걸친 칸은 걸친 줄마다 같은 값. 전부 빈 줄은 뺀다."""
    if not cells:
        return [], []
    ys = _cluster([c.y0 for c in cells] + [c.y1 for c in cells], tol)
    xs = _cluster([c.x0 for c in cells] + [c.x1 for c in cells], tol)
    nr, nc = len(ys) - 1, len(xs) - 1
    if nr < 1 or nc < 1:
        return [], []

    def idx(bounds, v0, v1):
        return [k for k in range(len(bounds) - 1) if bounds[k] >= v0 - tol and bounds[k + 1] <= v1 + tol]

    grid: dict[tuple[int, int], str] = {}
    spans: set[tuple[int, int]] = set()          # 세로로 걸친 칸이 채운 자리(빈 줄 판정에서 제외)
    for c in cells:
        rs = idx(ys, c.y0, c.y1)
        for r in rs:
            for k in idx(xs, c.x0, c.x1):
                grid[(r, k)] = c.text
                if len(rs) > 1:
                    spans.add((r, k))
    cols: list[str] = []
    for k in range(nc):
        name = " ".join(t for t in (grid.get((r, k), "") for r in range(header_rows)) if t).strip()
        name = name or f"열{k + 1}"
        if name in cols:
            name = f"{name}({k + 1})"
        cols.append(name)
    rows: list[dict] = []
    for r in range(header_rows, nr):
        vals = [grid.get((r, k), "") for k in range(nc)]
        own = [v for k, v in enumerate(vals) if (r, k) not in spans]
        if not any(v.strip() for v in (own or vals)):
            continue                              # 걸친 칸 값만 있는 빈 줄은 뺀다
        rows.append(dict(zip(cols, vals)))
    return cols, rows


def extract_table(page: PdfPage, box: dict, pdf_path: str | None,
                  columns: list[str] | None = None) -> tuple[list[str], list[dict]]:
    """표 박스 하나 → (열 이름, 행들). columns(템플릿에서 정한 열 이름)가 열 수와 맞으면 그걸 쓴다."""
    if not pdf_path:
        return list(columns or []), []
    bx0, by0, bx1, by1 = (float(box["x0"]), float(box["y0"]), float(box["x1"]), float(box["y1"]))
    # 입력 쪽에서 표가 위아래로 밀려 있어도(양식마다 여백 다름) 박스와 가장 많이 겹치는 표를 쓴다 —
    # 박스 영역만 자르면 머리글 위 테두리가 잘려 첫 데이터 줄이 머리글로 오인될 수 있다
    cells: list[Cell] = []
    try:
        best, best_ov = None, 0.0
        for cs in find_tables(pdf_path, page):
            tx0, ty0 = min(c.x0 for c in cs), min(c.y0 for c in cs)
            tx1, ty1 = max(c.x1 for c in cs), max(c.y1 for c in cs)
            ov = max(0.0, min(bx1, tx1) - max(bx0, tx0)) * max(0.0, min(by1, ty1) - max(by0, ty0))
            if ov > best_ov:
                best, best_ov = cs, ov
        if best is not None and best_ov >= 0.5 * max(1.0, (bx1 - bx0) * (by1 - by0)):
            cells = best
    except Exception:  # noqa: BLE001
        cells = []
    if not cells:
        pad = 4.0   # 박스가 표 테두리에 딱 붙어 있어도 바깥 선이 잘리지 않게
        region = (max(0.0, bx0 - pad), max(0.0, by0 - pad),
                  min(page.width, bx1 + pad), min(page.height, by1 + pad))
        cells = cells_in_region(pdf_path, page, region)
    if not cells:
        return list(columns or []), []
    cols, rows = table_rows(cells, header_rows=int(box.get("header_rows", 1) or 1))
    if columns and len(columns) == len(cols):
        rows = [dict(zip(columns, r.values())) for r in rows]
        cols = list(columns)
    return cols, rows


# ---------- 자동 제안(디자이너) ----------

def _labelish(t: str) -> bool:
    from core.pdf_pipeline import _looks_like_label
    return _looks_like_label(t)


def find_tables(pdf_path: str, page: PdfPage) -> list[list[Cell]]:
    """페이지의 표들(칸 묶음). 글자 PDF는 pdfplumber 표 단위, 스캔은 이미지 격자(가로선 묶음)."""
    tables: list[list[Cell]] = []
    if not getattr(page, "ocr", False):
        # 글자 PDF: 표 영역은 pdfplumber 로 찾고, 칸은 이미지 격자로(합쳐진 칸 보존)
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                if page.page_no < len(pdf.pages):
                    for t in pdf.pages[page.page_no].find_tables():
                        cs = [Cell(*c) for c in t.cells if c]
                        if not cs:
                            continue
                        bbox = (min(c.x0 for c in cs) - 2, min(c.y0 for c in cs) - 2,
                                max(c.x1 for c in cs) + 2, max(c.y1 for c in cs) + 2)
                        try:
                            grid = image_grid(pdf_path, page.page_no, bbox)
                        except Exception:  # noqa: BLE001
                            grid = []
                        tables.append(grid or cs)
        except Exception:  # noqa: BLE001
            tables = []
    if not tables:
        # 스캔: 긴 가로선들을 세로 간격으로 묶어 표 영역을 나눈 뒤 영역마다 격자
        try:
            import cv2
            import fitz
            import numpy as np
            doc = fitz.open(pdf_path)
            try:
                pix = doc[page.page_no].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
            finally:
                doc.close()
            gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
            W = bw.shape[1]
            hmask = cv2.morphologyEx(bw, cv2.MORPH_OPEN,
                                     cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, W // 8), 1)))
            hb = hmask > 0
            ys = _line_positions(hb, axis=1, min_frac=0.15)
            s = 72.0 / 100
            # 가로선 묶음(간격이 페이지 높이 35% 넘게 벌어지면 다른 표 — 합쳐진 큰 칸도 한 표)
            groups: list[list[int]] = []
            for y in ys:
                if groups and y - groups[-1][-1] <= bw.shape[0] * 0.35:
                    groups[-1].append(y)
                else:
                    groups.append([y])
            for g in groups:
                if len(g) < 2:
                    continue
                rows = hb[g[0]:g[-1] + 1]
                xs_on = np.where(rows.any(axis=0))[0]
                if xs_on.size == 0:
                    continue
                region = (max(0.0, xs_on.min() * s - 4), max(0.0, g[0] * s - 4),
                          min(page.width, xs_on.max() * s + 4), min(page.height, g[-1] * s + 4))
                cs = image_grid(pdf_path, page.page_no, region)
                if cs:
                    tables.append(cs)
        except Exception:  # noqa: BLE001
            pass
    for cs in tables:
        for c in cs:
            if not c.text:
                c.text = _cell_text(page, c)
    return tables


def _ink_fraction(pdf_path: str, page_no: int, cells: list[Cell], dpi: int = 100) -> list[float]:
    """칸마다 진한 픽셀 비율(0~1) — 칸 안쪽(가장자리 15% 제외). 굵은 머리글 글자는 높고
    빈 칸·가는 값 글자는 낮다(회색 음영 칸도 점무늬로 스캔되면 조금 올라간다)."""
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        pix = doc[page_no].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    finally:
        doc.close()
    g = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    s = dpi / 72.0
    out = []
    for c in cells:
        w, h = (c.x1 - c.x0) * s, (c.y1 - c.y0) * s
        x0, x1 = int(c.x0 * s + w * 0.15), int(c.x1 * s - w * 0.15)
        y0, y1 = int(c.y0 * s + h * 0.15), int(c.y1 * s - h * 0.15)
        patch = g[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
        out.append(float((patch <= 100).mean()) if patch.size else 0.0)
    return out


def suggest_table_boxes(pdf_path: str, page: PdfPage) -> list[dict]:
    """머리글 한 줄 + 데이터 줄들인 '목록형 표'를 표 박스로 제안(열 3개 이상).

    항목–값 서식(이름표 칸과 값 칸이 번갈아 있는 조사표)과 구분:
    · 머리글 줄만 음영(회색)이고 데이터 칸은 흰색이면 목록형 표(가장 확실한 단서)
    · 이름표 칸마다 음영이 있으면(줄마다 회색 칸) 항목–값 서식 → 제외
    · 음영이 전혀 없으면 글자로 판단: 머리글이 짧은 이름표(숫자 없음)이고 데이터 줄이 2줄 이상이며
      비어 있는 줄(채우라고 남긴 줄)이나 숫자 값(전화·수치)이 있을 때만."""
    out: list[dict] = []
    for cs in find_tables(pdf_path, page):
        cols, rows = table_rows(cs)
        if len(cols) < 3:
            continue
        ys = _cluster([c.y0 for c in cs] + [c.y1 for c in cs], 3.0)
        n_data = len(ys) - 2           # 머리글 한 줄 제외
        if n_data < 1:
            continue
        real = [c for c in cols if not c.startswith("열")]
        if len(real) < max(2, int(0.6 * len(cols))) or any(re.search(r"\d", c) for c in real) \
                or any(len(c) > 12 for c in real):
            continue
        try:
            ink = _ink_fraction(pdf_path, page.page_no, cs)
        except Exception:  # noqa: BLE001
            ink = [0.0] * len(cs)
        top = ys[0]
        head_idx = [i for i, c in enumerate(cs) if abs(c.y0 - top) <= 3.0 and (c.y1 - top) <= (ys[1] - top) + 3.0]
        data_idx = [i for i in range(len(cs)) if i not in head_idx]
        hd = (sum(ink[i] for i in head_idx) / len(head_idx)) if head_idx else 0.0
        dd = (sum(ink[i] for i in data_idx) / len(data_idx)) if data_idx else 0.0
        blank_rows = n_data - len(rows)
        digit_rows = sum(1 for r in rows if any(re.search(r"\d{2,}", v) for v in r.values()))
        if len(head_idx) >= 3 and hd >= 0.03 and hd >= 4 * max(dd, 0.003):
            ok = True          # 머리글 줄만 굵은 글씨·음영, 데이터 칸은 가볍다 → 목록형 표
        elif hd >= 0.03 and dd >= 0.6 * hd and n_data < 3:
            ok = False         # 줄마다 굵은 이름표 칸 → 항목–값 서식
        else:
            ok = n_data >= 2 and (blank_rows >= 1 or digit_rows >= 1)
        if not ok:
            continue
        out.append({
            "field": "표", "page": page.page_no, "mode": "table", "columns": cols,
            "x0": min(c.x0 for c in cs), "y0": min(c.y0 for c in cs),
            "x1": max(c.x1 for c in cs), "y1": max(c.y1 for c in cs),
            "use_anchor": False, "suggested": True, "anchor": None,
        })
    return out


# ---------- 추출 결과 펼치기 ----------

def is_table_value(v) -> bool:
    return isinstance(v, dict) and bool(v.get(TABLE_MARK))


def explode_rows(row: dict, fields: list[str]) -> tuple[list[dict], list[str]]:
    """표 값이 든 한 건 → 표 행 수만큼 여러 건. 열 이름은 표 열로 바꿔 넣는다.
    표가 둘 이상이면 순서대로 짝지어(짧은 쪽은 빈칸) 한 행에 놓는다."""
    tables = {k: v for k, v in row.items() if is_table_value(v)}
    if not tables:
        return [row], list(fields)
    base = {k: v for k, v in row.items() if not is_table_value(v)}
    fields2: list[str] = []
    colmap: dict[str, list[tuple[str, str]]] = {}      # 표 필드 → [(표 열, 출력 열)]
    taken = set(f for f in fields if f not in tables) | set(base)
    for f in fields:
        if f in tables:
            pairs = []
            for c in tables[f].get("columns", []):
                name = c if c not in taken else f"{f}_{c}"
                taken.add(name)
                pairs.append((c, name))
                fields2.append(name)
            colmap[f] = pairs
        else:
            fields2.append(f)
    for f in tables:
        if f not in colmap:            # fields 목록에 없는 표 필드도 펼친다
            pairs = []
            for c in tables[f].get("columns", []):
                name = c if c not in taken else f"{f}_{c}"
                taken.add(name)
                pairs.append((c, name))
                fields2.append(name)
            colmap[f] = pairs
    n = max([len(t.get("rows", [])) for t in tables.values()] + [1])
    out: list[dict] = []
    for i in range(n):
        r = dict(base)
        for f, t in tables.items():
            src = t.get("rows", [])
            tr = src[i] if i < len(src) else {}
            for c, name in colmap[f]:
                r[name] = tr.get(c, "")
        out.append(r)
    return out, fields2
