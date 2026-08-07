"""추출 정확도 채점 — 예측값을 골드(정답)와 필드 단위로 비교.

경진대회 계획 Phase 2: "정확도 몇 %"를 숫자로 만드는 채점 코어.
네트워크·모델 없이 순수 함수라 단위 테스트로 검증 가능.

비교 규칙:
  - 둘 다 숫자면 float 로 비교(오차 허용 numeric_tol).
  - 아니면 normalize_key(공백 제거·NFC) 후 문자열 일치.
  - 둘 다 비었으면(미기재) 일치로 본다.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.normalize import normalize_key

_NUM_CHARS = set("0123456789.-")

# 좌표 분/초 등: 유니코드 prime(′″)과 ASCII 따옴표('")·굽은 따옴표를 동일하게 취급
_PUNCT_MAP = str.maketrans({"′": "'", "‘": "'", "’": "'", "″": '"', "“": '"', "”": '"'})


def _canon(s: str) -> str:
    return normalize_key(s).translate(_PUNCT_MAP)


def _as_float(s: str) -> float | None:
    t = (s or "").strip()
    if not t or any(ch not in _NUM_CHARS for ch in t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def field_match(gold: str, pred: str, numeric_tol: float = 0.0) -> bool:
    g, p = (gold or "").strip(), (pred or "").strip()
    gf, pf = _as_float(g), _as_float(p)
    if gf is not None and pf is not None:
        return abs(gf - pf) <= numeric_tol
    return _canon(g) == _canon(p)


@dataclass
class ScoreResult:
    total: int
    correct: int
    mismatches: list  # [(field, gold, pred), ...]

    @property
    def accuracy(self) -> float:
        return round(self.correct / self.total, 4) if self.total else 0.0


def score_record(gold_values: dict, pred_values: dict,
                 numeric_tol: float = 0.0) -> ScoreResult:
    """골드에 있는 필드만 채점. 예측에 없으면 빈 값으로 간주."""
    total = correct = 0
    mismatches: list = []
    for k, gv in gold_values.items():
        total += 1
        pv = pred_values.get(k, "")
        if field_match(str(gv), str(pv), numeric_tol):
            correct += 1
        else:
            mismatches.append((k, gv, pv))
    return ScoreResult(total, correct, mismatches)


def aggregate(results: list[ScoreResult]) -> ScoreResult:
    """여러 레코드 결과를 전체 합산."""
    total = sum(r.total for r in results)
    correct = sum(r.correct for r in results)
    mism = [m for r in results for m in r.mismatches]
    return ScoreResult(total, correct, mism)
