"""공용 텍스트 정규화 (R10 대응).

앵커(서식 제목) 매칭이 NBSP/전각공백/유니코드 조합 차이로 실패하는 것을 막기 위해,
detector·segmenter·mapper·checkbox 가 모두 이 함수를 동일하게 사용합니다.
"""
import re
import unicodedata

# 공백류: 일반공백, NBSP(U+00A0), 전각공백(U+3000), 탭/개행 등
_WS_RE = re.compile(r"[\s 　​﻿]+")

# 체크 표시로 인정하는 문자들 (√ ✓ ☑ ■ 등)
CHECK_MARKS = frozenset("√✓✔☑■◼◾▪●⦿")
# 빈 체크박스(선택 안 됨)로 인정하는 문자들
UNCHECK_MARKS = frozenset("□☐◻▫○")


def normalize(text: str | None) -> str:
    """NFC 정규화 + 모든 공백류를 단일 공백으로 축약 + 앞뒤 공백 제거."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def normalize_key(text: str | None) -> str:
    """비교/매칭용 키: 정규화 후 모든 공백 제거(앵커 매칭을 공백에 관대하게)."""
    return normalize(text).replace(" ", "")


def has_check_mark(text: str | None) -> bool:
    """텍스트에 선택 표시(√ 등)가 있는지."""
    if not text:
        return False
    return any(ch in CHECK_MARKS for ch in text)


def has_uncheck_box(text: str | None) -> bool:
    """텍스트에 '빈 네모(□)' 가 있는지 (선택 안 된 신호)."""
    if not text:
        return False
    return any(ch in UNCHECK_MARKS for ch in text)
