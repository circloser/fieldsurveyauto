"""스캔(OCR) 글자 교정 — 자주 틀리는 모양만 바로잡는다(없는 글자를 추측해 만들지 않는다).

실제 사례(저어새 번식지 조사표 스캔): 설정(해상도·디코더·대비)을 바꿔도 거의 같은 오독이 남았다 —
  가락지 번호 TOO·NGO·3OK·F6O(T00·N60·30K·F60), 노광부리백로(노랑부리백로), 광이갈매기(괭이갈매기),
  둥지합게(둥지합계), 육주(육추), 포관(포란), 사람 이름 홍길둥(홍길동).

① 사용자 교정 사전(data/ocr_교정사전.txt, '틀린 글자 = 바른 글자' 한 줄씩) — 이름처럼 규칙으로 못 고치는 것.
   기본으로 몇 쌍(포관→포란)을 함께 쓴다.
② 가락지·개체 번호: '영문 1자 + 숫자 2자'(T00) 또는 '숫자 2자 + 영문 1자'(30K) 자리에서 숫자를 영문으로
   읽은 것(O→0, G→6, I·l→1, B→8, o→0). 같은 값에 제대로 읽힌 번호가 2개 이상일 때만(영문 낱말 보호).
③ 낱말: 사전 낱말(양식 라벨 + 조사 용어·새 이름)과 한 음절만 모양이 비슷하게 다른 한글 낱말을 사전 낱말로.
   비슷한 음절 = 자모 1개 다름, 또는 받침이 같고 자모 2개 다름(광↔랑, 괭↔광, 게↔계, 추↔주).
   2음절 낱말은 그 양식의 라벨과 자모 1개만 다를 때만 — '실제'가 라벨 '실패'로 바뀌지 않게.
"""
from __future__ import annotations

import re
from pathlib import Path

DICT_NAME = "ocr_교정사전.txt"
DEFAULT_PAIRS: list[tuple[str, str]] = [("포관", "포란")]
DICT_HEADER = (
    "# 스캔 글자 교정 사전 — 스캔(사진) 문서에서 늘 틀리게 읽히는 글자를 바로잡습니다.\n"
    "# 한 줄에 하나씩 '틀린 글자 = 바른 글자' 로 적으세요. # 으로 시작하는 줄은 설명입니다.\n"
    "# 예) 홍길둥 = 홍길동\n"
)
# 조사표·생태 조사에서 자주 나오는 낱말(3음절 이상만 비슷한 모양 교정에 쓰인다)
DEFAULT_TERMS = """
조사지역 조사시간 조사자 개체군 성장단계 단계별 개체수 가락지 위치추적기 번식준비 둥지합계 동소종 특이사항
조사사진 현장사진 번식지 관찰개체수 부착개체수
저어새 노랑부리저어새 노랑부리백로 중대백로 중백로 쇠백로 대백로 흑로 황로 왜가리 해오라기 검은댕기해오라기
괭이갈매기 재갈매기 한국재갈매기 붉은부리갈매기 검은머리갈매기 쇠제비갈매기 제비갈매기 검은머리물떼새
가마우지 민물가마우지 쇠가마우지 흰뺨검둥오리 청둥오리 물수리 뿔쇠오리 바다제비 알락꼬리마도요 마도요
흰물떼새 꼬마물떼새 개개비 섬개개비 흑비둘기 원앙 매
""".split()

_HANGUL = re.compile(r"[가-힣]+")
_CODE_OK = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z]\d{2}|\d{2}[A-Z])(?![A-Za-z0-9])")
_CODE_BAD = re.compile(r"(?<![A-Za-z0-9])(?:([A-Z])([0-9OoGIlB]{2})|([0-9OoIl]{2})([A-Z]))(?![A-Za-z0-9])")
_TO_DIGIT = str.maketrans({"O": "0", "o": "0", "G": "6", "I": "1", "l": "1", "B": "8"})


def _jamo(ch: str) -> tuple[int, int, int]:
    code = ord(ch) - 0xAC00
    return code // 588, (code // 28) % 21, code % 28


def _close(a: str, b: str) -> bool:
    """두 한글 음절의 모양이 비슷한가 — 자모 1개 다름, 또는 받침이 같고 자모 2개 다름."""
    ja, jb = _jamo(a), _jamo(b)
    d = sum(x != y for x, y in zip(ja, jb))
    return d == 1 or (d == 2 and ja[2] == jb[2])


