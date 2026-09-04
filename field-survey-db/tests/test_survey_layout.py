"""설문지 인식 — 실제 설문지에서 나온 레이아웃 변형들.

· 가로 쪽 2단(좌·우) 배치 → 단을 나눠 왼쪽 → 오른쪽 순서로 읽는다
· 번호 없는 인적사항 표('성 별 ① 남 ② 여', 이름이 선택지 아래·위 줄에 따로 있는 칸)
· 하위 문항('3-1.'), 안내문 속 번호 언급('④번을 선택한 경우만') 오인 방지
· 번호 접두어('문1.'), 점 빠진 번호('6 시설은…'), 번호 건너뜀('7' 없이 '8.') 재동기화
· 쪽을 넘어 번호가 이어지는 설문(1~4 → 5~8)은 응답자 한 명 = 엑셀 한 행으로 합친다
· 척도표(리커트) 머리글은 '1점 2점…'처럼 점수 토큰뿐인 줄만 — 선택지 줄('② 1회 ③ 2회')은 아님
"""
from pathlib import Path

import fitz

from core.pdf_reader import read_pdf
from core.survey import (extract_survey, is_survey_page, merge_survey_rows, parse_survey,
                         survey_row, survey_span, survey_title)


def _write(doc, page, lines):
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    for x, y, t, sz in lines:
        tw.append((x, y), t, font=font, fontsize=sz)
    tw.write_text(page)


def _two_col_survey(path: Path):
    """1쪽(가로, 2단): 왼쪽 인적사항 표 + 문항 1~2, 오른쪽 3(3-1)~4 / 2쪽(세로): 5~8."""
    doc = fitz.open()
    p1 = doc.new_page(width=842, height=595)
    left = [
        (60, 50, "이용자 만족도 조사", 16),
        (40, 80, "<<통계 처리를 위한 질문입니다>>", 9),
        (40, 100, "성 별   ① 남   ② 여", 9),
        (40, 120, "① 10대  ② 20대  ③ 30대", 9),
        (40, 135, "연 령   ④ 40대  ⑤ 50대 이상", 9),
        (40, 160, "최근1년간", 9),
        (40, 175, "① 첫방문  ② 2회  ③ 3회 이상", 9),
        (40, 190, "방문횟수", 9),
        (40, 220, "1. 방문 목적은 무엇입니까?", 9),
        (40, 240, "① 관람   ② 교육   ③ 기타(   )", 9),
        (40, 270, "2. 전시에 만족하십니까?", 9),
        (40, 290, "① 매우 만족  ② 만족  ③ 보통  ④ 불만족", 9),
        (40, 320, "→ 2페이지로 이동", 9),
        (200, 560, "- 1 -", 9),
    ]
    right = [
        (460, 100, "3. 직원은 친절했습니까?", 9),
        (460, 120, "① 매우 친절  ② 친절  ③ 보통  ④ 불친절", 9),
        (460, 150, "3-1.(3번에서 ④번을 선택한 경우만 답변) 불친절한 이유는", 9),
        (460, 165, "무엇입니까?", 9),
        (460, 185, "① 응대 태도  ② 설명 부족  ③ 기타", 9),
        (460, 215, "4. 다시 방문하시겠습니까?", 9),
        (460, 235, "① 예   ② 아니오", 9),
    ]
    _write(doc, p1, left + right)
    p2 = doc.new_page(width=595, height=842)
    _write(doc, p2, [
        (40, 60, "5. 안내 표지판은 알기 쉬웠습니까?", 9),
        (40, 80, "① 예   ② 아니오", 9),
        (40, 110, "6 시설은 청결했습니까?", 9),                     # 점이 빠진 번호
        (40, 130, "① 매우 그렇다  ② 그렇다  ③ 아니다", 9),
        (40, 160, "8. 개선 의견을 적어 주세요.", 9),                # 7번 누락 → 이어 붙음
        (40, 180, "없음", 9),
        (40, 220, "☆★☆ 끝까지 응답해 주셔서 감사합니다 ☆★☆", 9),
    ])
    doc.save(str(path))
    doc.close()


def test_two_column_survey_structure(tmp_path):
    p = tmp_path / "two_col.pdf"
    _two_col_survey(p)
    d = read_pdf(str(p), ocr_scanned=False)
    q1 = parse_survey(d.pages[0])
    assert [q.qid for q in q1] == ["성별", "연령", "최근1년간 방문횟수", "1", "2", "3", "3-1", "4"]
    assert [len(q.choices) for q in q1] == [2, 5, 3, 3, 4, 4, 3, 2]
    assert q1[6].text.endswith("불친절한 이유는 무엇입니까?")   # 하위 문항 질문이 다음 줄로 이어짐
    assert survey_span(q1) == (1, 4)
    assert is_survey_page(d.pages[0])

    q2 = parse_survey(d.pages[1])
    assert [q.qid for q in q2] == ["5", "6", "8"]
    assert q2[1].text == "시설은 청결했습니까?" and len(q2[1].choices) == 3
    assert q2[2].choices == [] and q2[2].free_text == ["없음"]     # 감사 인사·쪽번호는 잡음
    assert survey_span(q2) == (5, 8)

    row = survey_row(q1)
    assert list(row)[:3] == ["성별", "연령", "최근1년간 방문횟수"]
    assert any(k.startswith("3-1_") for k in row)
    assert survey_title(str(p), 0) == "이용자 만족도 조사"


