"""디지털 입력 기록 → 현장조사표 PDF.

템플릿과 함께 저장된 양식 PDF 위에, 박스 자리마다 기록값을 써 넣는다(기록 하나 = 양식 한 벌, 여러 기록은 이어 붙임).
  · 글·숫자: 칸에 맞춰 글자 크기를 9→5pt 로 줄여 가며 넣고, 한 줄이면 세로 가운데. 그래도 넘치면 들어간 만큼만
  · 체크: 칸 가운데 √   · 사진: 칸 비율에 맞춰 축소 삽입
  · 표(여러 행): 양식의 칸 선을 찾아 머리글 아래 줄부터 채우고, 줄이 모자라면 남는 기록은 표 아래에 작은 글씨로 덧붙인다
  · 각 기록의 첫 쪽 아래에 '오토다타 디지털 입력 · 기록 번호 · 기록 시각 · 위치' 를 작게 남긴다
글꼴은 PyMuPDF 에 든 CJK(Droid Sans Fallback) — 한글·√ 모두 있어 따로 설치할 것이 없다.
"""
from __future__ import annotations

import json
import os

INK = (0.10, 0.22, 0.58)        # 진한 파랑 — 인쇄된 양식 글자와 구분
GRAY = (0.45, 0.45, 0.45)
SIZE_MAX, SIZE_MIN = 9.0, 5.0


def _fmt(v) -> str:
    if v is None or v is False:
        return ""
    if v is True:
        return "√"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def _write_text(page, font, rect, text: str, *, size_max: float = SIZE_MAX, size_min: float = SIZE_MIN,
                align: int = 0) -> bool:
    """칸(rect)에 글을 넣는다 — 크기를 줄여 가며 맞추고, 한 줄이면 세로 가운데. 반환: 전부 들어갔는가."""
    import fitz
    text = text.strip()
    if not text:
        return True
    box = fitz.Rect(rect.x0 + 1.5, rect.y0 + 1.0, rect.x1 - 1.5, rect.y1 - 1.0)
    if box.is_empty or box.width < 6 or box.height < 5:      # 너무 작은 박스 — 최소 크기로 늘려 쓴다
        box = fitz.Rect(rect.x0, rect.y0, rect.x0 + max(rect.width, 24), rect.y0 + max(rect.height, 8))
    fs = size_max
    last = None
    while fs >= size_min:
        target = box
        if "\n" not in text and font.text_length(text, fontsize=fs) <= box.width:
            lh = fs * 1.3
            y0 = box.y0 + max(0.0, (box.height - lh) / 2)
            target = fitz.Rect(box.x0, y0, box.x1, max(box.y1, y0 + lh + 1))
        tw = fitz.TextWriter(page.rect, color=INK)
        try:
            rest = tw.fill_textbox(target, text, font=font, fontsize=fs, align=align)
        except (ValueError, RuntimeError):
            rest = [text]
        if not rest:
            tw.write_text(page)
            return True
        last = tw
        fs -= 0.5
    if last is not None:
        last.write_text(page)         # 최소 크기로 들어간 만큼만
    return False


def _draw_check(page, font, rect) -> None:
    import fitz
    fs = max(6.0, min(12.0, rect.height * 0.7, rect.width * 0.9))
    w = font.text_length("√", fontsize=fs)
    x = rect.x0 + max(0.0, (rect.width - w) / 2)
    y = rect.y0 + (rect.height + fs * 0.7) / 2
    tw = fitz.TextWriter(page.rect, color=INK)
    tw.append(fitz.Point(x, y), "√", font=font, fontsize=fs)
    tw.write_text(page)


def _table_grid(pdf_path: str, page_no: int, rect, header_rows: int) -> list[list]:
    """박스 안의 표 칸(선 기준)을 줄별로 — 머리글 줄은 뺀다. 못 찾으면 빈 목록."""
    import fitz
    try:
        from core.pdf_pipeline import page_cells
        cells = page_cells(pdf_path, page_no)
    except Exception:  # noqa: BLE001
        return []
    inside = [c for c in cells
              if rect.x0 - 2 <= (c.x0 + c.x1) / 2 <= rect.x1 + 2 and rect.y0 - 2 <= (c.y0 + c.y1) / 2 <= rect.y1 + 2
              and (c.x1 - c.x0) >= 6 and (c.y1 - c.y0) >= 5]
    rows: list[list] = []
    for c in sorted(inside, key=lambda z: (round(z.y0), z.x0)):
        if rows and abs(rows[-1][0].y0 - c.y0) <= 3:
            rows[-1].append(c)
        else:
            rows.append([c])
    grid = [[fitz.Rect(c.x0, c.y0, c.x1, c.y1) for c in sorted(r, key=lambda z: z.x0)] for r in rows]
    return grid[header_rows:] if len(grid) > header_rows else []