def _one_jamo(a: str, b: str) -> bool:
    return sum(x != y for x, y in zip(_jamo(a), _jamo(b))) == 1


def fix_codes(text: str) -> str:
    """가락지 번호 자리의 O·G·I·l·B → 숫자. 제대로 읽힌 번호가 2개 이상인 값에서만."""
    if not text or len(_CODE_OK.findall(text)) < 2:
        return text

    def repl(m: re.Match) -> str:
        if m.group(1):
            return m.group(1) + m.group(2).translate(_TO_DIGIT)
        return m.group(3).translate(_TO_DIGIT) + m.group(4)

    return _CODE_BAD.sub(repl, text)


def vocab_from_labels(labels) -> set[str]:
    """양식 라벨들에서 한글 낱말(2음절 이상)만 뽑는다('둥지 현황 (둥지수)' → 둥지·현황·둥지수)."""
    out: set[str] = set()
    for lab in labels:
        for w in _HANGUL.findall(str(lab or "")):
            if len(w) >= 2:
                out.add(w)
    return out


def fix_words(text: str, labels: set[str] | None = None, terms=None) -> str:
    """사전 낱말과 한 음절만 비슷하게 다른 한글 낱말을 사전 낱말로(후보가 하나일 때만)."""
    if not text:
        return text
    labels = labels or set()
    big = {w for w in set(DEFAULT_TERMS if terms is None else terms) | labels if len(w) >= 3}
    two = {w for w in labels if len(w) == 2}
    known = big | two | set(DEFAULT_TERMS if terms is None else terms)
    by_len: dict[int, list[str]] = {}
    for w in big:
        by_len.setdefault(len(w), []).append(w)

    def candidates(span: str) -> set[str]:
        pool = by_len.get(len(span), []) if len(span) >= 3 else [w for w in two]
        found = set()
        for w in pool:
            if len(w) != len(span):
                continue
            diff = [i for i, (x, y) in enumerate(zip(span, w)) if x != y]
            if len(diff) != 1:
                continue
            i = diff[0]
            if (_close(span[i], w[i]) if len(span) >= 3 else _one_jamo(span[i], w[i])):
                found.add(w)
        return found

    def repl(m: re.Match) -> str:
        span = m.group(0)
        if len(span) < 2 or span in known:
            return span
        c = candidates(span)
        if len(c) == 1:
            return c.pop()
        # 낱말 뒤에 조사·글자가 붙은 경우('노광부리백로가') — 앞부분(3음절 이상)만 맞춰 본다
        for n in range(len(span) - 1, 2, -1):
            head = span[:n]
            if head in known:
                return span
            c = candidates(head)
            if len(c) == 1:
                return c.pop() + span[n:]
        return span

    return _HANGUL.sub(repl, text)


def load_pairs(path: Path | str | None) -> list[tuple[str, str]]:
    """교정 사전 파일의 (틀린, 바른) 쌍 — 파일이 없으면 빈 목록."""
    pairs: list[tuple[str, str]] = []
    if not path:
        return pairs
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return pairs
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        wrong, _, right = s.partition("=")
        wrong, right = wrong.strip(), right.strip()
        if wrong and wrong != right:
            pairs.append((wrong, right))
    return pairs


def apply_pairs(text: str, pairs: list[tuple[str, str]]) -> str:
    for wrong, right in sorted(pairs, key=lambda p: -len(p[0])):
        if wrong in text:
            text = text.replace(wrong, right)
    return text


def correct(text, labels: set[str] | None = None, dict_path: Path | str | None = None):
    """OCR로 읽은 값 하나 교정: 사용자 사전(+기본 쌍) → 가락지 번호 → 비슷한 모양 낱말. 문자열이 아니면 그대로."""
    if not isinstance(text, str) or not text.strip():
        return text
    out = apply_pairs(text, DEFAULT_PAIRS + load_pairs(dict_path))
    out = fix_codes(out)
    return fix_words(out, labels)


def default_dict_path() -> Path | None:
    try:
        from app import config
        return config.DATA_DIR / DICT_NAME
    except Exception:  # noqa: BLE001
        return None
