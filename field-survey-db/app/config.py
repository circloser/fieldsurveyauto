"""경로/설정 모음. 모든 작업 폴더는 프로젝트 안에만 만들어집니다(로컬 전용)."""
from pathlib import Path

# 프로젝트 루트 (이 파일 기준 상위 폴더)
ROOT = Path(__file__).resolve().parent.parent

STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "output"
PDF_CACHE_DIR = DATA_DIR / "pdf_cache"
REPORT_CACHE_DIR = DATA_DIR / "report_cache"

# 시작 포트 (흔치 않은 값). 사용 중이면 start.bat이 다음 포트를 찾습니다.
DEFAULT_PORT = 8765

APP_TITLE = "현장 조사표 DB화"
APP_VERSION = "0.5.0 (MVP: 업로드→추출→엑셀)"


def ensure_dirs() -> None:
    """작업 폴더가 없으면 만듭니다."""
    for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PDF_CACHE_DIR, REPORT_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
