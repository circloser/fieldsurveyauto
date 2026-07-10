"""추출 엔진 파사드 — 웹 프레임워크에 의존하지 않는 순수 파이프라인.

FastAPI(app/main.py)나 Streamlit 등 어떤 화면이든 이 run() 하나만 호출한다.
  파일들 → 파싱 → 서식판별/보분리 → 스키마 매핑 → 레코드 + 신뢰도 플래그
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.extraction.mapper import Record, map_block
from core.extraction.segmenter import segment
from core.parsers.hwpx_parser import parse_hwpx


@dataclass
class FileStatus:
    name: str
    ok: bool
    record_count: int = 0
    error: str = ""


@dataclass
class ExtractionResult:
    records: list[Record] = field(default_factory=list)
    files: list[FileStatus] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return len(self.records)

    @property
    def flagged_count(self) -> int:
        return sum(1 for r in self.records if r.flags)

    @property
    def ok_files(self) -> int:
        return sum(1 for f in self.files if f.ok)

    @property
    def failed_files(self) -> int:
        return sum(1 for f in self.files if not f.ok)


def _process_one(path: str) -> tuple[list[Record], FileStatus]:
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()

    if ext == ".hwpx":
        doc = parse_hwpx(path)
    elif ext == ".pdf":
        return [], FileStatus(name, False, error="PDF는 다음 단계에서 지원 예정입니다.")
    elif ext == ".hwp":
        return [], FileStatus(
            name, False,
            error="구버전 .hwp 입니다. 한글에서 hwpx로 저장 후 다시 올려주세요.",
        )
    else:
        return [], FileStatus(name, False, error=f"지원하지 않는 형식: {ext}")

    if not doc.ok:
        return [], FileStatus(name, False, error=doc.error)

    records = [map_block(b, name) for b in segment(doc)]
    return records, FileStatus(name, True, record_count=len(records))


def run(paths: list[str]) -> ExtractionResult:
    result = ExtractionResult()
    for path in paths:
        try:
            records, status = _process_one(path)
        except Exception as e:  # noqa: BLE001 — 한 파일 실패가 배치를 멈추지 않도록
            records, status = [], FileStatus(
                os.path.basename(path), False, error=f"처리 중 오류: {e}"
            )
        result.records.extend(records)
        result.files.append(status)
    return result
