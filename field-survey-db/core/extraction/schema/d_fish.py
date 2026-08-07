"""D: 어류 현장 조사표 — 식별정보 + 어종 목록(종명·개체수).

목록형이지만 평면 파이프라인을 유지하기 위해 어종 목록을 한 필드('어종목록')에
"종명:개체수" 쉼표 나열로 담는다(예: "붕어:2, 잉어:2, 피라미:32").
※ 규칙기반은 core.extraction.fish.extract_species(표 기반)를 계속 사용하고,
   이 스키마는 Vision 전용 레지스트리에만 등록한다(SCHEMAS 불변).
"""
from core.extraction.schema.spec import FieldSpec as F

SCHEMA_D = [
    F("대권역", "right", "대권역"),
    F("하천명", "right", "하천명"),
    F("보명칭", "right", "보/어도 명칭", required=False),
    F("관리기관", "right", "관리 기관"),
    F("조사기관", "right", "조사기관"),
    F("조사자1", "right", "조사자명 1"),
    F("조사자2", "right", "조사자명 2", required=False),
    F("조사자3", "right", "조사자명 3", required=False),
    F("위도", "right", "위도"),
    F("경도", "right", "경도"),
    F("조사일시", "right", "조사일시"),
    F("기상상태", "right", "기상상태", required=False),
    # 어종 목록: '종명:개체수'를 쉼표로 나열 (표의 No.1~30 채워진 행만)
    F("어종목록", "self", "종명·개체수 목록(예: 붕어:2, 잉어:2, 피라미:32)"),
]
