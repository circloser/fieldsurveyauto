"""bundle 신뢰도 플래그 + 서식별 엑셀 — 네트워크 없이 순수 로직 검증."""
from openpyxl import load_workbook

from core.bundle import _flags_for
from core.extraction.form_detector import FORM_A
from core.template.writer import write_bundle_excel


def test_flags_empty_and_format():
    vals = {"하천명": "탄천", "보길이": "20", "용도": "", "월류수심": "abc"}
    flags = _flags_for(FORM_A, vals)
    assert flags.get("용도") == "빈값"          # 빈 값
    assert flags.get("월류수심") == "형식오류"    # 숫자 필드인데 비숫자
    assert "하천명" not in flags                 # 정상 텍스트
    assert "보길이" not in flags                 # 정상 숫자


def test_bundle_excel_sheets(tmp_path):
    out = tmp_path / "b.xlsx"
    groups = [
        {"label": "인공구조물", "fields": ["하천명", "보길이"],
         "rows": [{"_파일명": "a.pdf p1", "하천명": "탄천", "보길이": "20"}]},
        {"label": "어도", "fields": ["어도폭", "어도유형"],
         "rows": [{"_파일명": "a.pdf p3", "어도폭": "3.5", "어도유형": "계단식"}]},
    ]
    write_bundle_excel(groups, str(out))
    wb = load_workbook(out)
    assert wb.sheetnames == ["인공구조물", "어도"]
    ws = wb["인공구조물"]
    assert [c.value for c in ws[1]] == ["파일명", "하천명", "보길이"]
    assert [c.value for c in ws[2]] == ["a.pdf p1", "탄천", "20"]
