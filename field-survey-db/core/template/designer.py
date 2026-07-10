"""템플릿 디자이너 백엔드 — 양식을 격자로 내보내고, 추출 박스를 자동 제안.

칸(셀) 기반: 양식의 표 구조를 그대로 화면에 재현하고, 사용자가 칸을 골라
'박스'(=추출 항목)를 정의한다. 시스템이 라벨→값 칸을 감지해 미리 제안한다.
"""
from __future__ import annotations

import re

from core.extraction.form_detector import FORM_LABELS_KO, detect_form
from core.normalize import normalize_key
from core.parsers.base import ParsedDoc, Table

# 값처럼 보이는(라벨이 아닌) 셀 판정용
_LABEL_MAX_LEN = 18
_DIGIT_START = re.compile(r"^\s*[\d(]")

# HWPUNIT(1/7200 inch) → 화면 px (96dpi): value/75
_HWPUNIT_PX = 75.0


def _col_widths(t: Table) -> list[float]:
    """칸 크기(cellSz)로 열별 너비(px)를 추정."""
    acc = [0.0] * max(1, t.n_cols)
    cnt = [0] * max(1, t.n_cols)
    for c in t.cells:
        if c.width <= 0:
            continue
        per = c.width / max(1, c.col_span)
        for col in range(c.col, min(t.n_cols, c.col + max(1, c.col_span))):
            acc[col] += per
            cnt[col] += 1
    widths = []
    known = [acc[i] / cnt[i] for i in range(len(acc)) if cnt[i]]
    avg = (sum(known) / len(known)) if known else 4000.0
    for i in range(len(acc)):
        raw = acc[i] / cnt[i] if cnt[i] else avg
        widths.append(round(max(18.0, raw / _HWPUNIT_PX), 1))
    return widths


def _row_heights(t: Table) -> list[float]:
    acc = [0.0] * max(1, t.n_rows)
    cnt = [0] * max(1, t.n_rows)
    for c in t.cells:
        if c.height <= 0:
            continue
        per = c.height / max(1, c.row_span)
        for row in range(c.row, min(t.n_rows, c.row + max(1, c.row_span))):
            acc[row] += per
            cnt[row] += 1
    known = [acc[i] / cnt[i] for i in range(len(acc)) if cnt[i]]
    avg = (sum(known) / len(known)) if known else 2000.0
    heights = []
    for i in range(len(acc)):
        raw = acc[i] / cnt[i] if cnt[i] else avg
        heights.append(round(max(20.0, raw / _HWPUNIT_PX), 1))
    return heights


def grid_dto(doc: ParsedDoc) -> list[dict]:
    """각 표를 화면 재현용 격자로 직렬화(실제 비율 + 서식 라벨 포함)."""
    tables = []
    for ti, t in enumerate(doc.tables):
        cells = [
            {
                "r": c.row, "c": c.col,
                "rs": max(1, c.row_span), "cs": max(1, c.col_span),
                "text": c.text,
                "bold": c.bold_text if c.bold_text and c.bold_text != c.text else "",
            }
            for c in t.cells
        ]
        det = detect_form(t)
        tables.append({
            "table": ti,
            "n_rows": t.n_rows,
            "n_cols": t.n_cols,
            "cells": cells,
            "col_widths": _col_widths(t),
            "row_heights": _row_heights(t),
            "form": det.form_type,
            "form_label": FORM_LABELS_KO.get(det.form_type, "기타"),
        })
    return tables


def _looks_like_label(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > _LABEL_MAX_LEN:
        return False
    if _DIGIT_START.match(t):
        return False
    # 한글이 포함되고, 안내문 표시가 없는 짧은 라벨
    if not re.search(r"[가-힣]", t):
        return False
    if any(m in t for m in ("※", "붙임", "참고", "√", "■", "□")):
        return False
    return True


def _looks_like_value(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if any(m in t for m in ("※", "붙임", "참고")):
        return False
    return True


def suggest_boxes(doc: ParsedDoc) -> list[dict]:
    """라벨→값(오른쪽 우선, 없으면 아래) 칸을 감지해 박스를 제안."""
    boxes: list[dict] = []
    seen_values: set[tuple[int, int, int]] = set()
    order = 0
    def nonempty(x):
        return x is not None and x.text.strip() and _looks_like_value(x.text)

    def clean_value(x):
        # 명백한 값: 비어있지 않고, 라벨스럽지 않고, 지나치게 길지 않음(병합 안내문 배제)
        return nonempty(x) and not _looks_like_label(x.text) and len(x.text) < 22

    for ti, t in enumerate(doc.tables):
        for cell in t.cells:
            if not _looks_like_label(cell.text):
                continue
            right, below = t.right_of(cell), t.below(cell)
            left = t.at(cell.row, cell.col - 1) if cell.col > 0 else None
            left_is_label = left is not None and _looks_like_label(left.text)

            # 관계 판정(경험 규칙, 사용자가 앵커 칩으로 수정 가능):
            # 1) 오른쪽이 명백한 값(라벨 아님)      → right  (위도→34°)
            # 2) 아래가 명백한 값(라벨 아님)        → below  (제원 보길이→30)
            # 3) 왼쪽도 라벨 = 가로 라벨그룹 헤더   → below  (행정구역 시도→전남)
            # 4) 그 외 오른쪽에 무언가 있으면       → right  (하천명→해남천)
            relation = neighbor = None
            if clean_value(right):
                relation, neighbor = "right", right
            elif clean_value(below):
                relation, neighbor = "below", below
            elif left_is_label and nonempty(below):
                relation, neighbor = "below", below
            elif nonempty(right):
                relation, neighbor = "right", right
            elif nonempty(below):
                relation, neighbor = "below", below
            if neighbor is None:
                continue

            sig = (ti, neighbor.row, neighbor.col)
            if sig in seen_values:
                continue
            seen_values.add(sig)
            order += 1
            boxes.append({
                "order": order,
                "field": cell.text.strip(),
                "table": ti,
                "cells": [{"r": neighbor.row, "c": neighbor.col}],
                "label_cell": {"r": cell.row, "c": cell.col},
                # 라벨 기준 앵커(hwpx·PDF·양식 편차 대응)
                "anchor": {"label": cell.text.strip(), "relation": relation},
                "use_anchor": True,
                "suggested": True,
            })
    return boxes
