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
