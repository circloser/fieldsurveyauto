"""설문지(칸 없는 문서) 인식 — 문항/선택지 번호 구분, 표시 판정(타이핑·스캔 손표시)."""
from pathlib import Path

import pytest

from core.pdf_reader import read_pdf
from core.survey import extract_survey, is_survey_page, parse_survey, survey_row

FONT_TTC = r"C:\Windows\Fonts\batang.ttc"


def _typed_survey(path: Path):
    """타이핑 설문지 — 번호 표기 3종 + 표시 문자(✓ ■) + 복수응답 + 주관식."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=500, height=640)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    lines = [
        (40, 40, "생태 교육 만족도 설문", 16),
        (40, 80, "1. 귀하의 연령대는?", 11),
        (60, 100, "① 20대   ② 30대   ✓③ 40대   ④ 50대 이상", 10),
        (40, 130, "2. 교육 내용은 이해하기 쉬웠습니까?", 11),
        (60, 150, "1) 매우 그렇다  2) 그렇다  3) 보통  ■4) 아니다", 10),
        (40, 180, "3. 참여 동기를 모두 고르세요. (복수 응답)", 11),
        (60, 200, "(1) 관심  ✓(2) 업무 필요  (3) 권유  ✓(4) 기타", 10),
        (40, 230, "4. 개선 의견을 자유롭게 적어 주세요.", 11),
        (60, 250, "현장 실습 시간을 늘려 주세요", 10),
        (40, 280, "5. 다시 참여할 의향이 있습니까?", 11),
        (60, 300, "① 예   ② 아니오", 10),
    ]
    for x, y, t, sz in lines:
        tw.append((x, y), t, font=font, fontsize=sz)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def test_typed_survey_structure(tmp_path):
    """문항 번호 ≠ 선택지 번호 — 표기가 섞여도 구조를 정확히 잡는다."""
    p = tmp_path / "survey.pdf"
    _typed_survey(p)
    d = read_pdf(str(p), ocr_scanned=False)
    pg = d.pages[0]
    assert is_survey_page(pg)
    qs = parse_survey(pg)
    assert [q.no for q in qs] == [1, 2, 3, 4, 5]
    assert [len(q.choices) for q in qs] == [4, 4, 4, 0, 2]
    assert qs[0].answers == ["3:40대"]
    assert qs[1].answers == ["4:아니다"]
    assert qs[2].answers == ["2:업무 필요", "4:기타"]          # 복수응답
    assert qs[3].free_text == ["현장 실습 시간을 늘려 주세요"]  # 주관식
    assert qs[4].answers == []                                # 무응답
    row = survey_row(qs)
    k1 = next(k for k in row if k.startswith("1_"))
    k3 = next(k for k in row if k.startswith("3_"))
    assert row[k1] == "3:40대"
    assert row[k3] == "2:업무 필요;4:기타"
    assert "_이상치" not in row


def _scanned_survey(path: Path, W=1240, H=900, dpi=150):
    """스캔 설문지(글자 레이어 없음) — 손으로 ③에 동그라미, 2)에 체크, 흐린 점(애매)."""
    from PIL import Image, ImageDraw, ImageFont
    import fitz
    try:
        f_q = ImageFont.truetype(FONT_TTC, 40, index=0)
        f_c = ImageFont.truetype(FONT_TTC, 36, index=0)
    except Exception:  # noqa: BLE001
        pytest.skip("바탕 폰트 없음")
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    dr.text((100, 40), "현장 교육 만족도 설문", font=ImageFont.truetype(FONT_TTC, 60, index=0), fill="black")
    qs = [("1. 귀하의 연령대는?", ["1) 20대", "2) 30대", "3) 40대", "4) 50대"]),
          ("2. 내용은 이해하기 쉬웠습니까?", ["1) 매우 그렇다", "2) 그렇다", "3) 보통"]),
          ("3. 다시 참여하시겠습니까?", ["1) 예", "2) 아니오"])]
    y = 160
    pos = {}   # (문항, 선택지번호) → 번호 토큰 픽셀 상자
    for qi, (qt, chs) in enumerate(qs, 1):
        dr.text((100, y), qt, font=f_q, fill="black")
        x = 160
        for ci, ct in enumerate(chs, 1):
            dr.text((x, y + 70), ct, font=f_c, fill="black")
            bb = dr.textbbox((x, y + 70), ct[:2], font=f_c)   # '1)' 토큰 상자
            pos[(qi, ci)] = bb
            x += 300
        y += 200
    # 손표시: 문항1 → 3)에 동그라미 / 문항2 → 2)에 체크 / 문항3 → 1)에 아주 흐린 점(애매)
    b = pos[(1, 3)]; dr.ellipse([b[0] - 22, b[1] - 18, b[2] + 22, b[3] + 18], outline="black", width=5)
    b = pos[(2, 2)]; dr.line([(b[0] - 10, b[3] - 8), (b[0] + 12, b[3] + 14), (b[2] + 26, b[1] - 20)], fill="black", width=6)
    b = pos[(3, 1)]; dr.ellipse([b[0] - 6, b[3] + 4, b[0] + 2, b[3] + 10], fill=(120, 120, 120))
    png = path.with_suffix(".png")
    img.save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * 72 / dpi, height=H * 72 / dpi)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def ocr_ready():
    from core import ocr
    if not ocr.available():
        pytest.skip("OCR 엔진(easyocr) 없음")


def test_scanned_survey_ink_marks(tmp_path, ocr_ready):
    """스캔 설문지 — 손으로 그린 동그라미·체크를 잉크 밀도로 판정, 흐린 표시는 확인 요청."""
    p = tmp_path / "scan_survey.pdf"
    _scanned_survey(p)
    d = read_pdf(str(p), ocr_scanned=True)
    pg = d.pages[0]
    assert pg.ocr
    assert is_survey_page(pg), [w.text for w in pg.words]
    row = extract_survey(pg, pdf_path=str(p))
    k1 = next(k for k in row if k.startswith("1_"))
    k2 = next(k for k in row if k.startswith("2_"))
    k3 = next(k for k in row if k.startswith("3_"))
    assert row[k1].startswith("3:")            # 동그라미 → 3번
    assert row[k2].startswith("2:")            # 체크(OCR이 깨뜨린 번호를 순서로 복원) → 2번
    flags = row.get("_이상치", {})
    assert k1 not in flags                      # 뚜렷한 동그라미는 확인 요청 없음
    # 얇은 체크는 표시로 잡되 '확인 필요' 플래그가 붙을 수 있다(주황 표시 → 사람이 확인)
    # 흐린 점: 표시로 확정하지 않거나(빈값), 확정하더라도 '확인 필요' 플래그가 붙어야 한다
    assert row[k3] == "" or k3 in flags


def test_survey_page_goes_to_survey_sheet(tmp_path, monkeypatch):
    """4번 일괄 처리 — 템플릿과 안 맞는 설문지 페이지는 버리지 않고 설문 파서로 추출,
    설문 제목 시트에 문항별 열로 들어간다."""
    import app.main as app_main
    from fastapi.testclient import TestClient
    from tests.test_pdf_pipeline import _draw_form

    tpl = tmp_path / "tpl.pdf"
    _draw_form(tpl, [("하천명", ""), ("보길이", "")], y_top=60, title="하천 조사표")
    from core.pdf_pipeline import suggest_from_cells
    boxes = suggest_from_cells(str(tpl), 0)
    store = type("S", (), {"list_names": lambda self: ["조사표"],
                           "get": lambda self, n: {"name": "조사표", "boxes": boxes}})()
    monkeypatch.setattr(app_main, "_TEMPLATES", store)
    monkeypatch.setattr(app_main, "_tpl_pdf_path", lambda name: tpl)

    sv = tmp_path / "survey.pdf"
    _typed_survey(sv)
    client = TestClient(app_main.app)
    with sv.open("rb") as f:
        r = client.post("/api/pdf/apply",
                        data={"boxes": "[]", "sheet_name_field": "__group_title__",
                              "auto_classify": "1"},
                        files=[("files", ("survey.pdf", f, "application/pdf"))])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok_count"] == 1 and d["forms"] == 1
    assert d["by_form"][0]["form"] == "생태 교육 만족도 설문"
    assert not d.get("discarded")
    assert any(m["template"] == "설문지(자동 인식)" for m in d["match_info"])
    row = app_main._PDF_APPLY["rows"][0]
    k1 = next(k for k in row if k.startswith("1_"))
    assert row[k1] == "3:40대"