def _fill_table(page, font, pdf_path: str, page_no: int, rect, box: dict, value, warnings: list[str],
                seq) -> None:
    import fitz
    cols = [str(c) for c in (box.get("columns") or []) if str(c).strip()] or ["값"]
    rows = [r for r in (value or []) if isinstance(r, dict)] if isinstance(value, list) else []
    if not rows:
        return
    header_rows = int(box.get("header_rows", 1) or 1)
    grid = _table_grid(pdf_path, page_no, rect, header_rows)
    if not grid:                                   # 칸 선이 없는 양식 — 머리글 한 줄 아래를 고르게 나눠 쓴다
        n = max(len(rows), 1)
        top = rect.y0 + rect.height / (n + 1)
        rh = (rect.y1 - top) / n
        cw = rect.width / len(cols)
        grid = [[fitz.Rect(rect.x0 + j * cw, top + i * rh, rect.x0 + (j + 1) * cw, top + (i + 1) * rh)
                 for j in range(len(cols))] for i in range(n)]
    for i, r in enumerate(rows[:len(grid)]):
        cells = grid[i]
        for j, c in enumerate(cols):
            if j < len(cells):
                _write_text(page, font, cells[j], _fmt(r.get(c)), size_max=8.0)
    extra = rows[len(grid):]
    if extra:
        lines = [" · ".join(f"{c} {_fmt(r.get(c))}" for c in cols if _fmt(r.get(c))) for r in extra]
        y1 = min(page.rect.y1 - 18, rect.y1 + 9 * len(lines) + 4)
        _write_text(page, font, fitz.Rect(rect.x0, rect.y1 + 1, rect.x1, y1), "\n".join(lines),
                    size_max=6.5, size_min=5.0)
        warnings.append(f"기록 {seq} '{box.get('field')}': 표 {len(rows)}줄 중 {len(extra)}줄은 양식 칸이 모자라 "
                        f"표 아래에 작은 글씨로 적었습니다.")


def _footer(page, font, text: str) -> None:
    import fitz
    r = fitz.Rect(page.rect.x0 + 24, page.rect.y1 - 15, page.rect.x1 - 24, page.rect.y1 - 3)
    tw = fitz.TextWriter(page.rect, color=GRAY)
    try:
        tw.fill_textbox(r, text, font=font, fontsize=6.5)
        tw.write_text(page)
    except (ValueError, RuntimeError):
        pass


def _is_checked(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "1", "√", "v", "o", "예", "yes")


def fill_pdf(template_pdf: str, boxes: list[dict], entries: list[dict], out_path: str, *,
             photo_path=None, gps: bool = False, footer: bool = True) -> dict:
    """entries 하나마다 양식 전체 쪽을 복사해 값을 써 넣고 한 파일로 저장. photo_path(entry, field) → 파일 경로."""
    import fitz
    from core.forms import local_time

    font = fitz.Font("cjk")
    tpl = fitz.open(template_pdf)
    n_pages = tpl.page_count
    out = fitz.open()
    warnings: list[str] = []
    ordered = sorted(boxes, key=lambda b: b.get("order", 0))
    for e in entries:
        start = out.page_count
        out.insert_pdf(tpl)
        values = e.get("values") or {}
        for b in ordered:
            pno = int(b.get("page", 0) or 0)
            mode = b.get("mode") or "text"
            key = b.get("field")
            if pno >= n_pages or mode == "title" or key is None:
                continue
            page = out[start + pno]
            try:
                rect = fitz.Rect(float(b["x0"]), float(b["y0"]), float(b["x1"]), float(b["y1"]))
            except (KeyError, TypeError, ValueError):
                continue
            v = values.get(key)
            if mode == "check":
                if _is_checked(v):
                    _draw_check(page, font, rect)
            elif mode == "image":
                p = photo_path(e, key) if photo_path else None
                if p and os.path.exists(p):
                    try:
                        page.insert_image(fitz.Rect(rect.x0 + 1, rect.y0 + 1, rect.x1 - 1, rect.y1 - 1),
                                          filename=p, keep_proportion=True)
                    except Exception as ex:  # noqa: BLE001
                        warnings.append(f"기록 {e.get('seq')} '{key}': 사진을 넣지 못했습니다({ex})")
            elif mode == "table":
                _fill_table(page, font, template_pdf, pno, rect, b, v, warnings, e.get("seq"))
            else:
                text = _fmt(v)
                if text and not _write_text(page, font, rect, text):
                    warnings.append(f"기록 {e.get('seq')} '{key}': 값이 길어 칸에 일부만 들어갔습니다.")
        if footer:
            g = ((e.get("meta") or {}).get("gps") or {}) if gps else {}
            loc = f" · 위치 {g.get('lat')}, {g.get('lon')}" if g.get("lat") is not None else ""
            _footer(out[start], font, f"오토다타 디지털 입력 · 기록 {e.get('seq')} · {local_time(e.get('created', ''))}{loc}")
    out.save(out_path, garbage=3, deflate=True)
    pages = out.page_count
    out.close()
    tpl.close()
    return {"path": out_path, "pages": pages, "entries": len(entries), "warnings": warnings}
