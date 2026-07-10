"""LLM 자동 양식 이해 — Claude API로 표 칸의 '의미'를 판단해 추출 항목을 자동 제안·명명.

선택(옵션) 기능. 표 칸(테두리)은 우리가 좌표를 정확히 알고 있으므로, Claude에는
'칸 텍스트 + 위치'만 보내 "어느 칸이 추출할 데이터 값이고 이름이 무엇인지"만 판단시킨다.
→ 좌표를 모델이 지어내지 않아 안정적이고, 좌표 계산은 규칙 기반 그대로 재사용한다.

⚠️ 개인정보/보안: 이 기능은 샘플 양식 1건의 '칸 글자'를 Claude(외부 API)로 보낸다.
대량 실데이터 추출은 계속 로컬에서만 처리된다. 화면에서 명확히 안내하고, 켜야만 동작.
"""
from __future__ import annotations

import json
import os

from core.pdf_reader import detect_cells

# 항상 최신·최상위 모델을 기본값으로. 비용을 낮추려면 환경변수로 교체 가능.
_MODEL = os.environ.get("FIELD_SURVEY_LLM_MODEL", "claude-opus-4-8")
# 칸이 너무 많으면(비정상) 비용 방어
_MAX_CELLS = 1600

_SYSTEM = (
    "당신은 한국 공공기관의 '현장 조사표'(하천·습지·보 제원 등)를 디지털화하는 전문가입니다. "
    "표는 이미 칸(셀) 단위로 감지되어 있고, 각 칸에는 번호·글자·위치가 주어집니다. "
    "당신의 임무는 '데이터로 뽑아야 할 값이 들어가는 칸'만 골라, 각 항목에 사람이 이해하기 쉬운 "
    "짧은 한글 이름을 붙이는 것입니다.\n"
    "규칙:\n"
    "- 값 칸(빈 칸 포함)만 고른다. 라벨 칸(항목 이름 칸), 제목, 안내문, 단위설명 칸은 고르지 않는다.\n"
    "- 이름은 인접한 라벨을 근거로 짓는다. 예: '하천명' 라벨 오른쪽 빈 칸 → 이름 '하천명'.\n"
    "- 하나의 라벨에 값 칸이 여러 개면 각각 구분되게 이름 짓는다. 예: 'X좌표', 'Y좌표'.\n"
    "- 값이 이미 채워진 칸(숫자·좌표·날짜 등)도 대상이다(다른 조사표에선 값이 바뀐다).\n"
    "- label 에는 이름을 지은 근거가 된 라벨 칸의 글자를 그대로 넣는다(없으면 빈 문자열).\n"
    "- 확실히 값 칸이 아닌 것은 넣지 않는다. 과하게 많이 고르기보다 정확하게."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cell": {"type": "integer"},
                    "name": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["cell", "name", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fields"],
    "additionalProperties": False,
}


def available() -> tuple[bool, str]:
    """(사용가능, 안내메시지). 패키지·API 키가 모두 있어야 True."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "AI 기능을 쓰려면 anthropic 패키지가 필요합니다. (pip install -r requirements-ai.txt)"
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return False, (
            "AI 기능을 쓰려면 Claude API 키가 필요합니다. 환경변수 ANTHROPIC_API_KEY 를 설정한 뒤 "
            "프로그램을 다시 시작하세요. (외부 API 호출 — 샘플 양식의 칸 글자만 전송됩니다.)"
        )
    return True, ""


def _collect_cells(pdf_path: str, pages: list) -> tuple[list, list[dict]]:
    """전체 페이지의 칸을 모아 (칸객체리스트, 모델전송용 페이로드) 반환. 인덱스는 전역 통일."""
    flat_cells: list = []
    payload: list[dict] = []
    gi = 0
    for p in pages:
        cells = detect_cells(pdf_path, p.page_no)
        pc = []
        for c in cells:
            flat_cells.append((p.page_no, c))
            pc.append({
                "i": gi,
                "t": (c.text or "")[:40],
                "box": [round(c.x0), round(c.y0), round(c.x1), round(c.y1)],
            })
            gi += 1
        if pc:
            payload.append({"page": p.page_no, "cells": pc})
    return flat_cells, payload


def understand_form(pdf_path: str, pages: list) -> list[dict]:
    """Claude로 추출 항목을 자동 이해·명명 → 픽셀박스 리스트(기존 포맷) 반환.

    표 칸이 없는(스캔) 양식은 대상 칸이 없어 빈 리스트를 반환한다.
    """
    import anthropic

    flat_cells, payload = _collect_cells(pdf_path, pages)
    if not flat_cells:
        return []
    if len(flat_cells) > _MAX_CELLS:
        # 비정상적으로 칸이 많으면 앞부분만(비용 방어)
        payload = _truncate_payload(payload, _MAX_CELLS)

    client = anthropic.Anthropic()
    user = (
        "다음은 감지된 표 칸들입니다(페이지별, i=칸번호, t=글자, box=[x0,y0,x1,y1] PDF좌표). "
        "추출할 값 칸만 골라 이름을 지어 주세요.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    boxes: list[dict] = []
    for f in data.get("fields", []):
        idx = f.get("cell")
        if not isinstance(idx, int) or not (0 <= idx < len(flat_cells)):
            continue
        page_no, c = flat_cells[idx]
        name = (f.get("name") or c.text or "항목").strip()[:20]
        label = (f.get("label") or "").strip()
        boxes.append({
            "field": name,
            "page": page_no,
            "x0": round(c.x0, 1), "y0": round(c.y0, 1),
            "x1": round(c.x1, 1), "y1": round(c.y1, 1),
            "mode": "text",
            "use_anchor": False,
            "suggested": True,
            "from_cell": True,
            "ai": True,
            "anchor": {"label": label, "relation": "right"} if label else None,
        })
    boxes.sort(key=lambda b: (b["page"], b["y0"], b["x0"]))
    for n, b in enumerate(boxes, start=1):
        b["order"] = n
    return boxes


def _truncate_payload(payload: list[dict], limit: int) -> list[dict]:
    out, n = [], 0
    for pg in payload:
        keep = pg["cells"][: max(0, limit - n)]
        n += len(keep)
        if keep:
            out.append({"page": pg["page"], "cells": keep})
        if n >= limit:
            break
    return out
