"""템플릿 디자이너 검증 — 격자/자동제안/적용/저장."""
import pytest
from fastapi.testclient import TestClient

from core.parsers.hwpx_parser import parse_hwpx
from core.template.apply import apply_template, field_order
from core.template.designer import grid_dto, suggest_boxes
from core.template.store import TemplateStore


@pytest.fixture(scope="module")
def doc(request):
    fixture = request.path.parent / "fixtures" / "sample.hwpx"
    if not fixture.exists():
        pytest.skip("샘플 없음")
    return parse_hwpx(str(fixture))


def test_grid_dto_shape(doc):
    tables = grid_dto(doc)
    assert len(tables) == 14
    t0 = tables[0]
    assert t0["n_cols"] > 0 and t0["cells"]
    assert {"r", "c", "rs", "cs", "text"} <= set(t0["cells"][0])


def test_suggest_boxes(doc):
    boxes = suggest_boxes(doc)
    assert len(boxes) > 10
    # 제원 라벨이 값 칸으로 제안되는지(예: 보 길이 -> 30)
    apply = apply_template(doc, boxes)
    assert apply.get("보 길이") == "30"


def test_check_mode(doc):
    """체크 모드: 옵션 중 √ 표시된 것만, 없으면 빈 값(#4)."""
    checked = [{"order": 1, "field": "재질", "table": 0, "mode": "check",
                "cells": [{"r": 13, "c": 0}, {"r": 13, "c": 8}, {"r": 13, "c": 20}, {"r": 13, "c": 31}]}]
    assert apply_template(doc, checked)["재질"] == "콘크리트"
    # 체크 없는 옵션만 -> 빈 값
    none = [{"order": 1, "field": "가동보", "table": 0, "mode": "check", "cells": [{"r": 13, "c": 31}]}]
    assert apply_template(doc, none)["가동보"] == ""


def test_label_anchor(doc):
    """라벨 기준 앵커: 좌표가 틀려도 라벨로 값을 찾는다(양식 편차·PDF 대응)."""
    box = [{"order": 1, "field": "하천명", "table": 0, "mode": "text",
            "cells": [{"r": 99, "c": 99}],  # 일부러 엉뚱한 좌표
            "anchor": {"label": "하천명", "relation": "right"}, "use_anchor": True}]
    assert apply_template(doc, box)["하천명"] == "해남천"
    # 앵커 끄면 좌표(엉뚱) 사용 → 빈 값
    box[0]["use_anchor"] = False
    assert apply_template(doc, box)["하천명"] == ""


def test_anchor_below_relation(doc):
    box = [{"order": 1, "field": "시도", "table": 0, "mode": "text", "cells": [{"r": 0, "c": 0}],
            "anchor": {"label": "시,도", "relation": "below"}, "use_anchor": True}]
    assert apply_template(doc, box)["시도"] == "전남"


def test_suggest_has_anchor(doc):
    from core.template.designer import suggest_boxes
    boxes = suggest_boxes(doc)
    anchored = [b for b in boxes if b.get("anchor")]
    assert anchored, "자동 제안 박스는 라벨 앵커를 가져야 한다"
    assert all("label" in b["anchor"] and "relation" in b["anchor"] for b in anchored)


def test_bold_mode(doc):
    """굵게 모드: 굵게 표시된 텍스트만 추출."""
    box = [{"order": 1, "field": "기상", "table": 0, "mode": "bold", "cells": [{"r": 6, "c": 26}]}]
    val = apply_template(doc, box)["기상"]
    assert "흐림" in val  # 이 샘플에서 선택된 날씨는 굵은 '흐림'


def test_apply_respects_order(doc):
    boxes = [
        {"order": 2, "field": "하천", "table": 0, "cells": [{"r": 3, "c": 2}]},
        {"order": 1, "field": "위도", "table": 0, "cells": [{"r": 2, "c": 30}]},
    ]
    assert field_order(boxes) == ["위도", "하천"]  # order 순


def test_template_store(tmp_path):
    store = TemplateStore(tmp_path / "t.json")
    store.save("내양식", [{"order": 1, "field": "하천명", "table": 0, "cells": [{"r": 3, "c": 2}]}])
    store2 = TemplateStore(tmp_path / "t.json")
    assert "내양식" in store2.list_names()
    assert store2.get("내양식")["boxes"][0]["field"] == "하천명"


def test_template_save_get_delete_api(tmp_path):
    from app import main as app_main
    app_main._TEMPLATES = TemplateStore(tmp_path / "t.json")
    client = TestClient(app_main.app)
    boxes = [{"order": 1, "field": "하천명", "table": 0, "cells": [{"r": 3, "c": 2}]}]
    r = client.post("/api/designer/save", json={"name": "양식A", "boxes": boxes})
    assert r.status_code == 200 and "양식A" in r.json()["templates"]
    g = client.get("/api/designer/template", params={"name": "양식A"})
    assert g.status_code == 200 and g.json()["boxes"][0]["field"] == "하천명"
    d = client.post("/api/designer/template/delete", json={"name": "양식A"})
    assert "양식A" not in d.json()["templates"]


def test_designer_api_load(request):
    fixture = request.path.parent / "fixtures" / "sample.hwpx"
    if not fixture.exists():
        pytest.skip("샘플 없음")
    from app.main import app
    client = TestClient(app)
    with fixture.open("rb") as f:
        r = client.post("/api/designer/load",
                        files={"file": ("sample.hwpx", f, "application/octet-stream")})
    assert r.status_code == 200
    d = r.json()
    assert len(d["tables"]) == 14
    assert len(d["boxes"]) > 10
