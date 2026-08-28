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


def write_bundle_excel(groups: list[dict], out_path: str) -> str:
    """서식별 시트로 나눠 저장(AI 번들 추출용).

    groups: [{"label": 시트이름, "fields": [열...], "rows": [{'_파일명':.., field:val}]}]
    """
    wb = Workbook()
    wb.remove(wb.active)  # 기본 시트 제거 후 서식별로 생성
    used: set[str] = set()
    for g in groups:
        title = _sheet_name(g.get("label") or "추출결과", used)
        used.add(title)
        ws = wb.create_sheet(title)
        headers = ["파일명"] + list(g["fields"])
        ws.append(headers)
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=1, column=col)
            c.fill = _HEADER_FILL
            c.font = _HEADER_FONT
            c.alignment = _CENTER
        ws.freeze_panes = "A2"
        for row in g["rows"]:
            ws.append([row.get("_파일명", "")] + [row.get(f, "") for f in g["fields"]])
        for i, h in enumerate(headers, start=1):
            ws.column_dimensions[get_column_letter(i)].width = max(10, min(30, len(str(h)) * 2 + 4))
    if not wb.sheetnames:  # 추출 결과가 하나도 없을 때
        wb.create_sheet("추출결과")
    wb.save(out_path)
    return out_path


def _style_header(ws, ncols: int) -> None:
    for col in range(1, ncols + 1):
        c = ws.cell(row=1, column=col)
        c.fill = _HEADER_FILL
        c.font = _HEADER_FONT
        c.alignment = _CENTER
    ws.freeze_panes = "A2"


def write_template_excel(rows: list[dict], fields: list[str], out_path: str,
                         sheet_name_field: str | None = None,
                         group_field: str | None = None,
                         max_sheets: int = 300) -> str:
    """rows: [{'_파일명':..., field: value, ...}], fields: 박스 순서.

    group_field: 그 필드 값(예: 제목)이 같은 행끼리 묶어 값 이름의 시트로 분류.
    sheet_name_field: 행(대상지)마다 개별 시트(항목|값). 둘은 배타적으로 쓰인다.
    """
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

    # 제목(양식)별 분류 시트 — 같은 값의 행들을 묶어 그 값 이름의 시트로
    if group_field:
        groups: dict[str, list[dict]] = {}
        for row in rows:
            key = str(row.get(group_field, "") or "").strip() or "(제목없음)"
            groups.setdefault(key, []).append(row)
        for gname, grows in list(groups.items())[:max_sheets]:
            s = wb.create_sheet(_sheet_name(gname, set(wb.sheetnames)))
            s.append(headers)
            _style_header(s, len(headers))
            for row in grows:
                s.append([row.get("_파일명", "")] + [row.get(f, "") for f in fields])
            for i, h in enumerate(headers, start=1):
                s.column_dimensions[get_column_letter(i)].width = max(10, min(30, len(str(h)) * 2 + 4))

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
