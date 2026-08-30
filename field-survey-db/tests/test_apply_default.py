"""4번 일괄 처리 기본 흐름 — 자동 대조 + 제목별 시트(제목 없으면 시트 하나)."""
import io
import json

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import app
from tests.test_pdf_pipeline import _draw_form

client = TestClient(app)


def _boxes_for(pdf_path):
    from core.pdf_pipeline import suggest_from_cells
    return suggest_from_cells(str(pdf_path), 0)


def _apply(named_files, boxes):
    files = [("files", (name, open(path, "rb"), "application/pdf"))
             for name, path in named_files]
    try:
        return client.post(
            "/api/pdf/apply",
            data={"boxes": json.dumps(boxes),
                  "sheet_name_field": "__group_title__",
                  "auto_classify": "1"},
            files=files)
    finally:
        for _, (_, fh, _) in files:
            fh.close()


def test_default_apply_groups_by_title(tmp_path):
    """제목이 다른 조사표 → 제목 이름의 시트로 나뉜다(제목 박스 없어도 큰 글씨 감지)."""
    base = tmp_path / "base.pdf"
    _draw_form(base, [("하천명", "한천"), ("보길이", "30")], y_top=60, title="하천 조사표")
    a = tmp_path / "a.pdf"
    _draw_form(a, [("하천명", "가곡천"), ("보길이", "25")], y_top=60, title="하천 조사표")
    b = tmp_path / "b.pdf"
    _draw_form(b, [("하천명", "묵논습지"), ("보길이", "12")], y_top=60, title="습지 조사표")

    r = _apply([("a.pdf", a), ("b.pdf", b)], _boxes_for(base))
    assert r.status_code == 200
    d = r.json()
    assert d["auto_classify"] is True
    assert d["ok_count"] == 2
    assert d["forms"] == 2
    assert {g["form"] for g in d["by_form"]} == {"하천 조사표", "습지 조사표"}

    dl = client.get("/api/pdf/download")
    assert dl.status_code == 200
    wb = load_workbook(io.BytesIO(dl.content))
    assert set(wb.sheetnames) == {"하천 조사표", "습지 조사표"}


def test_default_apply_without_title_single_sheet(tmp_path):
    """제목이 아예 없으면 — 전부 시트 하나(추출결과)에 들어간다."""
    base = tmp_path / "base.pdf"
    _draw_form(base, [("하천명", "한천"), ("보길이", "30")], y_top=60)
    a = tmp_path / "a.pdf"
    _draw_form(a, [("하천명", "가곡천"), ("보길이", "25")], y_top=60)
    b = tmp_path / "b.pdf"
    _draw_form(b, [("하천명", "오십천"), ("보길이", "18")], y_top=60)

    r = _apply([("a.pdf", a), ("b.pdf", b)], _boxes_for(base))
    assert r.status_code == 200
    d = r.json()
    assert d["auto_classify"] is True
    assert d["ok_count"] == 2
    assert d["forms"] == 1
    assert d["by_form"][0]["form"] == "추출결과"

    dl = client.get("/api/pdf/download")
    wb = load_workbook(io.BytesIO(dl.content))
    assert wb.sheetnames == ["추출결과"]
    ws = wb["추출결과"]
    assert ws.max_row == 3  # 헤더 + 2행


class _FakeStore:
    def __init__(self, d):
        self.d = d

    def list_names(self):
        return list(self.d)

    def get(self, n):
        return self.d.get(n)


