# -*- coding: utf-8 -*-
"""포터블 패키징 — 빌드 → 부속 문서 동봉 → 기동 스모크 → 날짜·시간 병기 zip.

사용:
  .venv/Scripts/python scripts/make_portable.py              # 기본판(CPU 처리, OCR 포함, ~430MB)
  .venv/Scripts/python scripts/make_portable.py --gpu        # GPU 가속판(.venv-gpu 의 CUDA torch, zip ~2.2GB)
  .venv/Scripts/python scripts/make_portable.py --lite       # 경량판(OCR 없음)
  .venv/Scripts/python scripts/make_portable.py --skip-build # 기존 dist로 zip만

산출물: dist/FieldSurveyDB[_GPU|_경량]_포터블_YYYYMMDD_HHMM.zip
(날짜·시간이 파일명에 붙어 버전이 섞이지 않는다)

GPU판 준비(한 번만): python -m venv .venv-gpu
  .venv-gpu/Scripts/pip install torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cu130
  .venv-gpu/Scripts/pip install -r requirements.txt -r requirements-ocr.txt pyinstaller
"""
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "FieldSurveyDB"
PACKAGING = ROOT / "packaging"
EXTRAS = ["사용법.txt", "배포_점검표.md", "README_AI_자동추출.md", "ai_config.txt"]
PORT = 8765


def clean_dist():
    """이전 산출물 제거 — 백신 스캔과 겹치면 잠깐 잠기므로 재시도."""
    for i in range(5):
        try:
            if DIST.exists():
                shutil.rmtree(DIST)
            return
        except PermissionError:
            print(f"dist 잠김 — {i + 1}/5 재시도")
            time.sleep(3)
    raise SystemExit("dist/FieldSurveyDB 를 지울 수 없습니다(파일 잠김). "
                     "실행 중인 FieldSurveyDB.exe 를 닫고 다시 시도하세요.")


GPU = "--gpu" in sys.argv          # GPU판: CUDA 빌드 torch 가 든 .venv-gpu 로 빌드(zip ~2.2GB)
VENV = ROOT / (".venv-gpu" if GPU else ".venv")
VARIANT = "GPU" if GPU else ("경량" if "--lite" in sys.argv else "")


def build():
    clean_dist()
    # 기본 = OCR 포함 스펙(스캔·수기 문서 글자 인식 기본 탑재). --lite 는 경량판, --gpu 는 GPU 가속판.
    spec = "FieldSurveyDB.spec" if "--lite" in sys.argv else "FieldSurveyDB_OCR.spec"
    py = VENV / "Scripts" / "pyinstaller.exe"
    if not py.exists():
        raise SystemExit(f"{py} 가 없습니다" + (" — GPU판은 .venv-gpu(CUDA torch) 가 필요합니다: "
                                             "python -m venv .venv-gpu && pip install torch --index-url "
                                             "https://download.pytorch.org/whl/cu130 && pip install -r requirements.txt"
                                             if GPU else ""))
    if GPU:
        chk = subprocess.run([str(VENV / "Scripts" / "python.exe"), "-c",
                              "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"])
        if chk.returncode != 0:
            raise SystemExit(".venv-gpu 의 torch 가 CUDA를 못 씁니다(CPU 빌드거나 드라이버 없음) — GPU판 빌드 중단")
    r = subprocess.run([str(py), str(ROOT / spec), "--noconfirm"], cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit("PyInstaller 빌드 실패")


def add_extras():
    for name in EXTRAS:
        src = PACKAGING / name
        if src.exists():
            shutil.copy2(src, DIST / name)
        else:
            print(f"경고: packaging/{name} 없음 — 동봉 생략")


def smoke():
    """빌드된 exe 기동 → /health 200 확인 → 종료."""
    proc = subprocess.Popen([str(DIST / "FieldSurveyDB.exe")],
                            cwd=str(DIST),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            time.sleep(1)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{PORT}/health", timeout=2) as resp:
                    if resp.status == 200:
                        print("스모크 OK — /health 200")
                        return
            except OSError:
                pass
        raise SystemExit("스모크 실패: 30초 안에 /health 응답 없음")
    finally:
        proc.kill()
        time.sleep(2)  # DLL 잠금이 풀릴 시간


def make_zip() -> Path:
    """data/ 는 절대 담지 않는다 — 실데이터(조사표·템플릿·캐시)가 배포본에 섞이는 것 방지.
    (앱을 한 번이라도 켜면 exe 옆에 data/ 가 생기므로 필터가 안전망이다)"""
    import zipfile
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    tag = f"_{VARIANT}" if VARIANT else ""
    out = ROOT / "dist" / f"FieldSurveyDB{tag}_포터블_{stamp}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(DIST.rglob("*")):
            rel = p.relative_to(DIST)
            if rel.parts and rel.parts[0] == "data":
                continue
            if p.is_file():
                z.write(p, Path("FieldSurveyDB") / rel)
    return out


def main():
    skip_build = "--skip-build" in sys.argv
    if skip_build:
        if not DIST.exists():
            raise SystemExit("dist/FieldSurveyDB 가 없습니다 — --skip-build 를 빼고 실행하세요.")
        print("빌드 생략 — 기존 dist 사용")
    else:
        build()
    add_extras()
    smoke()
    out = make_zip()
    mb = out.stat().st_size / 1048576
    print(f"완료: {out.name} ({mb:.0f} MB)")


if __name__ == "__main__":
    main()
