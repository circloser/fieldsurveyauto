"""기울어진 스캔 쪽 바로잡기 + 칸을 못 찾을 때 라벨 글자로 위치 보정.

실제 사례(저어새 번식지 조사표 스캔): 1쪽 1.5°·6쪽 0.5° 기울어 칸 인식이 실패(칸 4·0개)하고
라벨을 하나도 못 따라가 좌표로만 읽어 값이 한 줄씩 밀렸다(조사자 칸에 '칠산도 날짜 2026. 5. 13 …').
2026년 양식이 2024년 템플릿보다 약 10pt 아래에 있어 좌표만으로는 한 줄이 어긋났다.
"""
from pathlib import Path

import fitz
import numpy as np
import pytest

FONT_TTC = r"C:\Windows\Fonts\batang.ttc"


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_TTC, size, index=0)
    except Exception:  # noqa: BLE001
        pytest.skip("바탕 폰트 없음")


def _scan_form(path: Path, angle: float, W=1240, H=1754, dpi=150):
    """표 선 8줄 + 항목 글자의 스캔 쪽(그림 한 장). angle(도, 반시계)만큼 기울임."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    for k in range(8):
        y = 200 + k * 60
        dr.line([(100, y), (1140, y)], fill="black", width=3)
    for x in (100, 400, 1140):
        dr.line([(x, 200), (x, 200 + 7 * 60)], fill="black", width=3)
    for k in range(7):
        dr.text((120, 212 + k * 60), f"항목{k + 1}", font=_font(30), fill="black")
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, fillcolor="white")
    png = path.with_suffix(".png")
    img.save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * 72 / dpi, height=H * 72 / dpi)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()


def _skew_of(pdf) -> float | None:
    from core.deskew import estimate_skew
    d = fitz.open(str(pdf))
    pix = d[0].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    d.close()
    return estimate_skew(gray)


def test_tilted_scan_is_straightened(tmp_path):
    from core.deskew import deskew_pdf

    src = tmp_path / "tilted.pdf"
    _scan_form(src, 1.5)
    a0 = _skew_of(src)
    assert a0 is not None and abs(abs(a0) - 1.5) < 0.3
    out = deskew_pdf(str(src), str(tmp_path / "cache"))
    assert out != str(src) and Path(out).exists()
    a1 = _skew_of(out)
    assert a1 is None or abs(a1) < 0.3                       # 곧게 폈다(반대로 돌렸으면 3°)
    assert deskew_pdf(str(src), str(tmp_path / "cache")) == out


def test_straight_scan_and_text_pdf_untouched(tmp_path):
    from core.deskew import deskew_pdf

    src = tmp_path / "straight.pdf"
    _scan_form(src, 0)
    assert deskew_pdf(str(src), str(tmp_path / "c")) == str(src)
    txt = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    for k in range(5):
        page.draw_line((50, 100 + k * 20), (550, 110 + k * 20))
    doc.save(str(txt))
    doc.close()
    assert deskew_pdf(str(txt), str(tmp_path / "c")) == str(txt)   # 글자 PDF는 대상 아님


def test_to_pdf_uses_straightened_copy(tmp_path):
    from core.pdf_pipeline import to_pdf

    src = tmp_path / "tilted.pdf"
    _scan_form(src, -1.2)
    assert to_pdf(str(src), str(tmp_path / "cache")) != str(src)


def test_label_words_correct_position_when_no_cells(tmp_path):
    """표 선이 없어 칸을 못 찾는 쪽 — 라벨 글자 위치로 쪽 이동량을 재서 값을 제자리에서 읽는다."""
    from core.pdf_pipeline import apply_pixel_template
    from core.pdf_reader import read_pdf

    rows = [("조사지역", "칠산도"), ("조사일자", "2026.5.13"), ("조사시간", "13:00"), ("둥지합계", "375")]

    def draw(path, dy):
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        font = fitz.Font("cjk")
        tw = fitz.TextWriter(page.rect)
        for k, (lab, val) in enumerate(rows):
            y = 120 + k * 25 + dy
            tw.append((50, y), lab, font=font, fontsize=10)
            tw.append((160, y), val, font=font, fontsize=10)
        tw.write_text(page)
        doc.save(str(path))
        doc.close()

    tpl = tmp_path / "tpl.pdf"
    draw(tpl, 0)
    words = read_pdf(str(tpl), ocr_scanned=False).pages[0].words
    boxes = []
    for k, (lab, val) in enumerate(rows):
        vw = next(w for w in words if w.text == val)
        boxes.append({"field": lab, "page": 0, "mode": "text", "order": k,
                      "x0": 150, "y0": vw.cy - 9, "x1": 320, "y1": vw.cy + 9,
                      "use_anchor": False, "anchor": {"label": lab, "relation": "right"}})

    same = apply_pixel_template(read_pdf(str(tpl), ocr_scanned=False).pages, boxes, pdf_path=str(tpl))
    assert same == dict(rows)

    moved = tmp_path / "moved.pdf"
    draw(moved, 14)                                           # 줄 간격(25pt)의 절반을 넘게 밀림
    got = apply_pixel_template(read_pdf(str(moved), ocr_scanned=False).pages, boxes, pdf_path=str(moved))
    assert got == dict(rows)
