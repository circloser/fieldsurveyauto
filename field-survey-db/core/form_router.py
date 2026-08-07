"""서식 라우터 — 페이지마다 어떤 조사표 서식인지 판별해 알맞은 스키마를 고른다.

경진대회 계획 Phase 1: 한 파일에 A(인공구조물)·C(어도)·사진 등이 섞인 실제 번들을
페이지별로 자동 라우팅. 제목이 아니라 '페이지에 어떤 라벨이 있는가'(form_detector
시그니처)로 판별하므로, 제목/사무실이 달라도 견고하다.

기본은 무료·빠른 시그니처 판별. 애매하면(UNKNOWN) Vision 분류로 폴백(선택).
"""
from __future__ import annotations

from core.extraction.form_detector import (
    FORM_LABELS_KO,
    FORM_UNKNOWN,
    Detection,
    detect_form_words,
)
from core.pdf_reader import PdfPage


def route_page(page: PdfPage) -> Detection:
    """페이지 단어로 서식 판별(무료·빠름)."""
    return detect_form_words(page.words)


def route_pages(pages: list[PdfPage]) -> list[tuple[int, Detection]]:
    return [(p.page_no, route_page(p)) for p in pages]


# --- Vision 분류 폴백 (선택) ------------------------------------------------

def _classify_schema() -> tuple[dict, str]:
    codes = list(FORM_LABELS_KO.keys())  # unknown 포함
    schema = {
        "type": "object",
        "properties": {"form": {"type": "string", "enum": codes}},
        "required": ["form"],
        "additionalProperties": False,
    }
    desc = ", ".join(f"{c}={FORM_LABELS_KO[c]}" for c in codes)
    hint = ("이 페이지가 어떤 현장 조사표 서식인지 코드 하나로 판별하세요.\n"
            f"코드: {desc}\n표가 아니거나 사진 페이지면 photo, 판단 불가면 unknown.")
    return schema, hint


def classify_page_vision(pdf_path: str, page_no: int) -> str:
    """Vision 으로 서식 코드 분류(폴백). 프록시 미설정이면 unknown 반환."""
    from core import vision_extract
    ok, _ = vision_extract.available()
    if not ok:
        return FORM_UNKNOWN
    schema, hint = _classify_schema()
    try:
        result = vision_extract.extract_page(pdf_path, page_no, schema, hint, dpi=120)
    except Exception:  # noqa: BLE001
        return FORM_UNKNOWN
    return result.get("form") or FORM_UNKNOWN
