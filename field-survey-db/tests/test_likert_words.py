"""말 머리글 척도표 설문 — '매우 그렇다 | 그렇다 | 보통이다 | 그렇지 않다 | 매우 그렇지 않다'.

실제 사례(혼합 일괄 점검): 장학금 만족도 설문(2쪽, 글자 PDF)은 머리글이 숫자가 아니라 말이고,
번호가 '1.1', 구역(1. ○○장학금)마다 머리글이 반복되며, '개선·보완 의견' 글 칸 행과
전체 폭 '기타 의견' 문항이 섞여 있어 설문으로 인식되지 않고 버려졌다.
"""
from pathlib import Path

import fitz

from core.likert import extract_likert, parse_likert
from core.pdf_reader import read_pdf
from core.survey import is_survey_page

LABELS = ["매우 그렇다", "그렇다", "보통이다", "그렇지 않다", "매우 그렇지 않다"]
STACK = [["매우", "그렇다"], ["그렇다"], ["보통이다"], ["그렇지", "않다"], ["매우 그렇지", "않다"]]
FONT = fitz.Font("cjk")


def _put(tw, x, y, text, size=9, center=False):
    if center:
        x -= FONT.text_length(text, fontsize=size) / 2
    tw.append((x, y), text, font=FONT, fontsize=size)


def _header(tw, y, cols):
    """칸 안에서 두 줄로 쌓인 말 머리글(한 줄짜리 열은 가운데 줄)."""
    _put(tw, 150, y + 4, "내 용", 8)
    for x, words in zip(cols, STACK):
        if len(words) == 1:
            _put(tw, x, y + 4, words[0], 8, center=True)
        else:
            _put(tw, x, y, words[0], 8, center=True)
            _put(tw, x, y + 8, words[1], 8, center=True)


def _scholarship(path: Path):
    cols1 = [290, 345, 400, 455, 510]
    cols2 = [c - 6 for c in cols1]                     # 구역마다 열 위치가 조금씩 다름
    doc = fitz.open()
    # ---- 1쪽: 응답자 칸 + 구역 1·2
    page = doc.new_page(width=595, height=842)
    tw = fitz.TextWriter(page.rect)
    _put(tw, 150, 60, "장학금 지원 만족도 조사 설문지", 18)
    xs, ys = [60, 130, 260, 330, 460], [90, 115]
    for yy in ys:
        page.draw_line((xs[0], yy), (xs[-1], yy), width=0.8)
    for xx in xs:
        page.draw_line((xx, ys[0]), (xx, ys[1]), width=0.8)
    for x, t in zip(xs, ["학과명", "생명과학과", "성명", "홍길동"]):
        _put(tw, x + 6, 107, t)
    _put(tw, 60, 150, "1. 생활안정 장학금", 10)
    _header(tw, 168, cols1)
    _put(tw, 62, 200, "1.1")
    _put(tw, 85, 200, "생활안정에 도움이 되었다.")
    _put(tw, cols1[1], 200, "○", center=True)
    _put(tw, 62, 225, "1.2")
    _put(tw, 85, 225, "학업 시간을 늘리는 데")
    _put(tw, 88, 239, "도움이 되었다.")
    _put(tw, cols1[0], 232, "V", center=True)
    _put(tw, 62, 265, "1.3")
    _put(tw, 85, 265, "개선, 보완, 추가 등에 대한 의견")
    _put(tw, 280, 265, "금액 증액 필요")
    _put(tw, 60, 295, "2. 학습동아리 장학금", 10)
    _header(tw, 313, cols2)
    _put(tw, 62, 345, "2.1")
    _put(tw, 85, 345, "구성원 모두 적극 참여하였다.")
    _put(tw, cols2[4], 345, "●", center=True)
    _put(tw, 62, 370, "2.2")
    _put(tw, 85, 370, "활동 결과에 만족한다.")
    tw.write_text(page)
    # ---- 2쪽: 구역 3 + 전체 폭 기타 의견 + 안내문
    page = doc.new_page(width=595, height=842)
    tw = fitz.TextWriter(page.rect)
    _put(tw, 60, 60, "3. 연구조교 장학금", 10)
    _header(tw, 78, cols1)
    _put(tw, 62, 110, "3.1")
    _put(tw, 85, 110, "진학 결심에 도움이 되었다.")
    _put(tw, cols1[2], 110, "●", center=True)
    _put(tw, 62, 135, "3.2")
    _put(tw, 85, 135, "연구 역량이 향상되었다.")
    _put(tw, cols1[3], 135, "○", center=True)
    _put(tw, 60, 180, "4. 기타 의견을 자유롭게 기술해주세요", 10)
    _put(tw, 70, 205, "행정 절차 간소화 바랍니다")
    _put(tw, 66, 400, "※ 작성대상: 1~3번은 수혜 대상자 작성", 8)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def _val(row: dict, qid: str):
    return next(v for k, v in row.items() if k.startswith(qid + "_"))


