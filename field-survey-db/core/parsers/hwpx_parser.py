"""HWPX 파서 — 무료(표준 라이브러리 zip + XML)로 표 셀을 추출.

HWPX 구조: ZIP 컨테이너. 본문은 Contents/section*.xml.
  <hp:tbl> ─ <hp:tr> ─ <hp:tc>            (표 → 행 → 셀)
     <hp:tc> 안에: <hp:cellAddr colAddr rowAddr/>, <hp:cellSpan colSpan rowSpan/>
     텍스트: <hp:subList> ─ <hp:p> ─ <hp:run> ─ <hp:t>

R9 대응: 한 셀 값이 여러 <hp:t> 런으로 쪼개지므로, 같은 문단(p)의 런은 붙여서,
문단 사이는 줄바꿈으로 이어붙인다(구분자 임의 삽입 금지).
"""
from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

from core.normalize import normalize
from core.parsers.base import Cell, ParsedDoc, Table


def _local(tag: str) -> str:
    """네임스페이스를 떼고 지역 태그명만 반환 (예: '{...}tc' -> 'tc')."""
    return tag.rsplit("}", 1)[-1]


def _run_text(run: ET.Element) -> str:
    """<hp:run> 안 모든 <hp:t> 텍스트."""
    parts: list[str] = []
    for t in run.iter():
        if _local(t.tag) == "t":
            parts.append("".join(t.itertext()))
    return "".join(parts)


def _cell_text(tc: ET.Element, bold_ids: set[str]) -> tuple[str, str]:
    """하나의 <hp:tc> 안 텍스트를 (전체, 굵게만) 으로 반환.

    같은 문단의 run 은 붙이고, 문단 사이는 줄바꿈. 굵게는 run 의 charPrIDRef 로 판정.
    """
    paras: list[str] = []
    bold_parts: list[str] = []
    for p in tc.iter():
        if _local(p.tag) != "p":
            continue
        runs: list[str] = []
        for run in p.iter():
            if _local(run.tag) != "run":
                continue
            txt = _run_text(run)
            if not txt:
                continue
            runs.append(txt)
            if run.get("charPrIDRef") in bold_ids:
                bold_parts.append(txt)
        if runs:
            paras.append("".join(runs))
    return "\n".join(paras), "".join(bold_parts)


def _bold_charpr_ids(header_xml: bytes) -> set[str]:
    """header.xml 에서 굵게(bold)인 charPr id 집합을 추출."""
    ids: set[str] = set()
    try:
        root = ET.fromstring(header_xml)
    except ET.ParseError:
        return ids
    for cp in root.iter():
        if _local(cp.tag) != "charPr":
            continue
        cid = cp.get("id")
        if cid is None:
            continue
        for child in cp:
            if _local(child.tag) == "bold":
                ids.add(cid)
                break
    return ids


def _parse_table(tbl: ET.Element, bold_ids: set[str]) -> Table:
    table = Table()
    for tc in tbl.iter():
        if _local(tc.tag) != "tc":
            continue
        row = col = 0
        rspan = cspan = 1
        width = height = 0
        for child in tc:
            lt = _local(child.tag)
            if lt == "cellAddr":
                row = int(child.get("rowAddr", "0"))
                col = int(child.get("colAddr", "0"))
            elif lt == "cellSpan":
                rspan = int(child.get("rowSpan", "1"))
                cspan = int(child.get("colSpan", "1"))
            elif lt == "cellSz":
                width = int(child.get("width", "0"))
                height = int(child.get("height", "0"))
        raw, bold = _cell_text(tc, bold_ids)
        table.cells.append(
            Cell(
                row=row,
                col=col,
                row_span=max(1, rspan),
                col_span=max(1, cspan),
                raw_text=raw,
                text=normalize(raw),
                bold_text=normalize(bold),
                width=width,
                height=height,
            )
        )
    table.build_grid()
    return table


def parse_hwpx(path: str) -> ParsedDoc:
    doc = ParsedDoc(source_path=str(path), file_type="hwpx")
    try:
        with zipfile.ZipFile(path) as zf:
            section_names = sorted(
                n for n in zf.namelist()
                if n.startswith("Contents/section") and n.endswith(".xml")
            )
            if not section_names:
                doc.ok = False
                doc.error = "본문(section*.xml)을 찾지 못했습니다."
                return doc

            # 굵게 charPr id 목록(있으면)
            bold_ids: set[str] = set()
            if "Contents/header.xml" in zf.namelist():
                bold_ids = _bold_charpr_ids(zf.read("Contents/header.xml"))

            all_text_parts: list[str] = []
            for name in section_names:
                xml_bytes = zf.read(name)
                root = ET.fromstring(xml_bytes)
                for el in root.iter():
                    if _local(el.tag) == "tbl":
                        table = _parse_table(el, bold_ids)
                        if table.cells:
                            doc.tables.append(table)
                # 앵커 탐색용 전체 본문(문서 순서대로 모든 <hp:t>)
                for el in root.iter():
                    if _local(el.tag) == "t":
                        all_text_parts.append("".join(el.itertext()))
            doc.full_text = normalize("\n".join(all_text_parts))
    except zipfile.BadZipFile:
        doc.ok = False
        doc.error = "hwpx 파일을 열 수 없습니다(손상되었거나 형식이 다릅니다)."
    except ET.ParseError as e:
        doc.ok = False
        doc.error = f"본문 XML 해석 실패: {e}"
    return doc
