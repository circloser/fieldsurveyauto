"""A: 인공 구조물 현장 조사표 스키마.

레이아웃(샘플 table[0]) 기준:
  행정구역/제원 = 라벨 아래 값,  대권역/하천명/조사자 등 = 라벨 오른쪽 값,
  재질/용도 = √ 체크 선택.
"""
from core.extraction.schema.spec import FieldSpec as F

SCHEMA_A = [
    # 행정구역 (라벨 아래)
    F("시도", "below", "시,도"),
    F("시군구", "below", "시,군,구"),
    F("읍면동", "below", "읍,면,동"),
    F("리_지번", "below", "리"),
    # 식별/기관 (라벨 오른쪽)
    F("대권역", "right", "대권역"),
    F("하천명", "right", "하천명"),
    F("관리기관", "right", "관리 기관"),
    F("위도", "right", "위도"),
    F("경도", "right", "경도"),
    F("조사기관", "right", "조사기관"),
    F("조사자1", "right", "조사자 1"),
    F("조사자2", "right", "조사자 2", required=False),
    F("조사자3", "right", "조사자 3", required=False),
    F("조사일시", "right", "조사일시"),
    F("기상상태", "right", "기상상태", required=False),
    F("어도유무", "right", "어도유무"),
    # 제원(m) — 라벨 아래 숫자
    F("보길이", "number_below", "보 길이"),
    F("보마루폭", "number_below", "보 마루폭"),
    F("보하단폭", "number_below", "보 하단폭"),
    F("물받이길이", "number_below", "물받이 길이"),
    F("바닥보호공길이", "number_below", "바닥보호공 길이"),
    F("배사구높이", "number_below", "배사구 높이"),
    F("월류수심", "number_below", "월류수심"),
    # 재질 / 용도 — √ 선택
    F("재질", "checkbox", options=["콘크리트", "돌", "복합", "가동보"]),
    F("용도", "checkbox",
      options=["취수구 활용", "용수 직접 활용", "여가", "이동"], required=False),
]
