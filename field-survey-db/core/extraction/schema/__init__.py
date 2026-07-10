"""서식별 스키마 템플릿 레지스트리.

새 서식을 추가하려면 스키마 모듈 하나 + 여기 등록만 하면 된다.
"""
from core.extraction.form_detector import FORM_A, FORM_C
from core.extraction.schema.a_artificial_structure import SCHEMA_A
from core.extraction.schema.c_fishway import SCHEMA_C

SCHEMAS = {
    FORM_A: SCHEMA_A,
    FORM_C: SCHEMA_C,
}
