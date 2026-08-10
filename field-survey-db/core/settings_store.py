"""AI 설정 저장 — API 키를 Windows DPAPI로 암호화해 저장(사용자 계정에 귀속).

평문 txt 유출 위험 완화: 저장 파일은 그 Windows 사용자만 복호화 가능(다른 사용자·다른 PC 불가),
디스크에 평문으로 남지 않는다.
※ 한계(정직): 같은 사용자로 실행되는 프로그램은 결국 키를 복호화해 쓸 수 있다(로컬 앱의 본질적 한계).
   완전한 비밀 보관이 필요하면 프록시 방식(키를 서버에만)을 쓴다.
DPAPI 불가 환경(비-Windows/pywin32 없음)에서는 평문 저장하고 encrypted=False 로 표시한다.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

PROVIDERS = ("claude", "openai", "gemini")


def _encrypt(text: str) -> tuple[str, bool]:
    """(저장문자열, 암호화여부). DPAPI 가능하면 암호화(base64), 아니면 평문."""
    if not text:
        return "", True
    try:
        import win32crypt
        blob = win32crypt.CryptProtectData(text.encode("utf-8"), "field-survey-ai",
                                           None, None, None, 0)
        return base64.b64encode(blob).decode(), True
    except Exception:  # noqa: BLE001
        return text, False


def _decrypt(stored: str, encrypted: bool) -> str:
    if not stored:
        return ""
    if not encrypted:
        return stored
    try:
        import win32crypt
        blob = base64.b64decode(stored)
        _, data = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return data.decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def load(path) -> dict:
    """설정 로드 → {provider, keys:{claude,openai,gemini}, models:{}}. 없으면 기본값."""
    out = {"provider": "claude", "keys": {k: "" for k in PROVIDERS}, "models": {}}
    p = Path(path)
    if not p.exists():
        return out
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    out["provider"] = raw.get("provider") or "claude"
    encrypted = raw.get("encrypted", True)
    stored_keys = raw.get("keys", {}) or {}
    for k in PROVIDERS:
        out["keys"][k] = _decrypt(stored_keys.get(k, ""), encrypted)
    out["models"] = raw.get("models", {}) or {}
    return out


def save(path, provider: str, keys: dict, models: dict | None = None) -> bool:
    """저장. 반환: 암호화 저장 여부(False면 평문 — DPAPI 불가 환경)."""
    enc_flag = True
    stored: dict[str, str] = {}
    for k in PROVIDERS:
        s, ok = _encrypt((keys.get(k) or "").strip())
        stored[k] = s
        if (keys.get(k) or "").strip():   # 실제 값이 있는 것만 암호화 성공여부 반영
            enc_flag = enc_flag and ok
    data = {
        "provider": provider if provider in PROVIDERS else "claude",
        "encrypted": enc_flag,
        "keys": stored,
        "models": models or {},
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return enc_flag


def status(path) -> dict:
    """UI 표시용 — 키는 노출하지 않고 '설정됨' 여부와 암호화 여부만."""
    s = load(path)
    return {
        "provider": s["provider"],
        "configured": {k: bool(s["keys"][k]) for k in PROVIDERS},
        "encrypted": bool(json.loads(Path(path).read_text(encoding="utf-8")).get("encrypted"))
        if Path(path).exists() else None,
    }
