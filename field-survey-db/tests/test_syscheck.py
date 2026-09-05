"""배포용 시스템 점검·성능 프로필 — 항목 구성, 상태값, 보고서 텍스트, API, OCR 장치 선택."""
from core import perf
from core.syscheck import report_text, run_checks

CORE_IDS = {"os", "cpu", "ram", "disk", "gpu", "hwp", "browser", "port", "write", "pdf", "excel", "ai"}


def test_quick_checks_cover_required_items():
    r = run_checks(quick=True)
    ids = {i["id"] for i in r["items"]}
    assert CORE_IDS <= ids
    assert "ocr" not in ids                                   # 빠른 점검은 OCR 로드 생략
    assert all(i["status"] in ("ok", "warn", "fail", "info") for i in r["items"])
    assert r["overall"] in ("ok", "warn", "fail")
    assert sum(r["counts"].values()) == len(r["items"])
    # 이 개발 PC에서 반드시 정상이어야 하는 것들
    by = {i["id"]: i for i in r["items"]}
    assert by["write"]["status"] == "ok" and by["pdf"]["status"] == "ok" and by["excel"]["status"] == "ok"
    assert by["hwp"]["status"] in ("ok", "warn")
    assert by["hwp"]["fix"] or by["hwp"]["status"] == "ok"    # 미설치면 해결 방법(다운로드) 안내


def test_report_text_lists_every_item():
    r = run_checks(quick=True)
    t = report_text(r)
    assert t.startswith("오토다타 (AutoData) 시스템 점검 결과")
    for it in r["items"]:
        assert it["name"] in t
    assert "처리 방식:" in t


def test_perf_profile_shape():
    p = perf.profile()
    for k in ("os", "cpu", "logical_cores", "ram_total_gb", "gpus", "nvidia", "torch", "mode", "advice"):
        assert k in p
    assert p["mode"] in ("gpu", "cpu")
    assert p["logical_cores"] >= 1
    assert perf.use_gpu() == bool(p["torch"]["cuda_available"])
    assert perf.summary_lines() and perf.summary_lines()[0].startswith("[성능]")


def test_ocr_reader_follows_gpu_availability(monkeypatch):
    """GPU(CUDA)가 되면 EasyOCR을 gpu=True·큰 배치로, 아니면 CPU로 연다."""
    from core import ocr
    monkeypatch.setattr(perf, "use_gpu", lambda: True)
    kw = ocr._reader_kwargs()
    assert kw["gpu"] is True and ocr._batch_size() > 1
    monkeypatch.setattr(perf, "use_gpu", lambda: False)
    kw = ocr._reader_kwargs()
    assert kw["gpu"] is False and ocr._batch_size() == 1


def test_system_check_api_and_page():
    import app.main as app_main
    from fastapi.testclient import TestClient

    client = TestClient(app_main.app)
    r = client.get("/api/system/check?quick=1")
    assert r.status_code == 200
    d = r.json()
    assert d["overall"] in ("ok", "warn", "fail") and len(d["items"]) >= len(CORE_IDS)
    t = client.get("/api/system/report?quick=1")
    assert t.status_code == 200 and "시스템 점검 결과" in t.text
    page = client.get("/system")
    assert page.status_code == 200 and "시스템 점검" in page.text
