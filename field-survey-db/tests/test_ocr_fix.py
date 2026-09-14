"""스캔(OCR) 글자 교정 — 자주 틀리는 모양만, 확실할 때만 바로잡는다.

실제 사례(저어새 번식지 조사표 스캔, 해상도·디코더를 바꿔도 남은 오독):
가락지 번호 TOO·NGO·3OK·F6O, 노광부리백로·광이갈매기·둥지합게·육주·포관, 이름 홍길둥(홍길동).
"""
from core import ocr_fix
from core.pdf_pipeline import apply_pixel_template
from core.pdf_reader import PdfPage, Word


def test_ring_codes_fixed_only_among_real_codes():
    assert ocr_fix.fix_codes("V12, M29, 2019_K25, T96, TOO NGO, N68") == "V12, M29, 2019_K25, T96, T00 N60, N68"
    assert ocr_fix.fix_codes("가락지 확인 11마리: 30E, 3OK, F52 , M49") == "가락지 확인 11마리: 30E, 30K, F52 , M49"
    assert ocr_fix.fix_codes("F59, F6O, F61, S2o(WG)") == "F59, F60, F61, S20(WG)"
    assert ocr_fix.fix_codes("S09, S55 확인") == "S09, S55 확인"                 # 영문 S 는 번호 글자
    assert ocr_fix.fix_codes("TOO BIG") == "TOO BIG"                             # 번호가 없는 영문은 그대로


def test_similar_syllable_words_fixed_by_vocabulary():
    labels = ocr_fix.vocab_from_labels(["둥지합계", "육추", "둥지 현황 (둥지수)", "실패", "이소"])
    fix = lambda s: ocr_fix.fix_words(s, labels)  # noqa: E731
    assert fix("(본섬) 노광부리백로 31쌍 , 중백로 42쌍") == "(본섬) 노랑부리백로 31쌍 , 중백로 42쌍"
    assert fix("광이갈매기 약 4,000쌍 번식 추정") == "괭이갈매기 약 4,000쌍 번식 추정"
    assert fix("둥지합게") == "둥지합계"
    assert fix("육주 17개 , 서사면 준비 1개") == "육추 17개 , 서사면 준비 1개"        # 라벨과 자모 1개 차이
    assert fix("둥지 현화") == "둥지 현황"
    assert fix("노광부리백로가 많음") == "노랑부리백로가 많음"                        # 조사가 붙어도
    # 고치면 안 되는 것: 자모 2개 다른 2음절(실제↔실패), 사전 낱말, 비슷한 후보가 없는 낱말
    assert fix("실제 더 많을 것임") == "실제 더 많을 것임"
    assert fix("저어새 이소 둥지") == "저어새 이소 둥지"
    assert fix("인공바위에 번식중") == "인공바위에 번식중"


def test_user_dictionary_and_default_pairs(tmp_path):
    d = tmp_path / ocr_fix.DICT_NAME
    d.write_text(ocr_fix.DICT_HEADER + "홍길둥 = 홍길동\n홍길뚱=홍길동\n# 설명 줄\n잘못된줄\n", encoding="utf-8")
    assert ocr_fix.load_pairs(d) == [("홍길둥", "홍길동"), ("홍길뚱", "홍길동")]
    assert ocr_fix.correct("김철수 , 홍길둥 , 이영희", dict_path=d) == "김철수 , 홍길동 , 이영희"
    assert ocr_fix.correct("(본섬) 포관 281개", dict_path=d) == "(본섬) 포란 281개"    # 기본 쌍
    assert ocr_fix.correct("", dict_path=d) == "" and ocr_fix.correct(None) is None
    assert ocr_fix.load_pairs(tmp_path / "없음.txt") == []


def test_scanned_page_values_corrected_in_template_apply(tmp_path, monkeypatch):
    """스캔(OCR) 쪽 값만 교정 — 글자 PDF 값은 그대로(원문이 정확)."""
    d = tmp_path / ocr_fix.DICT_NAME
    d.write_text("홍길둥 = 홍길동\n", encoding="utf-8")
    monkeypatch.setattr(ocr_fix, "default_dict_path", lambda: d)
    words = [Word(150, 100, 230, 112, "홍길둥"), Word(150, 130, 300, 142, "TOO NGO, T96, N68")]
    boxes = [{"field": "조사자", "page": 0, "mode": "text", "order": 1, "x0": 140, "y0": 95, "x1": 320, "y1": 117,
              "use_anchor": False, "anchor": {"label": "조 사 자", "relation": "right"}},
             {"field": "가락지 현황", "page": 0, "mode": "text", "order": 2, "x0": 140, "y0": 125, "x1": 320, "y1": 147,
              "use_anchor": False, "anchor": None}]
    scan = PdfPage(page_no=0, width=595, height=842, words=list(words), ocr=True)
    got = apply_pixel_template([scan], boxes)
    assert got == {"조사자": "홍길동", "가락지 현황": "T00 N60, T96, N68"}
    text = PdfPage(page_no=0, width=595, height=842, words=list(words), ocr=False)
    assert apply_pixel_template([text], boxes) == {"조사자": "홍길둥", "가락지 현황": "TOO NGO, T96, N68"}


def test_corrections_api_roundtrip(tmp_path, monkeypatch):
    """설정 화면의 교정 사전 — 없으면 설명 머리말, 저장하면 파일에 쓰이고 개수가 돌아온다."""
    import app.main as app_main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(app_main.config, "DATA_DIR", tmp_path)
    client = TestClient(app_main.app)
    d = client.get("/api/ocr/corrections").json()
    assert d["text"] == ocr_fix.DICT_HEADER and d["count"] == 0 and "포관 = 포란" in d["builtin"]
    r = client.post("/api/ocr/corrections", json={"text": ocr_fix.DICT_HEADER + "홍길둥 = 홍길동"}).json()
    assert r == {"ok": True, "count": 1}
    assert (tmp_path / ocr_fix.DICT_NAME).read_text(encoding="utf-8").endswith("홍길둥 = 홍길동\n")
    assert ocr_fix.default_dict_path() == tmp_path / ocr_fix.DICT_NAME
