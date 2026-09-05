"""설문지(칸 없는 문서) 구조 인식 — 문항 번호 / 선택지 번호 / 응답 표시.

문항:   줄 맨 앞의 'N.' 'N)' 'QN.' '문N.' + 질문 문장. 번호는 앞 문항 +1 로 이어져야 문항으로 본다
        (선택지 번호와 혼동 방지). 쪽의 첫 문항은 어떤 번호든 허용(쪽을 넘어 11번부터 시작 등).
        점이 빠진 번호('12 이용 편리성…')는 기대 번호와 같을 때만, 번호가 한두 개 건너뛰면
        ('26.' 다음 '28.') 다시 이어 붙는다. 'N-M.' 은 N번의 하위 문항(5-1, 9-1).
        번호 없이 짧은 이름 + 선택지가 붙은 줄('성별 ① 남 ② 여')은 이름을 항목명으로 하는
        암시 문항(인적사항 표 등). 이름이 선택지 줄의 아래·위에 따로 있어도 붙인다.
선택지: 문항 아래 줄에서 ①…⑩ / (1) / 1) / 1 형태의 번호가 여러 개 반복.
레이아웃: 한 쪽에 두 단(좌·우)이 있으면 단을 나눠 왼쪽 단 → 오른쪽 단 순서로 읽는다.
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
_Q_NUM = re.compile(r"^(?P<pre>Q|문)?\s*(?P<no>\d{1,2})\s*(?P<p>[.,)])$")        # '3.' '문1.' '27,' '2)'
_Q_BARE = re.compile(r"^(?P<pre>Q|문)?(?P<no>\d{1,2})$")                        # '12' (점이 빠진 번호)
_Q_FULL = re.compile(r"^(?P<pre>Q|문)?\s*(?P<no>\d{1,2})\s*(?P<p>[.,)])\s*(?P<text>.+)$")   # '1.박물관의 …'
_SUB_Q = re.compile(r"^(\d{1,2})-(\d{1,2})[.)]?(.*)$")          # '5-1.' '9-1' '5-1.(5번에서' '10-1.병원이용'
_NOISE = re.compile(r"^(→|<<|※|☆|★|◆|◇|▶|♣|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*\.|-\s*\d+\s*-$)")   # 안내·섹션 머리글·쪽번호
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
    no: int | None          # 본문항 번호(하위·암시 문항은 None)
    text: str
    qid: str = ""           # 열 이름에 쓰는 식별자: '3', '문1', '5-1', '성별', '항목2'
    pre: str = ""           # 번호 접두어('문', 'Q') — 번호 체계 구분
    choices: list[Choice] = field(default_factory=list)
    free_text: list[str] = field(default_factory=list)
    flag: str = ""          # 확인 필요 사유(있으면)
    words: list[Word] = field(default_factory=list)   # 질문 줄의 단어들(화면 표시용 위치)

    @property
    def answers(self) -> list[str]:
        return [f"{c.no}:{c.text}" if c.text else str(c.no) for c in self.choices if c.marked]

    @property
    def key(self) -> str:
        """엑셀 열 이름(타이핑 문서 기준) — survey_row 와 같은 규칙."""
        if self.qid == self.text or not self.text:
            return self.qid
        return f"{self.qid}_{self.text[:18].rstrip('?？. ')}"

    def bbox(self) -> tuple[float, float, float, float] | None:
        """질문 줄 + 선택지 번호들을 감싸는 상자(pt) — 디자이너 화면에 인식 결과를 표시할 때."""
        ws = list(self.words) + [c.word for c in self.choices]
        if not ws:
            return None
        return (min(w.x0 for w in ws), min(w.y0 for w in ws),
                max(w.x1 for w in ws), max(w.y1 for w in ws))


# ---------- 줄 묶기(2단 레이아웃 지원) ----------

def _columns(page: PdfPage) -> list[list[Word]]:
    """좌·우 두 단이면 단별 단어 목록을(왼쪽→오른쪽), 아니면 전체 하나를 돌려준다.

    가로 30~70% 구간에서 어떤 단어도 걸치지 않는 가장 넓은 빈 띠를 찾아,
    띠가 쪽 너비의 3% 이상이고 양쪽에 모두 단어가 충분히(15%↑) 있으면 두 단으로 본다.
    """
    ws = [w for w in page.words if (w.text or "").strip()]
    if len(ws) < 20 or not page.width:
        return [ws]
    n = 200
    W = float(page.width)
    cov = [0] * n
    for w in ws:
        a = max(0, min(n - 1, int(w.x0 / W * n)))
        b = max(0, min(n - 1, int(w.x1 / W * n)))
        for i in range(a, b + 1):
            cov[i] = 1
    best = None
    i = int(0.3 * n)
    while i < int(0.7 * n):
        if cov[i] == 0:
            j = i
            while j < n and cov[j] == 0:
                j += 1
            if best is None or (j - i) > (best[1] - best[0]):
                best = (i, j)
            i = j
        else:
            i += 1
    if best is None or (best[1] - best[0]) < 0.03 * n:
        return [ws]
    split = (best[0] + best[1]) / 2 / n * W
    left = [w for w in ws if w.cx < split]
    right = [w for w in ws if w.cx >= split]
    if min(len(left), len(right)) < 0.15 * len(ws):
        return [ws]

    if min(len(_lines_of(left)), len(_lines_of(right))) < 3:
        return [ws]     # 한쪽이 한두 줄뿐이면(오른쪽으로 밀린 선택지 줄 등) 단이 아니다
    return [left, right]


def _lines_of(ws: list[Word]) -> list[list[Word]]:
    """단어를 줄로 묶는다(세로 중심 기준). 각 줄은 x 순서."""
    ws = [w for w in ws if (w.text or "").strip()]
    if not ws:
        return []
    hs = [w.y1 - w.y0 for w in ws]
    gap = max(3.0, statistics.median(hs) * 0.6)
    rows: dict[int, list[Word]] = {}
    for w in ws:
        rows.setdefault(round(w.cy / gap), []).append(w)
    return [sorted(rows[k], key=lambda w: w.x0) for k in sorted(rows)]


def _lines(page: PdfPage) -> list[list[Word]]:
    out: list[list[Word]] = []
    for col in _columns(page):
        out.extend(_lines_of(col))
    return out


# ---------- 문항 / 선택지 ----------

def _looks_like_choice_line(line: list[Word], no: int) -> bool:
    """'1) 예  2) 아니오' 처럼 번호 표기가 선택지 스타일이고 다음 번호가 같은 줄에 있으면 선택지 줄."""
    first = line[0].text.strip()
    if not re.match(r"^\(?\d{1,2}\)$", first):
        return False
    nxt = re.compile(rf"^\(?{no + 1}\)$")
    return any(nxt.match(w.text.strip()) for w in line[1:])


def _question_of(line: list[Word], expected: int | None, last_main: int | None, last_pre: str,
                 ) -> tuple[int | None, str, str, list[Word], str] | None:
    """줄이 문항이면 (본문항 번호|None, qid, 질문문, 질문 부분 단어들, 접두어).

    expected: 다음 본문항으로 기대하는 번호(None이면 아무 번호나 허용 — 쪽의 첫 문항).
    last_main: 직전 본문항 번호 — 'N-M' 하위 문항은 N이 last_main(또는 +1)일 때 인정.
    last_pre: 직전 문항의 번호 접두어 — 접두어가 바뀌면('문1' → '1') 새 번호 체계로 본다.
    """
    first = line[0].text.strip()
    m = _Q_NUM.match(first)
    if m and len(line) > 1:
        pre, no, style = m.group("pre") or "", int(m.group("no")), m.group("p")
        rest = line[1:]
        text = " ".join(w.text for w in rest)
    else:
        mb = _Q_BARE.match(first)
        if mb and len(line) > 1:
            pre, no, style = mb.group("pre") or "", int(mb.group("no")), ""
            rest = line[1:]
            text = " ".join(w.text for w in rest)
        else:
            sm = _SUB_Q.match(first)
            if sm:
                n_main, n_sub = int(sm.group(1)), int(sm.group(2))
                ok = (last_main is not None and n_main in (last_main, last_main + 1)) or \
                     (last_main is None and expected is None)
                if not ok:
                    return None
                rest = " ".join(([sm.group(3)] if sm.group(3) else []) + [w.text for w in line[1:]])
                return None, f"{n_main}-{n_sub}", normalize(rest), line[1:], last_pre
            mf = _Q_FULL.match(" ".join(w.text for w in line))
            if not mf:
                return None
            pre, no, style = mf.group("pre") or "", int(mf.group("no")), mf.group("p")
            rest = line
            text = mf.group("text")
    if style == ")" and _looks_like_choice_line(line, no):
        return None
    if pre != last_pre:
        expected = None                 # 번호 체계가 바뀜 → 첫 번호부터 다시
    if expected is None:
        ok = bool(style) or bool(pre)   # 점·괄호가 있거나 접두어('문1')가 있어야 첫 문항으로 인정
    else:
        ok = no == expected or (style in (".", ",") and expected < no <= expected + 2)
    if not ok:
        return None
    return no, f"{pre}{no}", normalize(text), rest, pre


_GARBLED = re.compile(r"^(\d{1,2})[^\d\s]?(.*)$")   # 손표시로 깨진 번호: '2y그렇다', '3' 등


def _choices_of(line: list[Word]) -> tuple[list[Choice], list[Word]]:
    """줄에서 선택지 토큰들을 뽑는다 → (선택지들, 첫 선택지 앞의 단어들).
    맨숫자('1 2 3')는 2개 이상·오름차순일 때만 인정.

    스캔본에서 손표시(체크·동그라미)가 번호를 덮어 OCR이 깨지면('2)'→'2y'),
    번호 순서의 빈자리를 그 위치의 깨진 단어로 복원한다.
    """
    out: list[Choice] = []
    trail: list[list[Word]] = []      # 선택지별 뒤따르는 단어들(라벨 텍스트)
    lead: list[Word] = []             # 첫 선택지 앞의 단어들('성 별' 같은 항목명)
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
        else:
            lead.append(w)

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
        return [], lead
    if not all(1 <= c.no <= 20 for c in out):
        return [], lead
    return out, lead


def _starts_group(chs: list[Choice]) -> bool:
    """새 선택지 묶음으로 볼 만한가 — 1번부터 시작하거나 3개 이상.
    안내문 속 '④번과 ⑤번을' 같은 번호 언급을 선택지로 오인하지 않게."""
    return bool(chs) and (chs[0].no == 1 or len(chs) >= 3)


def _label_text(ws: list[Word]) -> str:
    """짧은 항목명('성 별' → '성별', '거주지역', '최근1년간')이면 그 글, 아니면 ''."""
    if not ws:
        return ""
    raw = normalize(" ".join(w.text for w in ws))
    compact = raw.replace(" ", "")
    if not compact or len(compact) > 8 or "?" in compact or compact.endswith((")", ":", ".")):
        return ""
    if compact.startswith("(") or re.search(r"\d번", compact):
        return ""       # '(9번에서 ②번부터…' 같은 안내문
    if re.fullmatch(r"[\d.\-/~년월일\s]+", compact):
        return ""       # 날짜·숫자만 있는 것은 항목명이 아님
    return compact if len(compact) <= 4 else raw


_END_PUNCT = ("?", "？", ")", ".", ":")   # 여기서 끝난 질문문은 다음 줄로 이어지지 않는다


def parse_survey(page: PdfPage) -> list[Question]:
    qs: list[Question] = []
    cur: Question | None = None
    last_main: int | None = None
    last_pre = ""
    pending_label = ""          # 선택지 없이 나온 짧은 이름 — 바로 다음 선택지 묶음의 항목명
    pending_words: list[Word] = []
    name_from_above = False     # 현재 암시 문항의 이름이 선택지 '위' 줄에서 왔는지(두 줄 이름 결합용)
    prev_line: list[Word] | None = None
    for line in _lines(page):
        joined = normalize(" ".join(w.text for w in line))
        if not joined or _NOISE.match(joined):
            prev_line = line
            continue
        h = statistics.median(w.y1 - w.y0 for w in line)
        dy = (line[0].cy - prev_line[0].cy) if prev_line else 0.0
        close = 0 <= dy < max(8.0, 2.2 * h)     # 바로 아래 줄(단이 바뀌면 close 아님)
        prev_line = line

        chs, lead = _choices_of(line)
        # 앞 문항의 선택지가 이어지는 줄('⑤ 학교 ⑥ 기타', '3) 보통', '연 령 ⑤ 50대 ⑥ 60대')은
        # 문항 검사 없이 선택지로(앞에 붙은 글은 짧은 항목명일 때만 허용)
        continues = (cur is not None and bool(cur.choices) and bool(chs)
                     and chs[0].no == cur.choices[-1].no + 1
                     and (not lead or bool(_label_text(lead))))
        expected = None if last_main is None else last_main + 1
        q = None if continues else _question_of(line, expected, last_main, last_pre)
        if q:
            no, qid, text, rest, pre = q
            cur = Question(no=no, text=text, qid=qid, pre=pre, words=list(line))
            qs.append(cur)
            last_main = no if no is not None else int(qid.split("-")[0])
            last_pre = pre
            pending_label, pending_words = "", []
            name_from_above = False
            ichs, ilead = _choices_of(rest)      # '1. 성별? ① 남 ② 여' — 같은 줄의 선택지
            if ichs and ichs[0].no == 1 and [c.no for c in ichs] == list(range(1, len(ichs) + 1)):
                lead_txt = normalize(" ".join(w.text for w in ilead))
                lm = _Q_FULL.match(lead_txt)
                cur.text = normalize(lm.group("text")) if lm else lead_txt
                cur.choices.extend(ichs)
            continue

        if chs and (continues or _starts_group(chs)):
            label = _label_text(lead)
            restart = cur is None or (bool(cur.choices) and chs[0].no <= cur.choices[-1].no)
            if restart:
                # 번호 없이 새 선택지 묶음이 시작 → 암시 문항(인적사항 표의 '성별' 같은 항목)
                cur = Question(no=None, text=label or pending_label, qid="",
                               words=list(lead) + list(pending_words))
                qs.append(cur)
                name_from_above = bool(pending_label) and not label
            elif label and not cur.text:
                cur.text = label            # 이름이 두 번째 선택지 줄에 있는 칸('연 령 ⑤ …')
                cur.words.extend(lead)
            pending_label, pending_words = "", []
            cur.choices.extend(chs)
            continue

        if cur is None:
            continue
        label = _label_text(line)
        if label and cur.no is None and cur.choices:
            if not cur.text:
                cur.text = label            # 선택지 줄 아래에 이름이 오는 칸('직 업')
                cur.words.extend(line)
            elif name_from_above and close and len((cur.text + label).replace(" ", "")) <= 10 \
                    and label != cur.text:
                cur.text = normalize(cur.text + " " + label)   # 두 줄 이름('최근1년간'+'방문횟수')
                cur.words.extend(line)
                name_from_above = False
            else:
                pending_label, pending_words = label, list(line)
        elif label and cur.choices:
            pending_label, pending_words = label, list(line)   # 다음 선택지 묶음의 이름 후보
        elif not cur.choices and not cur.free_text and close and \
                not cur.text.rstrip().endswith(_END_PUNCT):
            cur.text = normalize(cur.text + " " + joined)   # 질문이 다음 줄로 이어짐
            cur.words.extend(line)
        else:
            cur.free_text.append(joined)
    for i, q in enumerate(qs, 1):
        if not q.qid:
            q.qid = q.text if q.text else f"항목{i}"
    return qs


def is_survey_page(page: PdfPage, pdf_path: str | None = None) -> bool:
    """번호 문항이 2개 이상(또는 항목 3개 이상)이고 선택지가 달린 페이지 — 또는 척도표(리커트)."""
    from core.likert import _COL_CACHE, parse_likert
    if parse_likert(page, fallback=_COL_CACHE.get(pdf_path or "")) is not None:
        return True
    qs = parse_survey(page)
    numbered = sum(1 for q in qs if q.no is not None)
    return (numbered >= 2 or len(qs) >= 3) and any(q.choices for q in qs)


def survey_items(page: PdfPage) -> list[dict]:
    """디자이너 화면 표시용 — 쪽에서 인식한 문항들의 이름·선택지 수·위치(pt)."""
    out = []
    for q in parse_survey(page):
        bb = q.bbox()
        if bb is None:
            continue
        out.append({"page": page.page_no, "key": q.key, "qid": q.qid, "text": q.text,
                    "choices": len(q.choices), "x0": bb[0], "y0": bb[1], "x1": bb[2], "y1": bb[3]})
    return out


def survey_span(questions: list[Question]) -> tuple[int, int] | None:
    """쪽의 본문항 번호 범위(첫, 끝) — 쪽을 넘어 이어지는 설문을 한 행으로 합칠 때 씀.
    번호 체계가 둘이면('문1~5' 인적사항 + '1~12' 본문) 마지막 체계 기준."""
    numbered = [q for q in questions if q.no is not None]
    if not numbered:
        return None
    pre = numbered[-1].pre
    nos = [q.no for q in numbered if q.pre == pre]
    return (min(nos), max(nos))


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


def survey_row(questions: list[Question], stable_keys: bool = False) -> dict:
    """문항 → 엑셀 한 행. 열 = '번호_질문'(번호 없는 항목은 이름), 값 = '번호:선택지'(복수는 ;),
    주관식은 글.
    stable_keys(스캔본): 열 이름을 '문항NN'(순서)로 — OCR 글자 흔들림에도 열이 일치."""
    row: dict = {}
    flags: dict = {}
    for i, q in enumerate(questions):
        if stable_keys:
            key = f"문항{i + 1:02d}"
        elif q.qid == q.text or not q.text:
            key = q.qid
        else:
            key = f"{q.qid}_{q.text[:18].rstrip('?？. ')}"
        if key in row:
            key = f"{key}({i + 1})"
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
    """페이지 하나를 설문 행으로. 척도표(리커트)면 격자 판정, 아니면 문항 목록 파서.
    스캔(OCR) 페이지면 잉크 밀도로 표시를 판정한다.
    문항 목록 쪽이면 '_문항범위'=(첫 번호, 끝 번호)와 '_문항수'를 같이 돌려준다(쪽 병합용)."""
    from core.likert import extract_likert
    lk = extract_likert(page, pdf_path=pdf_path)
    if lk is not None:
        return lk
    qs = parse_survey(page)
    if pdf_path and getattr(page, "ocr", False):
        try:
            mark_by_ink(pdf_path, page, qs)
        except Exception:  # noqa: BLE001  (렌더 실패 등 — 글자 표시만으로)
            pass
    row = survey_row(qs, stable_keys=bool(getattr(page, "ocr", False)))
    span = survey_span(qs)
    if span:
        row["_문항범위"] = span
    row["_문항수"] = len(qs)
    return row


def survey_title(pdf_path: str, page_no: int) -> str:
    """설문지 제목 — 쪽 위쪽(30%)의 큰 글씨 줄 중 섹션 머리글('Ⅰ. 의료서비스의 질')·
    안내문(※, <<)이 아닌 가장 큰 줄. 앞의 짧은 영문 토큰('ID')은 뗀다. 글자 레이어가 없으면 ''."""
    import fitz

    try:
        doc = fitz.open(pdf_path)
    except Exception:  # noqa: BLE001
        return ""
    try:
        page = doc[page_no]
        h = page.rect.height
        spans = []
        for b in page.get_text("dict").get("blocks", []):
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    t = (s.get("text") or "").strip()
                    if t:
                        spans.append((s["bbox"], float(s.get("size", 0)), t))
    finally:
        doc.close()
    if len(spans) < 3:
        return ""
    med = statistics.median(sz for _, sz, _ in spans)
    lines: dict[int, list] = {}
    for s in spans:
        if s[0][1] < h * 0.30:
            lines.setdefault(round(s[0][1] / 6), []).append(s)
    cands = []
    for row in lines.values():
        row.sort(key=lambda s: s[0][0])
        size = max(s[1] for s in row)
        if size < max(med * 1.15, med + 1.5):
            continue
        words = [s[2] for s in row if s[1] >= size * 0.6]
        if words and re.fullmatch(r"[A-Za-z]{1,3}", words[0]):
            words = words[1:]                       # 'ID' 같은 칸 이름
        text = normalize(" ".join(words))
        if not text or _NOISE.match(text):
            continue
        cands.append((size, -min(s[0][1] for s in row), text))
    if not cands:
        return ""
    return max(cands)[2]


def merge_survey_rows(base: dict, nxt: dict, offset: int) -> None:
    """쪽을 넘어 이어지는 설문의 다음 쪽 행을 앞 쪽 행에 합친다(스캔본 '문항NN' 열은 번호를 이어붙임)."""
    def _shift(k: str) -> str:
        m = re.fullmatch(r"문항(\d{2,})", k)
        return f"문항{int(m.group(1)) + offset:02d}" if m else k
    flags = dict(base.get("_이상치", {}))
    for k, v in nxt.items():
        if k.startswith("_"):
            continue
        base[_shift(k)] = v
    for k, v in nxt.get("_이상치", {}).items():
        flags[_shift(k)] = v
    if flags:
        base["_이상치"] = flags
