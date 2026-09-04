"""척도표(리커트) 설문 인식 — '문항 행 × 점수 열' 격자에서 손표시 칸을 찾는다.

형태: 왼쪽에 문항 번호(1-1, 1-2, 2-1 … 또는 1. 2.)와 질문, 오른쪽에 ①②③④⑤(1점~5점) 열.
스캔본에서 손으로 동그라미·사선을 친 ①~⑤는 OCR이 못 읽으므로,
  · 열 위치 = 머리글의 'N점'(또는 짧은 토큰들의 등간격 배열)에서 잡고
  · 행 위치 = 문항 번호 토큰의 세로 위치에서 잡은 뒤
  · 칸마다 잉크 비율을 같은 행 안에서 비교해 가장 짙은 칸 = 응답(1~5)으로 판정한다.
애매하면 '확인 필요' 플래그를 남긴다.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from core.normalize import normalize
from core.pdf_reader import PdfPage, Word

_ROW_ID = re.compile(r"^(\d{1,2}(?:-\d{1,2})?)[.)]?(?:\s+(.*))?$")   # '1-1' 또는 '1-1 질문…'(한 토큰)
_SCALE_TOK = re.compile(r"^(?=.*(?:\d|[점죄짐]))\W?\s*\S{1,2}\s*[점죄짐]?\W?$")   # '1점' '(점' '근점' '5죄' 같은 OCR 변형


@dataclass
class LikertRow:
    qid: str
    text: str
    word: Word                      # 번호 토큰(행 기준)
    scores: list[float] = field(default_factory=list)
    answer: int | None = None       # 1..k
    flag: str = ""


@dataclass
class LikertGrid:
    columns: list[float]            # 점수 열의 x 중심(pt), 왼쪽→오른쪽 = 1..k
    rows: list[LikertRow]
    header_y: float                 # 머리글 세로 위치
    notes: list[str] = field(default_factory=list)   # 표 아래 자유 의견 줄들


def _lines(page: PdfPage) -> list[list[Word]]:
    ws = [w for w in page.words if (w.text or "").strip()]
    if not ws:
        return []
    gap = max(3.0, statistics.median(w.y1 - w.y0 for w in ws) * 0.6)
    rows: dict[int, list[Word]] = {}
    for w in ws:
        rows.setdefault(round(w.cy / gap), []).append(w)
    return [sorted(rows[k], key=lambda w: w.x0) for k in sorted(rows)]


def _fill_even(xs: list[float]) -> list[float]:
    """등간격 열에서 OCR이 빠뜨린 열을 보간한다(간격의 1.5배 넘는 틈을 메움)."""
    xs = sorted(xs)
    if len(xs) < 3:
        return xs
    diffs = [b - a for a, b in zip(xs, xs[1:])]
    step = min(diffs)
    out = [xs[0]]
    for a, b in zip(xs, xs[1:]):
        n = round((b - a) / step)
        for i in range(1, max(1, n)):
            out.append(a + (b - a) * i / n)
        out.append(b)
    return out


def _find_columns(page: PdfPage, lines: list[list[Word]]) -> tuple[list[float], float] | None:
    """머리글 행: 오른쪽 절반에 짧은 점수 토큰이 3개 이상 등간격으로 놓인 줄."""
    best = None
    for line in lines:
        toks = [w for w in line if w.x0 > page.width * 0.5 and len(w.text.strip()) <= 3
                and _SCALE_TOK.match(w.text.strip())]
        if len(toks) < 3:
            continue
        xs = sorted(w.cx for w in toks)
        diffs = [b - a for a, b in zip(xs, xs[1:])]
        if not diffs:
            continue
        step = min(diffs)
        if step <= 0 or any(abs(d / step - round(d / step)) > 0.25 for d in diffs):
            continue   # 등간격(정수배)이 아니면 머리글이 아님
        cols = _fill_even(xs)
        if best is None or len(cols) > len(best[0]):
            best = (cols, statistics.mean(w.cy for w in toks))
    return best


_COL_CACHE: dict[str, tuple[list[float], float]] = {}   # pdf_path → (열 x들, 머리글 y)


def parse_likert(page: PdfPage, fallback: tuple[list[float], float] | None = None) -> LikertGrid | None:
    lines = _lines(page)
    found = _find_columns(page, lines)
    if not found:
        found = fallback   # 머리글이 어둡게 스캔돼 OCR이 못 읽으면, 같은 문서의 다른 쪽 열 위치
    if not found:
        return None
    cols, header_y = found
    rows: list[LikertRow] = []
    tail: list[str] = []
    after_table = False
    for line in lines:
        if line[0].cy <= header_y:
            continue
        first = line[0].text.strip()
        m = _ROW_ID.match(first)
        if m and line[0].x0 < page.width * 0.2:
            # 번호 바로 옆의 짧은 분류 라벨(예: '조작')은 질문이 아니므로 제외
            words = [w for w in line[1:] if not (len(w.text.strip()) <= 3 and w.x0 < line[0].x1 + 45)]
            text = " ".join(([m.group(2)] if m.group(2) else []) + [w.text for w in words])
            rows.append(LikertRow(qid=m.group(1), text=normalize(text), word=line[0]))
            continue
        text = normalize(" ".join(w.text for w in line))
        if rows and not after_table:
            # 질문이 다음 줄로 이어진 경우(왼쪽 분류 라벨은 제외) — 마지막 행에 붙인다
            if text in ("계", "합계") or text.startswith("기타"):
                after_table = True
                continue
            cont = [w for w in line if w.x0 > page.width * 0.18]
            if cont and not rows[-1].text.endswith("?"):
                rows[-1].text = normalize(rows[-1].text + " " + " ".join(w.text for w in cont))
            continue
        if after_table and text and not text.startswith("기타") and text not in ("계", "합계"):
            tail.append(text)
    if len(rows) < 2:
        return None
    return LikertGrid(columns=cols, rows=rows, header_y=header_y, notes=tail)


def _dark_map(pdf_path: str, page_no: int, dpi: int):
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        pix = doc[page_no].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    finally:
        doc.close()
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return arr < 140, dpi / 72.0


def mark_likert_by_ink(pdf_path: str, page: PdfPage, grid: LikertGrid,
                       dpi: int = 220, min_delta: float = 0.010, mad_k: float = 2.5) -> None:
    """행×열 칸의 잉크 비율을 같은 행 안에서 비교 — 기준(중앙값)보다 뚜렷이 짙은 칸이 응답.

    칸 영역은 인쇄된 ①~⑤ 글자 주변으로 좁혀(여백·표선 제외) 얇은 볼펜 체크도 잡히게 하고,
    문턱은 행 안의 잉크 편차(MAD)에 맞춰 적응한다: thr = 중앙값 + max(min_delta, mad_k·MAD).
    """
    dark, s = _dark_map(pdf_path, page.page_no, dpi)
    H, W = dark.shape
    cols = grid.columns
    step = statistics.median([b - a for a, b in zip(cols, cols[1:])]) if len(cols) > 1 else 30.0
    ys = [r.word.cy for r in grid.rows]
    for i, r in enumerate(grid.rows):
        h_txt = max(4.0, r.word.y1 - r.word.y0)
        gaps = []
        if i > 0:
            gaps.append(ys[i] - ys[i - 1])
        if i + 1 < len(ys):
            gaps.append(ys[i + 1] - ys[i])
        half = min(gaps) / 2 * 0.72 if gaps else h_txt * 1.4
        half = max(h_txt * 1.1, min(half, h_txt * 2.2))   # 가로 표선은 피하고 글자는 덮게
        r.scores = []
        for xc in cols:
            x0, x1 = max(0, int((xc - step * 0.36) * s)), min(W, int((xc + step * 0.36) * s))
            y0, y1 = max(0, int((r.word.cy - half) * s)), min(H, int((r.word.cy + half) * s))
            area = max(1, (x1 - x0) * (y1 - y0))
            r.scores.append(float(dark[y0:y1, x0:x1].sum()) / area)
        base = statistics.median(r.scores)
        others = sorted(r.scores)[:-1] if len(r.scores) > 2 else r.scores   # 최댓값 제외한 편차
        mad = statistics.median(abs(v - base) for v in others) if others else 0.0
        delta = max(min_delta, mad_k * mad)
        thr = base + delta
        above = [k for k, v in enumerate(r.scores) if v >= thr]
        top = max(r.scores)
        excess = top - base
        if len(above) == 1:
            r.answer = above[0] + 1
            if excess < delta * 1.6:
                r.flag = f"표시 확인 필요(잉크 차이 {excess:.1%}로 흐림)"
        elif len(above) >= 2:
            r.answer = r.scores.index(top) + 1
            r.flag = "표시 확인 필요(칸 2개 이상이 짙음)"
        else:
            r.answer = None
            if excess >= delta * 0.6:
                r.flag = f"표시 불명확(잉크 차이 {excess:.1%})"


def likert_row(grid: LikertGrid, stable_keys: bool = False) -> dict:
    """격자 → 엑셀 한 행: 열 = '번호_질문', 값 = 점수(1~k). 표 아래 의견은 '기타의견'.

    stable_keys(스캔본): 열 이름을 '문항01·문항02…'(행 순서)로 — OCR이 번호·글자를
    조금씩 다르게 읽어도 페이지끼리 같은 열에 쌓인다."""
    row: dict = {}
    flags: dict = {}
    for i, r in enumerate(grid.rows):
        key = f"문항{i + 1:02d}" if stable_keys else f"{r.qid}_{r.text[:18].rstrip('?？. ')}"
        row[key] = str(r.answer) if r.answer else ""
        if r.flag:
            flags[key] = r.flag
    if grid.notes:
        row["기타의견"] = " / ".join(grid.notes)
    if flags:
        row["_이상치"] = flags
    return row


def extract_likert(page: PdfPage, pdf_path: str | None = None) -> dict | None:
    fb = _COL_CACHE.get(pdf_path or "")
    grid = parse_likert(page, fallback=fb)
    if grid is None:
        return None
    if pdf_path and _find_columns(page, _lines(page)) is not None:
        _COL_CACHE[pdf_path] = (grid.columns, grid.header_y)   # 이 쪽에서 직접 읽은 열만 캐시
    if pdf_path and getattr(page, "ocr", False):
        try:
            mark_likert_by_ink(pdf_path, page, grid)
        except Exception:  # noqa: BLE001
            pass
    return likert_row(grid, stable_keys=bool(getattr(page, "ocr", False)))
