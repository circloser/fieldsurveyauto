"""합쳐진 칸(여러 행에 걸친 칸) 처리 — 그 칸의 값은 걸친 행 전체에 해당하므로 행마다 반복한다.

담당자가 두 줄로 적힌 칸은 '두 사람이 공동 담당'이라는 뜻이므로 쉼표로 한 값으로 합쳐 반복한다.
한 값이 줄바꿈된 칸('건설과' / '하천팀')은 공백으로 잇는다.
"""
from pathlib import Path

import fitz

from core.pdf_reader import read_pdf
from core.table_rows import extract_table, table_rows

HEAD = ["기관명", "관리 하천명", "담당부서", "성명"]
RIVERS = ["검단천", "대사천", "대산천", "검암천"]


def _merged_form(path: Path, names: list[str], org: str = "함안군"):
    """기관명·담당부서·성명 칸이 4행에 걸쳐 합쳐진 표. names 줄 수만큼 성명 칸에 적는다."""
    doc = fitz.open()
    page = doc.new_page(width=620, height=400)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((200, 50), "담당자 현황 제출서", font=font, fontsize=16)
    x = [40, 140, 260, 400, 580]
    y = [90, 115, 140, 165, 190, 215]                         # 머리글 + 데이터 4줄
    page.draw_line((x[0], y[0]), (x[-1], y[0]), width=1)      # 표 위
    page.draw_line((x[0], y[1]), (x[-1], y[1]), width=1)      # 머리글 아래
    for yy in y[2:-1]:                                        # 데이터 줄 경계는 하천명 칸에만
        page.draw_line((x[1], yy), (x[2], yy), width=1)
    page.draw_line((x[0], y[-1]), (x[-1], y[-1]), width=1)    # 표 아래
    for xx in x:
        page.draw_line((xx, y[0]), (xx, y[-1]), width=1)
    for k, h in enumerate(HEAD):
        tw.append((x[k] + 6, y[0] + 17), h, font=font, fontsize=9)
    mid = (y[1] + y[-1]) / 2
    tw.append((x[0] + 6, mid + 3), org, font=font, fontsize=9)          # 한 줄(4행에 걸침)
    tw.append((x[2] + 6, mid + 3), "안전총괄과", font=font, fontsize=9)  # 한 줄
    for i, nm in enumerate(names):                                       # 여러 줄
        tw.append((x[3] + 6, mid - 6 + i * 16), nm, font=font, fontsize=9)
    for i, rv in enumerate(RIVERS):
        tw.append((x[1] + 6, y[1] + 17 + i * 25), rv, font=font, fontsize=9)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def _rows(path: Path):
    pg = read_pdf(str(path), ocr_scanned=False).pages[0]
    box = {"x0": 38, "y0": 88, "x1": 582, "y1": 192, "mode": "table"}
    return extract_table(pg, box, str(path))


def test_single_line_merged_cell_repeats(tmp_path):
    """값이 한 줄인 합쳐진 칸(기관명·담당부서)은 걸친 행마다 같은 값."""
    p = tmp_path / "one.pdf"
    _merged_form(p, ["김철수"])
    cols, rows = _rows(p)
    assert cols == HEAD and len(rows) == 4
    assert [r["관리 하천명"] for r in rows] == RIVERS
    assert all(r["기관명"] == "함안군" for r in rows)
    assert all(r["담당부서"] == "안전총괄과" for r in rows)
    assert all(r["성명"] == "김철수" for r in rows)          # 한 줄이면 반복


def test_multi_line_merged_cell_joins_with_comma_and_repeats(tmp_path):
    """담당자가 두 줄인 합쳐진 칸 = 공동 담당 → '김철수, 이영희' 한 값으로 모든 행에 반복."""
    p = tmp_path / "two.pdf"
    _merged_form(p, ["김철수,", "이영희"])
    cols, rows = _rows(p)
    assert len(rows) == 4
    assert all(r["성명"] == "김철수, 이영희" for r in rows)     # 쉼표 하나로 정리(',,' 아님)
    assert all(r["기관명"] == "함안군" for r in rows)


def test_wrapped_value_joins_with_space(tmp_path):
    """쉼표 없이 줄바꿈된 한 값('건설과 하천팀')은 공백으로 이어 붙인다."""
    p = tmp_path / "wrap.pdf"
    _merged_form(p, ["건설과", "하천팀"])
    _, rows = _rows(p)
    assert all(r["성명"] == "건설과 하천팀" for r in rows)


def test_email_split_across_lines_stays_one_value(tmp_path):
    """줄바꿈으로 끊긴 이메일은 한 값으로 이어 붙인다(행에 나눠 담지 않는다)."""
    from core.table_rows import _cell_lines
    from core.pdf_reader import Cell

    p = tmp_path / "mail.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((20, 40), "id4455@korea.", font=font, fontsize=9)
    tw.append((20, 56), "kr", font=font, fontsize=9)
    tw.write_text(page)
    doc.save(str(p))
    doc.close()
    pg = read_pdf(str(p), ocr_scanned=False).pages[0]
    assert _cell_lines(pg, Cell(10, 20, 290, 80)) == ["id4455@korea.kr"]


def test_synthetic_cells_without_lines_still_work():
    """줄 정보가 없는 칸(합성·이전 경로)도 예전처럼 동작한다."""
    from core.pdf_reader import Cell

    cells = [Cell(0, 0, 10, 10, "기관"), Cell(10, 0, 20, 10, "하천"),
             Cell(0, 10, 10, 30, "함안군"),                      # 2행에 걸친 칸
             Cell(10, 10, 20, 20, "검단천"), Cell(10, 20, 20, 30, "대사천")]
    cols, rows = table_rows(cells)
    assert cols == ["기관", "하천"]
    assert [r["기관"] for r in rows] == ["함안군", "함안군"]
