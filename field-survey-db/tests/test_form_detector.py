"""Phase 2 검증 — 서식 판별 + 다중 보 분리 (AC-2, AC-4)."""
from core.extraction.form_detector import (
    FORM_A,
    FORM_C,
    FORM_D,
    FORM_E,
    detect_form,
)
from core.extraction.segmenter import segment
from core.parsers.hwpx_parser import parse_hwpx


def test_detect_known_tables(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    # 샘플 표 순서(Phase 2 탐색으로 확인): 0=A, 2=C, 3=D, 12=E
    assert detect_form(doc.tables[0]).form_type == FORM_A
    assert detect_form(doc.tables[2]).form_type == FORM_C
    assert detect_form(doc.tables[3]).form_type == FORM_D
    assert detect_form(doc.tables[12]).form_type == FORM_E


def test_detection_confidence(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    for idx in (0, 2, 3):
        det = detect_form(doc.tables[idx])
        assert det.confidence >= 0.5, (idx, det)
        assert len(det.matched) >= 2


def test_segment_extracts_structures(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    blocks = segment(doc)
    # 최소한 A, C, D 블록이 잡혀야 한다.
    types = {b.form_type for b in blocks}
    assert {FORM_A, FORM_C, FORM_D}.issubset(types)


def test_structure_codes_recognized(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    blocks = segment(doc)
    codes = {b.structure_code for b in blocks if b.structure_code}
    # 샘플에 남와리1/2/3 → 보코드 ...9/...8/...7 이 등장
    assert any(c.endswith("9") for c in codes), codes
    # 서로 다른 보가 별도 레코드로 분리되어야 한다(AC-2)
    assert len(codes) >= 2, codes


def test_stable_record_key(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    blocks = segment(doc)
    keys = [b.record_key("sample.hwpx") for b in blocks]
    # 키는 비어있지 않고 서로 구분되어야 한다.
    assert all(keys)
    assert len(set(keys)) == len(keys)