def test_word_header_sections_rows_and_opinion_rows(tmp_path):
    p = tmp_path / "scholar.pdf"
    _scholarship(p)
    d = read_pdf(str(p), ocr_scanned=False)
    assert all(is_survey_page(pg, str(p)) for pg in d.pages)
    g = parse_likert(d.pages[0])
    assert g is not None and g.labels == LABELS
    assert [r.qid for r in g.rows] == ["1.1", "1.2", "1.3", "2.1", "2.2"]   # 구역 제목·반복 머리글은 행 아님
    assert g.rows[1].text == "학업 시간을 늘리는 데 도움이 되었다."           # 다음 줄로 이어진 질문
    assert [r.free for r in g.rows] == [False, False, True, False, False]
    assert g.rows[3].cols[0] < g.rows[0].cols[0]                             # 구역마다 자기 머리글 열


def test_word_header_answers_opinions_and_respondent(tmp_path):
    p = tmp_path / "scholar.pdf"
    _scholarship(p)
    d = read_pdf(str(p), ocr_scanned=False)
    r0 = extract_likert(d.pages[0], str(p))
    r1 = extract_likert(d.pages[1], str(p))
    assert r0["학과명"] == "생명과학과" and r0["성명"] == "홍길동"            # 머리글 위 응답자 칸
    assert _val(r0, "1.1") == "그렇다" and _val(r0, "1.2") == "매우 그렇다"   # 칸 안 표시 글자 → 열 이름
    assert _val(r0, "1.3") == "금액 증액 필요"                                 # 칸 안 의견
    assert _val(r0, "2.1") == "매우 그렇지 않다" and _val(r0, "2.2") == ""
    assert _val(r1, "3.1") == "보통이다" and _val(r1, "3.2") == "그렇지 않다"
    assert _val(r1, "4") == "행정 절차 간소화 바랍니다"                        # ※ 안내문은 답이 아님
    assert "_이상치" not in r0 and "_이상치" not in r1
    assert r0["_문항범위"] == (1, 2) and r1["_문항범위"] == (3, 4)             # 쪽 병합 근거


def test_grade_header_of_field_form_is_not_survey(tmp_path):
    """조사표의 등급 머리글(매우우수·우수·보통·미흡)은 말 머리글 설문이 아니다."""
    p = tmp_path / "grade.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    tw = fitz.TextWriter(page.rect)
    for x, t in zip([290, 345, 400, 455], ["매우우수", "우수", "보통", "미흡"]):
        _put(tw, x, 100, t, 8, center=True)
    for i in range(3):
        _put(tw, 62, 130 + i * 25, f"1.{i + 1}")
        _put(tw, 85, 130 + i * 25, f"구조물 {i + 1} 상태")
    tw.write_text(page)
    doc.save(str(p))
    doc.close()
    pg = read_pdf(str(p), ocr_scanned=False).pages[0]
    assert parse_likert(pg) is None and is_survey_page(pg, str(p)) is False


def test_word_header_survey_pages_merge_into_one_row(tmp_path, monkeypatch):
    """4번 일괄 처리 — 2쪽 설문이 설문 제목 시트에 한 응답자 한 행으로 들어간다."""
    import app.main as app_main
    from fastapi.testclient import TestClient
    from core.pdf_pipeline import suggest_from_cells
    from tests.test_pdf_pipeline import _draw_form

    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    boxes = suggest_from_cells(str(tpl), 0)
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    sv = tmp_path / "scholar.pdf"
    _scholarship(sv)
    client = TestClient(app_main.app)
    with sv.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__", "auto_classify": "1"},
                        files=[("files", ("scholar.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok_count"] == 1 and d["forms"] == 1 and not d.get("discarded")
    assert d["by_form"][0]["form"] == "장학금 지원 만족도 조사 설문지"
    row = app_main._PDF_APPLY["rows"][0]
    assert row["학과명"] == "생명과학과"
    assert _val(row, "2.1") == "매우 그렇지 않다" and _val(row, "4") == "행정 절차 간소화 바랍니다"
