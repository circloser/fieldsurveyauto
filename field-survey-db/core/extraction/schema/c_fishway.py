"""C: 어도 현장 조사표 스키마.

레이아웃(샘플 table[2]) 기준:
  행정구역 = 라벨 아래, 식별/기관 = 라벨 오른쪽,
  어도 제원 = 라벨 아래 숫자, 어도유형/물흐름 = √ 선택.
"""
from core.extraction.schema.spec import FieldSpec as F

SCHEMA_C = [
    # 행정구역
    F("시도", "below", "시,도"),
    F("시군구", "below", "시,군,구"),
    F("읍면동", "below", "읍,면,동"),
    F("리_지번", "below", "리"),
    # 식별/기관
    F("대권역", "right", "대권역"),
    F("하천명", "right", "하천명"),
    F("관리기관", "right", "관리 기관"),
    F("위도", "right", "위도"),
    F("경도", "right", "경도"),
    F("조사기관", "right", "조사기관"),
    F("조사자1", "right", "조사자"),
    F("조사자2", "right", "조사자", required=False),
    F("조사일시", "right", "조사일시"),
    F("기상상태", "right", "기상상태", required=False),
    # 어도 제원 — 라벨 아래 숫자
    F("어도폭", "number_below", "폭 (m)"),
    F("어도길이", "number_below", "길이 (m)"),
    F("어도높이", "number_below", "높이 (m)"),
    F("평균경사도", "number_below", "평균경사도"),
    # 어도 유형 / 물흐름 — √ 선택
    F("어도유형", "checkbox", options=[
        "계단식", "버티컬슬롯식", "아이스하버식", "도벽식", "인공하도식",
        "데닐식", "갑문식", "리프트식", "엘리베이터식", "트럭식",
    ]),
    F("물흐름", "checkbox",
      options=["유 (유량 충분)", "유 (유량 적음)", "무 (유입 없음)"], required=False),
]
