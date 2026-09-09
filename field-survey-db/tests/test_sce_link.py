"""SCE(종적 연속성 평가) 연계 — 선택 기능(기본 꺼짐, 폴더 지정으로 켜기).

· 기본은 꺼짐 → 4번 결과 화면에 버튼이 나오지 않는다(SCE 안 쓰는 곳 배포용)
· 켜면 설치된 패키지 → 지정 폴더 순서로 찾는다
· 없는 폴더를 지정하면 저장 자체를 거절한다
"""
import sys

import pytest

from core import sce_link


@pytest.fixture
def clean_sce():
    """테스트가 넣은 가짜 sce 모듈·경로를 원상복구."""
    before_path = list(sys.path)
    before_mods = {k: v for k, v in sys.modules.items() if k == "sce" or k.startswith("sce.")}
    yield
    for name in [n for n in list(sys.modules) if n == "sce" or n.startswith("sce.")]:
        del sys.modules[name]
    sys.modules.update(before_mods)
    sys.path[:] = before_path


def _fake_sce(root):
    """sce/autodata_import.py 가 있는 최소 패키지 폴더를 만든다."""
    pkg = root / "sce"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "autodata_import.py").write_text("MARK = 'fake-sce'\n", encoding="utf-8")
    return root


def test_default_is_off(tmp_path):
    cfg = tmp_path / "sce_config.json"
    st = sce_link.status(cfg)
    assert st == {"enabled": False, "path": "", "available": False, "error": ""}
    mod, err = sce_link.module(sce_link.load(cfg))
    assert mod is None and "꺼져" in err


def test_enable_with_folder(tmp_path, clean_sce):
    cfg = tmp_path / "sce_config.json"
    root = _fake_sce(tmp_path / "sce_home")
    sce_link.save(cfg, True, str(root))
    st = sce_link.status(cfg)
    assert st["enabled"] and st["available"] and st["path"] == str(root)
    mod, err = sce_link.module(sce_link.load(cfg))
    assert err == "" and getattr(mod, "MARK", "") == "fake-sce"
    # 'sce' 폴더 자체를 가리켜도 상위를 import 경로로 잡는다
    sce_link.save(cfg, True, str(root / "sce"))
    assert sce_link.status(cfg)["available"]


def test_enabled_but_missing_reports_error(tmp_path, clean_sce):
    import importlib.util
    if importlib.util.find_spec("sce") is not None:
        pytest.skip("이 환경에는 SCE가 설치되어 있어 '못 찾음' 상황을 만들 수 없음")
    cfg = tmp_path / "sce_config.json"
    sce_link.save(cfg, True, str(tmp_path / "빈폴더"))
    st = sce_link.status(cfg)
    assert st["enabled"] and not st["available"]
    assert "찾지 못했습니다" in st["error"]


def test_candidates_resolve_folder_shapes(tmp_path):
    """폴더 지정 형태 3가지 — 상위 폴더 / 'sce' 폴더 자체 / src 레이아웃."""
    root = _fake_sce(tmp_path / "home")
    assert root in sce_link._candidates(str(root))
    assert root in sce_link._candidates(str(root / "sce"))     # sce 폴더를 가리켜도 상위를 쓴다
    srcroot = tmp_path / "proj"
    _fake_sce(srcroot / "src")
    assert (srcroot / "src") in sce_link._candidates(str(srcroot))
    assert sce_link._candidates("") == []


def test_api_config_and_status(tmp_path, monkeypatch, clean_sce):
    import app.config as cfgmod
    import app.main as app_main
    from fastapi.testclient import TestClient

    cfg = tmp_path / "sce_config.json"
    monkeypatch.setattr(cfgmod, "SCE_CONFIG_PATH", cfg)
    client = TestClient(app_main.app)

    d = client.get("/api/sce/status").json()
    assert d["enabled"] is False and d["available"] is False

    r = client.post("/api/sce/config", json={"enabled": True, "path": str(tmp_path / "없는폴더")})
    assert r.status_code == 400 and "찾을 수 없습니다" in r.json()["error"]

    root = _fake_sce(tmp_path / "sce_home")
    d = client.post("/api/sce/config", json={"enabled": True, "path": str(root)}).json()
    assert d["ok"] and d["enabled"] and d["available"]
    assert client.get("/api/sce/status").json()["available"]

    d = client.post("/api/sce/config", json={"enabled": False, "path": ""}).json()
    assert d["enabled"] is False and d["available"] is False
    # 꺼진 상태에서 내보내기를 부르면 '꺼져 있다'고 안내
    r = client.post("/api/sce/export", json={})
    assert r.status_code == 400 and "꺼져" in r.json()["error"]
