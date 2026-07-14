"""템플릿 기반 엑셀 출력 — 박스 순서 = 열 순서, 파일 하나당 한 행.

sheet_name_field 를 주면 요약 시트 뒤에 대상지(행)마다 개별 시트(항목|값)를 만든다.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core.report import _sheet_name, record_sheet_base

_HEADER_FILL = PatternFill("solid", fgColor="191F28")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_CENTER = Alignment(horizontal="center", vertical="center")


def write_template_excel(rows: list[dict], fields: list[str], out_path: str,
                         sheet_name_field: str | None = None,
                         max_sheets: int = 300) -> str:
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

    # 대상지별 개별 시트(항목|값 세로표) — 시트 이름 = 선택한 추출값
    if sheet_name_field:
        for n, row in enumerate(rows):
            if n >= max_sheets:
                break
            s = wb.create_sheet(_sheet_name(record_sheet_base(row, sheet_name_field),
                                            set(wb.sheetnames)))
            s.append(["항목", "값"])
            for col in (1, 2):
                c = s.cell(row=1, column=col)
                c.fill = _HEADER_FILL
                c.font = _HEADER_FONT
                c.alignment = _CENTER
            s.append(["파일명", row.get("_파일명", "")])
            for f in fields:
                s.append([f, row.get(f, "")])
            s.column_dimensions["A"].width = 22
            s.column_dimensions["B"].width = 34
            s.freeze_panes = "A2"

    wb.save(out_path)
    return out_path
