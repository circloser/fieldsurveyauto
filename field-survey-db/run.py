"""로컬 런처: 빈 포트를 찾아 서버를 켜고 브라우저를 자동으로 엽니다.

- 포트가 이미 사용 중이면 다음 포트를 찾습니다(비개발자가 실수로 두 번 켜도 안전).
- 실제로 열린 포트로 브라우저를 엽니다.
"""
import multiprocessing
import socket
import threading
import time
import webbrowser

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
    """처음 켤 때 이 PC에서 무엇이 되는지 자동 점검해 안내."""
    from app.main import hwp_installed
    if hwp_installed():
        print("  [점검] 한글(HWP): 설치됨 — hwpx 변환 가능")
    else:
        print("  [점검] 한글(HWP): 없음 — hwpx 변환 불가(PDF 파일은 그대로 사용 가능)")
        print("         hwpx도 쓰려면 한글을 설치하세요: https://www.hancom.com/cs_center/csDownload.do")


def main() -> None:
    port = find_free_port(DEFAULT_PORT)
    print("=" * 52)
    print("  현장 조사표 DB화 - 로컬 서버 시작")
    print(f"  주소: http://127.0.0.1:{port}")
    print("  종료하려면 이 창에서 Ctrl+C 를 누르세요.")
    _env_report()
    print("=" * 52)
    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller(Windows exe) 필수: 자기 재실행 방지
    main()
