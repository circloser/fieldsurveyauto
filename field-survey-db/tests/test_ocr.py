"""OCR 기본 탑재 검증 — 글자 레이어가 없는 스캔·수기(손글씨 느낌) 문서.

수기 대용: Windows 궁서체(batang.ttc 2번 face, 붓글씨 계열)로 값을 그린 이미지 PDF.
OCR 엔진(easyocr)이 없는 환경에서는 건너뛴다.
"""
from pathlib import Path

import pytest

from tests.test_pdf_pipeline import _draw_form  # noqa: F401  (라벨 지문 비교용)

FONT_TTC = r"C:\Windows\Fonts\batang.ttc"


def _font(size, idx):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_TTC, size, index=idx)
    except Exception:  # noqa: BLE001
        pytest.skip("궁서/바탕 폰트 없음")


def _make_scanned(path: Path, title: str, rows, W=1240, H=1000, dpi=150):
    """글자 레이어 없는 이미지 PDF(스캔본) — 라벨은 인쇄체, 값은 궁서(수기 대용)."""
    import fitz
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    dr.text((180, 40), title, font=_font(76, 0), fill="black")
    x0, x1, x2, rh, y = 120, 480, 1120, 110, 200
    for i, (lab, val) in enumerate(rows):
        yy = y + i * rh
        dr.rectangle([x0, yy, x1, yy + rh], outline="black", width=3)
        dr.rectangle([x1, yy, x2, yy + rh], outline="black", width=3)
        dr.text((x0 + 24, yy + 28), lab, font=_font(44, 0), fill="black")
        if val:
            dr.text((x1 + 30, yy + 22), val, font=_font(50, 2), fill="black")
    png = path.with_suffix(".png")
    img.save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * 72 / dpi, height=H * 72 / dpi)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()
    return {"scale": 72 / dpi, "x0": x0, "x1": x1, "x2": x2, "rh": rh, "y": y}


def _vector_twin(path: Path, title: str, rows, geo):
    """같은 좌표의 벡터(글자 레이어 있는) 양식 — 템플릿 제작용."""
    import fitz
    s = geo["scale"]
    doc = fitz.open()
    page = doc.new_page(width=1240 * s, height=1000 * s)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((180 * s, (40 + 70) * s), title, font=font, fontsize=76 * s)
    for i, (lab, _) in enumerate(rows):
        yy = (geo["y"] + i * geo["rh"]) * s
        page.draw_rect(fitz.Rect(geo["x0"] * s, yy, geo["x1"] * s, yy + geo["rh"] * s),
                       color=(0, 0, 0), width=0.8)
        page.draw_rect(fitz.Rect(geo["x1"] * s, yy, geo["x2"] * s, yy + geo["rh"] * s),
                       color=(0, 0, 0), width=0.8)
        tw.append(((geo["x0"] + 24) * s, yy + 70 * s), lab, font=font, fontsize=44 * s * 0.75)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def ocr_ready():
    from core import ocr
    if not ocr.available():
        pytest.skip("OCR 엔진(easyocr) 없음")
    return True


def test_ocr_reads_handwriting_style_values(tmp_path, ocr_ready):
    """스캔·수기(궁서체) 문서 — OCR이 값을 읽어 단어를 채운다."""
    from core.pdf_reader import read_pdf

    rows = [("하천명", "가곡천"), ("관리기관", "강원 삼척시"), ("보길이", "25"), ("조사일", "7월 1일")]
    p = tmp_path / "scan.pdf"
    _make_scanned(p, "하천 조사표", rows)
    d = read_pdf(str(p), ocr_scanned=True)
    pg = d.pages[0]
    assert pg.needs_ocr and pg.ocr
    got = " ".join(w.text for w in pg.words)
    for target in ("가곡천", "삼척시", "25", "7월"):
        assert target in got, f"OCR 미인식: {target} / 인식={got}"


def test_ocr_scanned_page_title_and_extraction(tmp_path, ocr_ready, monkeypatch):
    """스캔 문서도 제목을 감지(OCR 단어 크기)해 양식을 확인하고, 값을 추출한다."""
    import json
    from fastapi.testclient import TestClient
    import app.main as app_main
    from core.pdf_pipeline import detect_title_from_words, suggest_from_cells
    from core.pdf_reader import read_pdf

    rows = [("하천명", "가곡천"), ("관리기관", "강원 삼척시"), ("보길이", "25"), ("조사일", "7월 1일")]
    scan = tmp_path / "scan.pdf"
    geo = _make_scanned(scan, "하천 조사표", rows)
    # OCR 제목 감지
    d = read_pdf(str(scan), ocr_scanned=True)
    assert "조사표" in detect_title_from_words(d.pages[0])

    # 같은 좌표의 벡터 양식으로 템플릿 제작 → 스캔본 일괄 처리
    tpl = tmp_path / "tpl.pdf"
    _vector_twin(tpl, "하천 조사표", rows, geo)
    boxes = suggest_from_cells(str(tpl), 0)
    assert {b["field"] for b in boxes} >= {"하천명", "보길이"}
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    client = TestClient(app_main.app)
    with scan.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__",
                              "auto_classify": "1"},
                        files=[("files", ("scan.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["ok_count"] == 1 and res["forms"] == 1
    assert res["by_form"][0]["form"] == "하천 조사표"       # OCR 제목으로 양식 확인
    assert not res.get("discarded")
    row = app_main._PDF_APPLY["rows"][0]
    assert row.get("하천명") == "가곡천"                     # OCR 단어로 값 추출
    assert row.get("보길이") == "25"
