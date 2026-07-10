"""경로/설정 모음. 로컬 전용. 포터블(exe·PyInstaller) 실행도 지원합니다.

- 개발/venv 실행: 프로젝트 폴더 기준.
- 포터블(exe) 실행: 정적파일은 번들(_MEIPASS) 안에서 읽고,
  작업 폴더(data/)는 exe 옆에 만든다(폴더째 복사해도 유지·쓰기 가능).
"""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 번들. 정적자원=번들 내부, 쓰기 데이터=exe 옆.
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    BASE_DIR = Path(__file__).resolve().parent.parent

ROOT = BASE_DIR  # 하위 호환

STATIC_DIR = BUNDLE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "output"
PDF_CACHE_DIR = DATA_DIR / "pdf_cache"
REPORT_CACHE_DIR = DATA_DIR / "report_cache"

# 시작 포트 (흔치 않은 값). 사용 중이면 run.py가 다음 포트를 찾습니다.
DEFAULT_PORT = 8765

APP_TITLE = "현장 조사표 DB화"
APP_VERSION = "0.5.0 (MVP: 업로드→추출→엑셀)"


def ensure_dirs() -> None:
    """작업 폴더가 없으면 만듭니다."""
    for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PDF_CACHE_DIR, REPORT_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
