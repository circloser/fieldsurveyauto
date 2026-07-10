"""서식 판별 — 표(Table) 하나가 어떤 조사표 서식인지 시그니처로 자동 분류.

제목 근접이 아니라 '표 안에 어떤 라벨이 들어있는가'로 판별하므로,
제목 줄이 쪼개지거나 순서가 바뀌어도 견고하다.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.normalize import normalize_key
from core.parsers.base import Table

# 서식 코드
FORM_A = "artificial_structure"   # 인공 구조물 현장 조사표
FORM_B = "representative_point"    # 대표지점(어도 상세)
FORM_C = "fishway"                # 어도 현장 조사표
FORM_D = "fish"                   # 어류 현장 조사표
FORM_E = "lateral_continuity"     # 횡적 연속성 현장 조사표
FORM_PHOTO = "photo"              # 현장 사진 표
FORM_UNKNOWN = "unknown"

FORM_LABELS_KO = {
    FORM_A: "인공구조물",
    FORM_B: "대표지점(어도상세)",
    FORM_C: "어도",
    FORM_D: "어류",
    FORM_E: "횡적연속성",
    FORM_PHOTO: "현장사진",
    FORM_UNKNOWN: "미상",
}

# 각 서식의 시그니처 신호(정규화 키, 공백 제거). 표 전체 텍스트에 부분포함되면 매치.
_SIGNALS: dict[str, list[str]] = {
    FORM_A: ["보길이", "보마루폭", "월류수심", "인공구조물재질", "물받이길이", "배사구높이"],
    FORM_C: ["어도상태", "평균경사도", "계단식", "데닐식", "아이스하버식", "버티컬슬롯식"],
    FORM_D: ["종명", "개체수", "전장"],
    FORM_E: ["횡단면", "제방경사", "시가화", "연결통문", "식생피복", "제내지", "제외지",
             "조사구간", "하천코드", "매우우수", "매우미흡", "통문"],
    FORM_B: ["대표지점", "형태별물리"],
    FORM_PHOTO: ["보전경", "상류방향", "하류방향", "어도전경", "제외지전경"],
}

# 판별 우선순위(가장 특이한 것부터)
_ORDER = [FORM_A, FORM_C, FORM_D, FORM_E, FORM_B, FORM_PHOTO]


@dataclass
class Detection:
    form_type: str
    confidence: float
    matched: list[str]

    @property
    def label_ko(self) -> str:
        return FORM_LABELS_KO.get(self.form_type, "미상")


def _table_blob(table: Table) -> str:
    """표 안 모든 셀 텍스트를 정규화 키로 이어붙인 하나의 문자열."""
    return "".join(normalize_key(c.text) for c in table.cells)


def detect_form(table: Table) -> Detection:
    blob = _table_blob(table)
    best = Detection(FORM_UNKNOWN, 0.0, [])
    for form in _ORDER:
        signals = _SIGNALS[form]
        matched = [s for s in signals if s in blob]
        if not matched:
            continue
        conf = min(1.0, len(matched) / max(2, len(signals) * 0.5))
        # 우선순위 순회이므로, 2개 이상 매치되면 즉시 확정(특이 신호 우선)
        if len(matched) >= 2:
            return Detection(form, round(conf, 2), matched)
        # 1개만 매치면 후보로만 보관
        if conf > best.confidence:
            best = Detection(form, round(conf, 2), matched)
    return best
