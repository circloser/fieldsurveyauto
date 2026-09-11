"""이상치 경고는 드물고 확실한 것만.

실제 사례(혼합 일괄 점검): 인공구조물 조사표 한 묶음에 정상값 경고가 21~31칸 붙었다.
원인 ① 구조물이 없는 칸의 0이 섞여 통상범위가 좁아짐 ② 1.5×IQR은 현장 수치에 좁음
③ 통상범위 하한이 음수로 표시 ④ 값이 넓게 퍼진 열에서 여러 칸이 한꺼번에 경고.
"""
from core.analysis import find_outliers


def _col(vals, f="x"):
    return [{f: str(v)} for v in vals]


def _flagged(rows):
    return [i for i, d in enumerate(find_outliers(rows)) if d]


def test_zero_heavy_column_ignores_zeros():
    assert _flagged(_col([0, 0, 0, 0, 0, 50, 0, 0])) == []                  # 0 = 해당 없음, 50은 정상
    assert _flagged(_col([0, 0, 0, 12, 14, 13, 15, 0, 400])) == [8]         # 0은 경고 안 하고 튀는 값만


def test_three_iqr_keeps_moderately_spread_values():
    assert _flagged(_col([1.2, 1.5, 1.9, 2.4, 3.1, 3.8, 5.0, 9.5])) == []   # 1.5×IQR이면 9.5가 경고됐음


def test_lower_bound_clipped_at_zero_for_non_negative_column():
    fl = find_outliers(_col([0.5, 1, 2, 3, 4, 50]))
    assert fl[5]["x"] == "이상치(통상범위 0~11.25 벗어남: 50)"


def test_many_flags_mean_spread_not_outliers():
    assert _flagged(_col([5] * 16 + [100, 110, 120, 130])) == []            # 4건(20%)이 튐 → 넓은 분포
    assert _flagged(_col([5] * 16 + [100])) == [16]                          # 한 건만 튀면 경고
