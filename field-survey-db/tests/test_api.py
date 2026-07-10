"""Phase 5 검증 — 웹 API 업로드/처리/다운로드 (AC-1, AC-9)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "현장 조사표 DB화" in r.text


def test_process_and_download(request):
    fixture = request.path.parent / "fixtures" / "sample.hwpx"
    if not fixture.exists():
        pytest.skip("샘플 없음")

    with fixture.open("rb") as f:
        r = client.post(
            "/api/process",
            files={"files": ("sample.hwpx", f, "application/octet-stream")},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["stats"]["files_ok"] == 1
    assert data["stats"]["records"] >= 2
    assert data["records"], "레코드 미리보기가 있어야 한다"

    # 다운로드
    d = client.get("/api/download")
    assert d.status_code == 200
    assert "spreadsheetml" in d.headers["content-type"]
    assert len(d.content) > 2000  # 실제 엑셀 바이트


def test_process_empty_rejected():
    r = client.post("/api/process", files=[])
    assert r.status_code in (400, 422)
