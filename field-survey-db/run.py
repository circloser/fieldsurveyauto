"""로컬 런처: 빈 포트를 찾아 서버를 켜고 브라우저를 자동으로 엽니다.

- 포트가 이미 사용 중이면 다음 포트를 찾습니다(비개발자가 실수로 두 번 켜도 안전).
- 실제로 열린 포트로 브라우저를 엽니다.
"""
import multiprocessing
import socket
import sys
import threading
import time
import webbrowser

# Windows 콘솔(cp949)이 표현 못 하는 문자가 있어도 죽지 않게(포터블 exe 안전장치).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

import uvicorn

from app.config import DEFAULT_PORT
from app.main import app


def find_free_port(start: int, tries: int = 20) -> int:
    """start 포트부터 비어있는 포트를 찾아 반환."""
    for offset in range(tries):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:  # 연결 실패 = 비어있음
                return port
    return start  # 못 찾으면 기본값


def open_browser_when_ready(port: int) -> None:
    """서버가 응답하기 시작하면 브라우저를 엽니다."""
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):  # 최대 ~10초 대기
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.2)
    webbrowser.open(url)


def _env_report() -> None:
    """처음 켤 때 이 PC에서 무엇이 되는지 자동 점검해 안내(빠른 점검 — OCR 로드는 제외)."""
    from core import perf
    from core.syscheck import HWP_DOWNLOAD, run_checks

    for line in perf.summary_lines():
        print("  " + line)
    r = run_checks(quick=True)
    by = {i["id"]: i for i in r["items"]}
    if by["hwp"]["status"] == "ok":
        print("  [점검] 한글(HWP): 설치됨 - hwpx 변환 가능")
    else:
        print("  [점검] 한글(HWP): 없음 - hwpx 변환 불가(PDF 파일은 그대로 사용 가능)")
        print(f"         hwpx도 쓰려면 한글을 설치하세요: {HWP_DOWNLOAD}")
    for it in r["items"]:
        if it["status"] == "fail":
            print(f"  [불가] {it['name']}: {it['detail']}")
            if it["fix"]:
                print(f"         → {it['fix']}")
        elif it["status"] == "warn" and it["id"] != "hwp":
            print(f"  [주의] {it['name']}: {it['detail']}")
    print("  [점검] 자세한 점검은 브라우저의 '시스템 점검' 메뉴 (또는 FieldSurveyDB.exe --check)")


def run_check_and_exit() -> None:
    """`--check`: 전체 점검(OCR 엔진 로드 포함)을 돌려 화면에 출력하고 결과 파일을 남긴 뒤 종료.
    IT 담당자가 배포 전에 각 PC를 확인하는 용도."""
    from app.config import BASE_DIR
    from core.syscheck import report_text, run_checks

    print("시스템 점검 중… (글자 인식 엔진 로드까지 최대 30초)")
    text = report_text(run_checks(quick=False))
    print()
    print(text)
    out = BASE_DIR / "시스템점검_결과.txt"
    try:
        out.write_text(text, encoding="utf-8")
        print(f"\n결과 파일: {out}")
    except OSError as e:
        print(f"\n결과 파일을 쓰지 못했습니다({e})")


def main() -> None:
    if "--check" in sys.argv:
        run_check_and_exit()
        return
    port = find_free_port(DEFAULT_PORT)
    print("=" * 52)
    print("  오토다타 (AutoData) - 로컬 서버 시작")
    print(f"  주소: http://127.0.0.1:{port}")
    print("  종료하려면 이 창에서 Ctrl+C 를 누르세요.")
    _env_report()
    print("=" * 52)
    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller(Windows exe) 필수: 자기 재실행 방지
    main()
