"""서식별 Vision 추출용 JSON 스키마 — 기존 FieldSpec 정의를 재사용해 생성.

규칙 기반과 같은 필드명을 쓰므로 엑셀 열/검수 UI가 그대로 재사용된다.
새 서식은 core/extraction/schema/ 에 FieldSpec 목록만 추가하면 여기서 자동 반영된다.
"""
from __future__ import annotations

from core.extraction.schema import SCHEMAS
from core.extraction.schema.spec import FieldSpec


def json_schema_from_specs(specs: list[FieldSpec]) -> dict:
    """FieldSpec 목록 → Vision 출력용 JSON Schema. 모든 필드 string(빈 문자열 허용)."""
    props = {spec.name: {"type": "string"} for spec in specs}
    return {
        "type": "object",
        "properties": props,
        # strict json 출력 안정성을 위해 전부 required(값 없으면 빈 문자열로 채우게 함)
        "required": [s.name for s in specs],
        "additionalProperties": False,
    }


def hint_from_specs(specs: list[FieldSpec]) -> str:
    """모델에게 각 항목의 의미/선택지를 알려주는 힌트 텍스트."""
    lines = []
    for s in specs:
        if s.kind == "checkbox":
            opts = ", ".join(s.options)
            lines.append(
                f"- {s.name}: √ 로 선택된 항목의 텍스트. 여러 개면 쉼표로 모두 적기(구간별로 다를 수 있음) [{opts}]")
        else:
            lines.append(f"- {s.name} (문서상 라벨: '{s.label}')")
    return "\n".join(lines)


def vision_schema(form_type: str) -> tuple[dict | None, str]:
    """(json_schema, hint). 등록되지 않은 서식은 (None, '')."""
    specs = SCHEMAS.get(form_type)
    if not specs:
        return None, ""
    return json_schema_from_specs(specs), hint_from_specs(specs)
