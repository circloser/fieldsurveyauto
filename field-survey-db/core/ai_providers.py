"""AI 제공자 추상화 — Claude / OpenAI(ChatGPT) / Gemini.

설정창(config.AI_PROVIDER)으로 선택. 각 제공자는 다음을 제공한다:
  - vision_json(png, schema, hint, system) -> dict   (이미지 + JSON 스키마 구조화 출력)
  - text(prompt, max_tokens) -> str                  (텍스트 전용)

Claude 는 기존 검증된 anthropic SDK 경로(vision_extract)를 그대로 쓰고, 여기서는
OpenAI/Gemini 를 SDK 의존 없이 REST(httpx)로 구현한다.
※ OpenAI/Gemini 는 제 환경에 키가 없어 라이브 미검증(구조는 표준 호출 규격). 키로 확인 필요.
"""
from __future__ import annotations

import base64
import json
import time

import httpx

from app import config

_TRANSIENT = {403, 408, 429, 500, 502, 503, 529}


def _post_json(url: str, headers: dict, body: dict, tries: int = 5, timeout: float = 90.0) -> dict:
    """POST + JSON, 일시적 상태코드(403/429/5xx)에 지수 백오프 재시도."""
    last = None
    for attempt in range(tries):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except httpx.HTTPError as e:  # 네트워크 오류도 재시도
            last = RuntimeError(f"네트워크 오류: {e}")
            time.sleep(min(2 ** attempt * 2, 24))
            continue
        if r.status_code == 200:
            return r.json()
        last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        if attempt < tries - 1 and r.status_code in _TRANSIENT:
            time.sleep(min(2 ** attempt * 2, 24))
            continue
        raise last
    raise last  # pragma: no cover


def _strip_unsupported(schema: dict) -> dict:
    """Gemini response_schema 용 — additionalProperties 등 미지원 키 제거(재귀)."""
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if k == "additionalProperties":
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {pk: _strip_unsupported(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _strip_unsupported(v)
        else:
            out[k] = v
    return out


# ─────────────── OpenAI (ChatGPT) ───────────────

class OpenAIProvider:
    name = "openai"

    def available(self) -> tuple[bool, str]:
        if not config.OPENAI_API_KEY:
            return False, "OpenAI 키가 필요합니다. 설정창에서 OpenAI API 키를 입력하세요."
        return True, ""

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json"}

    def vision_json(self, png: bytes, schema: dict, hint: str, system: str) -> dict:
        b64 = base64.standard_b64encode(png).decode()
        body = {
            "model": config.VISION_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": hint},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "result", "schema": schema,
                                                "strict": True}},
            "max_tokens": 4000,
        }
        data = _post_json("https://api.openai.com/v1/chat/completions", self._headers(), body)
        try:
            return json.loads(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, json.JSONDecodeError):
            return {}

    def text(self, prompt: str, max_tokens: int = 1500) -> str:
        body = {"model": config.VISION_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens}
        data = _post_json("https://api.openai.com/v1/chat/completions", self._headers(), body)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            return ""


# ─────────────── Gemini ───────────────

class GeminiProvider:
    name = "gemini"

    def available(self) -> tuple[bool, str]:
        if not config.GEMINI_API_KEY:
            return False, "Gemini 키가 필요합니다. 설정창에서 Gemini API 키를 입력하세요."
        return True, ""

    def _url(self) -> str:
        return (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{config.VISION_MODEL}:generateContent?key={config.GEMINI_API_KEY}")

    def vision_json(self, png: bytes, schema: dict, hint: str, system: str) -> dict:
        b64 = base64.standard_b64encode(png).decode()
        body = {
            "contents": [{"parts": [
                {"text": system + "\n\n" + hint},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ]}],
            "generationConfig": {"response_mime_type": "application/json",
                                 "response_schema": _strip_unsupported(schema)},
        }
        data = _post_json(self._url(), {"Content-Type": "application/json"}, body)
        return _gemini_json(data)

    def text(self, prompt: str, max_tokens: int = 1500) -> str:
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}}
        data = _post_json(self._url(), {"Content-Type": "application/json"}, body)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"] or ""
        except (KeyError, IndexError):
            return ""


def _gemini_json(data: dict) -> dict:
    try:
        txt = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(txt)
    except (KeyError, IndexError, json.JSONDecodeError):
        return {}


_REGISTRY = {"openai": OpenAIProvider, "gemini": GeminiProvider}


def get(name: str):
    cls = _REGISTRY.get(name)
    return cls() if cls else None
