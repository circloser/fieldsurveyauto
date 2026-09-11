"""작성 예시 양식을 올려도 박스 이름은 라벨 기준.

실제 사례(저어새 번식지 현지조사표 2024 작성 예시, 한글→PDF): 칸마다 박스를 만들면서 왼쪽 칸 글자를
이름으로 붙여, 값 칸 뒤의 라벨 칸이 '매도'(예시 값), 개체수 칸이 '다수'·'관찰 못함'·'90'으로 이름 붙고,
라벨 칸까지 박스가 돼 열 44개 중 절반이 라벨 글자만 담은 쓸모없는 열이 됐다.
"""
from pathlib import Path

import fitz
import numpy as np

CELLS = [
    (30, 78, 101, 96, ["조사지역"]), (101, 78, 176, 96, ["매도"]), (176, 78, 222, 96, ["날짜"]),
    (222, 78, 346, 96, ["2024. 05. 9."]), (346, 78, 406, 96, ["조사시간"]), (406, 78, 566, 96, ["17:20 ~ 17:40"]),
    (30, 96, 101, 113, ["조 사 자"]), (101, 96, 566, 113, ["김철수, 이영희, 박민수"]),
    (30, 113, 101, 171, ["개체군 현황"]), (101, 113, 150, 142, ["성장단계"]),
    (150, 113, 234, 142, ["■알", "(Egg)"]), (234, 113, 317, 142, ["□새끼", "(Chick)"]),
    (317, 113, 400, 142, ["□유조", "(Juvenile)"]), (400, 113, 483, 142, ["■성조", "(Adult)"]),
    (483, 113, 566, 142, ["□미성숙", "(Immature)"]),
    (101, 142, 150, 171, ["단계별", "개체수"]), (150, 142, 234, 171, ["다수"]), (234, 142, 317, 171, ["관찰 못함"]),
    (317, 142, 400, 171, []), (400, 142, 483, 171, ["90"]), (483, 142, 566, 171, []),
    (30, 171, 101, 286, ["가락지 현황"]), (101, 171, 566, 286, ["E02, K79, M08, V25"]),
    (30, 286, 101, 391, ["둥지 현황"]), (101, 286, 165, 303, ["번식준비"]), (165, 286, 270, 303, ["3"]),
    (270, 286, 328, 391, ["동소종 현황"]), (328, 286, 566, 391, ["한국재갈매기 약 16둥지"]),
    (101, 303, 165, 321, ["포란"]), (165, 303, 270, 321, ["61"]), (101, 321, 165, 338, ["육추"]),
    (165, 321, 270, 338, ["0"]), (101, 338, 165, 356, ["이소"]), (165, 338, 270, 356, ["0"]),
    (101, 356, 165, 373, ["실패"]), (165, 356, 270, 373, ["6"]), (101, 373, 165, 391, ["둥지합계"]),
    (165, 373, 270, 391, ["70"]),
]
PHOTO1 = (35, 596, 293, 768)


def _form(path: Path):
    from PIL import Image

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    font = fitz.Font("cjk")
    tw = fitz.TextWriter(page.rect)
    for x0, y0, x1, y1, lines in CELLS:
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=(0, 0, 0), width=0.8)
        h = 7.5 * len(lines)
        for k, t in enumerate(lines):
            tw.append((x0 + 3, (y0 + y1) / 2 - h / 2 + 6.5 + k * 7.5), t, font=font, fontsize=6.5)
    # 기타 특이사항: 첫 줄이 라벨, 아래는 글머리표 내용
    page.draw_rect(fitz.Rect(30, 391, 566, 579), color=(0, 0, 0), width=0.8)
    tw.append((34, 402), "기타 특이사항", font=font, fontsize=8)
    tw.append((40, 418), "• 5월 8일 사전 조사, 약 50개 관찰", font=font, fontsize=8)
    tw.append((40, 432), "• 정상부 둥지 16개 포란", font=font, fontsize=8)
    # 조사사진 1·2: 첫 줄 라벨 + 사진 + 사진 아래 설명
    png = path.with_suffix(".png")
    Image.fromarray(np.random.default_rng(1).integers(30, 200, size=(300, 450, 3), dtype=np.uint8)).save(png)
    for (x0, x1, label, ph) in ((30, 298, "조사사진 1", PHOTO1), (298, 566, "조사사진 2", (303, 596, 561, 760))):
        page.draw_rect(fitz.Rect(x0, 579, x1, 785), color=(0, 0, 0), width=0.8)
        tw.append((x0 + 4, 590), label, font=font, fontsize=8)
        page.insert_image(fitz.Rect(*ph), filename=str(png), keep_proportion=False)
        tw.append((x0 + 4, 780), "둥지 포란 모습", font=font, fontsize=8)
    tw.write_text(page)
    doc.save(str(path))
    doc.close()


