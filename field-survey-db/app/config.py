"""경로/설정 모음. 로컬 전용. 포터블(exe·PyInstaller) 실행도 지원합니다.

- 개발/venv 실행: 프로젝트 폴더 기준.
- 포터블(exe) 실행: 정적파일은 번들(_MEIPASS) 안에서 읽고,
  작업 폴더(data/)는 exe 옆에 만든다(폴더째 복사해도 유지·쓰기 가능).
"""
import os
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
TEMPLATE_PDF_DIR = DATA_DIR / "template_pdfs"   # 템플릿과 함께 저장하는 원본 양식 PDF

# 시작 포트 (흔치 않은 값). 사용 중이면 run.py가 다음 포트를 찾습니다.
DEFAULT_PORT = 8765

APP_TITLE = "현장 조사표 DB화"
APP_VERSION = "0.5.0 (MVP: 업로드→추출→엑셀)"

# --- AI(Vision) 프록시 설정 -------------------------------------------------
# 진짜 Claude 키는 프록시(Cloudflare Worker)에만 둔다. 이 프로그램은 아래 2개만 안다.
#   FIELD_SURVEY_PROXY_URL   : 프록시 주소(예: https://...workers.dev)  → anthropic base_url
#   FIELD_SURVEY_APP_TOKEN   : 프록시 인증용 앱 토큰(진짜 키 아님)
#   FIELD_SURVEY_VISION_MODEL: 사용할 모델(기본 최상위)
#
# 로드 우선순위: 환경변수 → exe(또는 프로젝트) 옆 'ai_config.txt'(KEY=VALUE).
# 직원 배포 시 dist 폴더에 ai_config.txt 를 함께 넣으면 각자 설정 없이 바로 AI 사용.
# (앱 토큰은 유출돼도 폐기·교체 가능한 통행증이라 배포 파일에 넣어도 되는 설계)

def _load_ai_config() -> dict:
    cfg: dict[str, str] = {}
    path = BASE_DIR / "ai_config.txt"
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
        except OSError:
            pass
    return cfg


_AI_CFG = _load_ai_config()


def _ai_get(key: str, default: str = "") -> str:
    return (os.environ.get(key) or _AI_CFG.get(key) or default).strip()


# 두 가지 모드(우선순위: 직접 > 프록시)
#  1) 직접 모드: 본인 Anthropic 키(ANTHROPIC_API_KEY) → 각자 키·사용량으로 Claude 직접 호출.
#  2) 프록시 모드: 회사 공용 프록시(FIELD_SURVEY_PROXY_URL + APP_TOKEN) → 키를 서버에 보관.
ANTHROPIC_API_KEY = _ai_get("ANTHROPIC_API_KEY")
PROXY_BASE_URL = _ai_get("FIELD_SURVEY_PROXY_URL")
PROXY_APP_TOKEN = _ai_get("FIELD_SURVEY_APP_TOKEN")
VISION_MODEL = _ai_get("FIELD_SURVEY_VISION_MODEL", "claude-opus-4-8")


def ensure_dirs() -> None:
    """작업 폴더가 없으면 만듭니다."""
    for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PDF_CACHE_DIR, REPORT_CACHE_DIR,
              TEMPLATE_PDF_DIR):
        d.mkdir(parents=True, exist_ok=True)
