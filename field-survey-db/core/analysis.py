"""추출 결과 분석 — 이상치(오추출 의심) 탐지. (규칙 기반, AI 불필요·테스트 가능)

경진대회 계획 #4: 제대로 추출 안 된 값이 있으면 해당 조사표에 경고.
방법(레코드 집합 = 같은 서식의 행들):
  - 숫자 열 통계 이상치: IQR(사분위) 밖의 값 → 오추출/오기 의심.
  - 좌표 범위: 위도/경도가 한국 범위를 벗어나면 오추출.
스키마에 의존하지 않고(범용 서식도 커버) 값에서 숫자 열을 자동 판별한다.
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# 한국 대략 범위(도 단위) — 위도 33~39, 경도 124~132
_LAT_RANGE = (32.0, 40.0)
_LON_RANGE = (123.0, 133.0)


def _as_float(s: str):
    t = (s or "").strip()
    if not t:
        return None
    # 단위(m, %, ㎡ 등)가 붙어도 앞 숫자를 취함
    m = _NUM_RE.match(t)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _degrees(s: str):
    """'34° 33′ 58.5″' → 34.0 (도 정수부만; 범위 점검용)."""
    m = _NUM_RE.search(s or "")
    return float(m.group()) if m else None


def _iqr_bounds(nums: list[float], k: float = 1.5):
    xs = sorted(nums)
    n = len(xs)

    def q(p):
        i = p * (n - 1)
        lo = int(i)
        frac = i - lo
        return xs[lo] + (xs[min(lo + 1, n - 1)] - xs[lo]) * frac

    q1, q3 = q(0.25), q(0.75)
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr, iqr


def find_outliers(records: list[dict], min_n: int = 4) -> list[dict]:
    """records: 같은 서식 행들의 [{field: value}]. 반환: 행별 {field: 사유}.

    - 숫자 열: 비어있지 않은 숫자가 min_n개 이상일 때 3×IQR 경계 밖 값 표시
      (IQR=0이면 중앙값 ± 여유). 드물고 확실한 것만 경고한다 —
      · 0이 30% 이상인 열은 0을 '해당 없음'(구조물·어도가 없는 칸)으로 보고 통계·표시에서 뺀다.
      · 음수가 없는 열은 하한을 0으로(통상범위 '-5~27' 같은 표시 방지).
      · 경고가 max(2, 10%)건을 넘는 열은 원래 값이 넓게 퍼진 것 — 이상치로 보지 않는다.
    - 위도/경도: 한국 범위 밖이면 표시.
    """
    out: list[dict] = [{} for _ in records]
    if not records:
        return out
    fields = list({k for r in records for k in r.keys()})

    for f in fields:
        # 좌표 범위 점검
        if f in ("위도", "경도"):
            rng = _LAT_RANGE if f == "위도" else _LON_RANGE
            for i, r in enumerate(records):
                d = _degrees(str(r.get(f, "")))
                if d is not None and not (rng[0] <= d <= rng[1]):
                    out[i][f] = f"이상치(좌표범위 밖 {d:g})"
            continue

        # 숫자 열 IQR 이상치
        pairs = [(i, _as_float(str(r.get(f, "")))) for i, r in enumerate(records)]
        nums = [(i, v) for i, v in pairs if v is not None]
        if len(nums) < min_n:
            continue
        if sum(1 for _, v in nums if v == 0) >= 0.3 * len(nums):
            nums = [(i, v) for i, v in nums if v != 0]   # 0 = 해당 없음 — 통계·경고에서 뺀다
            if len(nums) < min_n:
                continue
        vals = [v for _, v in nums]
        lo, hi, iqr = _iqr_bounds(vals, k=3.0)
        if iqr <= 0:
            # 대부분 동일값(IQR=0)인데 하나만 크게 튀는 오추출 잡기.
            # 작은 절대값(예: 0↔0.3)은 오탐하지 않도록 여유 = max(1,|중앙값|)*3.
            xs = sorted(vals)
            med = xs[len(xs) // 2]
            margin = max(1.0, abs(med)) * 3
            lo, hi = med - margin, med + margin
        if min(vals) >= 0:
            lo = max(lo, 0.0)
        hits = [(i, v) for i, v in nums if v < lo or v > hi]
        if len(hits) > max(2, 0.1 * len(nums)):
            continue   # 여러 칸이 한꺼번에 벗어남 = 원래 넓게 퍼진 열
        for i, v in hits:
            out[i][f] = f"이상치(통상범위 {lo:g}~{hi:g} 벗어남: {v:g})"
    return out


def build_analysis_prompt(groups: list[dict], max_rows: int = 40) -> str:
    """추출 결과(서식별 그룹)를 AI 종합/추세 분석용 프롬프트로. (순수 함수·테스트 가능)

    groups: [{'label', 'fields', 'rows':[{'_파일명':.., field:val}]}]
    """
    lines = [
        "다음은 현장 조사표에서 자동 추출한 데이터입니다.",
        "아래를 한국어 불릿으로 간결히 정리해 주세요(표는 다시 그리지 말 것):",
        "1) 전반 요약(건수·서식 구성)  2) 주요 수치의 분포·평균·범위  "
        "3) 눈에 띄는 추세/패턴  4) 데이터 품질(빈값·이상치·오추출 의심).",
        "",
    ]
    for g in groups:
        rows = g.get("rows", [])
        lines.append(f"## 서식: {g['label']} ({len(rows)}건)")
        lines.append("파일 | " + " | ".join(g["fields"]))
        for r in rows[:max_rows]:
            vals = [str(r.get(f, "")) for f in g["fields"]]
            lines.append(str(r.get("_파일명", "")) + " | " + " | ".join(vals))
        if len(rows) > max_rows:
            lines.append(f"...(외 {len(rows) - max_rows}건 생략)")
        lines.append("")
    return "\n".join(lines)


def analyze_records(groups: list[dict]) -> str:
    """추출 데이터 종합/추세 분석(AI 텍스트 호출). 프록시 경유(IP·설정 필요)."""
    from core import vision_extract
    return vision_extract.analyze_text(build_analysis_prompt(groups))


def merge_outlier_flags(records: list[dict], flags: list[dict]) -> int:
    """find_outliers 결과를 기존 flags(행별 {field:사유})에 병합. 반환: 추가된 경고 수.

    이미 빈값/형식오류로 잡힌 필드는 덮지 않는다(우선순위 유지).
    """
    outliers = find_outliers(records)
    added = 0
    for fl, ol in zip(flags, outliers):
        for field in ol:
            if field not in fl:
                fl[field] = "이상치"   # 화면 하이라이트용 짧은 타입(상세는 find_outliers)
                added += 1
    return added
