"""글자 인식(OCR) 기능 내려받기 — 목록(공개 저장소·SHA-256 고정), 받기·확인·풀기·붙이기,
잘못된 파일 거부, 지우기, API 보호, 시스템 점검 표시."""
import hashlib
import http.server
import io
import sys
import threading
import urllib.parse
import zipfile
from functools import partial

import pytest

from core import ocr_runtime
from core.ocr_manifest import MANIFEST

BUNDLED_IN_HELPER = {"numpy", "pillow", "opencv-python-headless", "opencv-python"}


def test_manifest_is_pinned_to_public_sources():
    assert MANIFEST["python"] == "cp311-win_amd64"
    for variant in ocr_runtime.VARIANTS:
        pkgs = MANIFEST["variants"][variant]
        names = {p["name"] for p in pkgs}
        assert {"torch", "torchvision", "easyocr", "scipy", "scikit-image"} <= names
        assert not names & BUNDLED_IN_HELPER                  # 도우미에 이미 든 패키지는 받지 않는다
        for p in pkgs + MANIFEST["models"]:
            u = urllib.parse.urlparse(p["url"])
            assert u.scheme == "https" and u.hostname in ocr_runtime.ALLOWED_HOSTS, p["url"]
            assert len(p["sha256"]) == 64 and int(p["sha256"], 16) >= 0 and p["size"] > 0
    torch = {v: next(p for p in MANIFEST["variants"][v] if p["name"] == "torch") for v in ocr_runtime.VARIANTS}
    assert "+cu" in torch["gpu"]["version"] and "+cu" not in torch["cpu"]["version"]
    assert {m["file"] for m in MANIFEST["models"]} == {"craft_mlt_25k.pth", "korean_g2.pth"}
    assert ocr_runtime.variant_size("gpu") > ocr_runtime.variant_size("cpu") > 0


