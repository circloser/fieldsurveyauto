"""번들 자동 처리 — 다중 서식 PDF를 페이지별로 라우팅 후 알맞은 스키마로 Vision 추출.

파일 하나(여러 서식 섞임)를 넣으면 페이지마다:
  1) 서식 판별(form_router, 무료 시그니처 → 애매하면 Vision 분류 폴백)
  2) 그 서식의 스키마로 Vision 추출
결과: 페이지별 {page, form, label, confidence, values}.
"""
from __future__ import annotations

import time

from core import vision_extract
from core.extraction.form_detector import FORM_LABELS_KO, FORM_UNKNOWN
from core.extraction.schema import SCHEMAS
from core.extraction.schema.vision_schemas import vision_schema
from core.form_router import classify_page_vision, route_page
from core.pdf_reader import read_pdf

_NUM_CHARS = set("0123456789.-+ ")


def _numeric_fields(form: str) -> set[str]:
    """서식 스키마에서 숫자형(number*) 필드명 집합."""
    return {s.name for s in SCHEMAS.get(form, []) if "number" in s.kind}


def _flags_for(form: str, values: dict) -> dict:
    """Phase 3 신뢰도 플래그 — 검수 권장 필드. field -> 사유.

    - 빈값: 값이 비어 있음(사람이 채우거나 원본이 빈칸인지 확인).
    - 형식오류: 숫자 필드인데 숫자로 안 보임(오인식 의심 → 우선 검수).
    """
    numeric = _numeric_fields(form)
    flags: dict[str, str] = {}
    for k, v in values.items():
        val = (v or "").strip()
        if not val:
            flags[k] = "빈값"
        elif k in numeric and any(ch not in _NUM_CHARS for ch in val):
            flags[k] = "형식오류"
    return flags


def extract_bundle(pdf_path: str, use_vision_fallback: bool = True,
                   use_generic: bool = True, dpi: int = 170,
                   pace_seconds: float = 1.0) -> list[dict]:
    """번들 PDF를 페이지별로 자동 추출.

    - 알려진 서식(A~E): 해당 스키마로 추출.
    - 미상 서식(정의 안 된 다른 조사표): use_generic 이면 스키마 없이 Vision으로
      '항목:값'을 통째로 뽑는다(범용 모드) → 어떤 조사표든 표로.
    - 사진(photo) 등 데이터 아님: 건너뜀.
    """
    doc = read_pdf(pdf_path)
    rows: list[dict] = []
    made_call = False

    def _pace():
        nonlocal made_call
        if made_call and pace_seconds:
            time.sleep(pace_seconds)   # 앞단 레이트 가드 발동 완화
        made_call = True

    for p in doc.pages:
        det = route_page(p)
        form = det.form_type
        source = "signature"
        # 시그니처가 못 잡으면 Vision 분류로 알려진 6종에 맞춰보기(선택)
        if form == FORM_UNKNOWN and use_vision_fallback:
            v = classify_page_vision(pdf_path, p.page_no)
            if v != FORM_UNKNOWN:
                form, source = v, "vision"

        schema, hint = vision_schema(form)
        row = {
            "page": p.page_no,
            "form": form,
            "label": FORM_LABELS_KO.get(form, form),
            "confidence": det.confidence,
            "route_source": source,
            "generic": False,
            "values": {},
            "flags": {},
        }
        if schema is not None:
            _pace()
            row["values"] = vision_extract.extract_page(pdf_path, p.page_no, schema, hint, dpi=dpi)
            row["flags"] = _flags_for(form, row["values"])
        elif form == FORM_UNKNOWN and use_generic:
            # 범용 모드: 정의 안 된 새 조사표도 자유형으로 추출
            _pace()
            row["values"] = vision_extract.extract_page_generic(pdf_path, p.page_no, dpi=dpi)
            row["generic"] = True
            row["label"] = "범용(미상 서식)"
            row["route_source"] = "generic"
            row["flags"] = _flags_for(form, row["values"])
        rows.append(row)
    return rows
