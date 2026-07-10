"""스키마 필드 정의(FieldSpec)와 값 해석 로직.

전략(kind):
  right         : 라벨 오른쪽 셀 값
  below         : 라벨 아래 셀 값
  number_right  : 오른쪽 셀에서 숫자만
  number_below  : 아래 셀에서 숫자만
  checkbox      : 옵션들 중 √ 선택된 것
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.extraction import checkbox
from core.parsers.base import Cell, Table

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
# 값 셀에 이런 안내문 표시가 섞여 있으면 숫자를 신뢰하지 않고 플래그 처리
_NOTE_MARKERS = ("※", "붙임", "참고", "방법", "기재", "지침")

# 값 해석 상태
OK = "ok"
EMPTY = "empty"                    # 라벨은 찾았으나 값이 비어있음(미기재)
ANCHOR_NOT_FOUND = "anchor_missing"  # 라벨 자체를 못 찾음(정렬 어긋남 의심 → 위험)


@dataclass
class FieldSpec:
    name: str                     # 출력 필드명(엑셀 열)
    kind: str
    label: str = ""
    options: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class FieldResult:
    name: str
    value: str
    status: str

    @property
    def is_flagged(self) -> bool:
        return self.status != OK


def _resolve_label_cell(table: Table, label: str) -> Cell | None:
    c = table.find_label(label)
    if c is not None:
        return c
    return table.find_label_contains(label)


def _first_number(text: str) -> str:
    text = text or ""
    # 안내문이 섞인 셀이면 숫자를 신뢰하지 않음(조용히 틀리느니 비워서 플래그)
    if any(marker in text for marker in _NOTE_MARKERS):
        return ""
    m = _NUM_RE.search(text)
    return m.group(0) if m else ""


def apply_spec(table: Table, spec: FieldSpec) -> FieldResult:
    if spec.kind == "checkbox":
        value, found_any = checkbox.select(table, spec.options)
        if not found_any:
            return FieldResult(spec.name, "", ANCHOR_NOT_FOUND)
        if not value:
            return FieldResult(spec.name, "", EMPTY)
        return FieldResult(spec.name, value, OK)

    label_cell = _resolve_label_cell(table, spec.label)
    if label_cell is None:
        return FieldResult(spec.name, "", ANCHOR_NOT_FOUND)

    if spec.kind in ("right", "number_right"):
        adj = table.right_of(label_cell)
    elif spec.kind in ("below", "number_below"):
        adj = table.below(label_cell)
    else:
        adj = None

    raw = adj.text if adj else ""
    if spec.kind.startswith("number"):
        raw = _first_number(raw)

    status = OK if raw.strip() else EMPTY
    return FieldResult(spec.name, raw.strip(), status)
