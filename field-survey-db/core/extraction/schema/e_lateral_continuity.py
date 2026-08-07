"""E: 횡적 연속성 현장 조사표 — 등급(매우우수~매우미흡)별 다중 매트릭스.

섹션: 횡단면 구조(길이) / 식생 피복(면적) / 연결 통문(개수) /
      제방 경사(제내지·제외지 비율) / 시가화·습지(면적·비율).
매트릭스를 평면 필드로 펼쳐 기존 파이프라인 그대로 사용. Vision 전용 등록.
"""
from core.extraction.schema.spec import FieldSpec as F

_GRADES = ["매우우수", "우수", "보통", "미흡", "매우미흡"]


def _by_grade(prefix: str, label_ctx: str, kind: str = "right"):
    return [F(f"{prefix}_{g}", kind, f"{label_ctx} '{g}' 등급 값", required=False) for g in _GRADES]


SCHEMA_E = [
    # 식별정보
    F("하천명", "right", "하천명"),
    F("하천코드", "right", "하천코드", required=False),
    F("조사구간명", "right", "조사구간명"),
    F("조사구간_m", "right", "조사구간(m)"),
    F("조사기관", "right", "조사기관"),
    F("조사자1", "right", "조사자명 1"),
    F("조사자2", "right", "조사자명 2", required=False),
    F("조사일", "right", "조사일"),
    # 횡단면 구조 — 등급별 길이(m)
    *_by_grade("횡단면_길이", "횡단면 구조 길이(m)"),
    # 식생 피복 비율 — 종류별 면적(㎡)
    F("식생_개방사주", "right", "식생 개방사주 면적", required=False),
    F("식생_절대습지식생", "right", "식생 절대습지식생 면적", required=False),
    F("식생_임의습지식생", "right", "식생 임의습지식생 면적", required=False),
    F("식생_양생임의육상절대육상식생", "right", "식생 양생/임의육상/절대육상식생 면적", required=False),
    F("식생_인공시설지", "right", "식생 인공시설지 면적", required=False),
    F("식생_총면적", "right", "식생 피복 총면적", required=False),
    # 연결 통문 — 등급별 개수
    *_by_grade("통문_개수", "연결 통문 개수"),
    # 제방 경사 — 등급별 비율(제내지/제외지)
    *_by_grade("제방경사_제내지", "제방 경사 제내지 비율(%)"),
    *_by_grade("제방경사_제외지", "제방 경사 제외지 비율(%)"),
    # 시가화·습지 — 유형별 면적/비율
    F("시가화습지_시가화_면적", "right", "시가화 지역 면적", required=False),
    F("시가화습지_육상_면적", "right", "육상 지역 면적", required=False),
    F("시가화습지_인공습지_면적", "right", "인공습지 지역 면적", required=False),
    F("시가화습지_자연습지_면적", "right", "자연습지 지역 면적", required=False),
    F("시가화습지_총면적", "right", "시가화·습지 총면적", required=False),
    F("시가화습지_시가화_비율", "right", "시가화 지역 비율(%)", required=False),
    F("시가화습지_육상_비율", "right", "육상 지역 비율(%)", required=False),
    F("시가화습지_인공습지_비율", "right", "인공습지 지역 비율(%)", required=False),
    F("시가화습지_자연습지_비율", "right", "자연습지 지역 비율(%)", required=False),
]
