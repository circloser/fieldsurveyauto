"""스캔(그림) 문서의 칸 인식 — 선이 벡터가 아니어도 이미지 격자로 칸·라벨을 잡는다.

스캔본은 pdfplumber 가 표 선을 못 찾아(벡터가 아님) 예전에는 칸 박스가 하나도 안 만들어졌다.
이제 이미지에서 격자를 찾아 글자 PDF와 같은 칸을 잡고, 라벨 기준 추출(줄 밀림에 강함)도 된다.
"""
from pathlib import Path

import fitz
import pytest

ROWS = [("하천명", "해남천"), ("관리기관", "전남 해남군"), ("구조물명", "1번 보"),
        ("보길이", "30"), ("낙차높이", "1.2"), ("어도유무", "있음")]


def _form(path: Path, rows=ROWS, y_top: float = 60):
    """라벨|값 2열 조사표(칸 테두리 있음)."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((60, 34), "인공구조물 현장 조사표", font=font, fontsize=18)
    x0, x1, x2, rh = 40, 160, 360, 28
    for i, (label, value) in enumerate(rows):
        y = y_top + i * rh
        page.draw_rect(fitz.Rect(x0, y, x1, y + rh), color=(0, 0, 0), width=0.8)
        page.draw_rect(fitz.Rect(x1, y, x2, y + rh), color=(0, 0, 0), width=0.8)
        tw.append((x0 + 6, y + 18), label, font=font, fontsize=10)
        if value:
            tw.append((x1 + 6, y + 18), value, font=font, fontsize=10)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def _rasterize(src: Path, dst: Path, dpi: int = 150):
    """글자 PDF → 그림만 있는 PDF(스캔본 재현)."""
    s = fitz.open(str(src))
    out = fitz.open()
    for i in range(len(s)):
        png = dst.with_suffix(f".p{i}.png")
        s[i].get_pixmap(dpi=dpi).save(str(png))
        pg = out.new_page(width=s[i].rect.width, height=s[i].rect.height)
        pg.insert_image(pg.rect, filename=str(png))
    out.save(str(dst))
    out.close()
    s.close()


@pytest.fixture(scope="module")
def ocr_ready():
    from core import ocr
    if not ocr.available():
        pytest.skip("OCR 엔진(easyocr) 없음")


def test_scanned_form_cells_match_text_pdf(tmp_path, ocr_ready):
    """스캔본의 칸 개수·위치가 글자 PDF와 같고, 칸 박스에 라벨이 붙는다."""
    from core.pdf_pipeline import detect_cells, page_cells, suggest_cells_maximal
    from core.pdf_reader import read_pdf

    text_pdf = tmp_path / "form.pdf"
    scan_pdf = tmp_path / "scan.pdf"
    _form(text_pdf)
    _rasterize(text_pdf, scan_pdf)

    base = read_pdf(str(text_pdf), ocr_scanned=False).pages[0]
    scan = read_pdf(str(scan_pdf), ocr_scanned=True).pages[0]
    assert scan.ocr and not detect_cells(str(scan_pdf), 0)      # 스캔본엔 벡터 표선이 없다

    n_text = len(page_cells(str(text_pdf), 0, base))
    cells = page_cells(str(scan_pdf), 0, scan)
    assert n_text == len(ROWS) * 2 and len(cells) == n_text      # 칸 12개(라벨 6 + 값 6)
    xs = sorted({round(c.x0) for c in cells})
    assert xs == [40, 160]                                      # 두 열 경계가 원본과 같다

    boxes = suggest_cells_maximal(str(scan_pdf), 0, scan)
    assert len(boxes) == len(ROWS)                               # 값 칸마다 하나 — 짝지은 라벨 칸 자체는 박스 없음
    labels = {(b.get("anchor") or {}).get("label", "") for b in boxes}
    assert "하천명" in labels and "어도유무" in labels           # 라벨(왼쪽 칸)이 이름으로 붙는다
    # 유형: 이름이 수치형인 값 칸만 '숫자', 나머지는 '일반'
    # (OCR이 '낙차 높이'처럼 띄어 읽을 수 있어 공백은 무시하고 비교)
    modes = {(b["anchor"]["label"] or "").replace(" ", ""): b["mode"]
             for b in boxes if b.get("anchor")}
    assert modes.get("보길이") == "number" and modes.get("낙차높이") == "number"
    assert modes.get("하천명") == "text" and modes.get("어도유무") == "text"


def test_scanned_form_extraction_uses_label_anchor(tmp_path, ocr_ready):
    """스캔본에서도 라벨 칸 기준으로 값을 읽어 — 줄이 하나 늘어 위치가 밀려도 값이 맞는다."""
    from core.pdf_pipeline import apply_pixel_template, suggest_cells_maximal
    from core.pdf_reader import read_pdf

    tpl_txt = tmp_path / "tpl.pdf"
    tpl_scan = tmp_path / "tpl_scan.pdf"
    _form(tpl_txt)
    _rasterize(tpl_txt, tpl_scan)
    tpl_page = read_pdf(str(tpl_scan), ocr_scanned=True).pages[0]
    boxes = [b for b in suggest_cells_maximal(str(tpl_scan), 0, tpl_page)
             if (b.get("anchor") or {}).get("label") and b["x0"] > 100]      # 값 칸만
    for b in boxes:                      # 라벨 기준 추출 켜기(디자이너의 '⇄ 항목명'과 같은 상태)
        b["use_anchor"] = True
        b["field"] = (b.get("anchor") or {}).get("label")

    # 입력: 맨 위에 줄이 하나 더 생겨 아래가 전부 밀린 스캔본
    in_txt = tmp_path / "in.pdf"
    in_scan = tmp_path / "in_scan.pdf"
    _form(in_txt, rows=[("조사일자", "2026-06-16"), *ROWS])
    _rasterize(in_txt, in_scan)
    doc = read_pdf(str(in_scan), ocr_scanned=True)
    row = apply_pixel_template(doc.pages, boxes, pdf_path=str(in_scan))
    assert row.get("하천명") == "해남천"
    assert row.get("어도유무") == "있음"
    assert (row.get("보길이") or "").strip() == "30"
