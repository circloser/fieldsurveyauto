"""체크(√) 감지 (R2) — 여러 옵션 중 어느 것이 선택됐는지 판정.

레이아웃 두 가지를 모두 지원:
  1) 옵션 라벨의 '오른쪽' 셀에 √  (예: 재질 콘크리트 √)
  2) 옵션 라벨의 '아래' 셀에 √      (예: 용도 취수구활용 / 아래 √)
옵션 사이 영역만 검사해 옆 옵션의 표시를 훔치지 않는다.
"""
from __future__ import annotations

from core.normalize import has_check_mark, normalize_key
from core.parsers.base import Cell, Table


def _find_option_cell(table: Table, option: str) -> Cell | None:
    """옵션 라벨 셀을 정확일치 → 부분포함 순으로 찾는다."""
    exact = table.find_label(option)
    if exact is not None:
        return exact
    return table.find_label_contains(option)


# 오른쪽으로 √ 를 찾을 최대 거리(무관한 √ 를 훔치지 않도록 제한)
_MAX_RIGHT_GAP = 8


def _has_mark_between(
    table: Table, cell: Cell, col_limit: int, option_rows: set[int]
) -> bool:
    # 옵션 셀 자신에 인라인 표시(예: '( √ )')
    if has_check_mark(cell.text):
        return True
    # 같은 행에서 옵션 오른쪽 ~ (다음 옵션 or 최대거리) 전까지
    right_limit = min(col_limit, cell.col + 1 + _MAX_RIGHT_GAP)
    for c in range(cell.col + 1, right_limit):
        x = table.at(cell.row, c)
        if x and has_check_mark(x.text):
            return True
    # 바로 아래 행 스캔 — 단, 아래 행이 '다른 옵션의 행'이면 건너뛴다.
    # (세로로 나열된 옵션에서 다음 옵션의 √ 를 훔치는 것을 방지)
    below_row = cell.row + max(1, cell.row_span)
    if below_row not in option_rows:
        for c in range(cell.col, cell.col + max(1, cell.col_span) + 1):
            x = table.at(below_row, c)
            if x and has_check_mark(x.text):
                return True
    return False


def select(table: Table, options: list[str]) -> tuple[str, bool]:
    """(선택된 옵션, 옵션을 하나라도 찾았는지) 반환.

    선택이 없으면 ('', found_any).  found_any=False 면 라벨 자체를 못 찾음(정렬 어긋남 의심).
    """
    located: list[tuple[str, Cell]] = []
    for opt in options:
        cell = _find_option_cell(table, opt)
        if cell is not None:
            located.append((opt, cell))
    if not located:
        return "", False

    # 같은 행 옵션들은 col 순으로 정렬해 영역 경계를 만든다.
    by_row: dict[int, list[tuple[str, Cell]]] = {}
    for opt, cell in located:
        by_row.setdefault(cell.row, []).append((opt, cell))
    option_rows = set(by_row.keys())

    for opt, cell in located:
        siblings = sorted(by_row[cell.row], key=lambda x: x[1].col)
        # 이 옵션 다음 형제의 col 이 경계(없으면 표 끝)
        col_limit = table.n_cols
        for _, sib in siblings:
            if sib.col > cell.col:
                col_limit = sib.col
                break
        if _has_mark_between(table, cell, col_limit, option_rows):
            return opt, True
    return "", True
