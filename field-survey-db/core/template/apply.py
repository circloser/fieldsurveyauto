"""템플릿 적용 — 저장된 박스 정의로 파일에서 값을 추출.

박스 mode:
  text  : 지정 칸들의 텍스트를 이어붙임 (기본)
  bold  : 굵게(bold) 표시된 텍스트만
  check : 지정 칸(옵션들) 중 √ 체크된 것만; 없으면 빈 값
"""
from __future__ import annotations

from core.normalize import has_check_mark
from core.parsers.base import ParsedDoc, Table

_MAX_RIGHT_GAP = 8


def _cell_at(table: Table, r: int, c: int):
    return table.at(int(r), int(c))


def _text_value(table: Table, cells: list[dict]) -> str:
    parts = []
    for cc in cells:
        cell = _cell_at(table, cc["r"], cc["c"])
        if cell and cell.text.strip():
            parts.append(cell.text.strip())
    return " ".join(parts)


def _bold_value(table: Table, cells: list[dict]) -> str:
    parts = []
    for cc in cells:
        cell = _cell_at(table, cc["r"], cc["c"])
        if cell and cell.bold_text.strip():
            parts.append(cell.bold_text.strip())
    return " ".join(parts)


def _is_checked(table: Table, cell) -> bool:
    """옵션 칸이 체크됐는지 — 자기 자신/오른쪽 가까이/아래 칸에 √ 가 있으면 참."""
    if has_check_mark(cell.text):
        return True
    for c in range(cell.col + 1, min(table.n_cols, cell.col + 1 + _MAX_RIGHT_GAP)):
        x = table.at(cell.row, c)
        if x and has_check_mark(x.text):
            return True
    below = table.at(cell.row + max(1, cell.row_span), cell.col)
    if below and has_check_mark(below.text):
        return True
    return False


def _check_value(table: Table, cells: list[dict]) -> str:
    """옵션 칸들 중 체크된 것의 라벨을 반환. 없으면 빈 값(#4)."""
    for cc in cells:
        cell = _cell_at(table, cc["r"], cc["c"])
        if cell and _is_checked(table, cell):
            return cell.text.strip()
    return ""


def _anchored_cell(table: Table, anchor: dict):
    """라벨 기준으로 값 칸을 찾는다. (hwpx·PDF·양식 편차에 강함)"""
    label = anchor.get("label", "")
    rel = anchor.get("relation", "right")
    lc = table.find_label(label) or table.find_label_contains(label)
    if lc is None:
        return None
    if rel == "self":
        return lc
    if rel == "below":
        return table.below(lc)
    return table.right_of(lc)


def _box_value(table: Table, box: dict) -> str:
    mode = box.get("mode", "text")
    cells = box.get("cells", [])

    # 라벨 앵커(text/bold 모드) — 켜져 있으면 우선, 못 찾으면 좌표로 폴백
    anchor = box.get("anchor")
    if anchor and box.get("use_anchor", True) and anchor.get("label") and mode in ("text", "bold"):
        cell = _anchored_cell(table, anchor)
        if cell is not None:
            return cell.bold_text.strip() if mode == "bold" else cell.text.strip()
        # 폴백: 저장된 좌표 사용

    if mode == "bold":
        return _bold_value(table, cells)
    if mode == "check":
        return _check_value(table, cells)
    return _text_value(table, cells)


def apply_template(doc: ParsedDoc, boxes: list[dict]) -> dict[str, str]:
    ordered = sorted(boxes, key=lambda b: b.get("order", 0))
    out: dict[str, str] = {}
    for b in ordered:
        ti = int(b["table"])
        if ti < 0 or ti >= len(doc.tables):
            out[b["field"]] = ""
            continue
        out[b["field"]] = _box_value(doc.tables[ti], b)
    return out


def field_order(boxes: list[dict]) -> list[str]:
    return [b["field"] for b in sorted(boxes, key=lambda b: b.get("order", 0))]