def test_classify_bundles_by_title_similarity(tmp_path, monkeypatch):
    """한 파일에 제목이 다른 조사표가 섞여 있으면 — 입력 제목이 템플릿 제목과
    유사한 양식으로 각각 분류되어 제목별 시트로 나뉜다(라벨이 같아도 제목이 가른다)."""
    import app.main as app_main

    # 템플릿 2개: 표 구조(라벨)는 같고 제목만 다름
    tpl_a = tmp_path / "tpl_하천.pdf"
    _draw_form(tpl_a, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    tpl_b = tmp_path / "tpl_습지.pdf"
    _draw_form(tpl_b, [("하천명", ""), ("보길이", "")], y_top=60, title="습지 조사표")
    tpl_paths = {"하천": tpl_a, "습지": tpl_b}
    store = _FakeStore({
        "하천": {"name": "하천", "boxes": _boxes_for(tpl_a)},
        "습지": {"name": "습지", "boxes": _boxes_for(tpl_b)},
    })
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl_paths[name])

    # 입력: 두 양식이 섞인 한 파일 (제목 끝 숫자까지 포함)
    import fitz
    p1 = tmp_path / "p1.pdf"
    _draw_form(p1, [("하천명", "가곡천"), ("보길이", "25")], y_top=60, title="하천 조사표 1")
    p2 = tmp_path / "p2.pdf"
    _draw_form(p2, [("하천명", "묵논습지"), ("보길이", "12")], y_top=60, title="습지 조사표 1")
    mixed = tmp_path / "mixed.pdf"
    m = fitz.open()
    for p in (p1, p2):
        src = fitz.open(str(p))
        m.insert_pdf(src)
        src.close()
    m.save(str(mixed))
    m.close()

    r = _apply([("mixed.pdf", mixed)], [])   # 현재 박스 없이 — 저장 템플릿만으로 분류
    assert r.status_code == 200
    d = r.json()
    assert d["ok_count"] == 2
    assert d["forms"] == 2
    assert {g["form"] for g in d["by_form"]} == {"하천 조사표 1", "습지 조사표 1"}
    tpl_used = {m2["template"] for m2 in d["match_info"]}
    assert tpl_used == {"하천", "습지"}      # 제목 유사도로 각자 맞는 템플릿에 배정

    import io
    from openpyxl import load_workbook
    dl = client.get("/api/pdf/download")
    wb = load_workbook(io.BytesIO(dl.content))
    assert set(wb.sheetnames) == {"하천 조사표 1", "습지 조사표 1"}
    ws = wb["하천 조사표 1"]
    vals = [c.value for row in ws.iter_rows(min_row=2) for c in row]
    assert "가곡천" in vals                   # 값도 맞는 시트에 들어간다


def test_page_level_classify_title_only(tmp_path, monkeypatch):
    """페이지 단위 대조 — 표 라벨이 템플릿과 달라도(라벨 근거 0) 페이지 제목이
    템플릿 제목과 유사하면 그 양식으로 배정되어 제목별 시트로 정리된다."""
    import app.main as app_main

    tpl_a = tmp_path / "tpl_하천.pdf"
    _draw_form(tpl_a, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    tpl_b = tmp_path / "tpl_습지.pdf"
    _draw_form(tpl_b, [("습지명", ""), ("수심", "")], y_top=60, title="습지 조사표")
    tpl_paths = {"하천": tpl_a, "습지": tpl_b}
    store = _FakeStore({
        "하천": {"name": "하천", "boxes": _boxes_for(tpl_a)},
        "습지": {"name": "습지", "boxes": _boxes_for(tpl_b)},
    })
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl_paths[name])

    # 입력: 라벨이 다른(명칭/길이) 페이지들 — 제목만이 분류 근거
    import fitz
    p1 = tmp_path / "p1.pdf"
    _draw_form(p1, [("명칭", "가곡천"), ("길이", "25")], y_top=60, title="하천 조사표 5")
    p2 = tmp_path / "p2.pdf"
    _draw_form(p2, [("명칭", "묵논습지"), ("길이", "12")], y_top=60, title="습지 조사표 5")
    mixed = tmp_path / "mixed2.pdf"
    m = fitz.open()
    for p in (p1, p2):
        src = fitz.open(str(p))
        m.insert_pdf(src)
        src.close()
    m.save(str(mixed))
    m.close()

    r = _apply([("mixed2.pdf", mixed)], [])
    assert r.status_code == 200
    d = r.json()
    assert d["ok_count"] == 2
    assert d["forms"] == 2
    assert {g["form"] for g in d["by_form"]} == {"하천 조사표 5", "습지 조사표 5"}
    tpl_used = {m2["template"] for m2 in d["match_info"]}
    assert tpl_used == {"하천", "습지"}

    import io
    from openpyxl import load_workbook
    dl = client.get("/api/pdf/download")
    wb = load_workbook(io.BytesIO(dl.content))
    assert set(wb.sheetnames) == {"하천 조사표 5", "습지 조사표 5"}
    vals = [c.value for row in wb["하천 조사표 5"].iter_rows(min_row=2) for c in row]
    assert "가곡천" in vals   # 라벨이 달라도 좌표 폴백으로 값까지 추출