def _rect(b):
    return (b["x0"], b["y0"], b["x1"], b["y1"])


def _near(a, b, tol=2.5):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def test_filled_example_form_named_by_labels(tmp_path):
    from core.pdf_pipeline import suggest_cells_maximal

    p = tmp_path / "example.pdf"
    _form(p)
    boxes = suggest_cells_maximal(str(p), 0)
    by = {b["field"]: b for b in boxes}
    names = [b["field"] for b in boxes]

    # 값 칸은 짝지은 라벨 이름('조 사 자' → '조사자')
    assert _near(_rect(by["조사지역"]), (101, 78, 176, 96))
    assert _near(_rect(by["날짜"]), (222, 78, 346, 96))
    assert _near(_rect(by["조사시간"]), (406, 78, 566, 96))
    assert _near(_rect(by["조사자"]), (101, 96, 566, 113))
    assert _near(_rect(by["가락지 현황"]), (101, 171, 566, 286))
    assert _near(_rect(by["포란"]), (165, 303, 270, 321))
    assert by["포란"]["anchor"] == {"label": "포란", "relation": "right"}
    assert _near(_rect(by["동소종 현황"]), (328, 286, 566, 391))
    # 예시 값·묶음 라벨은 이름이 되지 않고, 라벨 칸 자체는 박스가 없다
    for bad in ("매도", "다수", "관찰 못함", "90", "칸", "개체군 현황", "둥지 현황"):
        assert bad not in names, bad
    assert not any(_near(_rect(b), (30, 78, 101, 96)) for b in boxes)

    # 열 머리글 × 줄 라벨 — 위 머리글 앵커(□/■ 달라도 찾아지게 표시는 뗌), 예시 값 '다수'라 일반 유형
    assert _near(_rect(by["단계별 개체수_알"]), (150, 142, 234, 171))
    assert by["단계별 개체수_알"]["anchor"] == {"label": "알 (Egg)", "relation": "below"}
    assert by["단계별 개체수_성조"]["mode"] == "text"
    assert by["성장단계_알"]["mode"] == "check" and _near(_rect(by["성장단계_알"]), (150, 113, 234, 142))

    # 첫 줄이 라벨인 큰 칸 — 라벨 줄은 뺀 영역
    assert by["기타 특이사항"]["y0"] > 396 and _near((by["기타 특이사항"]["y1"],), (579,))
    # 사진 칸 — 사진은 이미지 박스, 사진 아래는 설명 박스
    assert by["조사사진 1"]["mode"] == "image" and _near(_rect(by["조사사진 1"]), PHOTO1)
    assert by["조사사진 1_설명"]["y0"] >= PHOTO1[3] - 1 and by["조사사진 1_설명"]["mode"] == "text"
    assert by["조사사진 1_설명"]["caption_of"] == "조사사진 1"        # 사진이 옮겨 가도 그 사진 아래 줄을 읽게


def test_blank_form_still_names_value_cells(tmp_path):
    """빈 양식(값 칸이 비어 있음) — 값 칸은 라벨 이름·수치형은 숫자 유형, 라벨 칸 박스는 없다."""
    from core.pdf_pipeline import suggest_cells_maximal
    from tests.test_numeric import _form as num_form

    p = tmp_path / "blank.pdf"
    num_form(p, [("하천명", ""), ("보 길이 (m)", ""), ("구조물번호", "")])
    boxes = suggest_cells_maximal(str(p), 0)
    by = {b["field"]: b for b in boxes}
    assert set(by) == {"하천명", "보 길이 (m)", "구조물번호"}
    assert by["보 길이 (m)"]["mode"] == "number" and by["하천명"]["mode"] == "text"
    assert all(b["x0"] >= 159 for b in boxes)                 # 모두 오른쪽 값 칸
