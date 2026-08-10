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


_AI_CFG: dict = {}   # reload_ai_settings()가 채움


def _ai_get(key: str, default: str = "") -> str:
    return (os.environ.get(key) or _AI_CFG.get(key) or default).strip()


# 멀티 제공자 + 암호화 설정.
# 키 출처 우선순위: 환경변수 > 암호화 설정창(ai_settings.enc, DPAPI) > ai_config.txt(평문 폴백).
from core import settings_store  # noqa: E402  (stdlib+win32만 의존, 순환 없음)

SETTINGS_PATH = BASE_DIR / "ai_settings.enc"
_SETTINGS: dict = {}
AI_PROVIDER = "claude"
CLAUDE_API_KEY = OPENAI_API_KEY = GEMINI_API_KEY = ANTHROPIC_API_KEY = ""
PROXY_BASE_URL = PROXY_APP_TOKEN = ""


def reload_ai_settings() -> None:
    """ai_config.txt + 암호화 설정(ai_settings.enc)을 다시 읽어 전역값 갱신.

    설정창 저장 후 이 함수를 부르면 실행 중에도(재시작 없이) 새 값이 반영된다
    (모듈들이 호출 시점에 config.X 를 읽으므로).
    """
    global _AI_CFG, _SETTINGS, AI_PROVIDER, VISION_MODEL
    global CLAUDE_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY
    global PROXY_BASE_URL, PROXY_APP_TOKEN
    _AI_CFG = _load_ai_config()
    _SETTINGS = settings_store.load(SETTINGS_PATH)
    AI_PROVIDER = (os.environ.get("FIELD_SURVEY_AI_PROVIDER")
                   or _SETTINGS.get("provider")
                   or _AI_CFG.get("AI_PROVIDER") or "claude").strip()
    CLAUDE_API_KEY = (_SETTINGS["keys"].get("claude") or _ai_get("ANTHROPIC_API_KEY")).strip()
    OPENAI_API_KEY = (_SETTINGS["keys"].get("openai") or _ai_get("OPENAI_API_KEY")).strip()
    GEMINI_API_KEY = (_SETTINGS["keys"].get("gemini") or _ai_get("GEMINI_API_KEY")).strip()
    ANTHROPIC_API_KEY = CLAUDE_API_KEY  # 뒤 호환(기존 Claude 경로)
    PROXY_BASE_URL = _ai_get("FIELD_SURVEY_PROXY_URL")
    PROXY_APP_TOKEN = _ai_get("FIELD_SURVEY_APP_TOKEN")
    _m = _SETTINGS.get("models") or {}
    VISION_MODEL = (os.environ.get("FIELD_SURVEY_VISION_MODEL")
                    or _m.get(AI_PROVIDER)
                    or _AI_CFG.get("FIELD_SURVEY_VISION_MODEL")
                    or _DEFAULT_MODELS.get(AI_PROVIDER, "claude-opus-4-8")).strip()

# 제공자별 기본 모델 (설정으로 덮어쓰기 가능)
_DEFAULT_MODELS = {"claude": "claude-opus-4-8", "openai": "gpt-4o", "gemini": "gemini-1.5-pro"}
VISION_MODEL = "claude-opus-4-8"   # reload_ai_settings()가 실제값으로 채움

reload_ai_settings()   # 최초 로드


def ensure_dirs() -> None:
    """작업 폴더가 없으면 만듭니다."""
    for d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, PDF_CACHE_DIR, REPORT_CACHE_DIR,
              TEMPLATE_PDF_DIR):
        d.mkdir(parents=True, exist_ok=True)
