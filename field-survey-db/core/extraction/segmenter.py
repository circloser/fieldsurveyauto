"""다중 보(保) 분리 — 파싱된 문서를 서식별·보별 레코드 블록으로 나눈다.

한 파일 안에 여러 보(예: 남와리1/2/3)가 섞여 있어도 (보명칭, 보코드) 로 구분한다.
MVP: 표 하나 = 한 서식 인스턴스로 취급(주요 서식 A/B/C/D). E(횡적연속성)는
여러 표에 걸쳐 있어 후속 단계에서 확장.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.extraction.form_detector import (
    FORM_UNKNOWN,
    FORM_PHOTO,
    Detection,
    detect_form,
)
from core.parsers.base import ParsedDoc, Table

_NAME_RE = re.compile(r"\(보명칭\)\s*(.+)")
_CODE_RE = re.compile(r"\(보코드\)\s*([0-9A-Za-z\-]+)")


@dataclass
class FormBlock:
    form_type: str
    confidence: float
    table_index: int
    table: Table
    structure_name: str = ""      # 보명칭 (예: 남와리1)
    structure_code: str = ""      # 보코드 (예: 5220140009)
    river_name: str = ""          # 하천명

    def record_key(self, source_file: str) -> str:
        """교정/중복 판정용 안정 키 (R11): 파일+보코드+서식."""
        code = self.structure_code or self.structure_name or f"tbl{self.table_index}"
        return f"{source_file}::{code}::{self.form_type}"


def _extract_structure_id(table: Table) -> tuple[str, str, str]:
    """표에서 (보명칭, 보코드, 하천명)을 추출."""
    name = code = river = ""
    for c in table.cells:
        txt = c.text
        if not name:
            m = _NAME_RE.search(txt)
            if m:
                name = m.group(1).strip()
        if not code:
            m = _CODE_RE.search(txt)
            if m:
                code = m.group(1).strip()
    # 하천명: '하천명' 라벨의 오른쪽 값
    for t_label in ("하천명",):
        v = table.value_right_of(t_label)
        if v:
            river = v
            break
    return name, code, river


def segment(doc: ParsedDoc) -> list[FormBlock]:
    blocks: list[FormBlock] = []
    for i, table in enumerate(doc.tables):
        det: Detection = detect_form(table)
        if det.form_type in (FORM_UNKNOWN, FORM_PHOTO):
            # 사진/미상 표는 레코드로 만들지 않음(후속 단계에서 사진 첨부 처리)
            continue
        name, code, river = _extract_structure_id(table)
        blocks.append(
            FormBlock(
                form_type=det.form_type,
                confidence=det.confidence,
                table_index=i,
                table=table,
                structure_name=name,
                structure_code=code,
                river_name=river,
            )
        )
    return blocks
