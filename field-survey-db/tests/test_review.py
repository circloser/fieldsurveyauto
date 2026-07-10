"""Phase 6 검증 — 검수 교정 저장/재적용 (AC-10)."""
import pytest
from fastapi.testclient import TestClient

from core.extraction.mapper import Record
from core.review.store import CorrectionStore


def test_store_roundtrip(tmp_path):
    store = CorrectionStore(tmp_path / "c.json")
    store.set("f.hwpx::123::fishway", "어도폭", "9.9")
    # 새 인스턴스로 다시 읽어도 유지(영속화)
    store2 = CorrectionStore(tmp_path / "c.json")
    assert store2.get("f.hwpx::123::fishway")["어도폭"] == "9.9"


def test_apply_clears_flag(tmp_path):
    store = CorrectionStore(tmp_path / "c.json")
    rec = Record("f.hwpx", "fishway", "남와리3", "123", "해남천",
                 values={}, flags={"어도폭": "empty"})
    store.set(rec.record_key, "어도폭", "3.7")
    store.apply_to([rec])
    assert rec.values["어도폭"] == "3.7"
    assert "어도폭" not in rec.flags  # 사람이 확인 → 플래그 해제


def test_correction_via_api(request, tmp_path, monkeypatch):
    fixture = request.path.parent / "fixtures" / "sample.hwpx"
    if not fixture.exists():
        pytest.skip("샘플 없음")

    # 교정 파일을 임시 폴더로 격리
    from app import main as app_main
    app_main._STORE = CorrectionStore(tmp_path / "c.json")
    client = TestClient(app_main.app)

    with fixture.open("rb") as f:
        r = client.post("/api/process",
                        files={"files": ("sample.hwpx", f, "application/octet-stream")})
    data = r.json()
    before = data["stats"]["flagged"]
    assert before >= 1

    # 플래그가 있는 레코드/필드를 찾아 교정
    target = next(r for r in data["records"] if r["flags"])
    field = list(target["flags"].keys())[0]
    c = client.post("/api/correct",
                    json={"key": target["key"], "field": field, "value": "2.25"})
    cd = c.json()
    assert cd["ok"] is True
    assert cd["flagged"] == before - 1  # 검수필요 1건 감소
    assert cd["record"]["values"][field] == "2.25"
    assert field not in cd["record"]["flags"]
