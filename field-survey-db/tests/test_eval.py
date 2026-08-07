"""eval_score.py — 필드 채점 로직 단위 테스트(네트워크 불필요)."""
from core.eval_score import aggregate, field_match, score_record


def test_text_match_ignores_spaces():
    assert field_match("전남 해남군", "전남해남군")
    assert field_match("해남천", "해남천")
    assert not field_match("해남천", "남해천")


def test_numeric_match_and_format():
    assert field_match("30", "30.0")          # 정수/실수 표기차 허용
    assert field_match("2.5", "2.5")
    assert not field_match("30", "31")


def test_numeric_tolerance():
    assert field_match("34.5", "34.6", numeric_tol=0.2)
    assert not field_match("34.5", "34.9", numeric_tol=0.2)


def test_both_empty_is_match():
    assert field_match("", "")


def test_coordinate_prime_vs_ascii_quotes_match():
    # 유니코드 prime(′″)과 ASCII 따옴표('")는 좌표에서 동일 값으로 취급
    assert field_match("37° 20′ 09.3″", "37° 20' 09.3\"")
    assert field_match("127° 06′ 45.9″", "127° 06' 45.9\"")


def test_score_record_counts_and_mismatches():
    gold = {"시도": "전남", "하천명": "해남천", "보길이": "30"}
    pred = {"시도": "전남", "하천명": "남해천", "보길이": "30.0"}
    r = score_record(gold, pred)
    assert r.total == 3
    assert r.correct == 2                      # 시도 O, 하천명 X, 보길이 O
    assert r.accuracy == round(2 / 3, 4)
    assert [m[0] for m in r.mismatches] == ["하천명"]


def test_missing_prediction_field_counts_as_wrong():
    r = score_record({"위도": "34.5"}, {})
    assert r.total == 1 and r.correct == 0


def test_aggregate():
    a = score_record({"a": "1", "b": "2"}, {"a": "1", "b": "2"})
    b = score_record({"c": "3", "d": "4"}, {"c": "3", "d": "9"})
    agg = aggregate([a, b])
    assert agg.total == 4 and agg.correct == 3
