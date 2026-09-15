"""웹 시작 페이지(깃허브 → 클라우드플레어 Pages)와 이 PC의 오토다타(도우미)를 잇는 접근 규칙.

웹 주소에서 여는 시작 페이지는 이 PC에서 도우미가 켜져 있는지, 한글·글자 인식·AI 키가 준비됐는지만 묻고,
실제 처리(파일 올리기·추출·엑셀)는 도우미의 작업 화면(http://127.0.0.1:포트)에서 한다.
  · 허용된 웹 주소는 상태를 묻는 몇 개 주소(READ_PATHS)만 읽을 수 있다(CORS + 크롬 로컬 네트워크 사전 요청).
  · 다른 웹사이트가 이 PC의 도우미에 파일을 올리거나 설정을 바꾸는 요청(POST 등)은 막는다 —
    이 PC의 작업 화면(127.0.0.1·localhost)에서 온 요청만 받는다.
허용 웹 주소 = 기본(클라우드플레어 Pages 기본 주소·미리보기 주소·로컬 개발) + 설치 폴더의 web_origins.txt(한 줄에 하나,
'https://*.example.org' 는 그 아래 주소 전체).
"""
from __future__ import annotations

import re
from pathlib import Path

ORIGINS_FILE = "web_origins.txt"
DEFAULT_ORIGINS = ["https://fieldsurveyauto.pages.dev", "http://localhost:8788", "http://127.0.0.1:8788"]
DEFAULT_SUFFIXES = [".fieldsurveyauto.pages.dev"]   # 브랜치 미리보기 주소 https://<이름>.fieldsurveyauto.pages.dev
READ_PATHS = ("/health", "/api/local/hello", "/api/system/check")
_LOCAL = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d{1,5})?$")
_ORIGIN = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$")


def load_origins(base_dir) -> tuple[set[str], list[str]]:
    """(정확히 일치하는 주소들, 하위 주소를 허용하는 접미어들)."""
    exact = {o.rstrip("/") for o in DEFAULT_ORIGINS}
    suffixes = list(DEFAULT_SUFFIXES)
    try:
        lines = (Path(base_dir) / ORIGINS_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for ln in lines:
        s = ln.strip().rstrip("/")
        if not s or s.startswith("#"):
            continue
        if s.startswith("https://*.") and _ORIGIN.match("https://" + s[len("https://*."):]):
            suffixes.append(s[len("https://*"):])
        elif _ORIGIN.match(s):
            exact.add(s)
    return exact, suffixes


def is_web_origin(origin: str | None, exact: set[str], suffixes: list[str]) -> bool:
    """허용된 웹 시작 페이지 주소인가. 접미어는 점으로 시작해 'evilfieldsurveyauto.pages.dev' 같은 흉내를 막는다."""
    if not origin:
        return False
    o = origin.rstrip("/")
    if o in exact:
        return True
    return (o.startswith("https://") and _ORIGIN.match(o) is not None
            and any(o.endswith(sfx) and len(o) > len("https://") + len(sfx) for sfx in suffixes))


def is_local_origin(origin: str | None) -> bool:
    """이 PC의 작업 화면(127.0.0.1·localhost)에서 온 요청인가."""
    return bool(origin) and _LOCAL.match(origin.rstrip("/")) is not None


def cors_headers(origin: str) -> dict[str, str]:
    return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}


def preflight_headers(origin: str) -> dict[str, str]:
    """사전 요청 응답 — 크롬의 공인 웹 → 이 PC(127.0.0.1) 요청 허용 표시 포함."""
    return {**cors_headers(origin),
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Private-Network": "true",
            "Access-Control-Max-Age": "600"}
