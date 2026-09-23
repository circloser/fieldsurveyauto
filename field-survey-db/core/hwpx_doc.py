"""한글(.hwpx) 문서 만들기 — 사용 설명서 같은 긴 문서를 한글 프로그램 없이 생성한다.

hwpx(OWPML)는 zip 안의 XML 묶음이다. 한글이 만든 서식 파일에서 가져온 헤더(글꼴·문단·테두리 정의, core/hwpx_base/)를
바탕으로 본문(section0.xml)을 직접 만든다. 표는 한글의 진짜 표(hp:tbl)라 열자마자 편집할 수 있고, 그림은 PNG 로 넣는다.
(수생태계 종적 연속성 평가 프로그램 SCE 의 hwpx_out 과 같은 방식.)

단위: HWPUNIT = 1/7200 inch (1 mm ≈ 283.5). 글자 크기 height 1000 = 10 pt.
"""
from __future__ import annotations

import re
import struct
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

BASE_DIR = Path(__file__).resolve().parent / "hwpx_base"
TEXT_WIDTH = 48000          # 본문 폭(A4 세로, 좌우 여백 20 mm)

# 기본 헤더(header.xml)에 이미 있는 스타일 ID
PP_BODY, PP_LEFT, PP_CENTER, PP_CELL, PP_CELL_LEFT = 0, 29, 20, 21, 11
CP_TITLE, CP_BODY, CP_CELL = 17, 10, 12          # 16pt 굵게 / 10pt / 8pt
BF_TABLE, BF_CELL = 4, 4                           # 0.12 mm 실선 사방
# 이 모듈이 헤더에 추가하는 스타일 ID
CP_H1, CP_H2, CP_CELL_BOLD, CP_CAPTION, CP_NOTE, CP_CELL7, CP_CELL7_BOLD = 35, 36, 37, 38, 39, 40, 41
CP_BODY_BOLD = 42                                  # 본문 10pt 굵게
BF_HEAD, BF_SUM = 19, 20                           # 회색 배경(머리글) / 옅은 회색(요약행·알림 상자)

_NEW_CHARPR = {  # id: (height, bold)
    CP_H1: (1300, True), CP_H2: (1100, True), CP_CELL_BOLD: (800, True), CP_CAPTION: (900, True),
    CP_NOTE: (900, False), CP_CELL7: (700, False), CP_CELL7_BOLD: (700, True), CP_BODY_BOLD: (1000, True),
}
_CP_HEIGHT = {CP_TITLE: 1600, CP_BODY: 1000, CP_CELL: 800, **{k: v[0] for k, v in _NEW_CHARPR.items()}}


@dataclass
class Table:
    header: list[list[str]]                         # 머리글 행들(빈 리스트 가능)
    body: list[list]                                # 데이터 행들
    merges: list[tuple[int, int, int, int]] = field(default_factory=list)   # (r1,c1,r2,c2) 0-based
    summary: list[tuple[str, str]] = field(default_factory=list)            # 하단 요약행 (라벨, 값)
    label_cols: int = 2                             # 요약행 라벨이 차지하는 열 수
    widths: list[float] | None = None               # 열 너비 가중치
    font_pt: float = 8
    kind: str = "grid"                              # grid | info | text | box


def _charpr_xml(cid: int, height: int, bold: bool) -> str:
    return (f'<hh:charPr id="{cid}" height="{height}" textColor="#000000" shadeColor="none" useFontSpace="0" '
            f'useKerning="0" symMark="NONE" borderFillIDRef="3"><hh:fontRef hangul="1" latin="1" hanja="0" japanese="0" '
            f'other="0" symbol="0" user="0"/><hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" '
            f'symbol="100" user="100"/><hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            f'<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
            f'<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
            f'{"<hh:bold/>" if bold else ""}<hh:strikeout shape="3D" color="#000000"/></hh:charPr>')


