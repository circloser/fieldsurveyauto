"""설문지(칸 없는 문서) 구조 인식 — 문항 번호 / 선택지 번호 / 응답 표시.

문항:   줄 맨 앞의 'N.' 'N)' 'QN' + 질문 문장. 번호가 1,2,3… 순차로 증가해야 문항으로 본다
        (선택지 번호와 혼동 방지).
선택지: 문항 아래 줄에서 ①…⑩ / (1) / 1) / 1 형태의 번호가 여러 개 반복.
응답:   (타이핑 PDF) ✓ ■ ● 같은 표시 문자가 붙은 선택지
        (스캔·수기)  선택지 번호 주변의 '잉크 밀도' — 인쇄 글자(단어 상자)를 지운 이미지에서
                     남는 검은 픽셀(손으로 그린 동그라미·체크)이 같은 문항의 다른 선택지보다
                     뚜렷이 많으면 표시됨. 애매하면 '_이상치'에 확인 요청을 남긴다.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from core.normalize import normalize
from core.pdf_reader import PdfPage, Word

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
MARKS = "✓√■●☑▣✔"
_Q_FULL = re.compile(r"^(?:Q\s*)?(\d{1,2})\s*[.)]\s*(.+)$")
_Q_NUM = re.compile(r"^(?:Q\s*)?(\d{1,2})\s*[.)]$")
_MARK_ONLY = re.compile("^[" + MARKS + "]$")
_CH = re.compile(
    "^(?P<mark>[" + MARKS + "])?\\s*"
    "(?:(?P<c>[" + CIRCLED + "])|\\((?P<p>\\d{1,2})\\)|(?P<n>\\d{1,2})\\)|(?P<b>\\d{1,2}))"
    "(?P<rest>.*)$")


@dataclass
class Choice:
    no: int
    text: str
    word: Word              # 번호 토큰(잉크 판정 기준 상자)
    marked: bool = False
    score: float = 0.0      # 잉크 밀도(스캔) — 0~1
    bare: bool = False      # 맨숫자('1 2 3') 표기였는지


@dataclass
class Question:
    no: int
    text: str
    choices: list[Choice] = field(default_factory=list)
    free_text: list[str] = field(default_factory=list)
    flag: str = ""          # 확인 필요 사유(있으면)

    @property
    def answers(self) -> list[str]:
        return [f"{c.no}:{c.text}" if c.text else str(c.no) for c in self.choices if c.marked]


def _lines(page: PdfPage) -> list[list[Word]]:
    """단어를 줄로 묶는다(세로 중심 기준). 각 줄은 x 순서."""
    ws = [w for w in page.words if (w.text or "").strip()]
    if not ws:
        return []
    hs = [w.y1 - w.y0 for w in ws]
    gap = max(3.0, statistics.median(hs) * 0.6)
    rows: dict[int, list[Word]] = {}
    for w in ws:
        rows.setdefault(round(w.cy / gap), []).append(w)
    return [sorted(rows[k], key=lambda w: w.x0) for k in sorted(rows)]


def _question_of(line: list[Word], expected: int) -> tuple[int, str] | None:
    """줄이 '다음 문항'이면 (번호, 질문문). 번호가 기대값(순차)이어야 한다."""
    first = line[0].text.strip()
    m = _Q_NUM.match(first)
    if m and len(line) > 1:
        no, text = int(m.group(1)), " ".join(w.text for w in line[1:])
    else:
        m = _Q_FULL.match(" ".join(w.text for w in line))
        if not m:
            return None
        no, text = int(m.group(1)), m.group(2)
    if no == expected:
        return no, normalize(text)
    return None


_GARBLED = re.compile(r"^(\d{1,2})[^\d\s]?(.*)$")   # 손표시로 깨진 번호: '2y그렇다', '3' 등


def _choices_of(line: list[Word]) -> list[Choice]:
    """줄에서 선택지 토큰들을 뽑는다. 맨숫자('1 2 3')는 2개 이상·오름차순일 때만 인정.

    스캔본에서 손표시(체크·동그라미)가 번호를 덮어 OCR이 깨지면('2)'→'2y'),
    번호 순서의 빈자리를 그 위치의 깨진 단어로 복원한다.
    """
    out: list[Choice] = []
    trail: list[list[Word]] = []      # 선택지별 뒤따르는 단어들(라벨 텍스트)
    pending_mark = False
    for w in line:
        t = w.text.strip()
        if _MARK_ONLY.match(t):
            pending_mark = True
            continue
        m = _CH.match(t)
        if m and m.group("b") and m.group("rest"):
            m = None   # '20대' 같은 숫자로 시작하는 일반 단어 — 맨숫자 선택지는 토큰 전체가 숫자일 때만
        if m and (m.group("c") or m.group("p") or m.group("n") or m.group("b")):
            if m.group("c"):
                no = CIRCLED.index(m.group("c")) + 1
            else:
                no = int(m.group("p") or m.group("n") or m.group("b"))
            out.append(Choice(no=no, text=(m.group("rest") or "").strip(), word=w,
                              marked=bool(m.group("mark")) or pending_mark,
                              bare=bool(m.group("b"))))
            trail.append([])
            pending_mark = False
        elif out:
            trail[-1].append(w)

    # 번호 빈자리 복원: (k, k+2) 사이의 뒤따르는 단어 중 'k+1'로 시작하는 깨진 토큰을 선택지로
    i = 0
    while i < len(out) - 1:
        want = out[i].no + 1
        if out[i + 1].no > want:
            found = None
            for j, w in enumerate(trail[i]):
                g = _GARBLED.match(w.text.strip())
                if g and int(g.group(1)) == want:
                    found = j
                    break
            if found is not None:
                w = trail[i][found]
                rest = _GARBLED.match(w.text.strip()).group(2).strip()
                new_c = Choice(no=want, text=rest, word=w)
                new_trail = trail[i][found + 1:]
                trail[i] = trail[i][:found]
                out.insert(i + 1, new_c)
                trail.insert(i + 1, new_trail)
        i += 1

    for c, ws in zip(out, trail):
        if ws:
            c.text = (c.text + " " + " ".join(w.text.strip() for w in ws)).strip()
    # 맨숫자만으로 된 선택지는 2개 이상·오름차순일 때만(값 '25' 등 오인 방지)
    if any(c.bare for c in out) and (len(out) < 2 or [c.no for c in out] != sorted(c.no for c in out)):
        return []
    if not all(1 <= c.no <= 20 for c in out):
        return []
    return out


def parse_survey(page: PdfPage) -> list[Question]:
    qs: list[Question] = []
    cur: Question | None = None
    for line in _lines(page):
        q = _question_of(line, (qs[-1].no + 1) if qs else 1)
        if q:
            cur = Question(no=q[0], text=q[1])
            qs.append(cur)
            continue
        if cur is None:
            continue
        chs = _choices_of(line)
        if chs:
            cur.choices.extend(chs)
        else:
            cur.free_text.append(normalize(" ".join(w.text for w in line)))
    return qs


def is_survey_page(page: PdfPage) -> bool:
    """문항 번호가 순차로 2개 이상 있고, 선택지나 답이 달린 페이지."""
    qs = parse_survey(page)
    return len(qs) >= 2 and any(q.choices or q.free_text for q in qs)


# ---------- 스캔·수기: 잉크 밀도로 표시 판정 ----------

def _dark_map(pdf_path: str, page_no: int, dpi: int):
    """페이지를 회색으로 렌더해 검은 픽셀 맵(bool)과 pt→px 배율을 돌려준다."""
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        pix = doc[page_no].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    finally:
        doc.close()
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return arr < 140, dpi / 72.0


def mark_by_ink(pdf_path: str, page: PdfPage, questions: list[Question],
                dpi: int = 150, delta: float = 0.015, ratio: float = 1.4) -> None:
    """선택지 '번호' 주변 영역의 잉크 비율을 같은 문항의 다른 선택지와 비교해 표시를 판정한다.

    인쇄된 번호('1)' '②')의 잉크는 선택지마다 비슷하므로, 기준(중앙값)보다 delta 이상·
    ratio배 이상 짙은 선택지 = 손으로 동그라미·체크한 것. 기준과 차이가 작으면
    '확인 필요' 플래그를 남긴다(주황 표시로 사람이 확인).
    """
    dark, s = _dark_map(pdf_path, page.page_no, dpi)
    H, W = dark.shape
    for q in questions:
        if not q.choices:
            continue
        for c in q.choices:
            w = c.word
            h = max(4.0, w.y1 - w.y0)
            ex = h * 0.7
            # 번호 토큰 영역: 단어 상자의 왼쪽 앞부분(번호 두 글자 폭) + 주변 여유
            x0 = max(0, int((w.x0 - ex) * s))
            x1 = min(W, int((w.x0 + min(w.x1 - w.x0, 1.8 * h) + ex) * s))
            y0 = max(0, int((w.y0 - ex) * s))
            y1 = min(H, int((w.y1 + ex) * s))
            area = max(1, (x1 - x0) * (y1 - y0))
            c.score = float(dark[y0:y1, x0:x1].sum()) / area
        scores = [c.score for c in q.choices]
        base = min(scores) if len(scores) <= 2 else statistics.median(scores)
        top = max(scores)
        thr = max(base + delta, base * ratio)
        for c in q.choices:
            if c.marked:          # 타이핑 표시 문자로 이미 확정된 것은 유지
                continue
            c.marked = c.score >= thr
        marked = [c for c in q.choices if c.marked]
        excess = top - base
        if marked and excess < delta * 1.5:
            q.flag = f"표시 확인 필요(잉크 차이 {excess:.0%}로 흐림)"
        elif len(marked) >= 2 and len(q.choices) >= 3:
            q.flag = "표시 확인 필요(선택지 여러 개가 짙음)"
        elif not marked and excess >= delta * 0.6:
            q.flag = f"표시 불명확(잉크 차이 {excess:.0%})"


def survey_row(questions: list[Question]) -> dict:
    """문항 → 엑셀 한 행. 열 = '번호_질문', 값 = '번호:선택지'(복수는 ;), 주관식은 글."""
    row: dict = {}
    flags: dict = {}
    for q in questions:
        key = f"{q.no}_{q.text[:18].rstrip('?？. ')}"
        if q.choices:
            row[key] = ";".join(q.answers)
        else:
            row[key] = " ".join(q.free_text).strip()
        if q.flag:
            flags[key] = q.flag
    if flags:
        row["_이상치"] = flags
    return row


def extract_survey(page: PdfPage, pdf_path: str | None = None) -> dict:
    """페이지 하나를 설문 행으로. 스캔(OCR) 페이지면 잉크 밀도로 표시를 판정한다."""
    qs = parse_survey(page)
    if pdf_path and getattr(page, "ocr", False):
        try:
            mark_by_ink(pdf_path, page, qs)
        except Exception:  # noqa: BLE001  (렌더 실패 등 — 글자 표시만으로)
            pass
    return survey_row(qs)
