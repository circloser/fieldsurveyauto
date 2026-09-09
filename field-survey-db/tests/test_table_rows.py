"""표(여러 행) 박스 — 머리글 + 데이터 여러 줄인 표를 줄마다 한 건으로.

· 글자 PDF: 표 선으로 칸을 찾고, 세로로 합쳐진 첫 칸(기관명)은 걸친 줄마다 채운다
· 스캔본(선만 있는 이미지): 이미지에서 격자를 찾는다(같은 좌표의 단어를 넣어 확인)
· 자동 제안: 목록형 표는 '표' 박스 하나로 제안하고 그 안의 칸 박스는 만들지 않는다
· 일괄 처리: 표 박스가 든 템플릿 → 데이터 줄 수만큼 행
"""
from pathlib import Path

import fitz

from core.pdf_reader import read_pdf
from core.table_rows import (explode_rows, extract_table, image_grid, suggest_table_boxes,
                             table_rows)

HEAD = ["기관명", "관리 하천명", "담당부서", "성명", "연락처"]
DATA = [["태안천", "건설과", "정범구", "041-670-2904"],
        ["원평천", "안전재난과", "김시현", "063-540-3985"],
        ["", "", "", ""]]          # 비워 둔 줄


def _draw_table(path: Path, org: str = "태안군", title: str = "담당자 현황 제출서"):
    """기관명 칸이 세로로 합쳐진 목록형 표 + 위에 제목, 아래에 날짜."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    tw.append((200, 50), title, font=font, fontsize=16)
    x = [40, 130, 240, 350, 430, 560]
    y = [90, 115, 140, 165, 190]
    # 가로선: 머리글 아래부터는 첫 칸(기관명)을 비워 두어 합쳐진 칸 표현
    page.draw_line((x[0], y[0]), (x[-1], y[0]), width=1)
    page.draw_line((x[0], y[1]), (x[-1], y[1]), width=1)
    for yy in y[2:]:
        page.draw_line((x[1], yy), (x[-1], yy), width=1)
    for xx in x:
        page.draw_line((xx, y[0]), (xx, y[-1]), width=1)
    for k, h in enumerate(HEAD):
        tw.append((x[k] + 6, y[0] + 17), h, font=font, fontsize=9)
    tw.append((x[0] + 6, (y[1] + y[-1]) / 2 + 3), org, font=font, fontsize=9)
    for r, vals in enumerate(DATA):
        for k, v in enumerate(vals):
            if v:
                tw.append((x[k + 1] + 6, y[r + 1] + 17), v, font=font, fontsize=9)
    tw.append((300, 300), "2026년 6월 16일", font=font, fontsize=9)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def test_text_pdf_table_rows_with_merged_first_column(tmp_path):
    p = tmp_path / "list.pdf"
    _draw_table(p)
    d = read_pdf(str(p), ocr_scanned=False)
    pg = d.pages[0]
    box = {"x0": 38, "y0": 88, "x1": 562, "y1": 192, "mode": "table"}
    cols, rows = extract_table(pg, box, str(p))
    assert cols == HEAD
    assert len(rows) == 2                                  # 빈 줄은 뺀다
    assert rows[0] == {"기관명": "태안군", "관리 하천명": "태안천", "담당부서": "건설과",
                       "성명": "정범구", "연락처": "041-670-2904"}
    assert rows[1]["기관명"] == "태안군" and rows[1]["관리 하천명"] == "원평천"   # 합쳐진 칸 채움
    # 템플릿에서 정한 열 이름이 열 수와 맞으면 그 이름을 쓴다(OCR 흔들림에도 열 일치)
    cols2, rows2 = extract_table(pg, box, str(p), columns=["기관", "하천", "부서", "이름", "전화"])
    assert cols2 == ["기관", "하천", "부서", "이름", "전화"] and rows2[1]["하천"] == "원평천"


def test_image_grid_on_scanned_table(tmp_path):
    """선만 있는 이미지에서도 같은 격자를 찾는다(단어는 글자 PDF 좌표를 그대로 사용)."""
    p = tmp_path / "list.pdf"
    _draw_table(p)
    d = read_pdf(str(p), ocr_scanned=False)
    words_page = d.pages[0]
    scan = tmp_path / "scan.pdf"
    src = fitz.open(str(p))
    pix = src[0].get_pixmap(dpi=150)
    png = tmp_path / "scan.png"
    pix.save(str(png))
    out = fitz.open()
    pg = out.new_page(width=src[0].rect.width, height=src[0].rect.height)
    pg.insert_image(pg.rect, filename=str(png))
    out.save(str(scan))
    out.close()
    src.close()
    cells = image_grid(str(scan), 0, (38, 88, 562, 192))
    assert len(cells) == 5 + 4 * 4 - 3          # 머리글 5칸 + 데이터 4줄×4칸 + 합쳐진 기관명 1칸
    for c in cells:
        c.text = " ".join(w.text for w in words_page.words
                          if c.x0 <= w.cx <= c.x1 and c.y0 <= w.cy <= c.y1)
    cols, rows = table_rows(cells)
    assert cols == HEAD and len(rows) == 2 and rows[1]["기관명"] == "태안군"


def test_suggest_table_box_instead_of_cells(tmp_path):
    import app.main as app_main

    p = tmp_path / "list.pdf"
    _draw_table(p)
    d = read_pdf(str(p), ocr_scanned=False)
    tb = suggest_table_boxes(str(p), d.pages[0])
    assert len(tb) == 1 and tb[0]["mode"] == "table" and tb[0]["columns"] == HEAD
    boxes = app_main._suggest_all(d, str(p))
    tables = [b for b in boxes if b.get("mode") == "table"]
    assert len(tables) == 1
    inside = [b for b in boxes if b.get("mode") != "table" and b.get("mode") != "title"
              and 88 <= (b["y0"] + b["y1"]) / 2 <= 192]
    assert not inside                            # 표 안의 칸은 따로 박스를 만들지 않음


def test_explode_rows():
    row = {"제목": "제출서", "표": {"__table__": True, "columns": ["기관명", "성명"],
                                  "rows": [{"기관명": "A", "성명": "a"}, {"기관명": "B", "성명": "b"}]}}
    rows, fields = explode_rows(row, ["제목", "표"])
    assert fields == ["제목", "기관명", "성명"]
    assert rows == [{"제목": "제출서", "기관명": "A", "성명": "a"},
                    {"제목": "제출서", "기관명": "B", "성명": "b"}]
    # 표가 비어 있어도 한 행(기본 항목)은 남는다 / 이름 충돌은 '표_열'로
    row2 = {"기관명": "X", "표": {"__table__": True, "columns": ["기관명"], "rows": []}}
    rows2, fields2 = explode_rows(row2, ["기관명", "표"])
    assert fields2 == ["기관명", "표_기관명"] and rows2 == [{"기관명": "X", "표_기관명": ""}]


def test_apply_with_table_box_makes_row_per_line(tmp_path, monkeypatch):
    import app.main as app_main
    from fastapi.testclient import TestClient

    tpl = tmp_path / "tpl.pdf"
    _draw_table(tpl)
    d = read_pdf(str(tpl), ocr_scanned=False)
    boxes = app_main._suggest_all(d, str(tpl))
    store = type("S", (), {"list_names": lambda self: ["제출서"],
                           "get": lambda self, n: {"name": "제출서", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    inp = tmp_path / "in.pdf"
    _draw_table(inp, org="김제시")
    client = TestClient(app_main.app)
    with inp.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__",
                              "auto_classify": "1"},
                        files=[("files", ("in.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    rows = app_main._PDF_APPLY["rows"]
    assert len(rows) == 2                                  # 데이터 줄마다 한 행
    assert [x["관리 하천명"] for x in rows] == ["태안천", "원평천"]
    assert all(x["기관명"] == "김제시" for x in rows)
    gs = app_main._PDF_APPLY["groups"]
    g = gs[0] if isinstance(gs, list) else next(iter(gs.values()))
    assert "관리 하천명" in g["fields"] and "표" not in g["fields"]   # 표 열이 엑셀 열이 된다
