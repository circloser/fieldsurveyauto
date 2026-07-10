"""매퍼 — 서식 블록에 스키마를 적용해 하나의 레코드(값 + 신뢰도 플래그)를 만든다."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.extraction.fish import extract_identity, extract_species
from core.extraction.form_detector import FORM_D
from core.extraction.schema import SCHEMAS
from core.extraction.schema.spec import ANCHOR_NOT_FOUND, OK, apply_spec
from core.extraction.segmenter import FormBlock


@dataclass
class Record:
    source_file: str
    form_type: str
    structure_name: str
    structure_code: str
    river_name: str
    values: dict[str, str] = field(default_factory=dict)
    # 필드명 -> 상태(anchor_missing / empty). ok 인 필드는 넣지 않음.
    flags: dict[str, str] = field(default_factory=dict)
    detect_confidence: float = 0.0
    # 목록형 서식(어류 종명/개체수 등)의 표 데이터
    table_rows: list[dict] = field(default_factory=list)

    @property
    def record_key(self) -> str:
        """교정/중복 판정용 안정 키 (R11): 파일+보코드+서식."""
        ident = self.structure_code or self.structure_name or "no-id"
        return f"{self.source_file}::{ident}::{self.form_type}"

    @property
    def misaligned_fields(self) -> list[str]:
        """정렬 어긋남 의심 필드(위험) — 라벨 자체를 못 찾음."""
        return [k for k, v in self.flags.items() if v == ANCHOR_NOT_FOUND]

    @property
    def field_completeness(self) -> float:
        total = len(self.values) + len(self.flags)
        if total == 0:
            return 0.0
        return round(len(self.values) / total, 2)


def map_block(block: FormBlock, source_file: str) -> Record:
    rec = Record(
        source_file=source_file,
        form_type=block.form_type,
        structure_name=block.structure_name,
        structure_code=block.structure_code,
        river_name=block.river_name,
        detect_confidence=block.confidence,
    )
    # 어류(D)는 목록형 — 전용 추출기 사용
    if block.form_type == FORM_D:
        rec.values.update(extract_identity(block.table))
        rec.table_rows = extract_species(block.table)
        return rec

    schema = SCHEMAS.get(block.form_type)
    if not schema:
        return rec  # 아직 미지원 서식(E 등)은 식별 정보만
    for spec in schema:
        result = apply_spec(block.table, spec)
        if result.status == OK:
            rec.values[result.name] = result.value
        else:
            # 필수 필드만 플래그(선택 필드가 비어도 위험 아님)
            if spec.required or result.status == ANCHOR_NOT_FOUND:
                rec.flags[result.name] = result.status
            if result.value:
                rec.values[result.name] = result.value
    return rec
