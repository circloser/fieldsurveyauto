"""Phase 1 검증 — hwpx 파서가 실제 샘플에서 표/값을 정확히 뽑는지 (AC-3)."""
from core.parsers.hwpx_parser import parse_hwpx


def test_parses_without_error(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    assert doc.ok, doc.error
    assert doc.file_type == "hwpx"


def test_extracts_tables(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    # 샘플에는 14개 표가 있다.
    assert len(doc.tables) == 14
    # 그리드가 병합을 반영해 세워져야 한다.
    assert all(t.n_rows > 0 and t.n_cols > 0 for t in doc.tables)


def test_form_anchors_in_full_text(sample_hwpx):
    doc = parse_hwpx(str(sample_hwpx))
    flat = doc.full_text.replace(" ", "")
    for anchor in [
        "인공구조물현장조사표",
        "어도현장조사표",
        "어류현장조사표",
        "횡적연속성현장조사표",
    ]:
        assert anchor in flat, f"앵커 누락: {anchor}"


def test_known_values_present(sample_hwpx):
    """골든값 — 손으로 확인한 샘플 값들이 그대로 추출되어야 한다."""
    doc = parse_hwpx(str(sample_hwpx))
    values = {c.text for t in doc.tables for c in t.cells}
    for probe in ["3.7", "27.9", "0.8", "콘크리트", "아이스하버식", "붕어", "피라미"]:
        assert probe in values, f"값 누락: {probe}"


def test_cell_carries_raw_and_normalized(sample_hwpx):
    """검수 화면(AC-10)을 위해 원본 텍스트도 보존되어야 한다."""
    doc = parse_hwpx(str(sample_hwpx))
    non_empty = [c for t in doc.tables for c in t.cells if c.text]
    assert non_empty, "비어있지 않은 셀이 있어야 한다"
    # 최소한 하나는 raw_text 를 갖는다.
    assert any(c.raw_text for c in non_empty)


def test_merged_grid_lookup(sample_hwpx):
    """병합셀 좌표맵이 동작하는지 — 라벨 옆/아래 값 조회 스모크 테스트."""
    doc = parse_hwpx(str(sample_hwpx))
    # '하천명' 라벨을 가진 셀이 어느 표엔가 있어야 하고, 그 옆이 조회 가능해야 한다.
    found = False
    for t in doc.tables:
        cell = t.find_label("하천명")
        if cell is not None:
            right = t.right_of(cell)
            below = t.below(cell)
            assert right is not None or below is not None
            found = True
            break
    assert found, "'하천명' 라벨 셀을 찾지 못했다"
