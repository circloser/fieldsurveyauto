"""같은 양식의 템플릿이 여러 개 저장돼 있을 때 — 일괄 처리가 어느 것을 쓰는가.

실사용(2026-09-18): 한 양식을 고쳐 가며 22·33·44 로 저장(33·44 에만 사진 칸을 '이미지' 유형으로).
쪽 배정 점수가 같아 먼저 저장한 22 가 배정돼 사진이 글자로 추출됐다. 이제 화면에 불러온 템플릿 > 최근 저장본 순."""
import json

from fastapi.testclient import TestClient

import app.main as app_main
from core.pdf_pipeline import IMG_PREFIX, suggest_from_cells
from tests.test_pdf_pipeline import _draw_form


def _store(entries: dict):
    return type("S", (), {"list_names": lambda self: list(entries), "get": lambda self, n: entries.get(n)})()


def _setup(tmp_path, monkeypatch):
    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", "해남천"), ("보 전경", "")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    old = [dict(b) for b in boxes]
    new = [dict(b) for b in boxes]
    photo = next(b for b in new if "전경" in b["field"])
    photo["mode"] = "image"
    photo_field = photo["field"]
    entries = {"22": {"name": "22", "boxes": old, "saved_at": "2026-09-18T08:00:00"},
               "44": {"name": "44", "boxes": new, "saved_at": "2026-09-18T09:00:00"}}
    monkeypatch.setattr(app_main, "_TEMPLATES", _store(entries))
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)
    return tpl, old, photo_field


def _apply(tpl, boxes_json="[]"):
    c = TestClient(app_main.app)
    with tpl.open("rb") as f:
        r = c.post("/api/pdf/apply", data={"boxes": boxes_json, "sheet_name_field": "__group_title__", "auto_classify": "1"},
                   files=[("files", ("survey.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    rows = [row for g in app_main._PDF_APPLY["groups"] for row in g["rows"]]
    return d, rows


def test_newest_duplicate_template_wins(tmp_path, monkeypatch):
    """저장 순서는 22 → 44 지만 최근 저장본(44, 이미지 박스)이 쓰여 사진이 그림으로 나온다."""
    tpl, _, photo_field = _setup(tmp_path, monkeypatch)
    d, rows = _apply(tpl)
    assert [m["template"] for m in d["match_info"]] == ["44"]
    assert rows and rows[0][photo_field].startswith(IMG_PREFIX)


def test_template_loaded_on_screen_wins_over_newer_duplicate(tmp_path, monkeypatch):
    """화면에 예전 템플릿(22)을 불러온 채 실행하면 그 템플릿이 우선(사용자가 보고 있는 것)."""
    tpl, old, photo_field = _setup(tmp_path, monkeypatch)
    d, rows = _apply(tpl, json.dumps(old, ensure_ascii=False))
    assert [m["template"] for m in d["match_info"]] == ["22"]
    assert rows and not str(rows[0][photo_field]).startswith(IMG_PREFIX)


def test_save_reports_duplicates_and_stamps_time(tmp_path, monkeypatch):
    """저장 API — 같은 자리의 박스를 다른 이름으로 저장하면 duplicates 로 알려 주고, 저장본에는 saved_at 이 남는다."""
    from core.template.store import TemplateStore

    store = TemplateStore(tmp_path / "templates.json")
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    c = TestClient(app_main.app)
    assert c.post("/api/designer/save", json={"name": "22", "boxes": boxes}).json()["duplicates"] == []
    changed = [dict(b, mode="image") for b in boxes]                 # 유형만 바꾼 같은 양식
    d = c.post("/api/designer/save", json={"name": "44", "boxes": changed}).json()
    assert d["ok"] and d["duplicates"] == ["22"]
    assert store.get("44")["saved_at"] >= store.get("22")["saved_at"]
