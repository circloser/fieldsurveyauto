"""숫자 값 규칙 — '숫자' 유형 추출과 엑셀 기록이 같은 규칙을 쓰도록 한 곳에 모았다.

· first_number_text: 칸 글자에서 첫 숫자만 남긴다(단위·한글 제거). '약 25.5 m' → '25.5'
· as_number:         그 값을 엑셀에 넣을 수(int/float)로. 숫자가 아니면 None(문자 그대로 둔다)
· looks_numeric_field: 항목명이 수치형인가(자동 제안에서 '숫자' 유형을 골라 줄 때)

전각 숫자(５０)도 반각으로 바꿔 처리한다 — 한글 서식·스캔 문서에 자주 섞인다.
"""
from __future__ import annotations

import re

# 전각 숫자·기호 → 반각(엑셀이 숫자로 인식하도록)
_FULLWIDTH = str.maketrans("０１２３４５６７８９．，＋－", "0123456789.,+-")

# 첫 숫자 하나: 부호, 천단위 콤마, 소수점(앞자리 없는 '.5' 포함)
_NUM_RE = re.compile(r"[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")
_STRICT_RE = re.compile(r"^[-+]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)$")


def normalize_digits(text) -> str:
    return str(text or "").translate(_FULLWIDTH)


def first_number_text(text) -> str:
    """칸 글자에서 첫 숫자만('약 25.5 m' → '25.5'). 숫자가 없으면 ''."""
    m = _NUM_RE.search(normalize_digits(text))
    if not m:
        return ""
    s = m.group(0).replace(",", "")
    if s.startswith("."):
        s = "0" + s                      # '.5' → '0.5'
    elif s.startswith(("+.", "-.")):
        s = s[0] + "0" + s[1:]
    return s.lstrip("+")


def as_number(text) -> int | float | None:
    """엑셀에 넣을 수 — 값 전체가 숫자일 때만 변환(일부만 숫자면 문자로 남긴다).

    '30' → 30, '25.5' → 25.5, '1,234' → 1234, '' → None, '없음' → None,
    '좌안 12 우안 15' → None(정보가 잘리지 않게 문자로 둔다)
    """
    s = normalize_digits(text).strip()
    if not s or not _STRICT_RE.match(s):
        return None
    s = s.replace(",", "").lstrip("+")
    if s.startswith("."):
        s = "0" + s
    elif s.startswith(("-.",)):
        s = "-0" + s[1:]
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() and "." not in s else f


def excel_cell_value(text, numeric: bool):
    """엑셀 셀 값 — 숫자 열이면 수로, 아니면 원래 값 그대로."""
    if not numeric:
        return text
    n = as_number(text)
    return text if n is None else n


# ---------- 항목명으로 수치형 판정(자동 제안) ----------

# 이름에 이런 말이 들어가면 값이 수(길이·높이 등)일 가능성이 높다
_NUM_WORDS = re.compile(
    r"길이|너비|폭|높이|깊이|수심|표고|고도|두께|지름|직경|반경|간격|연장|규모"
    r"|면적|체적|부피|경사|기울기|유속|유량|수량|강수량|적수량|수온|온도"
    r"|개소|개수|개체수|마리수|본수|비율|백분율|중량|무게|밀도|피도")
# 단위 표기((m), m, ㎡, % …)가 이름에 붙어 있으면 역시 수치형
_UNIT = re.compile(r"[(（]\s*(?:m|cm|mm|km|m2|m3|㎡|㎥|%|℃|°|ea|개|개소|초|분)\s*[)）]"
                   r"|(?:^|\s)(?:m|cm|mm|km|㎡|㎥|%|℃)\s*$")
# 숫자로 보이지만 계산 대상이 아닌 것(식별자·날짜·좌표)은 제외
_NOT_NUM = re.compile(r"번호|연락처|전화|휴대|이메일|메일|일시|일자|날짜|연도|시각"
                      r"|좌표|위도|경도|경위도|주소|코드|성명|이름|명칭|기관|유무|여부"
                      r"|종류|형식|형태|재질|재료|구분|유형|비고|특이사항|의견")


def looks_numeric_field(name: str) -> bool:
    """항목명이 수치형이면 True — 자동 제안에서 '숫자' 유형으로 잡아 준다."""
    n = str(name or "").strip()
    if not n or _NOT_NUM.search(n):
        return False
    return bool(_NUM_WORDS.search(n) or _UNIT.search(n))
