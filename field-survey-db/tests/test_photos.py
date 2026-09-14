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


def _photo_form(path: Path):
    """사진 양식 쪽(탄천·양양 '1차 인공구조물 현장 사진'과 같은 짜임): 왼쪽 묶음 칸 + 칸 이름 + 이름 아래 사진 칸."""
    from PIL import Image

    png = path.with_suffix(".png")
    Image.fromarray(_photo(11)).save(png)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((200, 70), "1차 인공구조물 현장 사진", font=font, fontsize=14)
    xs = [91, 229, 368, 506]
    groups = [("보 전경", ["상류 방향", "하류 방향", "측면 (좌안 □/ 우안 ☑)"], [0, 1]),
              ("어도", ["어도 입구", "어도 내부", "어도 출구"], [2])]
    y = 103
    for glabel, heads, filled in groups:
        page.draw_rect(fitz.Rect(58, y, 91, y + 149), color=(0, 0, 0), width=0.7)
        tw.append((61, y + 78), glabel, font=font, fontsize=7)
        for k in range(3):
            page.draw_rect(fitz.Rect(xs[k], y, xs[k + 1], y + 14), color=(0, 0, 0), width=0.7)
            page.draw_rect(fitz.Rect(xs[k], y + 14, xs[k + 1], y + 149), color=(0, 0, 0), width=0.7)
            tw.append((xs[k] + 30, y + 10), heads[k], font=font, fontsize=7)
            if k in filled:
                page.insert_image(fitz.Rect(xs[k] + 7, y + 18, xs[k + 1] - 3, y + 145), filename=str(png),
                                  keep_proportion=False)
        y += 149
    tw.append((60, 420), "※ 기타 : 구조물 파손, 낙차불량, 퇴적 현황 등", font=font, fontsize=8)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def test_photo_form_captions_from_cell_labels(tmp_path):
    from core.pdf_reader import read_pdf
    from core.photos import photo_form_items, photo_page_items

    p = tmp_path / "form.pdf"
    _photo_form(p)
    page = read_pdf(str(p), ocr_scanned=False).pages[0]
    assert photo_page_items(str(p), page) is None                  # 사진 대지 규칙으로는 안 잡힘(예전에 버려진 이유)
    items = photo_form_items(str(p), page)
    assert items is not None
    assert [it["caption"] for it in items] == ["보 전경 · 상류 방향", "보 전경 · 하류 방향", "어도 · 어도 출구"]


def test_survey_sheet_with_photo_slots_is_not_photo_form(tmp_path):
    """조사표 아래쪽에 '조사사진 1·2' 칸이 딸린 쪽은 사진 양식이 아니다(맞는 템플릿이 없을 때 사진 행으로 새지 않게)."""
    from PIL import Image

    from core.pdf_reader import read_pdf
    from core.photos import photo_form_items

    png = tmp_path / "ph.png"
    Image.fromarray(_photo(5)).save(png)
    p = tmp_path / "sheet.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    rows = [("조사지역", "칠산도"), ("날짜", "2026. 5. 13."), ("조사자", "김철수"), ("번식준비", "1"),
            ("포란", "287"), ("육추", "87"), ("둥지합계", "375"), ("동소종 현황", "노랑부리백로 31쌍")]
    for k, (lab, val) in enumerate(rows):
        y = 80 + k * 20
        page.draw_rect(fitz.Rect(30, y, 130, y + 20), color=(0, 0, 0), width=0.7)
        page.draw_rect(fitz.Rect(130, y, 566, y + 20), color=(0, 0, 0), width=0.7)
        tw.append((34, y + 14), lab, font=font, fontsize=8)
        tw.append((134, y + 14), val, font=font, fontsize=8)
    for x0, x1, lab in ((30, 298, "조사사진 1"), (298, 566, "조사사진 2")):
        page.draw_rect(fitz.Rect(x0, 300, x1, 315), color=(0, 0, 0), width=0.7)
        page.draw_rect(fitz.Rect(x0, 315, x1, 500), color=(0, 0, 0), width=0.7)
        tw.append((x0 + 4, 311), lab, font=font, fontsize=8)
        page.insert_image(fitz.Rect(x0 + 6, 320, x1 - 6, 495), filename=str(png), keep_proportion=False)
    tw.write_text(page)
    doc.save(str(p))
    doc.close()
    assert photo_form_items(str(p), read_pdf(str(p), ocr_scanned=False).pages[0]) is None


def test_album_page_is_not_photo_form(tmp_path):
    """사진 대지(사진 + 아래 '(설명) …')는 사진 양식 규칙에 걸리지 않고 기존 규칙으로 읽힌다."""
    from core.pdf_reader import read_pdf
    from core.photos import photo_form_items

    p = tmp_path / "album.pdf"
    _scan_photo_page(p)
    assert photo_form_items(str(p), read_pdf(str(p), ocr_scanned=False).pages[0]) is None


