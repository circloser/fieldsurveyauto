# -*- coding: utf-8 -*-
"""예제 파일 만들기 — 사용 설명서 3장(따라 해 보기)과 설명서 그림에 쓰는 가상의 조사표.

    python tools/make_examples.py [출력폴더]      (기본 examples/)

만드는 것
  야생조류_현장조사표_빈양식.pdf   빈 양식(템플릿 디자이너에 올리는 기준 양식) — 표 칸 선·라벨·체크 칸·사진 칸
  작성예시_01.pdf ~ 03.pdf         빈 양식에 가상의 기록 3건을 채운 조사표(데이터 추출 관리에 올리는 파일)
  현장사진_예제.jpg                작성예시에 든 사진(그림으로 그린 습지 풍경)
  template_boxes.json              이 양식의 추출 박스(설명서 그림을 만들 때 템플릿으로 저장)
  entries.json                     가상의 기록 3건(설명서 그림의 실시간 기록 표에 넣는 값)
모든 이름·장소·수치는 지어낸 것이며 실제 조사 자료가 아니다. 형식은 PDF 뿐이라 한글(HWP) 없이 열 수 있다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TITLE = "야생조류 현장 조사표"
PAGE_W, PAGE_H = 595.0, 842.0
# 칸 좌표(PDF 포인트). 라벨 칸 | 값 칸
LABEL_W = 80
L1, L2, R1, R2 = 60.0, 140.0, 330.0, 410.0     # 왼쪽 라벨/값 시작, 오른쪽 라벨/값 시작
X_END = 535.0
ROWS = [("조사지역", "조사일자"), ("조사자", "날씨"), ("시작 시각", "종료 시각")]
Y0 = 100.0
ROW_H = 24.0
CHECKS = [("도보", 140.0), ("차량", 230.0), ("선박", 320.0)]     # 라벨 x 시작(라벨 60 + 체크 칸 30)
TABLE_COLS = [("종명", 60.0, 200.0), ("개체수", 200.0, 270.0), ("행동", 270.0, 390.0), ("비고", 390.0, 535.0)]
TABLE_Y, TABLE_ROWS = 220.0, 5
NOTE_Y0, NOTE_Y1 = 380.0, 440.0
PHOTO_Y0, PHOTO_Y1 = 470.0, 660.0
PHOTO_X1 = 320.0
FOOT_Y = 690.0


def _photo(path: Path) -> None:
    """가상의 습지 풍경(그림) — 실제 사진이 아니다."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (960, 720), (198, 224, 244))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 960, 330], fill=(186, 214, 240))
    d.ellipse([620, 60, 760, 200], fill=(255, 244, 200))
    d.polygon([(0, 330), (220, 250), (420, 300), (640, 240), (960, 310), (960, 360), (0, 360)], fill=(120, 160, 110))
    d.rectangle([0, 360, 960, 720], fill=(96, 150, 190))
    for i in range(0, 960, 80):
        d.line([(i, 420 + (i // 80 % 3) * 6), (i + 50, 420 + (i // 80 % 3) * 6)], fill=(150, 195, 225), width=3)
    for x in (110, 170, 240, 700, 780):
        d.polygon([(x, 700), (x + 8, 470), (x + 16, 700)], fill=(120, 130, 70))
        d.ellipse([x - 2, 440, x + 18, 480], fill=(160, 120, 60))
    for bx, by in ((420, 520), (500, 540), (560, 515)):
        d.ellipse([bx, by, bx + 46, by + 26], fill=(240, 240, 235), outline=(90, 90, 90))
        d.ellipse([bx + 34, by - 8, bx + 50, by + 8], fill=(240, 240, 235), outline=(90, 90, 90))
    im.save(path, "JPEG", quality=85)


def blank_form(path: Path) -> list[dict]:
    """빈 양식 PDF 를 그리고, 그 양식의 추출 박스 목록을 돌려준다."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    font = fitz.Font("cjk")
    line = dict(color=(0, 0, 0), width=0.8)
    tw = fitz.TextWriter(page.rect)
    boxes: list[dict] = []
    order = [0]

    def box(field, x0, y0, x1, y1, mode="text", anchor=None, use_anchor=True, **extra):
        order[0] += 1
        b = {"field": field, "page": 0, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "mode": mode,
             "use_anchor": bool(anchor) and use_anchor, "suggested": False, "order": order[0],
             "anchor": {"label": anchor, "relation": "right"} if anchor else None}
        b.update(extra)
        boxes.append(b)

    def label(x0, y0, x1, y1, text, size=9.5, fill=(0.93, 0.95, 0.91)):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), fill=fill, **line)
        w = font.text_length(text, fontsize=size)
        tw.append((x0 + (x1 - x0 - w) / 2, y0 + (y1 - y0) / 2 + size * 0.35), text, font=font, fontsize=size)

    def cell(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), **line)

    # 제목
    tw.append((PAGE_W / 2 - font.text_length(TITLE, fontsize=18) / 2, 62), TITLE, font=font, fontsize=18)
    box("P1_제목", 150, 40, 450, 75, mode="title", anchor=TITLE, use_anchor=False)
    # 조사 개요
    y = Y0
    for left, right in ROWS:
        label(L1, y, L2, y + ROW_H, left)
        cell(L2, y, R1, y + ROW_H)
        box(left.replace(" ", ""), L2, y, R1, y + ROW_H, anchor=left)
        label(R1, y, R2, y + ROW_H, right)
        cell(R2, y, X_END, y + ROW_H)
        box(right.replace(" ", ""), R2, y, X_END, y + ROW_H, anchor=right)
        y += ROW_H
    # 조사 방법(체크)
    label(L1, y, L2, y + ROW_H, "조사 방법")
    cell(L2, y, X_END, y + ROW_H)
    for name, x in CHECKS:
        tw.append((x + 6, y + 16), name, font=font, fontsize=9.5)
        bx = x + 44
        page.draw_rect(fitz.Rect(bx, y + 6, bx + 12, y + 18), width=0.7, color=(0.2, 0.2, 0.2))
        box(name, x + 2, y + 3, bx + 16, y + 21, mode="check", use_anchor=False)   # 라벨+네모 한 박스
    tw.append((416, y + 16), "기타", font=font, fontsize=9.5)
    cell(440, y + 3, X_END - 3, y + 21)
    box("기타", 440, y + 3, X_END - 3, y + 21, anchor="기타")
    y += ROW_H
    # 관찰 기록 표
    tw.append((L1, TABLE_Y - 6), "관찰 기록", font=font, fontsize=10)
    for name, x0, x1 in TABLE_COLS:
        label(x0, TABLE_Y, x1, TABLE_Y + ROW_H, name)
    for r in range(TABLE_ROWS):
        ry = TABLE_Y + ROW_H * (r + 1)
        for name, x0, x1 in TABLE_COLS:
            cell(x0, ry, x1, ry + ROW_H)
    box("관찰기록", L1, TABLE_Y, X_END, TABLE_Y + ROW_H * (TABLE_ROWS + 1), mode="table",
        columns=[c[0] for c in TABLE_COLS], header_rows=1, use_anchor=False)
    # 특이사항
    label(L1, NOTE_Y0, L2, NOTE_Y1, "특이사항")
    cell(L2, NOTE_Y0, X_END, NOTE_Y1)
    box("특이사항", L2, NOTE_Y0, X_END, NOTE_Y1, anchor="특이사항")
    # 현장 사진 + 설명
    tw.append((L1, PHOTO_Y0 - 6), "현장 사진", font=font, fontsize=10)
    cell(L1, PHOTO_Y0, PHOTO_X1, PHOTO_Y1)
    box("현장사진", L1, PHOTO_Y0, PHOTO_X1, PHOTO_Y1, mode="image", use_anchor=False)
    label(PHOTO_X1, PHOTO_Y0, X_END, PHOTO_Y0 + ROW_H, "사진 설명")
    cell(PHOTO_X1, PHOTO_Y0 + ROW_H, X_END, PHOTO_Y1)
    box("사진설명", PHOTO_X1, PHOTO_Y0 + ROW_H, X_END, PHOTO_Y1, anchor="사진 설명", use_anchor=False)
    # 조사 기관 · 확인자
    label(L1, FOOT_Y, L2, FOOT_Y + ROW_H, "조사 기관")
    cell(L2, FOOT_Y, R1, FOOT_Y + ROW_H)
    box("조사기관", L2, FOOT_Y, R1, FOOT_Y + ROW_H, anchor="조사 기관")
    label(R1, FOOT_Y, R2, FOOT_Y + ROW_H, "확인자")
    cell(R2, FOOT_Y, X_END, FOOT_Y + ROW_H)
    box("확인자", R2, FOOT_Y, X_END, FOOT_Y + ROW_H, anchor="확인자")
    tw.append((L1, 760), "※ 이 조사표는 오토다타 사용 설명서의 예제입니다. 장소·이름·수치는 모두 지어낸 것입니다.",
              font=font, fontsize=7.5)
    tw.write_text(page)
    doc.subset_fonts()
    doc.save(str(path), garbage=4, deflate=True)
    doc.close()
    return boxes


ENTRIES = [
    {"id": "example000000001", "client_id": "phoneA", "created": "2026-04-12T00:00:00Z", "seq": 1,
     "values": {"조사지역": "가온천 하류 습지", "조사일자": "2026-04-12", "조사자": "홍길동", "날씨": "맑음",
                "시작시각": "09:00", "종료시각": "11:30", "도보": True, "차량": True, "선박": False, "기타": "",
                "관찰기록": [{"종명": "흰뺨검둥오리", "개체수": "12", "행동": "채식", "비고": ""},
                             {"종명": "왜가리", "개체수": "3", "행동": "휴식", "비고": "둥지 근처"},
                             {"종명": "물총새", "개체수": "1", "행동": "비행", "비고": ""}],
                "특이사항": "하류 갈대밭에서 어린 새 2마리 확인", "사진설명": "습지 전경(동쪽에서 촬영)",
                "조사기관": "예제 생태연구소", "확인자": "김영희"},
     "meta": {"gps": {"lat": 37.1234, "lon": 127.4567, "acc": 6}}, "photo": True},
    {"id": "example000000002", "client_id": "phoneA", "created": "2026-04-12T04:20:00Z", "seq": 2,
     "values": {"조사지역": "가온천 중류 보 상류", "조사일자": "2026-04-12", "조사자": "김영희", "날씨": "흐림",
                "시작시각": "13:00", "종료시각": "14:20", "도보": True, "차량": False, "선박": False, "기타": "",
                "관찰기록": [{"종명": "쇠백로", "개체수": "5", "행동": "채식", "비고": ""},
                             {"종명": "청둥오리", "개체수": "20", "행동": "휴식", "비고": "보 상류 정수역"}],
                "특이사항": "", "사진설명": "", "조사기관": "예제 생태연구소", "확인자": "홍길동"},
     "meta": {"gps": {"lat": 37.1402, "lon": 127.4391, "acc": 9}}, "photo": False},
    {"id": "example000000003", "client_id": "phoneB", "created": "2026-04-13T23:40:00Z", "seq": 3,
     "values": {"조사지역": "새들 저수지", "조사일자": "2026-04-14", "조사자": "이철수", "날씨": "비",
                "시작시각": "08:30", "종료시각": "10:00", "도보": False, "차량": False, "선박": True, "기타": "",
                "관찰기록": [{"종명": "민물가마우지", "개체수": "40", "행동": "휴식", "비고": "제방 위"},
                             {"종명": "논병아리", "개체수": "2", "행동": "잠수", "비고": ""},
                             {"종명": "흰뺨검둥오리", "개체수": "8", "행동": "채식", "비고": ""},
                             {"종명": "붉은부리갈매기", "개체수": "15", "행동": "비행", "비고": "저수지 상공"}],
                "특이사항": "비가 내려 조사를 30분 단축", "사진설명": "저수지 제방 방향",
                "조사기관": "예제 생태연구소", "확인자": "김영희"},
     "meta": {"gps": {"lat": 37.0988, "lon": 127.5012, "acc": 12}}, "photo": True},
]


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    photo = out_dir / "현장사진_예제.jpg"
    _photo(photo)
    blank = out_dir / "야생조류_현장조사표_빈양식.pdf"
    boxes = blank_form(blank)
    (out_dir / "template_boxes.json").write_text(json.dumps(boxes, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "entries.json").write_text(json.dumps(ENTRIES, ensure_ascii=False, indent=1), encoding="utf-8")
    from core.form_fill import fill_pdf
    for i, e in enumerate(ENTRIES, 1):
        fill_pdf(str(blank), boxes, [e], str(out_dir / f"작성예시_{i:02d}.pdf"),
                 photo_path=lambda ent, field: str(photo) if ent.get("photo") and field == "현장사진" else None,
                 gps=False, footer=False)
    print("예제 파일:", out_dir)
    for p in sorted(out_dir.iterdir()):
        print(f"  {p.name}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples")
