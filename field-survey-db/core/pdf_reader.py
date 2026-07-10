"""PDF 읽기 — 글자(위치·굵게) 추출, 페이지 이미지 렌더, 박스/라벨 기반 값 추출.

hwpx도 PDF로 변환한 뒤 이 모듈로 통일 처리한다.
타이핑 PDF는 텍스트 레이어에서 바로 읽고, 텍스트가 없는(스캔) 페이지는 OCR 필요로 표시.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # pymupdf

from core.normalize import has_check_mark, normalize, normalize_key


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    bold: bool = False

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class PdfPage:
    page_no: int
    width: float
    height: float
    words: list[Word] = field(default_factory=list)
    needs_ocr: bool = False
    ocr: bool = False   # OCR로 단어를 채운 페이지


@dataclass
class PdfDoc:
    path: str
    pages: list[PdfPage] = field(default_factory=list)


def _bold_word_map(page: "fitz.Page") -> list[tuple[float, float, float, float, str, bool]]:
    """dict 추출로 각 span의 굵게 여부를 파악해 단어별 bold 판정에 사용."""
    spans = []
    d = page.get_text("dict")
    for b in d.get("blocks", []):
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                font = s.get("font", "")
                bold = ("Bold" in font) or bool(s.get("flags", 0) & 16)
                spans.append((s["bbox"], bold))
    return spans


def read_pdf(path: str, ocr_scanned: bool = True, ocr_dpi: int = 170) -> PdfDoc:
    doc = PdfDoc(path=path)
    pdf = fitz.open(path)
    scanned_pages: list[int] = []
    for i, page in enumerate(pdf):
        spans = _bold_word_map(page)

        def is_bold(x0, y0, x1, y1):
            for (bx0, by0, bx1, by1), bold in spans:
                if not bold:
                    continue
                # 단어 중심이 굵은 span 안에 있으면 굵게로 판정
                if bx0 <= (x0 + x1) / 2 <= bx1 and by0 <= (y0 + y1) / 2 <= by1:
                    return True
            return False

        words: list[Word] = []
        for w in page.get_text("words"):
            x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
            words.append(Word(x0, y0, x1, y1, txt, is_bold(x0, y0, x1, y1)))
        pg = PdfPage(page_no=i, width=page.rect.width, height=page.rect.height, words=words)
        pg.needs_ocr = len(words) == 0  # 텍스트 없음 → 스캔(OCR 필요)
        if pg.needs_ocr:
            scanned_pages.append(i)
        doc.pages.append(pg)
    pdf.close()

    # 스캔(텍스트 없는) 페이지는 OCR로 단어를 채운다.
    if ocr_scanned and scanned_pages:
        _ocr_fill(path, doc, scanned_pages, ocr_dpi)
    return doc


def _ocr_fill(path: str, doc: PdfDoc, page_nos: list[int], dpi: int) -> None:
    from core import ocr as _ocr
    if not _ocr.available():
        return  # OCR 엔진 없음 — needs_ocr 플래그만 남김(사용자 안내용)
    scale = 72.0 / dpi
    for pno in page_nos:
        try:
            png = render_page_png(path, pno, dpi=dpi)
            ow = _ocr.ocr_image(png, scale=scale)
        except Exception:  # noqa: BLE001
            continue
        pg = doc.pages[pno]
        pg.words = [Word(w.x0, w.y0, w.x1, w.y1, w.text, False) for w in ow]
        pg.ocr = True  # OCR로 채워진 페이지 표시


@dataclass
class Cell:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str = ""


def detect_cells(path: str, page_no: int) -> list[Cell]:
    """표 테두리(선)로 칸(셀) 사각형을 감지. 스캔본(선 없음)이면 빈 리스트."""
    import pdfplumber

    cells: list[Cell] = []
    with pdfplumber.open(path) as pdf:
        if page_no >= len(pdf.pages):
            return cells
        page = pdf.pages[page_no]
        for table in page.find_tables():
            for c in table.cells:
                if not c:
                    continue
                x0, top, x1, bottom = c
                try:
                    txt = page.crop((x0, top, x1, bottom)).extract_text() or ""
                except Exception:  # noqa: BLE001
                    txt = ""
                cells.append(Cell(x0, top, x1, bottom, normalize(txt.replace("\n", " "))))
    return cells


def render_page_png(path: str, page_no: int, dpi: int = 130) -> bytes:
    pdf = fitz.open(path)
    pix = pdf[page_no].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    pdf.close()
    return data


# ---------- 추출 도우미 ----------

def words_in_bbox(page: PdfPage, bbox: dict) -> list[Word]:
    """박스(x0,y0,x1,y1) 안에 중심이 들어오는 단어들을 읽기 순서로 반환."""
    x0, y0, x1, y1 = bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]
    inside = [w for w in page.words if x0 <= w.cx <= x1 and y0 <= w.cy <= y1]
    inside.sort(key=lambda w: (round(w.cy / 5), w.cx))  # 행 우선, 그다음 좌→우
    return inside


def text_in_bbox(page: PdfPage, bbox: dict, bold_only: bool = False) -> str:
    ws = words_in_bbox(page, bbox)
    if bold_only:
        ws = [w for w in ws if w.bold]
    return normalize(" ".join(w.text for w in ws))


def _same_line(a: Word, b: Word) -> bool:
    return abs(a.cy - b.cy) < max(a.y1 - a.y0, b.y1 - b.y0) * 0.6


def find_label_word(page: PdfPage, label: str) -> Word | None:
    """라벨과 일치하는 단어(또는 같은 줄 연속 단어 결합)를 찾아 하나의 Word로 반환."""
    want = normalize_key(label)
    if not want:
        return None
    # 1) 단일 단어 정확 일치
    for w in page.words:
        if normalize_key(w.text) == want:
            return w
    # 2) 같은 줄 연속 단어 결합으로 일치 (예: '관리' + '기관' = '관리기관')
    lines: dict[int, list[Word]] = {}
    for w in page.words:
        lines.setdefault(round(w.cy / 4), []).append(w)
    for row in lines.values():
        row.sort(key=lambda w: w.x0)
        for i in range(len(row)):
            acc = ""
            for j in range(i, min(i + 5, len(row))):
                acc += normalize_key(row[j].text)
                if acc == want:
                    a, b = row[i], row[j]
                    return Word(a.x0, min(a.y0, b.y0), b.x1, max(a.y1, b.y1), label)
                if len(acc) > len(want):
                    break
    # 3) 부분 포함(단일 단어)
    for w in page.words:
        if want in normalize_key(w.text):
            return w
    return None


def value_words(page: PdfPage, label: str, relation: str = "right",
                gap: float = 45.0) -> list[Word]:
    """라벨 기준 값에 해당하는 단어들을 반환(위치 계산·박스 제안용)."""
    lw = find_label_word(page, label)
    if lw is None:
        return []
    if relation == "self":
        return [lw]
    if relation == "below":
        cands = [w for w in page.words
                 if w.y0 >= lw.y1 - 1 and abs(w.cx - lw.cx) < (lw.x1 - lw.x0) + 30]
        cands.sort(key=lambda w: (w.cy, w.cx))
        if not cands:
            return []
        base_y = cands[0].cy
        return [w for w in cands if abs(w.cy - base_y) < 6]
    # right
    row = [w for w in page.words if w.x0 >= lw.x1 - 1 and _same_line(w, lw)]
    row.sort(key=lambda w: w.x0)
    picked, prev_x1 = [], None
    for w in row:
        if prev_x1 is not None and w.x0 - prev_x1 > gap:
            break
        picked.append(w)
        prev_x1 = w.x1
    return picked


def value_by_label(page: PdfPage, label: str, relation: str = "right",
                   bold_only: bool = False, gap: float = 45.0) -> str:
    """라벨 기준으로 값을 찾는다. 값이 여러 단어면 큰 간격 전까지 모두 이어붙임."""
    row = value_words(page, label, relation, gap)
    if bold_only:
        row = [w for w in row if w.bold]
    return normalize(" ".join(w.text for w in row))