def test_photo_form_page_after_sheet_goes_to_photo_sheet(tmp_path, monkeypatch):
    import app.main as app_main
    from fastapi.testclient import TestClient

    from core.pdf_pipeline import suggest_from_cells
    from tests.test_pdf_pipeline import _draw_form

    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", "탄천"), ("보길이", "30")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    form = tmp_path / "form.pdf"
    _photo_form(form)
    bundle = tmp_path / "bundle.pdf"
    m = fitz.open()
    for src in (tpl, form):
        s = fitz.open(str(src))
        m.insert_pdf(s)
        s.close()
    m.save(str(bundle))
    m.close()
    client = TestClient(app_main.app)
    with bundle.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__", "auto_classify": "1"},
                        files=[("files", ("bundle.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    assert not r.json().get("discarded")
    g = next(g for g in app_main._PDF_APPLY["groups"] if g["label"] == "현장 사진")
    assert [row["설명"] for row in g["rows"]] == ["보 전경 · 상류 방향", "보 전경 · 하류 방향", "어도 · 어도 출구"]


def test_photo_pages_only_right_after_survey_sheets(tmp_path, monkeypatch):
    """조사표가 있는 파일에서는 조사표 바로 뒤에 이어진 사진 쪽만 '현장 사진' — 본문 뒤의 그림 쪽은 버림.
    혼합 일괄 점검에서 지침(131쪽)의 그림 쪽 15쪽('<그림 10> 조사정점 설정', 화면 캡처)이 사진으로 오인됐다."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    from core.pdf_pipeline import suggest_from_cells
    from tests.test_pdf_pipeline import _draw_form

    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", "해남천"), ("보길이", "30")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    photo = tmp_path / "photos.pdf"
    _scan_photo_page(photo)
    text = tmp_path / "text.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "Appendix notes page without photos", fontsize=12)
    doc.save(str(text))
    doc.close()
    bundle = tmp_path / "bundle.pdf"
    m = fitz.open()
    for src in (tpl, photo, text, photo):                    # 조사표 · 사진 · 본문 · 사진
        s = fitz.open(str(src))
        m.insert_pdf(s)
        s.close()
    m.save(str(bundle))
    m.close()

    client = TestClient(app_main.app)
    with bundle.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__", "auto_classify": "1"},
                        files=[("files", ("bundle.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    g = next(g for g in app_main._PDF_APPLY["groups"] if g["label"] == "현장 사진")
    assert {row["쪽"] for row in g["rows"]} == {2}                 # 조사표(1쪽) 바로 뒤 사진 쪽만
    assert sum(d["pages"] for d in r.json()["discarded"]) == 2    # 본문 쪽과 그 뒤 사진 쪽은 버림


def test_report_page_with_figures_is_not_photo_page(tmp_path):
    """본문 + 그림 쪽(지침·보고서)은 사진 모음이 아니다 — 혼합 일괄 점검에서 지침 15쪽이 '현장 사진'으로 오인됐다."""
    from PIL import Image

    from core.pdf_reader import read_pdf
    from core.photos import photo_page_items

    png = tmp_path / "fig.png"
    Image.fromarray(_photo(3)).save(png)

    def make(name, body_lines):
        p = tmp_path / name
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        font = fitz.Font("cjk")
        tw = fitz.TextWriter(page.rect)
        for r in ((20, 40, 300, 360), (305, 40, 585, 360)):
            page.insert_image(fitz.Rect(*r), filename=str(png), keep_proportion=False)
            tw.append((r[0] + 4, r[3] + 14), "(설명) 어도 입구부 전경", font=font, fontsize=9)
        for k in range(body_lines):
            tw.append((40, 420 + k * 18), "어도 입구부는 하류 수위 변동 범위를 고려하여 설치하며 유속은 어류 유영 능력 이내로 한다",
                      font=font, fontsize=10)
        tw.write_text(page)
        doc.save(str(p))
        doc.close()
        return p

    report = make("report.pdf", 8)
    assert photo_page_items(str(report), read_pdf(str(report), ocr_scanned=False).pages[0]) is None
    sheet = make("sheet.pdf", 0)
    items = photo_page_items(str(sheet), read_pdf(str(sheet), ocr_scanned=False).pages[0])
    assert items is not None and [it["caption"] for it in items] == ["(설명) 어도 입구부 전경"] * 2


def test_caption_box_follows_snapped_photo(tmp_path):
    """사진 설명 박스(caption_of)는 템플릿 좌표가 아니라 맞춘 사진 바로 아래 줄을 읽는다
    (2026년 조사표는 사진·설명이 2024년 템플릿보다 약 36pt 위에 있어 좌표로는 빈칸이었다)."""
    from core.pdf_pipeline import apply_pixel_template
    from core.pdf_reader import read_pdf

    p = tmp_path / "photos.pdf"
    want = _scan_photo_page(p)
    x0, y0, x1, y1 = want[1]
    boxes = [
        {"field": "조사사진 2", "page": 0, "mode": "image", "order": 1,
         "x0": x0, "y0": y0 + 40, "x1": x1, "y1": y1 + 40, "use_anchor": False, "anchor": None},
        {"field": "조사사진 2_설명", "page": 0, "mode": "text", "order": 2, "caption_of": "조사사진 2",
         "x0": x0, "y0": y1 + 40, "x1": x1, "y1": y1 + 60, "use_anchor": False, "anchor": None},
    ]
    got = apply_pixel_template(read_pdf(str(p), ocr_scanned=False).pages, boxes, pdf_path=str(p))
    assert got["조사사진 2_설명"] == "(설명) 사진2 번식지 전경"
