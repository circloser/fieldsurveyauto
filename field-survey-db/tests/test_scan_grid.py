"""스캔 표 격자 — 한 줄 안에서만 쓰는 짧은 칸 선도 칸 경계로 잡는다.

실제 사례(저어새 번식지 조사표 스캔): 첫 줄 '조사지역 | 칠산도 | 날짜 | 2026. 5. 13. | 조사시간 | 13:00~16:00' 의
칸 선은 줄 높이(약 18pt)만큼만 짧고 다른 줄의 열과 위치가 달라, 표 높이의 30%를 넘는 선만 열로 보던 격자에서
빠졌다 → 첫 줄 전체가 한 칸('칠산도 날짜 2026. 5 13 조사시간 13:00 16:00')으로 합쳐지고,
둥지 현황의 작은 줄들도 동소종 현황과 한 칸이 됐다.
사진 테두리처럼 줄 선에 닿지 않는 세로 경계는 칸 선이 아니다.
"""
from pathlib import Path

import fitz
import numpy as np

from core.table_rows import image_grid

DPI = 150
S = 72 / DPI
X_L, X_R = 100, 1140
ROW_Y = [200, 240, 280, 600, 900]       # 1줄(짧음) · 2줄 · 3줄(사진이 든 큰 줄) · 4줄
SHORT_X = [250, 520, 700]               # 첫 줄에만 있는 칸 선
LONG_X = 400                            # 2~4줄을 가르는 긴 칸 선


def _scan(path: Path):
    from PIL import Image, ImageDraw

    W, H = 1240, 1000
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    for y in ROW_Y:
        dr.line([(X_L, y), (X_R, y)], fill="black", width=3)
    for x in (X_L, X_R):
        dr.line([(x, ROW_Y[0]), (x, ROW_Y[-1])], fill="black", width=3)
    for x in SHORT_X:
        dr.line([(x, ROW_Y[0]), (x, ROW_Y[1])], fill="black", width=3)
    dr.line([(LONG_X, ROW_Y[1]), (LONG_X, ROW_Y[-1])], fill="black", width=3)
    arr = np.array(img)
    rng = np.random.default_rng(0)                # 3줄 안의 사진(칸 여백 안쪽, 줄 선에 닿지 않음)
    arr[300:580, 450:1100] = rng.integers(40, 200, size=(280, 650, 3), dtype=np.uint8)
    png = path.with_suffix(".png")
    Image.fromarray(arr).save(png)
    doc = fitz.open()
    page = doc.new_page(width=W * S, height=H * S)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(path))
    doc.close()


def _row(cells, y_px):
    return sorted((c for c in cells if abs(c.y0 - y_px * S) < 3), key=lambda c: c.x0)


def test_short_first_row_separators_split_cells(tmp_path):
    p = tmp_path / "scan.pdf"
    _scan(p)
    cells = image_grid(str(p), 0)
    first = _row(cells, ROW_Y[0])
    assert [round(c.x0 / S) for c in first] == [X_L, *SHORT_X] or \
        all(abs(c.x0 / S - x) <= 4 for c, x in zip(first, [X_L, *SHORT_X]))
    assert len(first) == 4 and abs(first[-1].x1 / S - X_R) <= 4
    assert all(abs(c.y1 / S - ROW_Y[1]) <= 4 for c in first)      # 첫 줄 칸은 첫 줄 높이만


def test_photo_border_is_not_a_column(tmp_path):
    p = tmp_path / "scan.pdf"
    _scan(p)
    cells = image_grid(str(p), 0)
    photo_row = _row(cells, ROW_Y[2])
    assert len(photo_row) == 2                                    # 긴 칸 선 하나로만 나뉨(사진 테두리는 칸 선 아님)
    assert abs(photo_row[1].x0 / S - LONG_X) <= 4
    second = _row(cells, ROW_Y[1])
    assert len(second) == 2 and abs(second[1].x0 / S - LONG_X) <= 4   # 짧은 칸 선이 아래 줄로 새지 않음
