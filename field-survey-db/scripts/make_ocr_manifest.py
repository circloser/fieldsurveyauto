# -*- coding: utf-8 -*-
"""글자 인식(OCR) 내려받기 목록 만들기 → core/ocr_manifest.py

경량 도우미(OCR 엔진을 넣지 않은 포터블)가 스캔 문서를 처음 만날 때 받을 파일을 고정한다.
  · 파이썬 패키지: pip 설치 계획(--dry-run --report)으로
      CPU판 = PyPI, GPU판 = PyTorch 공식 저장소(cu130) + PyPI 의 파일 주소와 SHA-256 을 얻는다
  · 경량 도우미에 이미 들어 있는 패키지(numpy·Pillow·OpenCV)는 뺀다
  · EasyOCR 모델(글자 위치 craft, 한국어 korean_g2): EasyOCR GitHub 릴리스 zip 을 한 번 받아 SHA-256 기록
받는 곳은 모두 공개 저장소이고, 도우미는 이 목록의 SHA-256 과 맞는 파일만 쓴다.

사용:   .venv/Scripts/python.exe scripts/make_ocr_manifest.py
버전 올리기: requirements-lock.txt 의 torch·torchvision·easyocr 를 바꾸고 다시 실행 → 커밋
"""
from __future__ import annotations

import hashlib
import json
import pprint
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "core" / "ocr_manifest.py"
LOCK = ROOT / "requirements-lock.txt"
BUNDLED = {"numpy", "pillow", "opencv-python-headless", "opencv-python"}   # 경량 도우미에 이미 동봉
SKIP_PINS = {"pywin32", "pywin32-ctypes"}                                     # 설치 계획 계산에 불필요
PY_VER, PY_IMPL, PLATFORM = "3.11", "cp", "win_amd64"
CUDA = "cu130"
MODELS = (("detection", "craft"), ("recognition", "korean_g2"))


def norm(name: str) -> str:
    return name.lower().replace("_", "-")


def pins() -> dict[str, str]:
    out = {}
    for ln in LOCK.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "==" in ln:
            k, v = ln.split("==", 1)
            out[norm(k)] = v.strip()
    return out


def head_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "autodata-manifest"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length") or 0)


def sha256_url(url: str) -> str:
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "autodata-manifest"})
    with urllib.request.urlopen(req, timeout=600) as r:
        while chunk := r.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def resolve(variant: str, p: dict[str, str]) -> list[dict]:
    tag = f"+{CUDA}" if variant == "gpu" else ""
    reqs = [f"easyocr=={p['easyocr']}", f"torch=={p['torch']}{tag}", f"torchvision=={p['torchvision']}{tag}"]
    idx = (["--index-url", f"https://download.pytorch.org/whl/{CUDA}", "--extra-index-url", "https://pypi.org/simple"]
           if variant == "gpu" else [])
    with tempfile.TemporaryDirectory() as td:
        cons = Path(td) / "constraints.txt"
        cons.write_text("\n".join(f"{k}=={v}" for k, v in p.items() if k not in SKIP_PINS), encoding="utf-8")
        report = Path(td) / "report.json"
        subprocess.run([sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
                        "--disable-pip-version-check", "--quiet", "--report", str(report),
                        "--only-binary=:all:", "--platform", PLATFORM, "--python-version", PY_VER,
                        "--implementation", PY_IMPL, "--target", str(Path(td) / "target"),
                        "-c", str(cons), *idx, *reqs], check=True)
        plan = json.loads(report.read_text(encoding="utf-8"))
    pkgs = []
    for item in plan["install"]:
        name = norm(item["metadata"]["name"])
        if name in BUNDLED:
            continue
        info = item["download_info"]
        hashes = (info.get("archive_info") or {}).get("hashes") or {}
        url = info["url"]
        size = head_size(url)
        sha = hashes.get("sha256")
        if not sha:          # 저장소 목록에 해시가 없는 파일(PyTorch 저장소 일부) — 작으면 직접 받아 계산
            if size > 400 * 1048576:
                raise SystemExit(f"{name}: SHA-256 없음(파일 {size / 1048576:.0f} MB) — 목록을 만들 수 없습니다")
            sha = sha256_url(url)
        pkgs.append({"name": name, "version": item["metadata"]["version"],
                     "file": urllib.parse.unquote(url.rsplit("/", 1)[-1]),
                     "url": url, "sha256": sha, "size": size})
        print(f"  [{variant}] {pkgs[-1]['file']} {pkgs[-1]['size'] / 1048576:.1f} MB")
    return sorted(pkgs, key=lambda x: x["name"])


def models() -> list[dict]:
    from easyocr import config as ecfg

    out = []
    for kind, key in MODELS:
        m = (ecfg.detection_models if kind == "detection" else ecfg.recognition_models["gen2"])[key]
        with tempfile.TemporaryDirectory() as td:
            zpath = Path(td) / "m.zip"
            req = urllib.request.Request(m["url"], headers={"User-Agent": "autodata-manifest"})
            with urllib.request.urlopen(req, timeout=600) as r, open(zpath, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            data = zpath.read_bytes()
            with zipfile.ZipFile(zpath) as z:
                pth = z.read(m["filename"])
            if hashlib.md5(pth).hexdigest() != m["md5sum"]:
                raise SystemExit(f"{m['filename']}: EasyOCR md5 불일치")
        out.append({"name": key, "file": m["filename"], "url": m["url"], "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data), "md5": m["md5sum"]})
        print(f"  [모델] {m['filename']} {len(data) / 1048576:.1f} MB")
    return out


def main() -> None:
    p = pins()
    manifest = {
        "id": f"t{p['torch'].replace('.', '')}e{p['easyocr'].replace('.', '')}",
        "python": f"{PY_IMPL}{PY_VER.replace('.', '')}-{PLATFORM}",
        "variants": {"cpu": resolve("cpu", p), "gpu": resolve("gpu", p)},
        "models": models(),
    }
    body = pprint.pformat(manifest, width=120, sort_dicts=False)
    OUT.write_text('"""글자 인식(OCR) 내려받기 목록 — scripts/make_ocr_manifest.py 가 만든 파일입니다. 직접 고치지 마세요."""\n'
                   f"MANIFEST = {body}\n", encoding="utf-8")
    for v, pk in manifest["variants"].items():
        print(f"{v}: {len(pk)}개 {sum(x['size'] for x in pk) / 1048576:.0f} MB")
    print(f"완료: {OUT}")


if __name__ == "__main__":
    main()
