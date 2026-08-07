"""Vision-LLM 추출 — PDF 페이지 이미지를 Claude Vision 에 보내 스키마(JSON)로 직접 추출.

경진대회 계획 Phase 1: '보이는 대로 뭘 뽑을지 정하고, 실제 내용 기준으로 유기적 추출'.
Vision 은 페이지를 사람처럼 통째로 읽으므로 밀림·제목변경·스캔/손글씨에 자연 강건하다.

보안: 키는 프록시(Cloudflare Worker)에만. 이 프로그램은 프록시 주소 + 앱 토큰만 안다.
      FIELD_SURVEY_PROXY_URL / FIELD_SURVEY_APP_TOKEN 미설정 시 available()=False.
하이브리드: 규칙 앵커(core.layout)가 못 풀거나 틀어진 페이지에만 이 경로를 쓴다(비용↓).
"""
from __future__ import annotations

import base64
import json

from app import config
from core.pdf_reader import render_page_png

_SYSTEM = (
    "당신은 한국 공공기관 현장 조사표(하천·습지·보 제원 등)를 디지털화하는 전문가입니다. "
    "주어진 페이지 이미지를 사람처럼 읽고, 요청된 스키마의 각 항목 값을 정확히 채우세요.\n"
    "규칙:\n"
    "- 문서에 실제로 보이는 값만 적는다. 값이 없거나 애매하면 빈 문자열로 둔다.\n"
    "- 체크(√·■)로 선택된 항목은 그 선택지의 텍스트를 값으로 적는다. 여러 개면 쉼표로 모두.\n"
    "- 조사자처럼 사람 이름 필드는 한 명씩 나눠 넣는다. 한 칸에 여러 명이 적혀 있어도 "
    "순서대로 조사자1, 조사자2, 조사자3 에 분리한다.\n"
    "- 추측·창작 금지. 애매하면 비워서 사람 검수에 맡긴다."
)


def available() -> tuple[bool, str]:
    """(사용가능, 안내메시지). anthropic 패키지 + 프록시 설정이 모두 있어야 True."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Vision 기능엔 anthropic 패키지가 필요합니다. (pip install -r requirements-ai.txt)"
    if not config.PROXY_BASE_URL:
        return False, ("Vision 기능을 쓰려면 프록시 주소가 필요합니다. "
                       "환경변수 FIELD_SURVEY_PROXY_URL 를 설정하세요.")
    if not config.PROXY_APP_TOKEN:
        return False, ("Vision 기능을 쓰려면 앱 토큰이 필요합니다. "
                       "환경변수 FIELD_SURVEY_APP_TOKEN 를 설정하세요.")
    return True, ""


def _client():
    import anthropic
    # base_url 을 프록시로 → 진짜 키는 서버에만. api_key 자리에는 앱 토큰이 들어간다.
    return anthropic.Anthropic(base_url=config.PROXY_BASE_URL, api_key=config.PROXY_APP_TOKEN)


def build_content(png: bytes, schema_hint: str) -> list:
    """모델에 보낼 user content(이미지 + 지시문) 구성. (네트워크 없이 테스트 가능)"""
    b64 = base64.standard_b64encode(png).decode()
    return [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/png", "data": b64}},
        {"type": "text",
         "text": "이 조사표 페이지에서 아래 항목을 추출해 주세요.\n\n" + schema_hint},
    ]


def extract_page(pdf_path: str, page_no: int, json_schema: dict,
                 schema_hint: str = "", dpi: int = 170) -> dict:
    """한 페이지를 Vision 으로 추출 → {필드명: 값}. 프록시 미설정 시 RuntimeError."""
    ok, msg = available()
    if not ok:
        raise RuntimeError(msg)
    png = render_page_png(pdf_path, page_no, dpi=dpi)
    resp = _client().messages.create(
        model=config.VISION_MODEL,
        max_tokens=4000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": build_content(png, schema_hint)}],
        output_config={"format": {"type": "json_schema", "schema": json_schema}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
