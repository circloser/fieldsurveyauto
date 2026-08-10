"""analysis.find_outliers / merge_outlier_flags — 이상치 탐지(규칙, 네트워크 불필요)."""
from core.analysis import find_outliers, merge_outlier_flags


def test_numeric_iqr_outlier():
    recs = [{"보길이": v} for v in ["20", "22", "21", "19", "20", "500"]]
    out = find_outliers(recs)
    assert out[5].get("보길이", "").startswith("이상치")   # 500 튐
    assert all("보길이" not in out[i] for i in range(5))    # 정상값은 무플래그


def test_no_outlier_when_uniformish():
    recs = [{"보마루폭": v} for v in ["0.5", "0.5", "2", "2.5", "0.6"]]
    out = find_outliers(recs)
    assert all(not o for o in out)


def test_too_few_records_skips_numeric():
    recs = [{"보길이": v} for v in ["20", "999"]]   # 2개(<min_n) → 판단 보류
    out = find_outliers(recs)
    assert all(not o for o in out)


def test_coordinate_range():
    recs = [
        {"위도": "34° 33′ 58.5″", "경도": "126° 35′ 15.2″"},   # 정상
        {"위도": "88° 00′ 00″", "경도": "126° 00′ 00″"},        # 위도 범위 밖
        {"위도": "35° 00′ 00″", "경도": "200° 00′ 00″"},        # 경도 범위 밖
    ]
    out = find_outliers(recs)
    assert not out[0]
    assert "위도" in out[1] and "경도" not in out[1]
    assert "경도" in out[2] and "위도" not in out[2]


def test_merge_keeps_existing_and_adds_short_tag():
    recs = [{"보길이": v} for v in ["20", "20", "21", "19", "500"]]
    flags = [{}, {}, {}, {}, {"보길이": "형식오류"}]   # 마지막은 이미 형식오류
    # 마지막(500)은 이미 형식오류라 덮지 않음 → 추가는 없음
    added = merge_outlier_flags(recs, flags)
    assert flags[4]["보길이"] == "형식오류"   # 기존 우선
    # 새 케이스: 기존 플래그 없으면 '이상치' 태그 추가
    recs2 = [{"x": v} for v in ["1", "1", "1", "1", "999"]]
    fl2 = [{}, {}, {}, {}, {}]
    n = merge_outlier_flags(recs2, fl2)
    assert n == 1 and fl2[4]["x"] == "이상치"
