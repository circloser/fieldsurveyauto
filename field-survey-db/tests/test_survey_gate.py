"""설문 판정은 엄격하게 — 지침·보고서 본문을 설문으로 오인하지 않는다.

실제 사례(혼합 일괄 점검): 지침 131쪽 중 11쪽, 보고서 33쪽 중 2쪽이 설문으로 처리돼
쓸모없는 시트 6개가 생겼다. 원인은 ① 본문의 '1)', '①', '1단계:' 목록을 문항·선택지로 읽음
② 보고서 수치 표('0 5 0 0 5')가 등간격이라 척도표 머리글로 오인.
진짜 설문(박물관·병원·척도표 등)은 기존 테스트들이 계속 인식되는지 지킨다.
"""
from pathlib import Path

import fitz

from core.likert import parse_likert
from core.pdf_reader import read_pdf
from core.survey import is_survey_page, parse_survey


def _page(path: Path, lines, w=595, h=842):
    doc = fitz.open()
    page = doc.new_page(width=w, height=h)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    for x, y, t, sz in lines:
        tw.append((x, y), t, font=font, fontsize=sz)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()
    return read_pdf(str(path), ocr_scanned=False).pages[0]


def test_guideline_page_with_numbered_steps_is_not_survey(tmp_path):
    """번호 제목 + ①② 단계 목록 + 긴 설명문 — 예전 판정은 설문, 이제는 아님."""
    prose = ["조사자는 대표지점에서 구조물 하류 100 m 구간의 물흐름을 확인하고 기록한다.",
             "구간별로 나뉘어 물이 흐르는 경우에는 각 구간의 유속과 수심을 따로 측정한다.",
             "측정값은 조사표의 해당 칸에 적고 사진 번호를 함께 기재하여 대조할 수 있게 한다.",
             "어도가 있는 구조물은 입구부 중앙부 출구부로 나누어 같은 방법으로 조사한다.",
             "현장 여건상 측정이 어려운 경우 그 사유를 비고란에 구체적으로 적는다."]
    lines = [(60, 60, "Ⅱ. 종적 연속성 조사 방법", 14),
             (60, 100, "1. 조사 절차", 11), (70, 122, "① 대표지점 선정  ② 조사자 배치", 10)]
    y = 150
    for t in prose:
        lines.append((60, y, t, 10)); y += 22
    lines += [(60, y + 10, "2. 결과 정리", 11), (70, y + 32, "① 표 작성  ② 사진 첨부", 10)]
    y += 60
    for t in prose:
        lines.append((60, y, t, 10)); y += 22
    pg = _page(tmp_path / "guide.pdf", lines)
    qs = parse_survey(pg)
    assert sum(1 for q in qs if q.no is not None) >= 2 and any(q.choices for q in qs)  # 예전 판정 근거
    assert is_survey_page(pg) is False


def test_numeric_table_is_not_likert_header(tmp_path):
    """오른쪽에 등간격 숫자 열('5 6 7 8 9')이 있는 수치 표 — 척도표 머리글이 아니다."""
    lines = [(60, 60, "구조물단위 평가 결과", 14), (300, 100, "5", 10), (350, 100, "6", 10),
             (400, 100, "7", 10), (450, 100, "8", 10), (500, 100, "9", 10)]
    for i in range(4):
        lines.append((60, 130 + i * 22, f"1-{i + 1} 가곡천{i + 1}보 평가값", 10))
    pg = _page(tmp_path / "table.pdf", lines)
    assert parse_likert(pg) is None
    assert is_survey_page(pg) is False


def test_real_likert_header_still_recognized_forward_and_reversed(tmp_path):
    """'1점 … 5점'은 그대로, '5점 … 1점'(거꾸로)은 열을 뒤집어 첫 열 = 1점으로 인식."""
    def make(name, labels):
        lines = [(60, 60, "만족도 조사", 14)]
        for k, lab in enumerate(labels):
            lines.append((320 + k * 50, 100, lab, 10))
        for i in range(3):
            lines.append((60, 130 + i * 22, f"1-{i + 1} 서비스가 친절했습니까?", 10))
        return _page(tmp_path / name, lines)

    fwd = parse_likert(make("fwd.pdf", ["1점", "2점", "3점", "4점", "5점"]))
    assert fwd is not None and len(fwd.rows) == 3 and fwd.columns[0] < fwd.columns[-1]
    rev = parse_likert(make("rev.pdf", ["5점", "4점", "3점", "2점", "1점"]))
    assert rev is not None and rev.columns[0] > rev.columns[-1]   # 첫 열(1점)이 오른쪽 끝
