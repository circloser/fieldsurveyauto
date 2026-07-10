"""어류(D) 서식 전용 추출 — 식별정보 + 종명/개체수 목록.

어류표는 좌/우 2개의 (No./종명/개체수/비고) 열그룹을 가진다.
종명 헤더 셀을 찾아 그 아래 행에서 종명·개체수를 읽는다.
"""
from __future__ import annotations

from core.normalize import normalize_key
from core.parsers.base import Table

# 식별 스칼라(라벨 오른쪽 값)
_ID_FIELDS = [
    ("대권역", "대권역"),
    ("하천명", "하천명"),
    ("관리기관", "관리 기관"),
    ("위도", "위도"),
    ("경도", "경도"),
    ("조사기관", "조사기관"),
    ("조사자1", "조사자명 1"),
    ("조사자2", "조사자명 2"),
    ("조사자3", "조사자명 3"),
    ("조사일시", "조사일시"),
]


def extract_identity(table: Table) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, label in _ID_FIELDS:
        v = table.value_right_of(label)
        if v:
            out[name] = v
    return out


def _is_number(text: str) -> bool:
    return text.strip().isdigit()


def extract_species(table: Table) -> list[dict]:
    """종명/개체수 목록을 추출. 좌/우 열그룹 모두 처리.

    경계: 'No.' 열이 숫자인 행만 종 목록으로 인정(번호가 끊기면 목록 종료).
    이렇게 하면 목록 아래의 안내문/특이사항을 긁지 않는다.
    """
    species: list[dict] = []
    name_headers = [c for c in table.cells if c.key == "종명"]
    for header in name_headers:
        name_col = header.col
        # 같은 행에서 종명 오른쪽의 '개체수' 열, 왼쪽 가장 가까운 'No.' 열을 찾는다.
        count_col = None
        no_col = None
        for c in table.cells:
            if c.row != header.row:
                continue
            if c.col > header.col and c.key == "개체수" and count_col is None:
                count_col = c.col
            if c.col < header.col and c.key in ("no.", "no"):
                no_col = c.col  # 가장 오른쪽(가까운) No.
        if no_col is None:
            no_col = max(0, name_col - 1)

        r = header.row + 1
        started = False
        while r < table.n_rows:
            no_cell = table.at(r, no_col)
            no_val = no_cell.text.strip() if no_cell else ""
            if _is_number(no_val):
                started = True
                name_cell = table.at(r, name_col)
                name_val = name_cell.text.strip() if name_cell else ""
                # 헤더 텍스트가 같은 셀에 병합돼 들어온 경우 방지
                if name_val and name_val != "종명":
                    count_val = ""
                    if count_col is not None:
                        cc = table.at(r, count_col)
                        count_val = cc.text.strip() if cc else ""
                    species.append({"종명": name_val, "개체수": count_val})
            elif started:
                break  # 번호가 끊기면 목록 종료
            r += 1
    return species
