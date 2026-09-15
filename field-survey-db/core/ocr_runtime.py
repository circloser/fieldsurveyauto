"""글자 인식(OCR) 기능 내려받기 — 경량 도우미가 스캔 문서를 처음 만날 때 공개 저장소에서 받아 이 PC에 둔다.

· 받는 곳(모두 공개): PyPI(파이썬 패키지) · PyTorch 공식 저장소(GPU판 torch) · EasyOCR GitHub 릴리스(모델)
  우리 서버를 거치지 않는다. 파일마다 목록(core/ocr_manifest.py)의 SHA-256 과 맞아야만 풀어서 쓴다.
· 두는 곳: %LOCALAPPDATA%\\AutoData\\ocr\\<목록 id>\\{cpu|gpu, models}
  새 버전 도우미도 목록이 같으면 다시 받지 않는다. 받다 끊기면 이어 받는다.
· 쓰는 법: 시작할 때 activate() 가 받아 둔 폴더를 import 경로 뒤에 붙인다.
  OCR 엔진이 이미 들어 있는 배포판(OCR 포함판)이나 개발 환경에서는 아무것도 하지 않는다.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from core.ocr_manifest import MANIFEST

VARIANTS = ("cpu", "gpu")
GPU_MIN_DRIVER = 580            # GPU판 torch(CUDA 13.0)가 요구하는 NVIDIA 드라이버
ALLOWED_HOSTS = ("files.pythonhosted.org", "download.pytorch.org", "download-r2.pytorch.org", "github.com")
SOURCES = ["PyPI (pypi.org)", "PyTorch (download.pytorch.org)", "EasyOCR (github.com/JaidedAI/EasyOCR)"]
_UA = "AutoData-OCR-Setup"
_CHUNK = 1 << 20
_RETRIES = 4

_BUNDLED: bool | None = None     # 엔진이 도우미에 이미 들어 있나(activate 전에 한 번만 판정)
_ACTIVE: str | None = None       # 이 프로세스에 붙인 판
_DLL_HANDLES: list = []
_GPU: dict | None = None
_LOCK = threading.Lock()
_JOB: dict = {"running": False, "variant": None, "phase": "", "file": "", "done": 0, "total": 0,
              "error": "", "finished": False, "cancel": False}


class _Cancelled(Exception):
    pass


# ---------- 위치 ----------
def _roots() -> list[Path]:
    env = os.environ.get("AUTODATA_OCR_HOME")
    if env:
        return [Path(env)]
    out = []
    if os.environ.get("LOCALAPPDATA"):
        out.append(Path(os.environ["LOCALAPPDATA"]) / "AutoData" / "ocr")
    try:
        from app import config
        out.append(Path(config.BASE_DIR) / "ocr")      # 사용자 폴더에 못 쓰는 PC — 도우미 폴더 옆
    except Exception:  # noqa: BLE001
        pass
    return out or [Path.home() / ".autodata" / "ocr"]


def _pack(root: Path) -> Path:
    return root / MANIFEST["id"]


def _marker(root: Path, variant: str) -> Path:
    return _pack(root) / f"{variant}.ok"


def _fingerprint(variant: str) -> str:
    items = [p["sha256"] for p in MANIFEST["variants"][variant]] + [m["sha256"] for m in MANIFEST["models"]]
    return hashlib.sha256("".join(items).encode()).hexdigest()[:16]


def _installed_in(root: Path, variant: str) -> bool:
    try:
        d = json.loads(_marker(root, variant).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return d.get("fingerprint") == _fingerprint(variant) and (_pack(root) / variant).is_dir()


def _find_root() -> Path | None:
    """받아 둔 판이 있는 위치(없으면 None)."""
    for r in _roots():
        if any(_installed_in(r, v) for v in VARIANTS):
            return r
    return None


def _writable_root() -> Path:
    last = None
    for r in _roots():
        try:
            _pack(r).mkdir(parents=True, exist_ok=True)
            probe = _pack(r) / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return r
        except OSError as e:
            last = e
    raise RuntimeError(f"글자 인식 기능을 저장할 폴더를 만들 수 없습니다({last})")


def installed() -> dict[str, bool]:
    root = _find_root()
    return {v: bool(root and _installed_in(root, v)) for v in VARIANTS}


def models_dir() -> Path | None:
    """받아 둔 EasyOCR 모델 폴더(모델 파일이 다 있을 때만)."""
    root = _find_root()
    if root is None:
        return None
    d = _pack(root) / "models"
    return d if all((d / m["file"]).is_file() for m in MANIFEST["models"]) else None


# ---------- 판정 ----------
def bundled() -> bool:
    """OCR 엔진이 도우미에 이미 들어 있나(OCR 포함판·개발 환경) — 그러면 내려받기가 필요 없다."""
    global _BUNDLED
    if _BUNDLED is None:
        _BUNDLED = (_ACTIVE is None and importlib.util.find_spec("easyocr") is not None
                    and importlib.util.find_spec("torch") is not None)
    return _BUNDLED


def active() -> str | None:
    return _ACTIVE


def gpu_info() -> dict:
    """NVIDIA GPU·드라이버 — GPU판을 권할지 판단(nvidia-smi, 한 번만)."""
    global _GPU
    if _GPU is None:
        try:
            from core import perf
            gpus = perf._nvidia_gpus()
        except Exception:  # noqa: BLE001
            gpus = []
        g = gpus[0] if gpus else None
        try:
            major = int(str(g["driver"]).split(".")[0]) if g else 0
        except ValueError:
            major = 0
        _GPU = {"name": g["name"] if g else "", "driver": g["driver"] if g else "",
                "vram_gb": g["vram_gb"] if g else 0, "capable": bool(g) and major >= GPU_MIN_DRIVER}
    return _GPU


def variant_size(variant: str) -> int:
    return sum(p["size"] for p in MANIFEST["variants"][variant]) + sum(m["size"] for m in MANIFEST["models"])


def size_text(variant: str) -> str:
    b = variant_size(variant)
    return f"약 {b / 1e9:.1f}GB" if b >= 1e9 else f"약 {max(1, round(b / 1e6))}MB"


def _choose(inst: dict[str, bool]) -> str | None:
    if inst.get("gpu") and (not inst.get("cpu") or gpu_info()["capable"]):
        return "gpu"          # GPU판 torch 는 GPU를 못 쓰면 CPU로도 돈다
    return "cpu" if inst.get("cpu") else None


# ---------- 붙이기 ----------
def activate() -> str | None:
    """받아 둔 글자 인식 기능을 이 프로세스에 붙인다. 붙인 판('cpu'|'gpu') 또는 None."""
    global _ACTIVE
    if _ACTIVE or bundled():
        return _ACTIVE
    root = _find_root()
    if root is None:
        return None
    v = _choose({x: _installed_in(root, x) for x in VARIANTS})
    if v is None:
        return None
    site = _pack(root) / v
    if str(site) not in sys.path:
        sys.path.append(str(site))          # 뒤에 붙인다 — 도우미에 든 numpy·OpenCV 가 먼저 쓰인다
    lib = site / "torch" / "lib"
    if lib.is_dir() and hasattr(os, "add_dll_directory"):
        try:
            _DLL_HANDLES.append(os.add_dll_directory(str(lib)))
        except OSError:
            pass
    importlib.invalidate_caches()
    _ACTIVE = v
    return v


def _after_install() -> None:
    """방금 받은 기능을 다시 켜지 않고 바로 쓰게 한다(엔진 캐시 초기화)."""
    if activate() is None:
        return
    try:
        from core import ocr, perf
        perf.profile.cache_clear()
        ocr.reset()
    except Exception:  # noqa: BLE001
        pass


# ---------- 상태 ----------
def status() -> dict:
    inst = installed()
    best = _choose(inst)
    root = _find_root()
    with _LOCK:
        job = {k: v for k, v in _JOB.items() if k != "cancel"}
    return {
        "bundled": bundled(),
        "active": _ACTIVE,
        "installed": inst,
        "ready": bundled() or _ACTIVE is not None,
        "restart_needed": bool(_ACTIVE and best and best != _ACTIVE),
        "job": job,
        "sizes": {v: variant_size(v) for v in VARIANTS},
        "gpu": gpu_info(),
        "recommended": "gpu" if gpu_info()["capable"] else "cpu",
        "location": str(_pack(root or _roots()[0])),
        "sources": SOURCES,
    }


def _set(**kw) -> None:
    with _LOCK:
        _JOB.update(kw)


def _check_cancel() -> None:
    if _JOB.get("cancel"):
        raise _Cancelled()


# ---------- 받기 ----------
def _check_url(url: str) -> None:
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"허용되지 않은 내려받기 주소: {url}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _download(item: dict, dl_dir: Path, base: int) -> Path:
    """파일 하나 받기 — 끊기면 이어 받고, SHA-256 이 맞을 때만 돌려준다."""
    _check_url(item["url"])
    final = dl_dir / item["file"]
    if final.is_file() and final.stat().st_size == item["size"] and _sha256(final) == item["sha256"]:
        _set(done=base + item["size"])
        return final
    part = final.with_name(final.name + ".part")
    for attempt in range(_RETRIES):
        _check_cancel()
        h = hashlib.sha256()
        have = part.stat().st_size if part.is_file() else 0
        if have > item["size"]:
            part.unlink()
            have = 0
        if have:
            with open(part, "rb") as f:
                while chunk := f.read(_CHUNK):
                    h.update(chunk)
        headers = {"User-Agent": _UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(item["url"], headers=headers), timeout=60) as r:
                if have and r.status != 206:          # 이어 받기를 안 받아 주는 서버 — 처음부터
                    h, have = hashlib.sha256(), 0
                with open(part, "ab" if have else "wb") as f:
                    got = have
                    while chunk := r.read(_CHUNK):
                        _check_cancel()
                        f.write(chunk)
                        h.update(chunk)
                        got += len(chunk)
                        _set(done=base + got)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code in (403, 404):
                raise RuntimeError(f"{item['file']} 를 받을 수 없습니다(HTTP {e.code})") from e
            if attempt == _RETRIES - 1:
                raise RuntimeError(f"{item['file']} 받기 실패 — 인터넷 연결이나 방화벽을 확인해 주세요({e})") from e
            time.sleep(2 + attempt * 3)
            continue
        if part.stat().st_size < item["size"] and attempt < _RETRIES - 1:
            continue                                   # 연결이 중간에 닫힘 — 이어 받기
        if h.hexdigest() != item["sha256"]:
            part.unlink(missing_ok=True)
            raise RuntimeError(f"{item['file']} 확인(SHA-256) 실패 — 받는 중 손상됐거나 바뀐 파일이라 쓰지 않았습니다. "
                               "다시 시도해 주세요.")
        part.replace(final)
        return final
    raise RuntimeError(f"{item['file']} 받기 실패")


def _long(p: Path) -> str:
    """Windows 긴 경로(260자 넘음)도 쓸 수 있게."""
    s = str(p.resolve())
    return "\\\\?\\" + s if os.name == "nt" and len(s) > 240 and not s.startswith("\\\\?\\") else s


def _wheel_rel(name: str) -> str | None:
    """휠 안 경로 → 설치 폴더 안 경로. 실행에 필요 없는 것(헤더·링크용 .lib·스크립트)은 None."""
    parts = name.split("/")
    if not name or name.endswith("/") or name.startswith("/") or ".." in parts or ":" in parts[0] or "\\" in name:
        return None if name.endswith("/") else "__bad__"
    if parts[0].endswith(".data"):
        if len(parts) > 2 and parts[1] in ("purelib", "platlib"):
            parts = parts[2:]
        else:
            return None
    rel = "/".join(parts)
    low = rel.lower()
    if "/include/" in f"/{low}" or low.startswith("torch/share/cmake/") or (low.startswith("torch/lib/") and low.endswith(".lib")):
        return None
    return rel


def _extract_wheel(whl: Path, target: Path) -> None:
    base = os.path.normcase(str(target.resolve()))
    with zipfile.ZipFile(whl) as z:
        for info in z.infolist():
            rel = _wheel_rel(info.filename)
            if rel is None:
                continue
            dest = target / rel
            if rel == "__bad__" or not os.path.normcase(str(dest.resolve())).startswith(base + os.sep):
                raise RuntimeError(f"{whl.name}: 설치 폴더 밖을 가리키는 파일이 있어 멈췄습니다")
            os.makedirs(_long(dest.parent), exist_ok=True)
            with z.open(info) as src, open(_long(dest), "wb") as out:
                shutil.copyfileobj(src, out, _CHUNK)


def _install_models(pack: Path, dl: Path, base: int) -> None:
    md = pack / "models"
    md.mkdir(parents=True, exist_ok=True)
    for m in MANIFEST["models"]:
        dest = md / m["file"]
        if dest.is_file() and hashlib.md5(dest.read_bytes()).hexdigest() == m["md5"]:
            base += m["size"]
            _set(done=base)
            continue
        _set(phase="모델 받는 중", file=m["file"])
        z = _download(m, dl, base)
        with zipfile.ZipFile(z) as zf:
            data = zf.read(m["file"])
        if hashlib.md5(data).hexdigest() != m["md5"]:
            raise RuntimeError(f"{m['file']} 모델 확인 실패")
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
        z.unlink(missing_ok=True)
        base += m["size"]


def _run_install(variant: str) -> None:
    try:
        root = _writable_root()
        pack = _pack(root)
        dl = pack / "download"
        dl.mkdir(parents=True, exist_ok=True)
        pkgs = MANIFEST["variants"][variant]
        need = int(sum(p["size"] for p in pkgs) * 3.2) + sum(m["size"] for m in MANIFEST["models"])
        free = shutil.disk_usage(pack).free
        if free < need:
            raise RuntimeError(f"저장 공간이 부족합니다 — 약 {need / 1e9:.1f}GB 필요, 남은 공간 {free / 1e9:.1f}GB")
        work = pack / f"{variant}.part"          # 받는 중인 판(끝나면 이름을 바꾼다)
        work.mkdir(exist_ok=True)
        base = 0
        for i, p in enumerate(pkgs, 1):
            _check_cancel()
            done_flag = work / f".done-{p['sha256'][:16]}"
            if done_flag.exists():
                base += p["size"]
                _set(done=base)
                continue
            _set(phase=f"받는 중 ({i}/{len(pkgs)})", file=p["file"])
            whl = _download(p, dl, base)
            _set(phase=f"푸는 중 ({i}/{len(pkgs)})", file=p["file"])
            _extract_wheel(whl, work)
            done_flag.write_text("ok", encoding="utf-8")
            whl.unlink(missing_ok=True)
            base += p["size"]
        _install_models(pack, dl, base)
        _check_cancel()
        final = pack / variant
        if final.exists():
            if _ACTIVE == variant:
                raise RuntimeError("이 판을 쓰는 중이라 바꿀 수 없습니다 — 도우미를 다시 켠 뒤 받아 주세요")
            shutil.rmtree(_long(final), ignore_errors=True)
        for f in work.glob(".done-*"):
            f.unlink()
        work.rename(final)
        _marker(root, variant).write_text(json.dumps(
            {"variant": variant, "fingerprint": _fingerprint(variant), "id": MANIFEST["id"],
             "installed_at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(dl, ignore_errors=True)
        _set(phase="완료", file="", done=_JOB["total"], finished=True)
        _after_install()
    except _Cancelled:
        _set(phase="취소됨", file="")
    except Exception as e:  # noqa: BLE001
        _set(phase="실패", error=str(e))
    finally:
        _set(running=False)


def start_install(variant: str) -> dict:
    """내려받기 시작(뒤에서 진행) → 상태. 이미 진행 중이면 그 상태."""
    if variant not in VARIANTS:
        raise ValueError("variant 는 cpu 또는 gpu")
    with _LOCK:
        if _JOB["running"]:
            return {k: v for k, v in _JOB.items() if k != "cancel"}
        _JOB.update(running=True, variant=variant, phase="준비", file="", done=0, total=variant_size(variant),
                    error="", finished=False, cancel=False)
    threading.Thread(target=_run_install, args=(variant,), daemon=True, name="ocr-install").start()
    return status()["job"]


def cancel() -> None:
    _set(cancel=True)


def remove(variant: str) -> None:
    """받아 둔 판 지우기(저장 공간 확보). 지금 쓰는 판은 도우미를 다시 켠 뒤에만."""
    if variant not in VARIANTS:
        raise ValueError("variant 는 cpu 또는 gpu")
    if _ACTIVE == variant:
        raise RuntimeError("지금 쓰는 판이라 지울 수 없습니다 — 도우미를 다시 켠 뒤 지워 주세요")
    if _JOB["running"]:
        raise RuntimeError("내려받는 중에는 지울 수 없습니다")
    for r in _roots():
        pack = _pack(r)
        _marker(r, variant).unlink(missing_ok=True)
        for d in (pack / variant, pack / f"{variant}.part"):
            if d.exists():
                shutil.rmtree(_long(d), ignore_errors=True)
        if pack.is_dir() and not any(_installed_in(r, v) for v in VARIANTS) and _ACTIVE is None:
            shutil.rmtree(_long(pack), ignore_errors=True)
