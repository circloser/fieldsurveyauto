"""척도표(리커트) 설문 인식 — '문항 행 × 점수 열' 격자에서 표시한 칸을 찾는다.

형태: 왼쪽에 문항 번호(1-1, 1.1, 1. …)와 질문, 오른쪽에 점수 열.
  · 점수 머리글: '1점 2점 … 5점'(또는 짧은 숫자 토큰의 등간격 배열)
  · 말 머리글: '매우 그렇다 | 그렇다 | 보통이다 | 그렇지 않다 | 매우 그렇지 않다' —
    구역(1. ○○장학금, 2. …)마다 머리글이 반복되고, '개선·보완 의견' 같은 글 칸 행이 섞인다.
응답 판정:
  · 스캔본 — 손으로 동그라미·사선을 친 ①~⑤는 OCR이 못 읽으므로 열 위치(머리글)와
    행 위치(문항 번호)로 칸을 잡고, 같은 행 안에서 잉크가 뚜렷이 짙은 칸 = 응답.
  · 글자 PDF — 칸 안에 친 표시 글자(● ○ V ✓ …)로 판정.
애매하면 '확인 필요' 플래그를 남긴다.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from core.normalize import normalize
from core.pdf_reader import PdfPage, Word

_ROW_ID = re.compile(r"^(\d{1,2}(?:[-.]\d{1,2})?)[.)]?(?:\s+(.*))?$")   # '1-1' '1.1' '3.' 또는 '1-1 질문…'(한 토큰)
# 점수 열 머리글 토큰: '1점' '2점' … 과 OCR 변형('(점' '근점' '3짐' '5죄'), 맨숫자 '1'.
# '1회' '6명' 같은 단위 붙은 숫자는 제외(설문 선택지 '② 1회 ③ 2회…'를 머리글로 오인 방지)
_SCALE_TOK = re.compile(r"^\W?\s*(?:\d{1,2}\s*[점죄짐]?|\S{1,2}[점죄짐])\W?$")
# 말 머리글 토큰: 척도 낱말로만 이루어진 토큰('매우' '그렇지' '보통이다' '매우그렇지' '불만족' …).
# 조사표의 등급 머리글(매우우수·우수·보통·미흡)은 설문이 아니므로 '우수·미흡·양호'는 넣지 않는다.
_SCALE_WORD = re.compile(
    r"^(?:매우|전혀|대체로|약간|다소|조금|별로|아주|그저|그런|보통|그렇다|그렇지|않다|않음|않은|아니다|"
    r"만족|불만족|불만|동의|반대|중립|좋다|나쁘다|이다|한다|함|임|편이다|편)+\.?$")
_SCALE_CORE = re.compile(r"그렇|않|아니|보통|만족|불만|동의|반대|중립|좋|나쁘")
_SCALE_DECO = re.compile(r"^\(?[1-7]\)?$|^[①-⑦]$")          # '매우 그렇다 (5)' 의 점수 표기
# 점수 없이 글로 답하는 행('1.4 개선, 보완, 추가 등에 대한 의견', '7. 기타 의견을 자유롭게 기술해주세요').
# 질문은 '…의견' '…주세요' '…바랍니다'에서 끝나고 그 뒤(같은 줄 오른쪽·아래 줄)가 적은 답이다.
# '…의견을 잘 반영한다.' '…의견이 있습니까?' 처럼 문장으로 끝나는 질문은 점수 행.
_FREE_Q = re.compile(r"의견|자유롭게|기술해|서술|적어\s*주|써\s*주")
_FREE_DONE = re.compile(r"(의견|요|오|니다)[.):]?$")
_QUESTION_END = re.compile(r"(\?|？|까|다\.?)$")
_MARK_FILLED = set("●◉■▣◆✓✔√☑☒✗✘VvXx×❶❷❸❹❺❻❼➊➋➌➍➎")
_MARK_HOLLOW = set("○◯◎⊙Oo")


@dataclass
class LikertRow:
    qid: str
    text: str
    word: Word                      # 번호 토큰(행 기준)
    scores: list[float] = field(default_factory=list)
    answer: int | None = None       # 1..k
    flag: str = ""
    cols: list[float] = field(default_factory=list)     # 이 행이 속한 머리글의 열 x(구역마다 조금씩 다름)
    labels: list[str] = field(default_factory=list)     # 말 머리글이면 열 이름('매우 그렇다' …)
    free: bool = False              # 점수 없이 글로 답하는 행
    note: str = ""                  # free 행에 적힌 글
    lines: list[list[Word]] = field(default_factory=list)   # 번호 줄 + 이어지는 줄들
    qwords: list[Word] = field(default_factory=list)        # 번호·질문 글자


@dataclass
class LikertGrid:
    columns: list[float]            # 점수 열의 x 중심(pt), 순서 = 1..k (첫 머리글 기준)
    rows: list[LikertRow]
    header_y: float                 # 머리글 세로 위치
    notes: list[str] = field(default_factory=list)   # 표 아래 자유 의견 줄들
    labels: list[str] = field(default_factory=list)  # 말 머리글의 열 이름


@dataclass
class _Head:
    cols: list[float]
    labels: list[str]
    top: float
    bot: float


def _lines(page: PdfPage) -> list[list[Word]]:
    ws = [w for w in page.words if (w.text or "").strip()]
    if not ws:
        return []
    gap = max(3.0, statistics.median(w.y1 - w.y0 for w in ws) * 0.6)
    rows: dict[int, list[Word]] = {}
    for w in ws:
        rows.setdefault(round(w.cy / gap), []).append(w)
    return [sorted(rows[k], key=lambda w: w.x0) for k in sorted(rows)]


def _join_split(lines: list[list[Word]]) -> list[list[Word]]:
    """번호 토큰만 따로 떨어진 줄을 바로 옆 질문 줄과 합친다('4.2' 와 질문이 0.4pt 차이로 갈라짐)."""
    out: list[list[Word]] = []
    for line in lines:
        if out and len(out[-1]) == 1 and _ROW_ID.match(out[-1][0].text.strip()):
            prev = out[-1][0]
            if abs(line[0].cy - prev.cy) < max(4.0, prev.y1 - prev.y0) * 0.5 and line[0].x0 > prev.x1:
                out[-1] = sorted(out[-1] + line, key=lambda w: w.x0)
                continue
        out.append(line)
    return out


def _step(cols: list[float]) -> float:
    return statistics.median([abs(b - a) for a, b in zip(cols, cols[1:])]) if len(cols) > 1 else 30.0


def _left(cols: list[float]) -> float:
    """점수 칸이 시작하는 x — 이보다 왼쪽에서 시작하는 글자는 질문, 오른쪽은 표시·응답."""
    return min(cols) - _step(cols) * 0.5


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


def _score_order(toks: list[Word], cols: list[float]) -> str | None:
    """점수 머리글 검사 — 숫자가 든 토큰은 열 위치와 같아야 한다(1..k 'fwd' 또는 k..1 'rev').

    보고서의 수치 표('5 6 7 8 9', '0 5 0 0 5')가 등간격이라 머리글로 오인되던 것을 막는다.
    스캔본 OCR이 숫자 하나쯤 잘못 읽어도 되도록 숫자 토큰의 60% 이상이 맞으면 인정하고,
    숫자를 잃은 '(점' '근점'은 '점'으로 끝나면 위치 검사 없이 허용한다."""
    k = len(cols)
    fwd = rev = digits = 0
    for w in toks:
        t = w.text.strip()
        pos = min(range(k), key=lambda i: abs(cols[i] - w.cx)) + 1
        m = re.search(r"\d+", t)
        if m:
            digits += 1
            v = int(m.group(0))
            fwd += v == pos
            rev += v == k + 1 - pos
        elif not re.search(r"[점죄짐]\W?$", t):
            return None
    if digits == 0:
        return "fwd"                    # 숫자가 모두 깨졌어도 '점' 토큰이 3개 이상이면 머리글
    if fwd >= 0.6 * digits:
        return "fwd"
    return "rev" if rev >= 0.6 * digits else None


def _find_columns(page: PdfPage, lines: list[list[Word]]) -> tuple[list[float], float] | None:
    """머리글 행: 오른쪽 절반에 짧은 점수 토큰이 3개 이상 등간격으로 놓인 줄.

    열 순서 = 점수 순서(첫 열이 1점). '5점 4점 … 1점'처럼 거꾸로 적힌 머리글이면 열을 뒤집어 돌려준다."""
    best = None
    for line in lines:
        right = [w for w in line if w.x0 > page.width * 0.5]
        toks = [w for w in right if len(w.text.strip()) <= 3 and _SCALE_TOK.match(w.text.strip())]
        if len(toks) < 3 or len(toks) < 0.6 * len(right):
            continue   # 머리글 줄은 오른쪽 절반이 거의 점수 토큰뿐이어야 함(선택지 줄과 구분)
        xs = sorted(w.cx for w in toks)
        diffs = [b - a for a, b in zip(xs, xs[1:])]
        if not diffs:
            continue
        step = min(diffs)
        if step <= 0 or any(abs(d / step - round(d / step)) > 0.25 for d in diffs):
            continue   # 등간격(정수배)이 아니면 머리글이 아님
        cols = _fill_even(xs)
        order = _score_order(toks, cols)
        if order is None:
            continue   # 숫자가 열 위치와 안 맞음 — 점수 머리글이 아니라 수치 표
        if order == "rev":
            cols = list(reversed(cols))
        if best is None or len(cols) > len(best[0]):
            best = (cols, statistics.mean(w.cy for w in toks))
    return best


def _word_headers(page: PdfPage, lines: list[list[Word]]) -> list[_Head]:
    """말 머리글 띠들(위→아래). 띠 = 오른쪽에 척도 낱말만 놓인 붙어 있는 줄들
    ('매우/그렇다'처럼 칸 안에서 두세 줄로 쌓인 머리글). 열 = 위아래로 겹치거나 붙은 낱말 묶음."""
    xmin = page.width * 0.35

    def is_word(w: Word) -> bool:
        return bool(_SCALE_WORD.match(w.text.strip()))

    def head_line(line: list[Word]) -> bool:
        right = [w for w in line if w.x0 > xmin]
        return (any(is_word(w) for w in right)
                and all(is_word(w) or _SCALE_DECO.match(w.text.strip()) for w in right))

    bands: list[list[list[Word]]] = []
    cur: list[list[Word]] = []
    for line in lines:
        if head_line(line):
            h = max(4.0, statistics.median(w.y1 - w.y0 for w in line))
            if cur and line[0].cy - cur[-1][0].cy > h * 1.6:
                bands.append(cur)
                cur = []
            cur.append(line)
        elif cur:
            bands.append(cur)
            cur = []
    if cur:
        bands.append(cur)

    heads: list[_Head] = []
    for band in bands:
        toks = sorted((w for line in band for w in line if w.x0 > xmin), key=lambda w: w.x0)
        groups: list[list[Word]] = []
        for w in toks:
            pad = max(2.0, (w.y1 - w.y0) * 0.5)
            g = next((g for g in groups
                      if w.x0 <= max(t.x1 for t in g) + pad and w.x1 >= min(t.x0 for t in g) - pad), None)
            if g is None:
                groups.append([w])
            else:
                g.append(w)
        groups = [g for g in groups if any(is_word(t) for t in g)]
        if len(groups) < 3 or not all(any(_SCALE_CORE.search(t.text) for t in g) for g in groups):
            continue
        groups.sort(key=lambda g: min(t.x0 for t in g) + max(t.x1 for t in g))
        cols = [(min(t.x0 for t in g) + max(t.x1 for t in g)) / 2 for g in groups]
        diffs = [b - a for a, b in zip(cols, cols[1:])]
        med = statistics.median(diffs)
        if med <= 0 or any(abs(d - med) > 0.25 * med for d in diffs):
            continue   # 열 간격이 고르지 않으면 머리글이 아님
        labels = [normalize(" ".join(t.text for t in sorted(g, key=lambda t: (round(t.cy / 4), t.x0))
                                     if not _SCALE_DECO.match(t.text.strip())))
                  for g in groups]
        heads.append(_Head(cols, labels, min(t.y0 for t in toks), max(t.y1 for t in toks)))
    return heads


def _category_label(w: Word, nxt: Word | None, id_word: Word) -> bool:
    """번호 바로 옆의 짧은 분류 라벨(예: '조작') — 뒤에 칸 경계만큼 떨어져 질문이 이어진다.
    '개선, 보완, …' 처럼 띄어쓰기 간격으로 이어지는 짧은 낱말은 질문의 일부."""
    return (len(w.text.strip()) <= 3 and w.x0 < id_word.x1 + 45
            and (nxt is None or nxt.x0 - w.x1 > 12))


def _is_free(text: str) -> bool:
    return bool(_FREE_Q.search(text)) and bool(_FREE_DONE.search(text)) and not _QUESTION_END.search(text)


def _question_words(body: list[Word], lead: list[str], left: float) -> tuple[list[Word], bool]:
    """번호 뒤 낱말 중 질문 글자, 그리고 의견 행인지.
    의견 문항은 '…의견' '…기술해주세요'(뒤가 비었거나 칸 경계만큼 떨어짐)에서 질문이 끝난다 —
    전체 폭 문항은 점수 칸 자리까지 질문이 이어지고, 칸 안 의견은 같은 줄 오른쪽이 적은 답.
    점수 행은 점수 칸 왼쪽에서 시작하는 글자만 질문(오른쪽은 표시 글자)."""
    for i, w in enumerate(body):
        nxt = body[i + 1] if i + 1 < len(body) else None
        if not _FREE_DONE.search(w.text.strip()) or (nxt is not None and nxt.x0 - w.x1 <= 12):
            continue
        if _is_free(" ".join(lead + [t.text for t in body[:i + 1]])):
            return body[:i + 1], True
    words = [w for w in body if w.x0 < left]
    return words, _is_free(" ".join(lead + [w.text for w in words]))


_COL_CACHE: dict[str, tuple[list[float], float]] = {}   # pdf_path → (열 x들, 머리글 y)


def parse_likert(page: PdfPage, fallback: tuple[list[float], float] | None = None) -> LikertGrid | None:
    ocr = bool(getattr(page, "ocr", False))
    lines = _lines(page) if ocr else _join_split(_lines(page))   # 스캔본은 기존 줄 묶음 그대로
    # 점수 머리글이 있으면 점수(숫자)로 기록한다 — 스캔 설문은 '1점…5점'과 '매우 그렇다…'가 함께 있다.
    # 머리글이 어둡게 스캔돼 OCR이 못 읽으면 같은 문서의 다른 쪽 열 위치(fallback).
    # 둘 다 없을 때만 말 머리글 표로 읽는다.
    found = _find_columns(page, lines) or fallback
    if found:
        cols, header_y = found
        heads = [_Head(list(cols), [], header_y, header_y)]
    else:
        heads = _word_headers(page, lines)
        if not heads:
            return None

    def in_band(y: float) -> bool:
        return any(h.labels and h.top - 1 <= y <= h.bot + 1 for h in heads)

    rows: list[LikertRow] = []
    tail: list[str] = []
    after_table = False
    last: LikertRow | None = None        # 이어지는 줄을 붙일 행(구역 제목·※ 안내 뒤에는 없음)
    for li, line in enumerate(lines):
        cy = line[0].cy
        if cy <= heads[0].bot or in_band(cy):
            continue
        head = max((h for h in heads if h.bot < cy), key=lambda h: h.bot)
        left = _left(head.cols)
        first = line[0].text.strip()
        text = normalize(" ".join(w.text for w in line))
        if first.startswith("※"):
            if after_table and text:
                tail.append(text)
            last = None
            continue
        m = _ROW_ID.match(first)
        if m and line[0].x0 < page.width * 0.2:
            nxt = lines[li + 1] if li + 1 < len(lines) else None
            if not re.search(r"[-.]\d", m.group(1)) and nxt is not None and in_band(nxt[0].cy):
                last = None          # 구역 제목('2. 학습동아리 활동 장학금') — 바로 아래가 머리글
                continue
            # 스캔본은 OCR 낱말 상자 간격이 들쭉날쭉해 번호 옆 짧은 낱말이면 간격과 상관없이 분류 라벨(기존 동작)
            body = [w for i, w in enumerate(line[1:])
                    if not _category_label(w, None if ocr or i + 2 >= len(line) else line[i + 2], line[0])]
            lead = [m.group(2)] if m.group(2) else []
            words, free = _question_words(body, lead, left)
            r = LikertRow(qid=m.group(1), text=normalize(" ".join(lead + [w.text for w in words])),
                          word=line[0], cols=list(head.cols), labels=list(head.labels), free=free,
                          lines=[line], qwords=[line[0]] + words)
            rows.append(r)
            last = r
            continue
        if rows and not after_table:
            if text in ("계", "합계") or text.startswith("기타"):
                after_table = True
                continue
            if last is None:
                continue
            last.lines.append(line)
            if last.free and _FREE_DONE.search(last.text):
                continue             # 의견 문항의 질문이 끝났으면 아래 줄들은 적은 답
            # 질문이 다음 줄로 이어진 경우(왼쪽 분류 라벨·오른쪽 표시 칸은 제외) — 마지막 행에 붙인다
            tx = last.qwords[1].x0 - 6 if len(last.qwords) > 1 else page.width * 0.18
            cont = [w for w in line if (w.x0 > page.width * 0.18 or w.x0 >= tx) and w.x0 < left]
            if cont and not last.text.endswith("?"):
                last.text = normalize(last.text + " " + " ".join(w.text for w in cont))
                last.qwords.extend(cont)
                last.free = last.free or _is_free(last.text)   # '… 등에 대한' + '의견' 처럼 접힌 의견 문항
            continue
        if after_table and text and not text.startswith("기타") and text not in ("계", "합계"):
            tail.append(text)
    if sum(1 for r in rows if not r.free) < 2:
        return None
    for r in rows:
        if r.free:
            q = {id(w) for w in r.qwords}
            r.note = normalize(" ".join(w.text for line in r.lines for w in line if id(w) not in q))
    h0 = heads[0]
    return LikertGrid(columns=list(h0.cols), rows=rows, header_y=(h0.top + h0.bot) / 2,
                      notes=tail, labels=list(h0.labels))


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
    ys = [r.word.cy for r in grid.rows]
    for i, r in enumerate(grid.rows):
        if r.free:
            continue
        cols = r.cols or grid.columns
        step = _step(cols)
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


def mark_likert_by_text(grid: LikertGrid) -> None:
    """글자 PDF — 칸 안에 친 표시 글자(● ○ V ✓ …)로 응답 판정.
    모든 칸에 ○가 인쇄된 양식이면(빈 선택 표시) 채운 표시(● ✓ V)만 응답으로 본다."""
    for r in grid.rows:
        if r.free:
            continue
        cols = r.cols or grid.columns
        step = _step(cols)
        filled: set[int] = set()
        hollow: set[int] = set()
        for line in r.lines:
            for w in line:
                t = w.text.strip()
                if len(t) != 1 or (t not in _MARK_FILLED and t not in _MARK_HOLLOW):
                    continue
                k = min(range(len(cols)), key=lambda i: abs(cols[i] - w.cx))
                if abs(cols[k] - w.cx) > step * 0.5:
                    continue
                (filled if t in _MARK_FILLED else hollow).add(k)
        hits = sorted(filled) or (sorted(hollow) if len(hollow) < len(cols) else [])
        if hits:
            r.answer = hits[0] + 1
            if len(hits) > 1:
                r.flag = "표시 확인 필요(칸 2개 이상에 표시)"


def likert_row(grid: LikertGrid, stable_keys: bool = False) -> dict:
    """격자 → 엑셀 한 행: 열 = '번호_질문', 값 = 점수(1~k) — 말 머리글이면 열 이름('그렇다').
    의견 행은 적힌 글, 표 아래 의견은 '기타의견'.

    stable_keys(스캔본): 열 이름을 '문항01·문항02…'(행 순서)로 — OCR이 번호·글자를
    조금씩 다르게 읽어도 페이지끼리 같은 열에 쌓인다."""
    row: dict = {}
    flags: dict = {}
    for i, r in enumerate(grid.rows):
        key = f"문항{i + 1:02d}" if stable_keys else f"{r.qid}_{r.text[:18].rstrip('?？. ')}"
        if r.free:
            row[key] = r.note
        elif r.answer:
            row[key] = r.labels[r.answer - 1] if r.answer <= len(r.labels) else str(r.answer)
        else:
            row[key] = ""
        if r.flag:
            flags[key] = r.flag
    if grid.notes:
        row["기타의견"] = " / ".join(grid.notes)
    if flags:
        row["_이상치"] = flags
    return row


def _info_fields(pdf_path: str, page: PdfPage, grid: LikertGrid) -> dict:
    """머리글 위 표의 '이름 칸 | 값 칸' 쌍(학과명 | … | 성명 | …) — 응답자 정보 열.
    표 선이 있는 글자 PDF만. 칸이 짝수 개로 붙어 있고 이름 칸이 짧은 글(숫자 없음)일 때."""
    try:
        from core.anchor_check import _cells
        cells = [c for c in _cells(pdf_path, page.page_no)
                 if c.y1 <= grid.header_y and c.x1 - c.x0 < page.width * 0.9 and c.y1 - c.y0 < 60]
    except Exception:  # noqa: BLE001
        return {}
    by_row: dict[int, list] = {}
    for c in cells:
        by_row.setdefault(round((c.y0 + c.y1) / 8), []).append(c)
    out: dict = {}
    for cs in by_row.values():
        cs.sort(key=lambda c: c.x0)
        if len(cs) < 2 or len(cs) % 2 or len(cs) > 8:
            continue
        if any(abs(a.x1 - b.x0) > 3 for a, b in zip(cs, cs[1:])):
            continue
        texts = [normalize(" ".join(w.text for w in page.words
                                    if c.x0 <= w.cx <= c.x1 and c.y0 <= w.cy <= c.y1)) for c in cs]
        names = texts[0::2]
        if not all(t and len(t.replace(" ", "")) <= 12 and not re.search(r"\d", t) for t in names):
            continue
        for name, val in zip(names, texts[1::2]):
            out[name.replace(" ", "")] = val
    return out


def _top_span(grid: LikertGrid) -> tuple[int, int] | None:
    """쪽의 큰 번호 범위(1.1~3.4 → 1~3) — 다음 쪽이 4.1 부터면 같은 응답자로 합친다.
    첫 행이 '3.3'처럼 구역 중간이면 앞 쪽에서 이어진 것이므로 시작을 다음 번호로 본다."""
    tops = []
    for r in grid.rows:
        m = re.match(r"(\d+)(?:[-.](\d+))?", r.qid)
        if m:
            tops.append((int(m.group(1)), int(m.group(2) or 0)))
    if not tops:
        return None
    return (tops[0][0] + (1 if tops[0][1] > 1 else 0), max(t for t, _ in tops))


def extract_likert(page: PdfPage, pdf_path: str | None = None) -> dict | None:
    fb = _COL_CACHE.get(pdf_path or "")
    grid = parse_likert(page, fallback=fb)
    if grid is None:
        return None
    ocr = bool(getattr(page, "ocr", False))
    if pdf_path and not grid.labels and _find_columns(page, _lines(page)) is not None:
        _COL_CACHE[pdf_path] = (grid.columns, grid.header_y)   # 이 쪽에서 직접 읽은 열만 캐시
    if ocr:
        if pdf_path:
            try:
                mark_likert_by_ink(pdf_path, page, grid)
            except Exception:  # noqa: BLE001
                pass
        return likert_row(grid, stable_keys=True)
    mark_likert_by_text(grid)
    row = _info_fields(pdf_path, page, grid) if pdf_path else {}
    row.update(likert_row(grid))
    span = _top_span(grid)
    if span:
        row["_문항범위"] = span                    # 쪽 병합용(4번 일괄 처리가 꺼내 씀)
    row["_문항수"] = len(grid.rows)
    return row
