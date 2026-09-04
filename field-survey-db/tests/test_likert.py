"""척도표(리커트) 설문 — 스캔본에서 '문항 행 × 점수 열' 격자의 손표시를 잉크로 판정."""
from pathlib import Path

import pytest

FONT_TTC = r"C:\Windows\Fonts\batang.ttc"
ROWS = ["1-1 메뉴가 명확하게 구분되어 있는가?", "1-2 필요한 정보를 쉽게 찾을 수 있는가?",
        "2-1 페이지로 쉽게 돌아갈 수 있는가?", "2-2 현재 위치를 명확히 알 수 있는가?"]


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_TTC, size, index=0)
    except Exception:  # noqa: BLE001
        pytest.skip("바탕 폰트 없음")


def _likert_scan(path: Path, marks: dict[int, tuple[int, str]], header: bool = True,
                 W=1240, H=900, dpi=150):
    """리커트 격자 스캔본. marks: {행 index: (열 1~5, 'circle'|'check'|'slash')}.
    header=False 면 머리글(1점~5점)을 지운 쪽(OCR 실패 상황 재현)."""
    import fitz
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    dr.text((300, 40), "시스템 사용 만족도 설문", font=_font(52), fill="black")
    cols = [800, 880, 960, 1040, 1120]
    y0 = 200
    if header:
        for k, x in enumerate(cols, 1):
            dr.text((x - 18, y0 - 60), f"{k}점", font=_font(30), fill="black")
    dr.line([(80, y0 - 20), (1180, y0 - 20)], fill="black", width=2)
    n = len(ROWS)
    for x in [80, 170, 760] + [c + 40 for c in cols]:          # 세로선: 번호 | 질문 | 점수 칸들
        dr.line([(x, y0 - 90), (x, y0 + n * 90 - 45)], fill="black", width=2)
    for i, txt in enumerate(ROWS):
        y = y0 + i * 90
        qid, qtxt = txt.split(" ", 1)
        dr.text((95, y - 18), qid, font=_font(30), fill="black")
        dr.text((185, y - 18), qtxt, font=_font(30), fill="black")
        for k, x in enumerate(cols, 1):
            dr.text((x - 14, y - 20), "①②③④⑤"[k - 1], font=_font(34), fill="black")
        dr.line([(80, y + 45), (1180, y + 45)], fill="black", width=2)
        if i in marks:
            col, kind = marks[i]
            cx, cy = cols[col - 1], y
            if kind == "circle":
                dr.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline="black", width=5)
            elif kind == "check":
                dr.line([(cx - 12, cy), (cx - 2, cy + 14), (cx + 18, cy - 18)], fill="black", width=4)
            elif kind == "slash":
                dr.line([(cx - 14, cy + 16), (cx + 14, cy - 16)], fill="black", width=4)
    png = path.with_suffix(".png")
    img.save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * 72 / dpi, height=H * 72 / dpi)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def ocr_ready():
    from core import ocr
    if not ocr.available():
        pytest.skip("OCR 엔진(easyocr) 없음")


def test_likert_grid_marks(tmp_path, ocr_ready):
    """동그라미·체크·사선 손표시를 행마다 점수(1~5)로 판정하고, 무응답 행은 비운다."""
    from core.likert import _COL_CACHE, extract_likert, parse_likert
    from core.pdf_reader import read_pdf

    p = tmp_path / "likert.pdf"
    _likert_scan(p, {0: (4, "circle"), 1: (3, "check"), 2: (5, "slash")})   # 4행은 무응답
    d = read_pdf(str(p), ocr_scanned=True)
    pg = d.pages[0]
    g = parse_likert(pg)
    assert g is not None and len(g.columns) == 5 and len(g.rows) == 4
    _COL_CACHE.clear()
    row = extract_likert(pg, pdf_path=str(p))
    assert row is not None
    keys = sorted(k for k in row if k.startswith("문항"))
    assert keys == ["문항01", "문항02", "문항03", "문항04"]    # 스캔본은 행 순서 열 이름
    assert row["문항01"] == "4" and row["문항02"] == "3" and row["문항03"] == "5"
    assert row["문항04"] == ""                                # 무응답
    assert "문항01" not in row.get("_이상치", {})             # 뚜렷한 동그라미는 확인 요청 없음


def test_likert_columns_borrowed_when_header_unreadable(tmp_path, ocr_ready):
    """머리글(1점~5점)이 없는/못 읽은 쪽도 같은 문서의 다른 쪽 열 위치를 빌려 판정한다."""
    import fitz
    from core.likert import _COL_CACHE, extract_likert
    from core.pdf_reader import read_pdf

    a = tmp_path / "a.pdf"
    _likert_scan(a, {0: (2, "circle")}, header=True)
    b = tmp_path / "b.pdf"
    _likert_scan(b, {1: (4, "circle")}, header=False)
    both = tmp_path / "both.pdf"
    m = fitz.open()
    for p in (a, b):
        src = fitz.open(str(p)); m.insert_pdf(src); src.close()
    m.save(str(both)); m.close()

    d = read_pdf(str(both), ocr_scanned=True)
    _COL_CACHE.clear()
    r1 = extract_likert(d.pages[0], pdf_path=str(both))
    r2 = extract_likert(d.pages[1], pdf_path=str(both))   # 머리글 없음 → 1쪽 열 위치 사용
    assert r1 and r1["문항01"] == "2"
    assert r2 is not None and r2["문항02"] == "4"
