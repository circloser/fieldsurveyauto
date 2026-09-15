"""웹 시작 페이지 ↔ 이 PC의 도우미 연결 규칙.

웹 주소(클라우드플레어 Pages)에서 여는 시작 페이지는 도우미 상태만 읽고, 실제 처리는 이 PC의 작업 화면에서 한다.
다른 웹사이트가 이 PC의 도우미에 파일을 올리거나 설정을 바꾸지 못해야 한다.
"""
from fastapi.testclient import TestClient

import app.main as app_main
from core import web_access

WEB = "https://fieldsurveyauto.pages.dev"
EVIL = "https://evil.example"


def _client():
    return TestClient(app_main.app)


def test_hello_tells_app_and_version_only():
    d = _client().get("/api/local/hello").json()
    assert d["app"] == "autodata" and d["ui"] == "/"
    assert d["version"] == app_main.config.APP_VERSION.split(" ")[0]        # 번호만('0.5.0 (MVP…)' → '0.5.0')
    assert "base_dir" not in d


def test_status_readable_only_from_allowed_web_origin():
    c = _client()
    ok = c.get("/api/local/hello", headers={"Origin": WEB})
    assert ok.headers.get("access-control-allow-origin") == WEB
    preview = c.get("/health", headers={"Origin": "https://abc123.fieldsurveyauto.pages.dev"})
    assert preview.headers.get("access-control-allow-origin") == "https://abc123.fieldsurveyauto.pages.dev"
    bad = c.get("/api/local/hello", headers={"Origin": EVIL})
    assert "access-control-allow-origin" not in bad.headers
    lookalike = c.get("/health", headers={"Origin": "https://evilfieldsurveyauto.pages.dev"})
    assert "access-control-allow-origin" not in lookalike.headers
    other_path = c.get("/api/templates", headers={"Origin": WEB})              # 상태 주소가 아니면 읽기 허용 안 함
    assert "access-control-allow-origin" not in other_path.headers


def test_preflight_allows_local_network_for_web_page_only():
    c = _client()
    pre = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Private-Network": "true"}
    r = c.options("/api/local/hello", headers={"Origin": WEB, **pre})
    assert r.status_code == 204
    assert r.headers.get("access-control-allow-private-network") == "true"
    assert r.headers.get("access-control-allow-origin") == WEB
    assert c.options("/api/local/hello", headers={"Origin": EVIL, **pre}).status_code == 403
    assert c.options("/api/pdf/apply", headers={"Origin": WEB, **pre}).status_code == 403


def test_changes_blocked_from_other_websites(tmp_path, monkeypatch):
    monkeypatch.setattr(app_main.config, "DATA_DIR", tmp_path)
    c = _client()
    body = {"text": "홍길둥 = 홍길동"}
    assert c.post("/api/ocr/corrections", json=body, headers={"Origin": EVIL}).status_code == 403
    assert c.post("/api/ocr/corrections", json=body, headers={"Origin": WEB}).status_code == 403   # 시작 페이지도 읽기만
    assert c.post("/api/ocr/corrections", json=body, headers={"Origin": "null"}).status_code == 403
    assert c.post("/api/ocr/corrections", json=body, headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
    assert c.post("/api/ocr/corrections", json=body, headers={"Origin": "http://localhost:8766"}).status_code == 200
    assert c.post("/api/ocr/corrections", json=body).status_code == 200                           # Origin 없는 요청(도구·테스트)


def test_custom_domains_from_file(tmp_path):
    (tmp_path / web_access.ORIGINS_FILE).write_text(
        "# 우리 기관 주소\nhttps://autodata.example.org/\nhttps://*.labs.example.org\n잘못된 줄\n", encoding="utf-8")
    exact, suffixes = web_access.load_origins(tmp_path)
    assert web_access.is_web_origin("https://autodata.example.org", exact, suffixes)
    assert web_access.is_web_origin("https://team.labs.example.org", exact, suffixes)
    assert not web_access.is_web_origin("https://labs.example.org.evil.io", exact, suffixes)
    assert web_access.is_web_origin(WEB, exact, suffixes)                  # 기본 주소는 그대로
    assert web_access.is_local_origin("http://127.0.0.1:8765") and not web_access.is_local_origin("http://127.0.0.1.evil.io")
