"""템플릿 박스의 '라벨(앵커)'이 믿을 만한지 템플릿 자신의 양식 PDF 위에서 확인한다.

추출 첫 단계는 박스에 라벨이 있으면 입력 문서에서 그 라벨 칸을 찾아 옆(오른쪽·아래) 칸을 읽는다.
줄이 추가되거나 위치가 밀려도 값을 따라가는 '유기적 추출'이다. 그런데 라벨과 방향이 박스와
맞지 않게 저장돼 있으면(예: 열 머리글 '매우우수'를 라벨로, 방향은 '오른쪽') 값 대신 옆 머리글
'우수'를 읽는다. 박스 위치는 정확해도 값이 조용히 틀린다.

그래서 템플릿 양식 PDF에서 라벨을 따라갔을 때 도착한 칸이 그 박스 자리가 아니면
anchor_ok=False 로 표시해 좌표 기준으로 읽게 한다. 확인할 근거가 없으면(표 선이 없는 양식,
라벨이 표 칸이 아님) 표시하지 않아 기존 동작을 그대로 둔다.
"""
from __future__ import annotations

import os

from core.pdf_pipeline import _cell_anchor_value
from core.pdf_reader import detect_cells

_CELLS: dict[tuple[str, float, int], list] = {}   # (양식 PDF, 수정시각, 쪽) → 표 칸들


def _cells(pdf, page) -> list:
    try:
        key = (str(pdf), os.path.getmtime(str(pdf)), int(page))
    except OSError:
        return []
    if key not in _CELLS:
        try:
            _CELLS[key] = detect_cells(str(pdf), int(page))
        except Exception:  # noqa: BLE001
            _CELLS[key] = []
    return _CELLS[key]


def validate_anchors(boxes: list[dict], tpl_pdf) -> int:
    """박스마다 라벨을 확인해 틀린 앵커에 anchor_ok=False 를 채운다. 반환: 믿지 않게 된 박스 수."""
    if not tpl_pdf or not os.path.exists(str(tpl_pdf)):
        return 0
    bad = 0
    for b in boxes:
        a = b.get("anchor") or {}
        if not a.get("label") or b.get("mode", "text") not in ("text", "number", "bold"):
            continue
        cells = _cells(tpl_pdf, b.get("page", 0))
        if not cells:
            continue                      # 표 선이 없는 양식 — 확인할 수 없어 그대로 둔다
        r = _cell_anchor_value(cells, b, return_cell=True)
        if r is None:
            continue                      # 라벨이 표 칸이 아님 — 확인할 수 없어 그대로 둔다
        _, cell = r
        cx = (float(b["x0"]) + float(b["x1"])) / 2
        cy = (float(b["y0"]) + float(b["y1"])) / 2
        ok = cell.x0 - 3 <= cx <= cell.x1 + 3 and cell.y0 - 3 <= cy <= cell.y1 + 3
        b["anchor_ok"] = ok
        bad += 0 if ok else 1
    return bad