def test_pages_merge_into_one_respondent_row(tmp_path):
    """문항 번호가 앞 쪽에서 이어지면(1~4 → 5~8) 두 쪽이 한 행."""
    p = tmp_path / "two_col.pdf"
    _two_col_survey(p)
    d = read_pdf(str(p), ocr_scanned=False)
    r1 = extract_survey(d.pages[0], str(p))
    r2 = extract_survey(d.pages[1], str(p))
    assert r1["_문항범위"] == (1, 4) and r2["_문항범위"] == (5, 8)
    merge_survey_rows(r1, r2, r1["_문항수"])
    keys = [k for k in r1 if not k.startswith("_")]
    assert keys[:3] == ["성별", "연령", "최근1년간 방문횟수"]
    assert any(k.startswith("8_") for k in keys) and len(keys) == 11


def test_question_prefix_and_resync(tmp_path):
    """'문1.' 접두어 번호 체계와 본문 '1.' 체계가 한 쪽에 같이 있어도 각각 이어진다."""
    p = tmp_path / "prefix.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=500, height=500)
    _write(doc, pg, [
        (40, 40, "고객 설문", 14),
        (40, 80, "문1. 귀하의 연령은?", 9), (60, 100, "① 20대  ② 30대  ③ 40대", 9),
        (40, 130, "문2. 귀하의 성별은?", 9), (60, 150, "① 남  ② 여", 9),
        (40, 190, "Ⅰ. 서비스 만족도", 11),
        (40, 220, "1. 서비스에 만족하십니까?", 9), (60, 240, "① 예  ② 아니오", 9),
        (40, 270, "2. 다시 이용하시겠습니까?", 9), (60, 290, "① 예  ② 아니오", 9),
    ])
    doc.save(str(p))
    doc.close()
    d = read_pdf(str(p), ocr_scanned=False)
    qs = parse_survey(d.pages[0])
    assert [q.qid for q in qs] == ["문1", "문2", "1", "2"]
    assert all(len(q.choices) >= 2 for q in qs)
    assert survey_span(qs) == (1, 2)
    assert survey_title(str(p), 0) == "고객 설문"       # 'Ⅰ. 서비스 만족도' 섹션 머리글은 제목이 아님


def test_likert_header_needs_score_tokens_only(tmp_path):
    """'② 1회 ③ 2회 ④ 3회…' 선택지 줄은 등간격이어도 척도표 머리글이 아니다(문항 목록으로 처리)."""
    from core.likert import parse_likert

    p = tmp_path / "not_likert.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=600, height=400)
    _write(doc, pg, [
        (40, 40, "방문 설문", 14),
        (40, 80, "1. 방문 횟수는?", 9),
        (320, 100, "① 없다  ② 1회  ③ 2회  ④ 3회  ⑤ 4회", 9),
        (40, 140, "2. 동행은?", 9),
        (60, 160, "① 혼자  ② 가족  ③ 친구", 9),
        (40, 200, "3. 만족도는?", 9),
        (60, 220, "① 예  ② 아니오", 9),
    ])
    doc.save(str(p))
    doc.close()
    d = read_pdf(str(p), ocr_scanned=False)
    assert parse_likert(d.pages[0]) is None
    assert [q.qid for q in parse_survey(d.pages[0])] == ["1", "2", "3"]


def test_designer_load_reports_survey(tmp_path):
    """디자이너 '양식 불러오기'에 설문지를 올리면 칸 박스 대신 설문 인식 정보를 돌려준다."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    p = tmp_path / "two_col.pdf"
    _two_col_survey(p)
    client = TestClient(app_main.app)
    with p.open("rb") as f:
        r = client.post("/api/pdf/load", files={"file": ("two_col.pdf", f, "application/pdf")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["survey"] and d["survey"]["pages"] == [0, 1] and d["survey"]["questions"] == 11
    assert d["boxes"] == []


def test_apply_merges_pages_and_titles_survey_sheet(tmp_path, monkeypatch):
    """4번 일괄 처리 — 2쪽짜리 설문지 1부 = 1행, 시트 이름은 설문 제목."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(app_main, "_TEMPLATES",
                        type("S", (), {"list_names": lambda self: [], "get": lambda self, n: None})())
    p = tmp_path / "two_col.pdf"
    _two_col_survey(p)
    client = TestClient(app_main.app)
    with p.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__",
                              "auto_classify": "1"},
                        files=[("files", ("two_col.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok_count"] == 1 and d["forms"] == 1
    assert d["by_form"][0]["form"] == "이용자 만족도 조사"
    row = app_main._PDF_APPLY["rows"][0]
    assert row["_파일명"].endswith("#1~2쪽")
    keys = [k for k in row if not k.startswith("_")]
    assert keys[:3] == ["성별", "연령", "최근1년간 방문횟수"] and any(k.startswith("8_") for k in keys)
