"""템플릿 기반 엑셀 출력 — 박스 순서 = 열 순서, 파일 하나당 한 행."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill("solid", fgColor="191F28")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_CENTER = Alignment(horizontal="center", vertical="center")


def write_template_excel(rows: list[dict], fields: list[str], out_path: str) -> str:
    """rows: [{'_파일명':..., field: value, ...}], fields: 박스 순서."""
    wb = Workbook()
    ws = wb.active
    ws.title = "추출결과"
    headers = ["파일명"] + fields
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        c.alignment = _CENTER
    ws.freeze_panes = "A2"

    for row in rows:
        ws.append([row.get("_파일명", "")] + [row.get(f, "") for f in fields])

    for i, h in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(10, min(30, len(str(h)) * 2 + 4))

    wb.save(out_path)
    return out_path
