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


# ── 범용(미상 서식) 추출 — 스키마 없이 '항목:값'을 통째로 뽑는다 ───────────────

_GENERIC_SYSTEM = (
    "당신은 어떤 현장 조사표든 디지털화하는 전문가입니다. 주어진 페이지 이미지를 사람처럼 "
    "읽고, 사람이 '기재한' 모든 항목을 (항목 이름, 값) 쌍으로 빠짐없이 추출하세요.\n"
    "규칙:\n"
    "- 항목=문서의 라벨/칸 이름, 값=그 옆이나 아래에 적힌 내용.\n"
    "- 체크(√·■)로 선택된 항목은 선택지 텍스트를 값으로. 표의 각 행도 항목:값으로.\n"
    "- 설명문·안내문·사진·그림·빈 칸은 제외. 실제 기재된 데이터만.\n"
    "- 추측·창작 금지. 보이는 그대로만."
)

_GENERIC_HINT = (
    "이 페이지에 사람이 기재한 모든 '항목'과 '값'을 찾아 나열하세요. "
    "(예: 항목='하천명' 값='탄천', 항목='보 길이' 값='20')"
)

_GENERIC_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"항목": {"type": "string"}, "값": {"type": "string"}},
                "required": ["항목", "값"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def items_to_dict(items: list | None) -> dict:
    """[{'항목','값'}] → {항목: 값}. 중복 항목은 접미어로 유일화(엑셀 열 충돌 방지)."""
    out: dict[str, str] = {}
    for it in items or []:
        k = (it.get("항목") or "").strip()
        v = (it.get("값") or "").strip()
        if not k:
            continue
        if k in out:
            n = 2
            while f"{k} ({n})" in out:
                n += 1
            k = f"{k} ({n})"
        out[k] = v
    return out


def extract_page_generic(pdf_path: str, page_no: int, dpi: int = 170) -> dict:
    """미상 서식 페이지를 스키마 없이 Vision으로 추출 → {항목: 값}. 프록시 미설정 시 RuntimeError."""
    ok, msg = available()
    if not ok:
        raise RuntimeError(msg)
    png = render_page_png(pdf_path, page_no, dpi=dpi)
    resp = _client().messages.create(
        model=config.VISION_MODEL,
        max_tokens=4000,
        system=_GENERIC_SYSTEM,
        messages=[{"role": "user", "content": build_content(png, _GENERIC_HINT)}],
        output_config={"format": {"type": "json_schema", "schema": _GENERIC_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return items_to_dict(data.get("items"))


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
