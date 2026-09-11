"""사진 경계 찾기 — 조사표 사진 칸을 사진 테두리에 맞춰 자르고, 사진 모음 쪽의 사진·설명을 꺼낸다.

실제 사례(저어새 조사표 스캔): 이미지 박스를 고정 좌표로 잘라 사진 윗부분이 잘리고 설명 글·칸 선이
섞였다(2026년 양식이 2024년 템플릿보다 약 36pt 아래). 사진만 모은 쪽(7~8장, 사진마다 '(설명) …')은
맞는 양식이 없어 통째로 버려졌다.
"""
from pathlib import Path

import fitz
import numpy as np

DPI = 150
S = 72 / DPI
SLOTS = [(80, 150), (640, 150), (80, 700), (640, 700)]      # 사진 왼쪽 위(px)
PW, PH = 520, 360


def _photo(seed: int, pale_sky: bool = False) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = rng.integers(40, 190, size=(PH, PW, 3), dtype=np.uint8)          # 짙은 풍경 무늬
    if pale_sky:                                                           # 위 40%는 옅은 하늘(종이와 거의 같은 밝기)
        sky = PH * 2 // 5
        img[:sky] = np.array([226, 232, 238], dtype=np.uint8) + rng.integers(0, 5, size=(sky, PW, 3), dtype=np.uint8)
    return img


def _scan_photo_page(path: Path) -> list[tuple[float, float, float, float]]:
    """사진 4장 스캔 쪽(그림 한 장) + 사진마다 아래에 설명 글(글자 레이어). 반환: 사진 위치(pt)."""
    from PIL import Image

    W, H = 1240, 1754
    canvas = np.full((H, W, 3), 255, dtype=np.uint8)
    rects = []
    for k, (x, y) in enumerate(SLOTS):
        canvas[y:y + PH, x:x + PW] = _photo(k, pale_sky=(k == 0))
        rects.append((x * S, y * S, (x + PW) * S, (y + PH) * S))
    png = path.with_suffix(".png")
    Image.fromarray(canvas).save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * S, height=H * S)
    page.insert_image(page.rect, filename=str(png))
    tw = fitz.TextWriter(page.rect)
    font = fitz.Font("cjk")
    for k, r in enumerate(rects):
        tw.append((r[0] + 4, r[3] + 12), f"(설명) 사진{k + 1} 번식지 전경", font=font, fontsize=9)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()
    return rects


def _near(a, b, tol=4.0):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def test_scan_photos_found_including_pale_sky(tmp_path):
    from core.photos import page_photos

    p = tmp_path / "photos.pdf"
    want = _scan_photo_page(p)
    got = page_photos(str(p), 0)
    assert len(got) == 4
    for g, w in zip(got, want):
        assert _near(g, w), (g, w)                       # 옅은 하늘까지 포함한 위쪽 경계


def test_photo_page_items_with_captions(tmp_path):
    from core.pdf_reader import read_pdf
    from core.photos import photo_page_items

    p = tmp_path / "photos.pdf"
    _scan_photo_page(p)
    page = read_pdf(str(p), ocr_scanned=False).pages[0]
    items = photo_page_items(str(p), page)
    assert items is not None and len(items) == 4
    assert [it["caption"] for it in items] == [f"(설명) 사진{k + 1} 번식지 전경" for k in range(4)]


def test_snap_image_box_to_photo_border(tmp_path):
    """템플릿 박스가 사진보다 아래·오른쪽으로 밀려 있어도 실제 사진 테두리로 자른다."""
    from core.photos import snap_photo_box

    p = tmp_path / "photos.pdf"
    want = _scan_photo_page(p)
    x0, y0, x1, y1 = want[0]
    bb = {"field": "조사사진1", "x0": x0 + 12, "y0": y0 + 30, "x1": x1 + 8, "y1": y1 + 34}
    got = snap_photo_box(str(p), 0, bb)
    assert _near((got["x0"], got["y0"], got["x1"], got["y1"]), want[0])
    assert got["field"] == "조사사진1"


def test_embedded_photo_in_text_pdf_exact(tmp_path):
    from PIL import Image

    from core.photos import page_photos, snap_photo_box

    png = tmp_path / "ph.png"
    Image.fromarray(_photo(7)).save(png)
    p = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 60), "Survey form", fontsize=14)
    page.insert_image(fitz.Rect(100, 400, 300, 540), filename=str(png), keep_proportion=False)
    doc.save(str(p))
    doc.close()
    assert page_photos(str(p), 0) == [(100, 400, 300, 540)]
    got = snap_photo_box(str(p), 0, {"x0": 90, "y0": 420, "x1": 310, "y1": 575})
    assert (got["x0"], got["y0"], got["x1"], got["y1"]) == (100, 400, 300, 540)


def test_template_image_box_crops_snapped_photo(tmp_path):
    """4번 일괄 처리의 이미지 박스 — 잘라 낸 그림 크기가 실제 사진 크기와 같다."""
    from core.pdf_pipeline import IMG_PREFIX, apply_pixel_template
    from core.pdf_reader import read_pdf

    p = tmp_path / "photos.pdf"
    want = _scan_photo_page(p)
    x0, y0, x1, y1 = want[1]
    box = {"field": "사진", "page": 0, "mode": "image", "order": 1,
           "x0": x0 - 10, "y0": y0 + 25, "x1": x1 - 5, "y1": y1 + 30, "use_anchor": False, "anchor": None}
    got = apply_pixel_template(read_pdf(str(p), ocr_scanned=False).pages, [box], pdf_path=str(p))
    path = got["사진"][len(IMG_PREFIX):]
    pix = fitz.Pixmap(path)
    assert abs(pix.width - (x1 - x0) * 150 / 72) <= 12 and abs(pix.height - (y1 - y0) * 150 / 72) <= 12


def test_photo_only_page_becomes_photo_sheet(tmp_path, monkeypatch):
    """4번 일괄 처리 — 사진만 모은 쪽은 버리지 않고 '현장 사진' 시트에 사진·설명이 한 장씩 들어간다."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    from core.pdf_pipeline import IMG_PREFIX, suggest_from_cells
    from tests.test_pdf_pipeline import _draw_form

    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    p = tmp_path / "photos.pdf"
    _scan_photo_page(p)
    client = TestClient(app_main.app)
    with p.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__", "auto_classify": "1"},
                        files=[("files", ("photos.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    assert not r.json().get("discarded")
    g = next(g for g in app_main._PDF_APPLY["groups"] if g["label"] == "현장 사진")
    assert [row["설명"] for row in g["rows"]] == [f"(설명) 사진{k + 1} 번식지 전경" for k in range(4)]
    assert [row["번호"] for row in g["rows"]] == [1, 2, 3, 4]
    assert all(Path(row["사진"][len(IMG_PREFIX):]).exists() for row in g["rows"])