def test_manifest_matches_pinned_build_versions():
    """requirements-lock.txt 의 torch·torchvision·easyocr 를 올리고 목록을 다시 만들지 않으면 실패."""
    from pathlib import Path

    lock = {}
    for ln in (Path(__file__).resolve().parent.parent / "requirements-lock.txt").read_text(encoding="utf-8").splitlines():
        if "==" in ln and not ln.startswith("#"):
            k, v = ln.strip().split("==", 1)
            lock[k.lower()] = v
    for variant in ocr_runtime.VARIANTS:
        got = {p["name"]: p["version"].split("+")[0] for p in MANIFEST["variants"][variant]}
        for name in ("torch", "torchvision", "easyocr"):
            assert got[name] == lock[name], (variant, name)


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def _entry(url_base, name, data, **extra):
    return {"name": name.split("-")[0], "version": "1.0", "file": name, "url": url_base + name,
            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), **extra}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """가짜 공개 저장소(로컬 HTTP) + 격리된 설치 위치."""
    srv = tmp_path / "srv"
    srv.mkdir()
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(http.server.SimpleHTTPRequestHandler, directory=str(srv)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"

    monkeypatch.setenv("AUTODATA_OCR_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(ocr_runtime, "_check_url", lambda url: None)     # 테스트 서버는 http
    monkeypatch.setattr(ocr_runtime, "_BUNDLED", False)
    monkeypatch.setattr(ocr_runtime, "_ACTIVE", None)
    monkeypatch.setattr(ocr_runtime, "_GPU", {"name": "", "driver": "", "vram_gb": 0, "capable": False})
    monkeypatch.setattr(ocr_runtime, "_JOB", dict(ocr_runtime._JOB, running=False, error="", phase=""))
    monkeypatch.setattr(ocr_runtime, "_after_install", ocr_runtime.activate)
    monkeypatch.setattr(sys, "path", list(sys.path))

    def publish(files: dict[str, bytes], model: bytes = b"craft-weights") -> dict:
        for name, data in files.items():
            (srv / name).write_bytes(data)
        mz = _zip({"craft_mlt_25k.pth": model})
        (srv / "craft.zip").write_bytes(mz)
        manifest = {"id": "test", "python": "cp311-win_amd64",
                    "variants": {"cpu": [_entry(base, n, d) for n, d in files.items()], "gpu": []},
                    "models": [_entry(base, "craft.zip", mz, file="craft_mlt_25k.pth",
                                      md5=hashlib.md5(model).hexdigest())]}
        monkeypatch.setattr(ocr_runtime, "MANIFEST", manifest)
        return manifest

    yield publish, base
    httpd.shutdown()
    sys.modules.pop("autodata_fakepkg", None)


def _install(variant="cpu"):
    ocr_runtime._set(running=True, total=ocr_runtime.variant_size(variant), cancel=False, error="")
    ocr_runtime._run_install(variant)
    return ocr_runtime.status()


def test_install_verifies_extracts_and_attaches(repo, tmp_path):
    publish, _ = repo
    publish({"autodata_fakepkg-1.0-py3-none-any.whl": _zip({
        "autodata_fakepkg/__init__.py": b"VALUE = 42\n",
        "autodata_fakepkg-1.0.dist-info/METADATA": b"Name: autodata-fakepkg\n",
        "autodata_fakepkg-1.0.data/purelib/autodata_fakepkg/extra.py": b"X = 1\n",
        "autodata_fakepkg-1.0.data/scripts/tool.exe": b"MZ",
        "torch/include/deep/header.h": "// 실행에 필요 없음".encode(),
        "torch/lib/torch_cpu.lib": b"link-only",
    })})
    s = _install()
    assert s["job"]["phase"] == "완료" and not s["job"]["error"], s["job"]
    assert s["installed"] == {"cpu": True, "gpu": False} and s["active"] == "cpu" and s["ready"]
    import autodata_fakepkg
    import autodata_fakepkg.extra
    assert autodata_fakepkg.VALUE == 42 and autodata_fakepkg.extra.X == 1
    site = tmp_path / "home" / "test" / "cpu"
    assert not (site / "torch").exists() and not list(site.rglob("tool.exe"))   # 헤더·링크용·스크립트는 풀지 않음
    assert not (tmp_path / "home" / "test" / "download").exists()               # 받은 원본은 정리
    assert (ocr_runtime.models_dir() / "craft_mlt_25k.pth").read_bytes() == b"craft-weights"

    with pytest.raises(RuntimeError):
        ocr_runtime.remove("cpu")                     # 지금 쓰는 판은 못 지움
    ocr_runtime._ACTIVE = None
    ocr_runtime.remove("cpu")
    assert ocr_runtime.installed() == {"cpu": False, "gpu": False}


def test_tampered_file_is_rejected(repo, tmp_path):
    publish, _ = repo
    m = publish({"autodata_fakepkg-1.0-py3-none-any.whl": _zip({"autodata_fakepkg/__init__.py": b"VALUE = 1\n"})})
    m["variants"]["cpu"][0]["sha256"] = "0" * 64                     # 목록과 다른 파일이 내려옴
    s = _install()
    assert s["job"]["phase"] == "실패" and "SHA-256" in s["job"]["error"]
    assert s["installed"]["cpu"] is False and s["active"] is None
    assert not list((tmp_path / "home").rglob("*.whl.part"))        # 확인 실패한 조각은 지운다
    assert not list((tmp_path / "home").rglob("__init__.py"))       # 확인 전에는 풀지 않는다


def test_wheel_with_path_escape_is_rejected(repo, tmp_path):
    publish, _ = repo
    publish({"evil-1.0-py3-none-any.whl": _zip({"evil/__init__.py": b"", "../../outside.py": b"bad"})})
    s = _install()
    assert s["job"]["phase"] == "실패" and "밖" in s["job"]["error"]
    assert not list(tmp_path.rglob("outside.py"))


def test_partial_download_resumes_or_restarts(repo, tmp_path):
    publish, _ = repo
    data = _zip({"autodata_fakepkg/__init__.py": b"VALUE = 7\n" * 500})
    publish({"autodata_fakepkg-1.0-py3-none-any.whl": data})
    dl = tmp_path / "home" / "test" / "download"
    dl.mkdir(parents=True)
    (dl / "autodata_fakepkg-1.0-py3-none-any.whl.part").write_bytes(b"garbage")   # 끊긴 조각(이어받기 불가 서버)
    s = _install()
    assert s["job"]["phase"] == "완료", s["job"]


def test_wheel_paths():
    assert ocr_runtime._wheel_rel("pkg/mod.py") == "pkg/mod.py"
    assert ocr_runtime._wheel_rel("pkg-1.data/platlib/pkg/_c.pyd") == "pkg/_c.pyd"
    assert ocr_runtime._wheel_rel("pkg-1.data/headers/x.h") is None
    assert ocr_runtime._wheel_rel("torch/lib/torch_cpu.dll") == "torch/lib/torch_cpu.dll"
    assert ocr_runtime._wheel_rel("torch/lib/torch_cpu.lib") is None
    assert ocr_runtime._wheel_rel("../x.py") == "__bad__"
    assert ocr_runtime._wheel_rel("C:/x.py") == "__bad__"


def test_api_status_and_protection(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as app_main

    started = []
    monkeypatch.setattr(ocr_runtime, "start_install", lambda v: started.append(v))
    c = TestClient(app_main.app)
    s = c.get("/api/ocr/runtime").json()
    assert {"bundled", "installed", "sizes", "job", "recommended", "sources", "gpu"} <= set(s)
    web = {"Origin": "https://autodata.singlena.workers.dev"}
    assert c.post("/api/ocr/runtime/install", json={"variant": "cpu"}, headers=web).status_code == 403
    assert c.post("/api/ocr/runtime/install", json={"variant": "x"}).status_code == 400
    monkeypatch.setattr(ocr_runtime, "_BUNDLED", False)
    assert c.post("/api/ocr/runtime/install", json={"variant": "cpu"}).status_code == 200 and started == ["cpu"]
    monkeypatch.setattr(ocr_runtime, "_BUNDLED", True)
    assert c.post("/api/ocr/runtime/install", json={"variant": "cpu"}).status_code == 400   # 엔진 동봉판


def _pdf_bytes(text: str | None) -> bytes:
    """글자 레이어가 있는 PDF(text) 또는 흰 그림만 든 스캔 흉내 PDF(None)."""
    import fitz
    from PIL import Image

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    if text:
        page.insert_text((40, 60), text, fontsize=14)
    else:
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(buf, format="PNG")
        page.insert_image(page.rect, stream=buf.getvalue())
    return doc.tobytes()


def test_batch_apply_reports_unread_scan_pages(monkeypatch):
    """경량 도우미(글자 인식 기능 없음)에서 스캔 문서를 일괄 처리하면 — 빈 행만 조용히 내려가지 않고
    '못 읽은 쪽'과 받기 안내(ocr_setup)를 함께 돌려준다. 글자 있는 PDF는 안내가 붙지 않는다."""
    from fastapi.testclient import TestClient

    import app.main as app_main
    from core import ocr

    monkeypatch.setattr(ocr, "available", lambda: False)          # 엔진 없음(스캔 쪽 OCR 건너뜀)
    monkeypatch.setattr(ocr_runtime, "_BUNDLED", False)
    monkeypatch.setattr(ocr_runtime, "_ACTIVE", None)
    monkeypatch.setattr(ocr_runtime, "_GPU", {"name": "", "driver": "", "vram_gb": 0, "capable": False})
    c = TestClient(app_main.app)
    form = {"boxes": "[]", "auto_classify": "1", "sheet_name_field": "__group_title__"}

    r = c.post("/api/pdf/apply", data=form, files=[("files", ("scan.pdf", _pdf_bytes(None), "application/pdf"))])
    d = r.json()
    assert d.get("ocr_missing") is True and d["ocr_gap"] == [{"name": "scan.pdf", "pages": 1, "total": 1}], d
    assert d["ocr_setup"]["ready"] is False and "sizes" in d["ocr_setup"]
    assert (d.get("ok_count") or 0) == 0

    r = c.post("/api/pdf/apply", data=form, files=[("files", ("typed.pdf", _pdf_bytes("하천명 남대천"), "application/pdf"))])
    assert "ocr_missing" not in r.json()


def test_syscheck_shows_download_when_not_installed(monkeypatch):
    from core import ocr, syscheck

    monkeypatch.setattr(ocr_runtime, "_BUNDLED", False)
    monkeypatch.setattr(ocr_runtime, "_ACTIVE", None)
    monkeypatch.setattr(ocr_runtime, "_GPU", {"name": "", "driver": "", "vram_gb": 0, "capable": False})
    monkeypatch.setattr(ocr, "_TRIED", False)
    it = syscheck._check_ocr_quick({"torch": {"cuda_available": False}})
    assert it.status == "info" and "필요할 때 내려받기" in it.detail and it.fix
