"""칸에 인쇄된 안내 괄호가 값에 섞이지 않게 — '(보명칭) 탄천_신20' → '탄천_신20'.

실제 사례(혼합 일괄 점검): 조사표 보명칭·보코드 칸에 '(보명칭)' '(보코드)'가 인쇄돼 있어
219칸의 값 앞에 안내 글자가 붙거나, 빈 칸이 '(보코드)'로 채워졌다.
"""
from core.pdf_pipeline import _strip_caption, apply_pixel_template, suggest_from_cells
from core.pdf_reader import read_pdf


def test_strip_caption_only_when_it_names_the_box():
    b = {"field": "P2_보명칭", "anchor": {"label": "보명칭"}}
    assert _strip_caption("(보명칭) 탄천_신20", b) == "탄천_신20"
    assert _strip_caption("탄천_신20 ( 보명칭 )", b) == "탄천_신20"
    assert _strip_caption("(보코드)", {"field": "보코드"}) == ""
    assert _strip_caption("(보 코드) HN-01", {"field": "보코드_2"}) == "HN-01"
    assert _strip_caption("(주)한국수자원공사", {"field": "시공사"}) == "(주)한국수자원공사"
    assert _strip_caption("가곡천(상류)", b) == "가곡천(상류)"
    assert _strip_caption(None, b) is None
    assert _strip_caption({"rows": []}, b) == {"rows": []}


def test_caption_removed_when_template_applied(tmp_path):
    from tests.test_pdf_pipeline import _draw_form

    base = tmp_path / "base.pdf"
    _draw_form(base, [("보명칭", "해남천_보1"), ("보코드", "HN001"), ("시공사", "대한건설")], y_top=60)
    boxes = suggest_from_cells(str(base), 0)
    assert {"보명칭", "보코드", "시공사"} <= {b["field"] for b in boxes}

    inp = tmp_path / "in.pdf"
    _draw_form(inp, [("보명칭", "(보명칭) 탄천_신20"), ("보코드", "(보코드)"), ("시공사", "(주)한국")], y_top=60)
    d = read_pdf(str(inp), ocr_scanned=False)
    got = apply_pixel_template(d.pages, boxes, pdf_path=str(inp))
    assert got["보명칭"] == "탄천_신20" and got["보코드"] == "" and got["시공사"] == "(주)한국"
