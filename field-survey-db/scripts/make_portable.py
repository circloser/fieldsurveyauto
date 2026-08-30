# -*- coding: utf-8 -*-
"""포터블 패키징 — 빌드 → 부속 문서 동봉 → 기동 스모크 → 날짜·시간 병기 zip.

사용:
  .venv/Scripts/python scripts/make_portable.py              # 전체(빌드부터)
  .venv/Scripts/python scripts/make_portable.py --skip-build # 기존 dist로 zip만

산출물: dist/FieldSurveyDB_포터블_YYYYMMDD_HHMM.zip
(날짜·시간이 파일명에 붙어 버전이 섞이지 않는다)
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
EXTRAS = ["사용법.txt", "README_AI_자동추출.md", "ai_config.txt"]
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


def build():
    clean_dist()
    r = subprocess.run([str(ROOT / ".venv" / "Scripts" / "pyinstaller.exe"),
                        str(ROOT / "FieldSurveyDB.spec"), "--noconfirm"],
                       cwd=str(ROOT))
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
    out = ROOT / "dist" / f"FieldSurveyDB_포터블_{stamp}.zip"
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
