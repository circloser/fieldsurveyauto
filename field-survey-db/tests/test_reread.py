"""쪽 전체 OCR이 놓친 칸 안의 외톨이 글자를 칸만 다시 읽기.

실제 사례(저어새 번식지 조사표 스캔): 둥지 현황의 한 자리 숫자만 있는 칸 — 1쪽 번식준비 '1', 6쪽 번식준비 '3'·
이소 '4' — 이 쪽 전체 OCR에서 글자로 잡히지 않아 빈칸이 됐다. 칸을 통째로 읽으면 칸 선을 '1'·'I'로 지어내므로
칸 안쪽만, 잉크가 있을 때만, 글자를 찾았을 때만 쓴다.
"""
from pathlib import Path

import fitz
import pytest

from core.pdf_pipeline import apply_pixel_template
from core.pdf_reader import PdfPage

DPI = 150
S = 72 / DPI
COLS = [100, 330, 560]
ROWS = [120, 190, 260, 330]
VALUES = ["1", "", "3"]


@pytest.fixture(scope="module")
def ocr_ready():
    from core import ocr
    if not ocr.available():
        pytest.skip("OCR 엔진(easyocr) 없음")


def _scan_table(path: Path):
    """라벨 칸 | 값 칸 3줄 스캔 쪽 — 값은 한 자리 숫자 또는 빈칸."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\batang.ttc", 26, index=0)
    except Exception:  # noqa: BLE001
        pytest.skip("바탕 폰트 없음")
    W, H = 1240, 600
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    for y in ROWS:
        dr.line([(COLS[0], y), (COLS[-1], y)], fill="black", width=3)
    for x in COLS:
        dr.line([(x, ROWS[0]), (x, ROWS[-1])], fill="black", width=3)
    for k, (lab, val) in enumerate(zip(["번식준비", "이소", "실패"], VALUES)):
        dr.text((COLS[0] + 20, ROWS[k] + 20), lab, font=font, fill="black")
        if val:
            dr.text(((COLS[1] + COLS[2]) // 2, ROWS[k] + 20), val, font=font, fill="black")
    png = path.with_suffix(".png")
    img.save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * S, height=H * S)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()


def _inner(k):
    return (COLS[1] * S + 3, ROWS[k] * S + 3, COLS[2] * S - 3, ROWS[k + 1] * S - 3)


def test_read_region_finds_lone_digit_and_skips_blank(tmp_path, ocr_ready):
    from core.ocr import read_region

    p = tmp_path / "scan.pdf"
    _scan_table(p)
    assert read_region(str(p), 0, _inner(0)) == "1"
    assert read_region(str(p), 0, _inner(1)) == ""          # 빈 칸은 읽지 않는다(칸 선을 '1'로 지어내지 않음)
    assert read_region(str(p), 0, _inner(2)) == "3"


def test_empty_scanned_box_is_reread_only_on_ocr_pages(monkeypatch):
    calls = []

    def fake(pdf_path, page_no, rect, **kw):
        calls.append(tuple(round(v) for v in rect))
        return "약 1"

    monkeypatch.setattr("core.ocr.read_region", fake)
    boxes = [{"field": "번식준비", "page": 0, "mode": "number", "order": 1,
              "x0": 160, "y0": 57, "x1": 270, "y1": 91, "use_anchor": False, "anchor": None},
             {"field": "기타 특이사항", "page": 0, "mode": "text", "order": 2,
              "x0": 20, "y0": 100, "x1": 580, "y1": 400, "use_anchor": False, "anchor": None}]
    scan = PdfPage(page_no=0, width=595, height=842, words=[], ocr=True)
    got = apply_pixel_template([scan], boxes, pdf_path="없는파일.pdf")
    assert got == {"번식준비": "1", "기타 특이사항": ""}     # 숫자 유형은 숫자만, 큰 칸은 다시 읽지 않음
    assert calls == [(163, 60, 267, 88)]                     # 칸 선을 뺀 안쪽(3pt 들임)
    calls.clear()
    text = PdfPage(page_no=0, width=595, height=842, words=[], ocr=False)
    assert apply_pixel_template([text], boxes, pdf_path="없는파일.pdf") == {"번식준비": "", "기타 특이사항": ""}
    assert calls == []                                       # 글자 PDF는 다시 읽지 않는다
