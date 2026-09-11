"""박스 자리와 맞지 않게 저장된 라벨(앵커)은 따라가지 않는다 — 좌표로 읽는다.

실제 사례: 횡적 연속성 조사표에서 '길이' 행의 값 칸에 열 머리글 '보통'이 라벨로, 방향은
'오른쪽'으로 저장돼 있어, 값 '531m' 대신 옆 머리글 '미흡'을 읽었다(박스 위치는 정확).
라벨이 맞게 저장된 박스의 '줄 밀림 대응(유기적 추출)'은 그대로 유지돼야 한다.
"""
from pathlib import Path

import fitz

from core.anchor_check import validate_anchors
from core.pdf_pipeline import apply_pixel_template, suggest_from_cells
from core.pdf_reader import read_pdf

GRADES = ["매우우수", "우수", "보통", "미흡"]


def _grade_form(path: Path, length: str = "531m", y_top: float = 80):
    """등급 머리글 한 줄 + '길이' 행. 보통 열의 길이 칸에만 값이 있다."""
    doc = fitz.open()
    page = doc.new_page(width=520, height=300)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    xs = [40, 120, 220, 320, 420, 500]
    ys = [y_top, y_top + 25, y_top + 50]
    for yy in ys:
        page.draw_line((xs[0], yy), (xs[-1], yy), width=0.8)
    for xx in xs:
        page.draw_line((xx, ys[0]), (xx, ys[-1]), width=0.8)
    tw.append((xs[0] + 6, ys[0] + 17), "등급", font=font, fontsize=9)
    for k, g in enumerate(GRADES):
        tw.append((xs[k + 1] + 6, ys[0] + 17), g, font=font, fontsize=9)
    tw.append((xs[0] + 6, ys[1] + 17), "길이", font=font, fontsize=9)
    for k in range(4):
        tw.append((xs[k + 1] + 6, ys[1] + 17), length if GRADES[k] == "보통" else "m",
                  font=font, fontsize=9)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()
    return xs, ys


def _box(field, x0, y0, x1, y1, label, rel="right", use_anchor=False):
    return {"field": field, "page": 0, "mode": "text", "order": 1,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "anchor": {"label": label, "relation": rel}, "use_anchor": use_anchor}


def test_wrong_anchor_is_disabled_and_value_read_by_position(tmp_path):
    tpl = tmp_path / "tpl.pdf"
    xs, ys = _grade_form(tpl)
    # '보통' 열의 길이 칸 — 라벨은 열 머리글 '보통', 방향은 '오른쪽'(틀림)
    b = _box("횡단면_보통_길이", xs[3] + 1, ys[1] + 1, xs[4] - 1, ys[2] - 1, "보통")
    doc = read_pdf(str(tpl), ocr_scanned=False)

    before = apply_pixel_template(doc.pages, [dict(b)], pdf_path=str(tpl))
    assert before["횡단면_보통_길이"] == "미흡"          # 수정 전 증상: 옆 머리글을 읽음

    boxes = [dict(b)]
    assert validate_anchors(boxes, tpl) == 1 and boxes[0]["anchor_ok"] is False
    after = apply_pixel_template(doc.pages, boxes, pdf_path=str(tpl))
    assert after["횡단면_보통_길이"] == "531m"            # 좌표로 읽어 실제 값


def test_correct_anchor_kept_and_row_insert_still_followed(tmp_path):
    """라벨이 맞는 박스(왼쪽 칸 라벨 → 오른쪽 값)는 확인 통과 — 줄이 밀린 문서도 따라간다."""
    from tests.test_pdf_pipeline import _draw_form

    base = tmp_path / "base.pdf"
    _draw_form(base, [("하천명", "해남천"), ("보길이", "30")], y_top=60)
    boxes = suggest_from_cells(str(base), 0)
    assert validate_anchors(boxes, base) == 0
    assert all(b.get("anchor_ok", True) for b in boxes)

    drift = tmp_path / "drift.pdf"
    _draw_form(drift, [("조사구분", "정기"), ("하천명", "가곡천"), ("보길이", "25")], y_top=88)
    dd = read_pdf(str(drift), ocr_scanned=False)
    got = apply_pixel_template(dd.pages, boxes, pdf_path=str(drift))
    assert got.get("하천명") == "가곡천" and got.get("보길이") == "25"


def test_unverifiable_anchor_left_untouched(tmp_path):
    """라벨이 표 칸이 아니거나 양식 PDF가 없으면 판단하지 않는다(기존 동작 유지)."""
    tpl = tmp_path / "tpl.pdf"
    xs, ys = _grade_form(tpl)
    b = _box("x", xs[1] + 1, ys[1] + 1, xs[2] - 1, ys[2] - 1, "표에없는제목")
    boxes = [dict(b)]
    assert validate_anchors(boxes, tpl) == 0 and "anchor_ok" not in boxes[0]
    assert validate_anchors([dict(b)], tmp_path / "없는파일.pdf") == 0


def test_apply_auto_uses_template_pdf_to_check_anchors(tmp_path, monkeypatch):
    """4번 일괄 처리 — 저장된 템플릿의 양식 PDF로 앵커를 확인해 값이 맞게 나온다."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    tpl = tmp_path / "tpl.pdf"
    xs, ys = _grade_form(tpl)
    boxes = [_box("횡단면_보통_길이", xs[3] + 1, ys[1] + 1, xs[4] - 1, ys[2] - 1, "보통")]
    store = type("S", (), {"list_names": lambda self: ["등급표"],
                           "get": lambda self, n: {"name": "등급표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    inp = tmp_path / "in.pdf"
    _grade_form(inp, length="612m")
    client = TestClient(app_main.app)
    with inp.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__",
                              "auto_classify": "1"},
                        files=[("files", ("in.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    rows = app_main._PDF_APPLY["rows"]
    assert len(rows) == 1 and rows[0]["횡단면_보통_길이"] == "612m"
    assert "anchor_ok" not in boxes[0]                      # 저장된 템플릿 원본은 건드리지 않음
