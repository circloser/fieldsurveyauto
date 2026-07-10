"""통합 표 모델 — hwpx/pdf/hwp 파서가 공통으로 만들어내는 자료구조.

핵심 설계(Architect 지적 반영):
- Cell 은 원본(raw_text)과 정규화(text) 텍스트를 모두 보관 → 검수 화면에서 원문 대조 가능(AC-10).
- 병합셀(rowspan/colspan)을 논리 좌표맵으로 펼쳐서, "라벨 오른쪽/아래 값 찾기"를
  원본 자식 순서가 아니라 좌표 기하로 처리 → 병합/정렬 흔들림에 강함.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.normalize import normalize, normalize_key


@dataclass
class Cell:
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    raw_text: str = ""          # 원본(줄바꿈 등 최소 보존)
    text: str = ""              # 정규화된 표시 텍스트
    bold_text: str = ""         # 굵게(bold) 표시된 텍스트만 추출
    width: int = 0              # 칸 너비(HWPUNIT, 병합 폭 전체)
    height: int = 0             # 칸 높이(HWPUNIT, 병합 높이 전체)

    @property
    def key(self) -> str:
        """비교/매칭용 키(공백 제거)."""
        return normalize_key(self.text)

    def is_empty(self) -> bool:
        return self.text.strip() == ""


@dataclass
class Table:
    """하나의 표. cells 는 파싱된 원본 셀 목록, grid 는 좌표→셀 논리 맵."""
    cells: list[Cell] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    _grid: dict[tuple[int, int], Cell] = field(default_factory=dict, repr=False)

    def build_grid(self) -> None:
        """병합셀을 펼쳐서 (row,col)->Cell 좌표맵을 만든다."""
        self._grid.clear()
        max_r = max_c = 0
        for c in self.cells:
            for dr in range(max(1, c.row_span)):
                for dc in range(max(1, c.col_span)):
                    self._grid[(c.row + dr, c.col + dc)] = c
            max_r = max(max_r, c.row + max(1, c.row_span))
            max_c = max(max_c, c.col + max(1, c.col_span))
        self.n_rows = max_r
        self.n_cols = max_c

    def at(self, row: int, col: int) -> Cell | None:
        return self._grid.get((row, col))

    def find_label(self, label: str) -> Cell | None:
        """정규화 키가 일치(부분포함 아님)하는 첫 셀을 반환."""
        want = normalize_key(label)
        for c in self.cells:
            if c.key == want:
                return c
        return None

    def find_label_contains(self, needle: str) -> Cell | None:
        """정규화 키에 needle 이 포함된 첫 셀."""
        want = normalize_key(needle)
        for c in self.cells:
            if want and want in c.key:
                return c
        return None

    def right_of(self, cell: Cell) -> Cell | None:
        """셀의 오른쪽(병합 폭 다음 열) 논리 셀."""
        return self.at(cell.row, cell.col + max(1, cell.col_span))

    def below(self, cell: Cell) -> Cell | None:
        """셀의 아래(병합 높이 다음 행) 논리 셀."""
        return self.at(cell.row + max(1, cell.row_span), cell.col)

    def value_right_of(self, label: str) -> str:
        c = self.find_label(label)
        if c is None:
            return ""
        r = self.right_of(c)
        return r.text if r else ""

    def value_below(self, label: str) -> str:
        c = self.find_label(label)
        if c is None:
            return ""
        b = self.below(c)
        return b.text if b else ""


@dataclass
class ParsedDoc:
    """한 파일의 파싱 결과."""
    source_path: str = ""
    file_type: str = ""                       # hwpx | pdf | hwp
    tables: list[Table] = field(default_factory=list)
    full_text: str = ""                       # 정규화된 전체 본문(앵커 탐색용)
    ok: bool = True
    error: str = ""

    def all_cells(self):
        for t in self.tables:
            yield from t.cells
