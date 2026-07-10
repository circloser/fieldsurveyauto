"""보고서 생성 검증 — {필드명} 채우기, 숫자 변환, 수식 보존, 요약+개별 시트."""
from openpyxl import Workbook, load_workbook

from core.report import (
    build_report_workbook,
    list_placeholders,
    read_grid,
    save_with_edits,
)


def _make_template(path):
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "조사 보고서"
    ws["A3"] = "하천명"; ws["B3"] = "{하천명}"
    ws["A4"] = "보길이"; ws["B4"] = "{보 길이}"
    ws["A5"] = "두배"; ws["B5"] = "=B4*2"
    ws["A6"] = "메모"; ws["B6"] = "조사: {조사일시}"
    wb.save(path)


def test_list_placeholders(tmp_path):
    tpl = tmp_path / "tpl.xlsx"
    _make_template(tpl)
    ph = list_placeholders(str(tpl))
    assert set(ph) == {"하천명", "보 길이", "조사일시"}


def test_read_grid_and_edit(tmp_path):
    tpl = tmp_path / "tpl.xlsx"
    _make_template(tpl)
    grid = read_grid(str(tpl))
    assert grid["nrows"] >= 6 and grid["ncols"] >= 2
    # B3 = row3,col2 = {하천명}
    assert grid["cells"][2][1] == "{하천명}"
    assert grid["cells"][4][1] == "=B4*2"  # 수식 보존
    # 편집: B3 값 바꾸고 새 셀 추가
    out = tmp_path / "edited.xlsx"
    save_with_edits(str(tpl), {"3,2": "{가곡천대체}", "7,1": "추가"}, str(out))
    g2 = read_grid(str(out))
    assert g2["cells"][2][1] == "{가곡천대체}"
    assert g2["cells"][6][0] == "추가"


def test_build_report(tmp_path):
    tpl = tmp_path / "tpl.xlsx"
    _make_template(tpl)
    recs = [
        {"_파일명": "a.pdf", "하천명": "해남천", "보 길이": "30", "조사일시": "2026-06-17"},
        {"_파일명": "b.pdf", "하천명": "가곡천", "보 길이": "25", "조사일시": "2026-06-29"},
    ]
    out = tmp_path / "out.xlsx"
    build_report_workbook(str(tpl), recs, ["하천명", "보 길이"], str(out))
    wb = load_workbook(out)
    # 요약 + 파일별 보고서 시트
    assert "요약(DB)" in wb.sheetnames
    assert "a.pdf" in wb.sheetnames and "b.pdf" in wb.sheetnames
    # 값 채움 + 숫자 변환 + 수식 보존
    a = wb["a.pdf"]
    assert a["B3"].value == "해남천"
    assert a["B4"].value == 30 and isinstance(a["B4"].value, int)
    assert a["B5"].value == "=B4*2"
    assert a["B6"].value == "조사: 2026-06-17"
    # 요약표
    s = wb["요약(DB)"]
    assert [c.value for c in s[1]] == ["파일명", "하천명", "보 길이"]
