"""Phase 3 검증 — A/C 스키마 매핑 + 체크(√) 감지 골든값 (AC-6)."""
import pytest

from core.extraction.form_detector import FORM_A, FORM_C
from core.extraction.mapper import map_block
from core.extraction.segmenter import segment
from core.parsers.hwpx_parser import parse_hwpx


@pytest.fixture(scope="module")
def records(request):
    fixture = request.path.parent / "fixtures" / "sample.hwpx"
    if not fixture.exists():
        pytest.skip("샘플 없음")
    doc = parse_hwpx(str(fixture))
    recs = {}
    for b in segment(doc):
        rec = map_block(b, "sample.hwpx")
        recs.setdefault(b.form_type, rec)  # 각 서식 첫 레코드
    return recs


def test_form_a_scalar_values(records):
    a = records[FORM_A]
    assert a.structure_code == "5220140009"
    assert a.values["하천명"] == "해남천"
    assert a.values["대권역"] == "영산강권역"
    assert a.values["보길이"] == "30"
    assert a.values["보마루폭"] == "2.5"
    assert a.values["월류수심"] == "0.3"


def test_form_a_checkbox(records):
    a = records[FORM_A]
    assert a.values["재질"] == "콘크리트"
    assert a.values["용도"] == "취수구 활용"


def test_form_a_flags_polluted_cell(records):
    """안내문이 겹친 셀은 틀린 숫자 대신 플래그되어야 한다(정직한 실패)."""
    a = records[FORM_A]
    assert "바닥보호공길이" in a.flags
    assert a.values.get("바닥보호공길이", "") != "1"


def test_form_c_scalar_values(records):
    c = records[FORM_C]
    assert c.structure_code == "5220140007"
    assert c.values["어도폭"] == "3.7"
    assert c.values["어도길이"] == "27.9"
    assert c.values["어도높이"] == "0.8"
    assert c.values["평균경사도"] == "3"


def test_form_c_checkbox_vertical_options(records):
    """세로로 나열된 어도 유형에서 올바른 선택을 집어야 한다."""
    c = records[FORM_C]
    assert c.values["어도유형"] == "아이스하버식"
    assert c.values["물흐름"] == "유 (유량 적음)"


def test_completeness_high(records):
    """A/C 주요 필드 완성도가 충분히 높아야 한다."""
    assert records[FORM_A].field_completeness >= 0.9
    assert records[FORM_C].field_completeness >= 0.9