def _borderfill_xml(bid: int, fill: str) -> str:
    b = 'type="SOLID" width="0.12 mm" color="#000000"'
    return (f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
            f'<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
            f'<hh:leftBorder {b}/><hh:rightBorder {b}/><hh:topBorder {b}/><hh:bottomBorder {b}/>'
            f'<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>'
            f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#999999" alpha="0"/></hc:fillBrush></hh:borderFill>')


class HwpxWriter:
    def __init__(self, title: str):
        self.title = title
        self._paras: list[str] = []
        self._preview: list[str] = [title]
        self._pid = 1000
        self._tid = 1
        self._images: list[tuple[str, bytes]] = []     # (항목 id, PNG 내용)

    # ---------------------------------------------------------------- 문단
    def _next_pid(self) -> int:
        self._pid += 1
        return self._pid

    def _lineseg(self, height: int, width: int = TEXT_WIDTH) -> str:
        return (f'<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="{height}" textheight="{height}" '
                f'baseline="{int(height * 0.85)}" spacing="{int(height * 0.6)}" horzpos="0" horzsize="{width}" '
                f'flags="393216"/></hp:linesegarray>')

    def _p(self, text: str, cp: int, pp: int, width: int = TEXT_WIDTH, page_break: bool = False) -> str:
        return self._p_runs([(text, cp)], pp, width, page_break)

    def _p_runs(self, runs: list[tuple[str, int]], pp: int, width: int = TEXT_WIDTH, page_break: bool = False) -> str:
        """글자 모양이 다른 조각(run)들로 된 문단."""
        body = "".join(f'<hp:run charPrIDRef="{cp}">' + (f"<hp:t>{escape(t)}</hp:t>" if t else "<hp:t/>") + "</hp:run>"
                       for t, cp in runs) or f'<hp:run charPrIDRef="{CP_BODY}"><hp:t/></hp:run>'
        h = max((_CP_HEIGHT.get(cp, 1000) for _, cp in runs), default=1000)
        return (f'<hp:p id="{self._next_pid()}" paraPrIDRef="{pp}" styleIDRef="0" pageBreak="{int(page_break)}" '
                f'columnBreak="0" merged="0">{body}{self._lineseg(h, width)}</hp:p>')

    def heading(self, text: str, level: int, page_break: bool = False) -> None:
        cp = CP_H1 if level <= 1 else CP_H2 if level == 2 else CP_CAPTION if level >= 4 else CP_H2
        if not page_break:
            self._paras.append(self._p("", CP_BODY, PP_BODY))
        self._paras.append(self._p(text, cp, PP_LEFT, page_break=page_break))
        self._preview.append(text)

    def rich(self, segments: list[tuple[str, bool]]) -> None:
        """본문 문단 — (글, 굵게 여부) 조각들."""
        self._paras.append(self._p_runs([(t, CP_BODY_BOLD if b else CP_BODY) for t, b in segments if t], PP_BODY))
        self._preview.append("".join(t for t, _ in segments))

    def para(self, text: str, kind: str = "body") -> None:
        cp = {"body": CP_BODY, "caption": CP_CAPTION, "note": CP_NOTE}.get(kind, CP_BODY)
        pp = PP_CENTER if kind == "caption" else PP_BODY
        self._paras.append(self._p(text, cp, pp))
        self._preview.append(text)

    # ---------------------------------------------------------------- 표
    def table(self, t: Table) -> None:
        rows: list[list[str]] = [[str(_c(x)) for x in r] for r in t.header + t.body]
        ncols = max((len(r) for r in rows), default=1)
        rows = [r + [""] * (ncols - len(r)) for r in rows]
        nhead = len(t.header)
        merges = list(t.merges)
        for label, value in t.summary:
            r = len(rows)
            rows.append([label] + [""] * (t.label_cols - 1) + [value] + [""] * (ncols - t.label_cols - 1))
            if t.label_cols > 1:
                merges.append((r, 0, r, t.label_cols - 1))
            if ncols - t.label_cols > 1:
                merges.append((r, t.label_cols, r, ncols - 1))
        nrows = len(rows)
        weights = list(t.widths or [1.0] * ncols)
        weights = (weights + [1.0] * ncols)[:ncols]
        tot = sum(weights)
        widths = [int(TEXT_WIDTH * w / tot) for w in weights]
        widths[-1] += TEXT_WIDTH - sum(widths)
        span = {(r1, c1): (r2 - r1 + 1, c2 - c1 + 1) for (r1, c1, r2, c2) in merges}
        covered = {(r, c) for (r1, c1, r2, c2) in merges for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)
                   if (r, c) != (r1, c1)}
        empty = [r for r in range(nrows) if all((r, c) in covered for c in range(ncols))]
        if empty:   # 셀이 하나도 없는 행은 한글이 열지 못한다
            keep = [r for r in range(nrows) if r not in empty]

            def nr(r: int) -> int:
                return sum(1 for k in keep if k <= r) - 1
            merges = [(nr(r1), c1, nr(r2), c2) for (r1, c1, r2, c2) in merges]
            merges = [m for m in merges if (m[0], m[1]) != (m[2], m[3])]
            rows = [rows[r] for r in keep]
            nhead = sum(1 for k in keep if k < nhead)
            nrows = len(rows)
            span = {(r1, c1): (r2 - r1 + 1, c2 - c1 + 1) for (r1, c1, r2, c2) in merges}
            covered = {(r, c) for (r1, c1, r2, c2) in merges for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)
                       if (r, c) != (r1, c1)}
        small = t.font_pt <= 7
        cp_n, cp_b = (CP_CELL7, CP_CELL7_BOLD) if small else (CP_CELL, CP_CELL_BOLD)
        prose = t.kind in ("text", "box")          # 설명 글이 든 표·알림 상자: 9pt, 왼쪽 정렬
        if prose:
            cp_n, cp_b = CP_NOTE, CP_CAPTION
        line_h = 900 if small else 1000
        row_h = []
        for r, row in enumerate(rows):
            lines = max((row[c].count("\n") + 1 for c in range(ncols) if (r, c) not in covered), default=1)
            row_h.append(lines * line_h + 300)
        n_sum = len(t.summary)
        tr_xml = []
        for r in range(nrows):
            tcs = []
            for c in range(ncols):
                if (r, c) in covered:
                    continue
                rs, cs = span.get((r, c), (1, 1))
                is_head = r < nhead
                is_sum = r >= nrows - n_sum
                is_info_label = t.kind == "info" and ((r == 0 and c % 2 == 0) or (r == 1 and c == 0))
                bold = is_head or is_sum or is_info_label
                bf = BF_HEAD if (is_head or is_info_label) else BF_SUM if (is_sum or t.kind == "box") else BF_CELL
                pp = PP_CELL_LEFT if ((t.kind == "info" and not is_info_label) or (prose and not is_head)) else PP_CELL
                w = sum(widths[c:c + cs])
                h = sum(row_h[r:r + rs])
                lines = rows[r][c].split("\n") or [""]
                ps = "".join(self._p(ln, cp_b if bold else cp_n, pp, w - 400) for ln in lines)
                tcs.append(
                    f'<hp:tc name="" header="{1 if is_head else 0}" hasMargin="0" protect="0" editable="0" dirty="0" '
                    f'borderFillIDRef="{bf}"><hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                    f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" '
                    f'hasTextRef="0" hasNumRef="0">{ps}</hp:subList><hp:cellAddr colAddr="{c}" rowAddr="{r}"/>'
                    f'<hp:cellSpan colSpan="{cs}" rowSpan="{rs}"/><hp:cellSz width="{w}" height="{h}"/>'
                    f'<hp:cellMargin left="200" right="200" top="100" bottom="100"/></hp:tc>')
            tr_xml.append("<hp:tr>" + "".join(tcs) + "</hp:tr>")
        W, H = sum(widths), sum(row_h)
        tid = self._tid
        self._tid += 1
        tbl = (f'<hp:tbl id="{tid}" zOrder="{tid}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" '
               f'lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" rowCnt="{nrows}" colCnt="{ncols}" '
               f'cellSpacing="0" borderFillIDRef="{BF_TABLE}" noAdjust="1"><hp:sz width="{W}" widthRelTo="ABSOLUTE" '
               f'height="{H}" heightRelTo="ABSOLUTE" protect="0"/><hp:pos treatAsChar="0" affectLSpacing="0" '
               f'flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" '
               f'vertAlign="TOP" horzAlign="CENTER" vertOffset="0" horzOffset="0"/><hp:outMargin left="0" right="0" '
               f'top="141" bottom="141"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>{"".join(tr_xml)}</hp:tbl>')
        self._paras.append(
            f'<hp:p id="{self._next_pid()}" paraPrIDRef="{PP_CENTER}" styleIDRef="0" pageBreak="0" columnBreak="0" '
            f'merged="0"><hp:run charPrIDRef="{CP_BODY}">{tbl}<hp:t/></hp:run>{self._lineseg(200)}</hp:p>')
        for row in rows[:3]:
            self._preview.append("<" + "><".join(row) + ">")

    # ---------------------------------------------------------------- 그림
    def image(self, path: str | Path, width_mm: float = 160.0) -> None:
        """PNG 그림을 본문에 넣는다(글자처럼 취급, 가운데 정렬, 가로 width_mm)."""
        data = Path(path).read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"PNG 그림만 넣을 수 있습니다: {path}")
        px_w, px_h = struct.unpack(">II", data[16:24])
        item = f"image{len(self._images) + 1}"
        self._images.append((item, data))
        W = min(int(width_mm * 283.465), TEXT_WIDTH)
        H = int(W * px_h / px_w)
        oid = self._tid
        self._tid += 1
        pic = (f'<hp:pic id="{2000000 + oid}" zOrder="{oid}" numberingType="NONE" textWrap="TOP_AND_BOTTOM" '
               f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="0" instid="{3000000 + oid}" '
               f'reverse="0"><hp:offset x="0" y="0"/><hp:orgSz width="{W}" height="{H}"/>'
               f'<hp:curSz width="{W}" height="{H}"/><hp:flip horizontal="0" vertical="0"/>'
               f'<hp:rotationInfo angle="0" centerX="{W // 2}" centerY="{H // 2}" rotateimage="1"/>'
               f'<hp:renderingInfo><hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/></hp:renderingInfo>'
               f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{W}" y="0"/><hc:pt2 x="{W}" y="{H}"/>'
               f'<hc:pt3 x="0" y="{H}"/></hp:imgRect><hp:imgClip left="0" right="{px_w * 75}" top="0" '
               f'bottom="{px_h * 75}"/><hp:inMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hc:img binaryItemIDRef="{item}" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/><hp:effects/>'
               f'<hp:sz width="{W}" widthRelTo="ABSOLUTE" height="{H}" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
               f'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>')
        self._paras.append(
            f'<hp:p id="{self._next_pid()}" paraPrIDRef="{PP_CENTER}" styleIDRef="0" pageBreak="0" columnBreak="0" '
            f'merged="0"><hp:run charPrIDRef="{CP_BODY}">{pic}<hp:t/></hp:run>{self._lineseg(H)}</hp:p>')

    # ---------------------------------------------------------------- 저장
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (BASE_DIR / "Contents" / "header.xml").read_text(encoding="utf-8")
        n_bf = int(re.search(r'<hh:borderFills itemCnt="(\d+)">', header).group(1))
        header = header.replace(f'<hh:borderFills itemCnt="{n_bf}">', f'<hh:borderFills itemCnt="{n_bf + 2}">', 1)
        header = header.replace("</hh:borderFills>", _borderfill_xml(BF_HEAD, "#E7E6E6") + _borderfill_xml(BF_SUM, "#F2F2F2")
                                + "</hh:borderFills>", 1)
        n_cp = int(re.search(r'<hh:charProperties itemCnt="(\d+)">', header).group(1))
        header = header.replace(f'<hh:charProperties itemCnt="{n_cp}">',
                                f'<hh:charProperties itemCnt="{n_cp + len(_NEW_CHARPR)}">', 1)
        header = header.replace("</hh:charProperties>",
                                "".join(_charpr_xml(i, h, b) for i, (h, b) in _NEW_CHARPR.items()) + "</hh:charProperties>", 1)
        sec_open = (BASE_DIR / "sec_open.xml").read_text(encoding="utf-8")
        secpr = (BASE_DIR / "secpr_run.xml").read_text(encoding="utf-8")
        first = (f'<hp:p id="{self._next_pid()}" paraPrIDRef="{PP_CENTER}" styleIDRef="0" pageBreak="0" columnBreak="0" '
                 f'merged="0">{secpr}<hp:run charPrIDRef="{CP_TITLE}"><hp:t>{escape(self.title)}</hp:t></hp:run>'
                 f'{self._lineseg(1600)}</hp:p>')
        section = sec_open + first + "".join(self._paras) + "</hs:sec>"
        hpf = (BASE_DIR / "Contents" / "content.hpf").read_text(encoding="utf-8")
        hpf = re.sub(r'<opf:item id="image1"[^>]*/>', "", hpf)
        items = "".join(f'<opf:item id="{i}" href="BinData/{i}.png" media-type="image/png" isEmbeded="1"/>'
                        for i, _ in self._images)
        hpf = hpf.replace("</opf:manifest>", items + "</opf:manifest>", 1)
        hpf = re.sub(r"<opf:title>.*?</opf:title>", f"<opf:title>{escape(self.title)}</opf:title>", hpf)
        now = datetime.now()
        hpf = re.sub(r'(<opf:meta name="(?:CreatedDate|ModifiedDate)" content="text">)[^<]*',
                     lambda m: m.group(1) + now.strftime("%Y-%m-%dT%H:%M:%SZ"), hpf)
        preview = "\n".join(self._preview[:200])
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("version.xml", (BASE_DIR / "version.xml").read_text(encoding="utf-8"), zipfile.ZIP_DEFLATED)
            z.writestr("Contents/header.xml", header, zipfile.ZIP_DEFLATED)
            z.writestr("Contents/section0.xml", section, zipfile.ZIP_DEFLATED)
            z.writestr("Contents/content.hpf", hpf, zipfile.ZIP_DEFLATED)
            for item, data in self._images:
                z.writestr(f"BinData/{item}.png", data, zipfile.ZIP_STORED)
            z.writestr("settings.xml", (BASE_DIR / "settings.xml").read_text(encoding="utf-8"), zipfile.ZIP_DEFLATED)
            for name in ("container.xml", "container.rdf", "manifest.xml"):
                z.writestr(f"META-INF/{name}", (BASE_DIR / "META-INF" / name).read_text(encoding="utf-8"), zipfile.ZIP_DEFLATED)
            z.writestr("Preview/PrvText.txt", preview, zipfile.ZIP_DEFLATED)
        return path


def _c(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return str(int(x)) if x.is_integer() else f"{x:g}"
    return x
