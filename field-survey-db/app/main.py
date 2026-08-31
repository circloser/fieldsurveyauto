"""FastAPI 앱 진입점 — 업로드/처리/검수/다운로드 라우트.

화면은 core.pipeline.run() 파사드만 호출한다(엔진과 화면 분리).
"""
from __future__ import annotations

import copy
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from core.analysis import analyze_records, merge_outlier_flags
from core.accumulate import AccumulateStore
from core.bundle import _norm_title, extract_bundle, group_rows
from core.excel.writer import write_excel
from core.extraction.form_detector import FORM_LABELS_KO
from core.extraction.schema.vision_schemas import vision_schema
from core.parsers.hwpx_parser import parse_hwpx
from core.pipeline import ExtractionResult, run
from core.review.store import CorrectionStore
from core.pdf_pipeline import (
    apply_pixel_template,
    field_order as pdf_field_order,
    match_bundles,
    match_pages,
    suggest_cells_maximal,
    suggest_pixel_boxes,
    to_pdf,
)
from core.pdf_reader import read_pdf, render_page_png
from core.template.apply import apply_template, field_order
from core.template.designer import grid_dto, suggest_boxes
from core.template.store import TemplateStore
from core.template.writer import write_bundle_excel, write_template_excel

config.ensure_dirs()

app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)


@app.middleware("http")
async def _no_cache_static(request, call_next):
    """화면 파일(html/css/js)은 캐시 금지 — 업데이트가 즉시 반영되게.

    브라우저가 옛 css/js를 캐시로 계속 쓰면 '업데이트가 안 된' 것처럼 보인다.
    로컬 단일 사용자 앱이라 캐시를 꺼도 성능 손해가 없다.
    """
    response = await call_next(request)
    p = request.url.path
    if p == "/" or p.startswith("/static") or p.endswith((".html", ".css", ".js")):
        response.headers["Cache-Control"] = "no-store"
    return response

_STORE = CorrectionStore(config.DATA_DIR / "corrections.json")
_TEMPLATES = TemplateStore(config.DATA_DIR / "templates.json")
# 마지막 처리 결과(다운로드/검수용). 로컬 단일 사용자 기준의 단순 보관.
_LAST: dict[str, object] = {"excel_path": None, "result": None}
_DESIGNER: dict[str, object] = {"excel_path": None}
_PDF_DOCS: dict[str, object] = {}   # doc_id -> {pdf_path, doc(PdfDoc)}
_PDF_APPLY: dict[str, object] = {"excel_path": None}
_REPORT_DOCS: dict[str, str] = {}   # report_id -> 원본 양식 xlsx 경로
# AI 번들 자동추출 결과(다운로드·검수용)
_VISION: dict[str, object] = {"excel_path": None, "rows": []}
# 회차 누적 DB(세션을 넘어 양식별로 축적) — 디스크에 영속
_ACCUM = AccumulateStore(config.OUTPUT_DIR / "누적DB.json")


def _regenerate_excel() -> str:
    result: ExtractionResult = _LAST["result"]  # type: ignore[assignment]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = config.OUTPUT_DIR / f"조사데이터_DB_{stamp}.xlsx"
    write_excel(result, str(excel_path))
    _LAST["excel_path"] = str(excel_path)
    return str(excel_path)


def _record_dto(rec) -> dict:
    return {
        "key": rec.record_key,
        "파일명": rec.source_file,
        "서식": FORM_LABELS_KO.get(rec.form_type, rec.form_type),
        "form_type": rec.form_type,
        "보명칭": rec.structure_name,
        "보코드": rec.structure_code,
        "완성도": rec.field_completeness,
        "values": rec.values,
        "flags": rec.flags,
        "종수": len(rec.table_rows),
    }


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": config.APP_VERSION})


@app.get("/")
def index() -> FileResponse:
    # 랜딩(시작) 화면 — AI 자동추출 / 템플릿 디자이너 / 환경설정 선택
    return FileResponse(config.STATIC_DIR / "landing.html")


@app.post("/api/process")
async def process(files: list[UploadFile]) -> JSONResponse:
    """업로드된 파일들을 저장 → 추출 → 교정 반영 → 엑셀 생성 → 통계 반환."""
    if not files:
        return JSONResponse({"error": "파일이 없습니다."}, status_code=400)

    # 요청별 폴더에 원본 파일명 그대로 저장(교정 키 안정성 위해 uuid 접두어 제거)
    req_dir = config.UPLOAD_DIR / uuid.uuid4().hex[:8]
    req_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        saved_paths.append(str(dest))

    result = run(saved_paths)
    _STORE.apply_to(result.records)  # 이전 교정 재적용
    _LAST["result"] = result
    _regenerate_excel()

    return JSONResponse({
        "files": [
            {"name": f.name, "ok": f.ok, "records": f.record_count, "error": f.error}
            for f in result.files
        ],
        "stats": {
            "files_ok": result.ok_files,
            "files_failed": result.failed_files,
            "records": result.total_records,
            "flagged": result.flagged_count,
        },
        "records": [_record_dto(r) for r in result.records],
    })


@app.get("/api/records")
def records() -> JSONResponse:
    result: ExtractionResult | None = _LAST.get("result")  # type: ignore[assignment]
    if not result:
        return JSONResponse({"records": []})
    return JSONResponse({"records": [_record_dto(r) for r in result.records]})


@app.post("/api/correct")
def correct(payload: dict = Body(...)) -> JSONResponse:
    """검수 수정 저장 → 레코드/엑셀 갱신."""
    key = payload.get("key")
    field = payload.get("field")
    value = payload.get("value", "")
    if not key or not field:
        return JSONResponse({"error": "key/field가 필요합니다."}, status_code=400)

    _STORE.set(key, field, value)
    result: ExtractionResult | None = _LAST.get("result")  # type: ignore[assignment]
    if result:
        _STORE.apply_to(result.records)
        _regenerate_excel()
        updated = next((r for r in result.records if r.record_key == key), None)
        return JSONResponse({"ok": True, "record": _record_dto(updated) if updated else None,
                             "flagged": result.flagged_count})
    return JSONResponse({"ok": True})


# ─────────────── 템플릿 디자이너 ───────────────

@app.get("/designer")
def designer_page() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "designer.html")


@app.post("/api/designer/load")
async def designer_load(file: UploadFile) -> JSONResponse:
    """샘플 양식 하나를 파싱해 격자 + 자동제안 박스를 반환."""
    req_dir = config.UPLOAD_DIR / ("tpl_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    dest = req_dir / (file.filename or "sample.hwpx")
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if dest.suffix.lower() != ".hwpx":
        return JSONResponse({"error": "지금은 hwpx 양식만 지원합니다(PDF는 다음 단계)."},
                            status_code=400)
    doc = parse_hwpx(str(dest))
    if not doc.ok:
        return JSONResponse({"error": doc.error}, status_code=400)
    return JSONResponse({
        "filename": file.filename,
        "tables": grid_dto(doc),
        "boxes": suggest_boxes(doc),
    })


def _tpl_pdf_path(name: str):
    """템플릿 이름 → 함께 저장된 양식 PDF 경로(파일명 안전화)."""
    safe = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "template"
    return config.TEMPLATE_PDF_DIR / f"{safe}.pdf"


@app.post("/api/designer/save")
def designer_save(payload: dict = Body(...)) -> JSONResponse:
    name = (payload.get("name") or "").strip()
    boxes = payload.get("boxes") or []
    if not name:
        return JSONResponse({"error": "템플릿 이름이 필요합니다."}, status_code=400)
    _TEMPLATES.save(name, boxes)
    # 지금 열려 있는 양식 PDF를 템플릿과 함께 보관 → 나중에 불러올 때 그대로 보여줌
    pdf_saved = False
    doc_id = (payload.get("doc_id") or "").strip()
    entry = _PDF_DOCS.get(doc_id)
    if entry:
        try:
            shutil.copyfile(entry["pdf_path"], _tpl_pdf_path(name))
            pdf_saved = True
        except OSError:
            pass  # PDF 보관 실패해도 박스 저장은 유효
    return JSONResponse({"ok": True, "pdf_saved": pdf_saved,
                         "templates": _TEMPLATES.list_names()})


@app.get("/api/designer/templates")
def designer_templates() -> JSONResponse:
    return JSONResponse({"templates": _TEMPLATES.list_names()})


@app.get("/api/designer/template")
def designer_template_get(name: str) -> JSONResponse:
    tpl = _TEMPLATES.get(name)
    if not tpl:
        return JSONResponse({"error": "템플릿을 찾을 수 없습니다."}, status_code=404)
    out = dict(tpl)
    # 함께 저장된 양식 PDF가 있으면 문서로 등록해 캔버스에 바로 보여준다
    pdf = _tpl_pdf_path(name)
    if pdf.exists():
        try:
            doc = read_pdf(str(pdf))
            doc_id = uuid.uuid4().hex[:10]
            _PDF_DOCS[doc_id] = {"pdf_path": str(pdf), "doc": doc}
            out["doc_id"] = doc_id
            out["pages"] = [{"page_no": p.page_no, "width": p.width, "height": p.height,
                             "needs_ocr": p.needs_ocr, "ocr": getattr(p, "ocr", False)}
                            for p in doc.pages]
        except Exception:  # noqa: BLE001
            pass  # PDF가 손상돼도 박스는 그대로 사용 가능(템플릿 모드)
    return JSONResponse(out)


@app.post("/api/designer/template/delete")
def designer_template_delete(payload: dict = Body(...)) -> JSONResponse:
    name = (payload.get("name") or "").strip()
    _TEMPLATES.delete(name)
    pdf = _tpl_pdf_path(name)
    if pdf.exists():
        try:
            pdf.unlink()
        except OSError:
            pass
    return JSONResponse({"ok": True, "templates": _TEMPLATES.list_names()})


@app.post("/api/designer/apply")
async def designer_apply(
    files: list[UploadFile],
    boxes: str = Form(""),
    template: str = Form(""),
) -> JSONResponse:
    """박스(또는 저장된 템플릿)를 여러 파일에 적용해 엑셀 생성."""
    import json as _json

    box_list: list[dict]
    if template:
        tpl = _TEMPLATES.get(template)
        if not tpl:
            return JSONResponse({"error": "템플릿을 찾을 수 없습니다."}, status_code=404)
        box_list = tpl["boxes"]
    else:
        try:
            box_list = _json.loads(boxes) if boxes else []
        except _json.JSONDecodeError:
            return JSONResponse({"error": "박스 형식이 올바르지 않습니다."}, status_code=400)
    if not box_list:
        return JSONResponse({"error": "추출할 박스가 없습니다."}, status_code=400)

    fields = field_order(box_list)
    req_dir = config.UPLOAD_DIR / ("apply_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    failed: list[dict] = []
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        if dest.suffix.lower() != ".hwpx":
            failed.append({"name": uf.filename, "error": "hwpx 아님"})
            continue
        doc = parse_hwpx(str(dest))
        if not doc.ok:
            failed.append({"name": uf.filename, "error": doc.error})
            continue
        row = apply_template(doc, box_list)
        row["_파일명"] = uf.filename
        rows.append(row)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = config.OUTPUT_DIR / f"템플릿추출_{stamp}.xlsx"
    write_template_excel(rows, fields, str(excel_path))
    _DESIGNER["excel_path"] = str(excel_path)

    return JSONResponse({
        "rows": rows,
        "fields": fields,
        "ok_count": len(rows),
        "failed": failed,
    })


@app.get("/api/designer/download")
def designer_download() -> FileResponse:
    path = _DESIGNER.get("excel_path")
    if not path:
        return JSONResponse({"error": "먼저 적용을 실행하세요."}, status_code=404)  # type: ignore[return-value]
    fname = str(path).replace("\\", "/").split("/")[-1]
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=fname,
    )


# ─────────────── PDF 통합 디자이너 (픽셀 박스) ───────────────

@app.get("/pdf-designer")
def pdf_designer_page() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "pdf_designer.html")


@app.post("/api/pdf/load")
async def pdf_load(file: UploadFile) -> JSONResponse:
    """입력(hwpx/pdf) → PDF 변환/읽기 → 페이지 메타 + 자동제안 박스."""
    req_dir = config.UPLOAD_DIR / ("pdf_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    src = req_dir / (file.filename or "sample.hwpx")
    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        pdf_path = to_pdf(str(src), str(config.PDF_CACHE_DIR))
        doc = read_pdf(pdf_path)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if src.suffix.lower() in (".hwpx", ".hwp"):
            msg = (f"hwpx를 PDF로 변환하지 못했습니다. 한글(HWP)이 설치되어 있어야 합니다. "
                   f"(원인: {e}) — PDF 파일을 직접 올리면 한글 없이도 됩니다.")
        return JSONResponse({"error": msg}, status_code=400)

    doc_id = uuid.uuid4().hex[:10]
    _PDF_DOCS[doc_id] = {"pdf_path": pdf_path, "doc": doc}
    # 표 테두리 기반 자동 제안(기본). 스캔본 등 칸이 없으면 단어 방식으로 폴백.
    boxes = _suggest_all(doc, pdf_path)
    return JSONResponse({
        "doc_id": doc_id,
        "filename": file.filename,
        "pages": [{"page_no": p.page_no, "width": p.width, "height": p.height,
                   "needs_ocr": p.needs_ocr, "ocr": getattr(p, "ocr", False)} for p in doc.pages],
        "boxes": boxes,
    })


def _suggest_all(doc, pdf_path: str) -> list[dict]:
    from core.pdf_pipeline import detect_title
    boxes: list[dict] = []
    for page in doc.pages:
        # 페이지 상단 큰 글씨 = 제목(위계 다름) → '제목' 모드 박스로 제안
        t = detect_title(pdf_path, page.page_no)
        if t:
            boxes.append({
                "field": "제목", "page": page.page_no, "mode": "title",
                "x0": t["x0"], "y0": t["y0"], "x1": t["x1"], "y1": t["y1"],
                "use_anchor": False, "suggested": True, "anchor": None,
            })
        # 표 칸 전체에 박스 생성(최대) → 사용자가 삭제. 칸 없으면(스캔) 단어 방식.
        cell_boxes = suggest_cells_maximal(pdf_path, page.page_no)
        boxes.extend(cell_boxes if cell_boxes else suggest_pixel_boxes(page))
    # 문서 위치(페이지→위→왼쪽) 순서로 번호 부여
    boxes.sort(key=lambda b: (b["page"], b["y0"], b["x0"]))
    for i, b in enumerate(boxes):
        b["order"] = i + 1
    return boxes


@app.post("/api/pdf/neighbor_labels")
def pdf_neighbor_labels(payload: dict = Body(...)) -> JSONResponse:
    """박스(값 칸)의 왼쪽·위쪽 라벨 칸 텍스트 — '항목명 전환' 후보."""
    entry = _PDF_DOCS.get(payload.get("doc_id") or "")
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    from core.pdf_pipeline import neighbor_labels
    try:
        out = neighbor_labels(entry["pdf_path"], int(payload.get("page", 0)),
                              {k: payload[k] for k in ("x0", "y0", "x1", "y1")})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"칸을 읽지 못했습니다: {e}"}, status_code=400)
    return JSONResponse(out)


@app.get("/api/pdf/suggest/{doc_id}")
def pdf_suggest(doc_id: str) -> JSONResponse:
    """자동 제안(표 테두리 기반) 다시 계산."""
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    return JSONResponse({"boxes": _suggest_all(entry["doc"], entry["pdf_path"])})


def hwp_installed() -> bool:
    """한글(HWP) 설치 여부 — COM ProgID 레지스트리로 빠르게 확인(한글 실행 안 함)."""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "HWPFrame.HwpObject"))
        return True
    except OSError:
        return False


@app.get("/api/env_status")
def env_status() -> JSONResponse:
    """실행 환경 자동 점검 — 다른 PC에서 처음 켤 때 무엇이 되고 안 되는지 안내용."""
    try:
        from core import ocr as _ocr
        ocr_ok = _ocr.available()
    except Exception:  # noqa: BLE001
        ocr_ok = False
    from core.llm_understand import available as _ai
    ai_ok, _ = _ai()
    return JSONResponse({
        "hwp": hwp_installed(),   # hwpx 변환 가능 여부(없어도 PDF는 가능)
        "ocr": ocr_ok,            # 스캔 PDF 글자 인식(선택)
        "ai": ai_ok,              # AI 자동 이해(선택)
        "hwp_download": "https://www.hancom.com/cs_center/csDownload.do",
    })


@app.get("/api/pdf/ai_status")
def pdf_ai_status() -> JSONResponse:
    """AI 자동 이해 사용 가능 여부(패키지+API키)."""
    from core.llm_understand import available
    ok, msg = available()
    return JSONResponse({"available": ok, "message": msg})


@app.post("/api/pdf/ai_understand/{doc_id}")
def pdf_ai_understand(doc_id: str) -> JSONResponse:
    """Claude API로 양식을 이해해 추출 항목을 자동 제안·명명(선택 기능)."""
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    from core.llm_understand import available, understand_form
    ok, msg = available()
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    try:
        boxes = understand_form(entry["pdf_path"], entry["doc"].pages)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"AI 이해 중 오류: {e}"}, status_code=502)
    if not boxes:
        return JSONResponse(
            {"error": "AI가 추출 항목을 찾지 못했습니다. (표 테두리가 있는 양식에서 동작합니다.)"},
            status_code=422,
        )
    return JSONResponse({"boxes": boxes})


# ─────────────── AI 번들 자동 추출 (템플릿 불필요) ───────────────

@app.get("/ai")
def ai_page() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "ai.html")


# ─────────────── AI 환경설정 (제공자·키, 암호화 저장) ───────────────

@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "settings.html")


@app.get("/api/settings")
def settings_get() -> JSONResponse:
    from core import settings_store
    from core.vision_extract import available
    st = settings_store.status(config.SETTINGS_PATH)
    ok, msg = available()
    st.update({"active_available": ok, "active_message": msg})
    return JSONResponse(st)


@app.post("/api/settings/test")
def settings_test() -> JSONResponse:
    """현재 저장된 설정으로 선택 제공자에 실제 1회 호출 → 연결 성공/실패 확인."""
    from core.vision_extract import analyze_text, available
    ok, msg = available()
    if not ok:
        return JSONResponse({"ok": False, "error": msg}, status_code=400)
    try:
        reply = analyze_text("연결 확인용입니다. 'OK' 라고만 짧게 답하세요.", max_tokens=20)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": _friendly_vision_error(e)})
    return JSONResponse({"ok": True, "provider": config.AI_PROVIDER,
                         "model": config.VISION_MODEL, "reply": (reply or "").strip()[:80]})


@app.post("/api/settings")
def settings_save(payload: dict = Body(...)) -> JSONResponse:
    """제공자·키 저장(키는 DPAPI 암호화). 빈 값은 기존 키 유지. 저장 후 즉시 반영."""
    from core import settings_store
    provider = (payload.get("provider") or "claude").strip()
    incoming = payload.get("keys") or {}
    clear = payload.get("clear") or {}
    cur = settings_store.load(config.SETTINGS_PATH)
    keys = dict(cur["keys"])
    for k in settings_store.PROVIDERS:
        if clear.get(k):
            keys[k] = ""
        else:
            v = (incoming.get(k) or "").strip()
            if v:                       # 빈 값이면 기존 키 유지(실수로 지워지지 않게)
                keys[k] = v
    encrypted = settings_store.save(config.SETTINGS_PATH, provider, keys, cur.get("models"))
    config.reload_ai_settings()         # 재시작 없이 반영
    from core.vision_extract import available
    ok, msg = available()
    return JSONResponse({
        "ok": True, "encrypted": encrypted,
        "status": settings_store.status(config.SETTINGS_PATH),
        "active_available": ok, "active_message": msg,
    })


@app.get("/api/vision/status")
def vision_status() -> JSONResponse:
    from core.vision_extract import available
    ok, msg = available()
    return JSONResponse({"available": ok, "message": msg})


def _vision_groups(rows: list[dict]) -> list[dict]:
    """서식(양식)별 시트 묶음 — 미상 서식은 '양식제목'으로 세분류. core.bundle.group_rows 사용."""
    return group_rows(rows)


def _vision_regenerate_excel() -> str:
    rows: list[dict] = _VISION["rows"]  # type: ignore[assignment]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = config.OUTPUT_DIR / f"AI추출_{stamp}.xlsx"
    write_bundle_excel(_vision_groups(rows), str(excel_path))
    _VISION["excel_path"] = str(excel_path)
    return str(excel_path)


def _friendly_vision_error(e: Exception) -> str:
    """Vision 호출 예외를 사용자 안내 문구로. 특히 이미지 403은 계정 한도 안내."""
    msg = str(e)
    low = msg.lower()
    if "403" in msg or "forbidden" in low or "request not allowed" in low:
        return ("이미지(Vision) 요청이 거부됐습니다(403). 텍스트는 되는데 이미지만 막히면 보통 "
                "Anthropic 계정의 '이미지 사용 한도' 초과입니다. 콘솔에서 사용량/지출 한도를 "
                "확인하거나 잠시 후 다시 시도하세요. (원문: " + msg + ")")
    if "429" in msg or "rate" in low:
        return "요청이 많아 잠시 제한됐습니다(429). 잠시 후 다시 시도하세요. (원문: " + msg + ")"
    return msg


@app.post("/api/vision/extract")
async def vision_extract_files(files: list[UploadFile]) -> JSONResponse:
    """업로드 파일들을 페이지별 서식 자동판별 → Vision 추출 → 서식별 엑셀 + 검수용 결과."""
    from core.vision_extract import available
    ok, msg = available()
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    if not files:
        return JSONResponse({"error": "파일이 없습니다."}, status_code=400)

    req_dir = config.UPLOAD_DIR / ("ai_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    failed: list[dict] = []
    rid = 0
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        try:
            pdf_path = to_pdf(str(dest), str(config.PDF_CACHE_DIR))
            page_rows = extract_bundle(pdf_path)
        except Exception as e:  # noqa: BLE001
            failed.append({"name": uf.filename, "error": _friendly_vision_error(e)})
            continue
        for pr in page_rows:
            label_file = f"{uf.filename} p{pr['page'] + 1}"
            rows.append({
                "_id": rid, "_파일명": label_file,
                "page": pr["page"], "form": pr["form"], "label": pr["label"],
                "form_title": pr.get("form_title", ""),
                "confidence": pr["confidence"], "route_source": pr.get("route_source", ""),
                "values": pr.get("values", {}), "flags": pr.get("flags", {}),
            })
            rid += 1

    # 이상치(오추출 의심) 교차검사 — 같은 '양식'(미상은 양식제목까지) 레코드끼리 비교해 튀는 값에 경고
    def _okey(r: dict) -> tuple:
        return (r["form"], _norm_title(r.get("form_title")))
    for key in {_okey(r) for r in rows}:
        grp = [r for r in rows if _okey(r) == key and r["values"]]
        if len(grp) >= 2:
            merge_outlier_flags([r["values"] for r in grp], [r["flags"] for r in grp])

    _VISION["rows"] = rows
    _vision_regenerate_excel()
    extracted = [r for r in rows if r["values"]]
    return JSONResponse({
        "rows": rows,
        "stats": {
            "files_ok": len({r["_파일명"].rsplit(" p", 1)[0] for r in rows}),
            "files_failed": len(failed),
            "pages": len(rows),
            "extracted": len(extracted),
            "flagged": sum(1 for r in extracted if r["flags"]),
        },
        "failed": failed,
    })


@app.post("/api/vision/correct")
def vision_correct(payload: dict = Body(...)) -> JSONResponse:
    """검수 수정 — 저장된 AI 추출 결과의 한 값을 고치고 엑셀 재생성."""
    rid = payload.get("id")
    field = payload.get("field")
    value = payload.get("value", "")
    rows: list[dict] = _VISION["rows"]  # type: ignore[assignment]
    row = next((r for r in rows if r["_id"] == rid), None)
    if row is None or not field:
        return JSONResponse({"error": "대상을 찾을 수 없습니다."}, status_code=400)
    row["values"][field] = value
    row["flags"].pop(field, None)  # 사람이 확인 → 플래그 해제
    if not value.strip():
        row["flags"][field] = "빈값"
    _vision_regenerate_excel()
    return JSONResponse({"ok": True, "row": row})


@app.post("/api/vision/analyze")
def vision_analyze() -> JSONResponse:
    """추출된 데이터 전체를 AI가 종합·추세 분석(텍스트) → 마크다운 반환."""
    from core.vision_extract import available
    ok, msg = available()
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    rows: list[dict] = _VISION.get("rows") or []  # type: ignore[assignment]
    groups = _vision_groups(rows)
    if not groups:
        return JSONResponse({"error": "먼저 AI 추출을 실행하세요."}, status_code=400)
    try:
        text = analyze_records(groups)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": _friendly_vision_error(e)}, status_code=502)
    return JSONResponse({"analysis": text})


@app.get("/api/vision/download")
def vision_download() -> FileResponse:
    path = _VISION.get("excel_path")
    if not path:
        return JSONResponse({"error": "먼저 AI 추출을 실행하세요."}, status_code=404)  # type: ignore[return-value]
    fname = str(path).replace("\\", "/").split("/")[-1]
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=fname,
    )


def _accum_status() -> dict:
    return {"total": _ACCUM.count(), "by_form": _ACCUM.label_counts()}


@app.post("/api/vision/accumulate")
def vision_accumulate() -> JSONResponse:
    """이번 회차 추출 결과(값 있는 행)를 누적 DB에 추가(양식별). 같은 파일·페이지는 갱신."""
    rows: list[dict] = _VISION.get("rows") or []  # type: ignore[assignment]
    entries = [{
        "_파일명": r.get("_파일명", ""),
        "form": r.get("form"),
        "form_title": r.get("form_title", ""),
        "label": r.get("label", ""),
        "values": r.get("values", {}),
    } for r in rows if r.get("values")]
    if not entries:
        return JSONResponse({"error": "누적할 추출 결과가 없습니다. 먼저 AI 추출을 실행하세요."},
                            status_code=400)
    added = _ACCUM.add(entries)
    return JSONResponse({"ok": True, "added": added, "updated": len(entries) - added,
                         **_accum_status()})


@app.get("/api/vision/accumulated/status")
def vision_accumulated_status() -> JSONResponse:
    return JSONResponse(_accum_status())


@app.post("/api/vision/accumulated/reset")
def vision_accumulated_reset() -> JSONResponse:
    _ACCUM.reset()
    return JSONResponse({"ok": True, **_accum_status()})


@app.get("/api/vision/accumulated/download")
def vision_accumulated_download() -> FileResponse:
    """누적 DB 전체를 양식별 시트로 묶은 엑셀로 내려받는다."""
    stored = _ACCUM.all()
    if not stored:
        return JSONResponse({"error": "누적된 데이터가 없습니다."}, status_code=404)  # type: ignore[return-value]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = config.OUTPUT_DIR / f"누적DB_{stamp}.xlsx"
    write_bundle_excel(group_rows(stored), str(out))
    return FileResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=out.name,
    )


def _editable_pdf(entry: dict, doc_id: str) -> str:
    """문서 PDF를 편집 작업본으로 전환(원본 업로드·템플릿 PDF를 건드리지 않게)."""
    work = config.PDF_CACHE_DIR / f"edit_{doc_id}.pdf"
    if entry["pdf_path"] != str(work):
        shutil.copyfile(entry["pdf_path"], work)
        entry["pdf_path"] = str(work)
    return str(work)


def _pages_dto(doc) -> list[dict]:
    return [{"page_no": p.page_no, "width": p.width, "height": p.height,
             "needs_ocr": p.needs_ocr, "ocr": getattr(p, "ocr", False)} for p in doc.pages]


@app.post("/api/pdf/pages/delete")
def pdf_pages_delete(payload: dict = Body(...)) -> JSONResponse:
    """양식에서 페이지 삭제 — 필요 없는 장을 빼고 템플릿을 구성."""
    entry = _PDF_DOCS.get(payload.get("doc_id") or "")
    page_no = int(payload.get("page_no", -1))
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    import fitz
    path = _editable_pdf(entry, payload["doc_id"])
    src = fitz.open(path)
    if len(src) <= 1:
        src.close()
        return JSONResponse({"error": "마지막 페이지는 삭제할 수 없습니다."}, status_code=400)
    if not (0 <= page_no < len(src)):
        src.close()
        return JSONResponse({"error": "잘못된 페이지 번호입니다."}, status_code=400)
    src.delete_page(page_no)
    tmp = path + ".tmp"
    src.save(tmp)
    src.close()
    shutil.move(tmp, path)
    entry["doc"] = read_pdf(path)
    return JSONResponse({"pages": _pages_dto(entry["doc"])})


@app.post("/api/pdf/pages/add")
async def pdf_pages_add(file: UploadFile, doc_id: str = Form("")) -> JSONResponse:
    """양식 뒤에 페이지 추가 — 다른 파일(hwpx/pdf)의 페이지를 이어붙이고 자동 박스 제안."""
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    req_dir = config.UPLOAD_DIR / ("pdfadd_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    dest = req_dir / (file.filename or "extra.pdf")
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        extra_pdf = to_pdf(str(dest), str(config.PDF_CACHE_DIR))
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"추가 파일 변환 실패: {e}"}, status_code=400)
    import fitz
    path = _editable_pdf(entry, doc_id)
    base = fitz.open(path)
    first_new = len(base)
    extra = fitz.open(extra_pdf)
    base.insert_pdf(extra)
    extra.close()
    tmp = path + ".tmp"
    base.save(tmp)
    base.close()
    shutil.move(tmp, path)
    entry["doc"] = read_pdf(path)
    # 새로 붙은 페이지에 자동 박스 제안(표 칸 기반, 없으면 단어 방식)
    new_boxes: list[dict] = []
    for p in entry["doc"].pages[first_new:]:
        cb = suggest_cells_maximal(path, p.page_no)
        new_boxes.extend(cb if cb else suggest_pixel_boxes(p))
    return JSONResponse({"pages": _pages_dto(entry["doc"]),
                         "first_new_page": first_new, "new_boxes": new_boxes})


@app.get("/api/pdf/page/{doc_id}/{page_no}")
def pdf_page_image(doc_id: str, page_no: int):
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    png = render_page_png(entry["pdf_path"], page_no, dpi=170)
    from fastapi.responses import Response
    return Response(content=png, media_type="image/png")


def _dedup_box_fields(boxes: list[dict]) -> tuple[list[dict], list[str]]:
    """박스 필드명을 유일화(엑셀 열 충돌 방지)하고 열 순서를 반환. 원본은 건드리지 않는다."""
    boxes = copy.deepcopy(boxes)
    seen: dict[str, int] = {}
    for b in sorted(boxes, key=lambda z: z.get("order", 0)):
        f = (b.get("field") or "항목").strip()
        if f in seen:
            seen[f] += 1
            b["field"] = f"{f} ({seen[f]})"
        else:
            seen[f] = 1
    return boxes, pdf_field_order(boxes)


def _best_template(pages: list, templates: list[dict]) -> tuple[dict | None, float]:
    """입력 페이지에 가장 잘 맞는 템플릿을 라벨 일치율로 고른다 → (템플릿, 일치율 0~1)."""
    best, best_score = None, 0.0
    for t in templates:
        tpages = {int(b["page"]) for b in t["boxes"]}
        if not tpages:
            continue
        matched = match_pages(t["boxes"], pages)
        score = len(matched) / len(tpages)
        if score > best_score:
            best, best_score = t, score
    return best, best_score


def _title_sim(a: str, b: str) -> float:
    """제목 유사도 0~1 — 공백 무시. 한쪽이 다른 쪽을 포함하면 0.9(예: '하천 조사표 1'
    vs '하천 조사표'), 그 외에는 문자열 유사율."""
    import difflib
    from core.normalize import normalize_key
    ka, kb = normalize_key(a), normalize_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    if ka in kb or kb in ka:
        return 0.9
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def _title_match(page_title: str, tpl_title: str) -> float:
    """페이지 제목 ↔ 템플릿 제목 '확인' — 같은 양식인지 검사한 유사도.

    꼬리 번호가 서로 다르면(예: '…조사표 1' vs '…조사표 2') 다른 양식으로
    보고 -1(탈락)을 준다. 글자만 비슷한 형제 양식('…현장사진' vs
    '…현장조사표')이 섞이지 않도록, 포함 관계가 아니면 점수가 낮게 나온다."""
    import re
    from core.normalize import normalize_key
    ka, kb = normalize_key(page_title), normalize_key(tpl_title)
    if not ka or not kb:
        return 0.0
    ta = re.search(r"(\d+)$", ka)
    tb = re.search(r"(\d+)$", kb)
    if ta and tb and ta.group(1) != tb.group(1):
        return -1.0
    return _title_sim(page_title, tpl_title)


def _pdf_title_text(pdf_path, max_pages: int = 3) -> str:
    """PDF 앞쪽 페이지에서 처음 발견되는 큰 글씨 제목(양식의 제목 텍스트)."""
    from core.pdf_pipeline import detect_title
    for pno in range(max_pages):
        try:
            t = detect_title(str(pdf_path), pno)
        except Exception:  # noqa: BLE001  (페이지 범위 밖 등)
            return ""
        if t and t.get("text"):
            return t["text"]
    return ""


def _pdf_apply_auto(files: list[UploadFile], req_dir, stamp: str,
                    box_list: list[dict] | None = None,
                    cur_pdf_path: str | None = None) -> JSONResponse:
    """기본 일괄 처리: 입력 파일의 '페이지 단위'로 템플릿과 대조해 분류한다.

    페이지마다 (제목 유사 0.6 + 라벨 일치 0.4)로 가장 맞는 템플릿에 배정하고,
    템플릿별로 배정된 페이지 안에서 묶음(조사표)을 짜서 추출한다.
    제목 유사: 페이지 큰 글씨 vs 템플릿 양식 PDF의 제목 또는 템플릿 이름(포함/유사율).
    시트는 제목 값별로 나뉘고, 제목이 전혀 없으면 시트 하나."""
    from core.analysis import find_outliers
    from core.normalize import normalize_key
    from core.pdf_pipeline import detect_title

    def _label_sets(bx: list[dict]) -> dict[int, set[str]]:
        out: dict[int, set[str]] = {}
        for b in bx:
            lbl = ((b.get("anchor") or {}).get("label")) or b.get("field") or ""
            k = normalize_key(lbl)
            if k and k != "칸":
                out.setdefault(int(b.get("page", 0)), set()).add(k)
        return out

    def _page_title_of(pdf_path, pno: int) -> str:
        try:
            t = detect_title(str(pdf_path), pno)
            return (t.get("text") or "").strip() if t else ""
        except Exception:  # noqa: BLE001
            return ""

    def _mk_template(name: str, boxes: list[dict], tpdf) -> dict:
        bx, flds = _dedup_box_fields(boxes)
        tpages = sorted({int(b.get("page", 0)) for b in bx})
        # 템플릿 페이지별 제목 — 여러 쪽에 제목이 있으면 '쪽 = 소양식' 묶음집이다
        ptitles = {tp: (_page_title_of(tpdf, tp) if tpdf else "") for tp in tpages}
        return {"name": name, "boxes": bx, "fields": flds,
                "title": next((v for v in ptitles.values() if v), ""),
                "labels": _label_sets(bx),
                "page_titles": ptitles,
                "multi": sum(1 for v in ptitles.values() if v) >= 2,
                "npages": max(1, len(tpages))}

    templates: list[dict] = []
    if box_list:  # 화면에서 편집 중인 박스를 첫 후보로 — 단일 양식 사용자는 항상 이걸로 추출됨
        templates.append(_mk_template("현재 양식", box_list, cur_pdf_path))
    for name in _TEMPLATES.list_names():
        t = _TEMPLATES.get(name)
        if not t or not t.get("boxes"):
            continue
        tpdf = _tpl_pdf_path(name)
        templates.append(_mk_template(t["name"], t["boxes"],
                                      tpdf if tpdf.exists() else None))
    if not templates:
        return JSONResponse(
            {"error": "추출할 박스가 없습니다. 양식을 올려 박스를 만들거나 템플릿을 저장하세요."},
            status_code=400)

    # 분류 단위: 묶음집(multi) 템플릿은 '페이지 하나 = 소양식 하나'로 쪼개고,
    # 일반 템플릿은 통째로 한 단위(묶음 추출 유지)
    units: list[dict] = []
    for T in templates:
        if T["multi"]:
            for tp, ptitle in T["page_titles"].items():
                ub = [b for b in T["boxes"] if int(b.get("page", 0)) == tp]
                if not ub:
                    continue
                units.append({"kind": "page", "T": T, "tp": tp,
                              "title": ptitle,
                              "labels": T["labels"].get(tp, set()),
                              "boxes": ub,
                              "fields": [b["field"] for b in
                                         sorted(ub, key=lambda z: z.get("order", 0))]})
        else:
            units.append({"kind": "whole", "T": T, "title": T["title"]})

    groups: dict[str, dict] = {}  # 제목 값 → {"label", "fields", "rows"}
    failed, match_info = [], []
    discarded: dict[str, int] = {}  # 버려진 페이지 제목 → 쪽수(맞는 양식 없음)
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        try:
            pdf_path = to_pdf(str(dest), str(config.PDF_CACHE_DIR))
            doc = read_pdf(pdf_path)

            ptitle: dict[int, str] = {}
            def page_title(ip: int) -> str:
                if ip not in ptitle:
                    try:
                        t = detect_title(pdf_path, ip)
                        ptitle[ip] = (t.get("text") or "").strip() if t else ""
                    except Exception:  # noqa: BLE001
                        ptitle[ip] = ""
                return ptitle[ip]

            # ① 페이지 단위 배정 — 페이지마다 모든 분류 단위(소양식 쪽·전체 템플릿)와
            #    대조해 가장 유사한 쪽으로. 제목 유사가 갈라주고 라벨 일치율이 받쳐준다.
            page_text = {p.page_no: normalize_key("".join(w.text for w in p.words))
                         for p in doc.pages}

            def _lbl_hit(labels: set, text: str) -> float:
                if not labels:
                    return 0.0
                return sum(1 for l in labels if l in text) / len(labels)

            page_assign: dict[int, dict] = {}
            unmatched: list[int] = []
            for ip, text in page_text.items():
                pt = page_title(ip)
                best_u, best_sc, best_ts, best_ls = None, -1.0, 0.0, 0.0
                for u in units:
                    T = u["T"]
                    if u["kind"] == "page":
                        tsim = _title_match(pt, u["title"])
                        if tsim < 0:      # 제목 확인 결과 다른 양식(꼬리 번호 불일치)
                            continue
                        lbest = _lbl_hit(u["labels"], text)
                    else:
                        tsim = _title_match(pt, T["title"])
                        if tsim < 0:
                            continue
                        tsim = max(tsim, _title_sim(pt, T["name"]))
                        lbest = max((_lbl_hit(ls, text)
                                     for ls in T["labels"].values()), default=0.0)
                    sc = 0.6 * tsim + 0.4 * lbest
                    if sc > best_sc:
                        best_u, best_sc, best_ts, best_ls = u, sc, tsim, lbest
                # 확인 통과 기준 — 제목이 사실상 같거나(포함·0.85↑), 표 구조(라벨)가
                # 맞거나, 둘 다 어느 정도 맞을 때만 배정. 아니면 버림.
                if best_u is not None and (
                        best_ts >= 0.85
                        or best_ls >= 0.35
                        or (best_ts >= 0.7 and best_ls >= 0.25)):
                    page_assign[ip] = best_u
                else:
                    unmatched.append(ip)

            # ② 추출 대상 확정 — 소양식 쪽은 '페이지 1장 = 1행',
            #    전체 템플릿은 배정된 페이지 안에서 묶음(조사표) 구성
            accepted = []  # (첫 페이지, {name, boxes, fields, title}, page_map)
            by_whole: dict[str, list[int]] = {}
            for ip, u in page_assign.items():
                if u["kind"] == "page":
                    accepted.append((ip, {"name": u["T"]["name"], "boxes": u["boxes"],
                                          "fields": u["fields"], "title": u["title"]},
                                     {u["tp"]: ip}))
                else:
                    by_whole.setdefault(u["T"]["name"], []).append(ip)
            tpl_by_name = {T["name"]: T for T in templates}
            for tname, ips in by_whole.items():
                T = tpl_by_name[tname]
                sub_pages = [p for p in doc.pages if p.page_no in ips]
                try:
                    maps = match_bundles(T["boxes"], sub_pages)
                except Exception:  # noqa: BLE001
                    maps = []
                if not maps and sub_pages:
                    # 라벨 지문이 약해 묶음을 못 짜면 — 제목으로 배정된 페이지를
                    # 템플릿 페이지 수 단위로 문서 순서대로 묶는다(제목만으로도 동작)
                    tps = sorted({int(b.get("page", 0)) for b in T["boxes"]}) or [0]
                    ips_sorted = sorted(ips)
                    for i in range(0, len(ips_sorted), len(tps)):
                        chunk = ips_sorted[i:i + len(tps)]
                        maps.append(dict(zip(tps, chunk)))
                for pm in maps:
                    if pm:
                        accepted.append((min(pm.values()),
                                         {"name": T["name"], "boxes": T["boxes"],
                                          "fields": T["fields"], "title": T["title"]},
                                         pm))
            if (not accepted and box_list
                    and not any(page_title(ip) for ip in page_text)):
                # 제목이 전혀 없는 문서(스캔 등)만 — 현재 양식으로 폴백(기존 동작).
                # 제목이 있는데 안 맞으면 억지로 넣지 않고 버림 처리한다.
                cur = templates[0]
                maps = (match_bundles(cur["boxes"], doc.pages)
                        or [match_pages(cur["boxes"], doc.pages)])
                accepted = [(min(pm.values()) if pm else 0,
                             {"name": cur["name"], "boxes": cur["boxes"],
                              "fields": cur["fields"], "title": cur["title"]}, pm)
                            for pm in maps]
            if not accepted:
                failed.append({"name": uf.filename,
                               "error": "맞는 양식(템플릿)이 없어 버림 처리했습니다."})
                if unmatched:
                    match_info.append({"name": uf.filename,
                                       "template": "버림(맞는 양식 없음)",
                                       "bundles": len(unmatched)})
                    for ip in unmatched:
                        t = page_title(ip) or "(제목 없음)"
                        discarded[t] = discarded.get(t, 0) + 1
                continue

            accepted.sort(key=lambda a: a[0])  # 문서 순서대로 행 생성
            tcount: dict[str, int] = {}
            for bi, (first_ip, ext, page_map) in enumerate(accepted, start=1):
                row = apply_pixel_template(doc.pages, ext["boxes"], page_map=page_map,
                                           pdf_path=pdf_path)
                fname = uf.filename if len(accepted) == 1 else f"{uf.filename} #{bi}"
                # 시트 제목: 템플릿(양식) 기준이 원칙 — 양식 쪽 제목을 시트 이름으로.
                # 차수 표기 등으로 입력 제목이 조금씩 달라도 같은 양식이면 같은 시트에
                # 축적된다. 템플릿에 제목이 없을 때만 입력 문서의 큰 글씨로 폴백.
                title = (ext.get("title") or "").strip()
                if not title:
                    title_field = next((b["field"] for b in sorted(ext["boxes"],
                                                                   key=lambda z: z.get("order", 0))
                                        if b.get("mode") == "title"), None)
                    title = (row.get(title_field) or "").strip() if title_field else ""
                if not title:
                    title = page_title(first_ip) if page_map else ""
                g = groups.setdefault(title, {"label": title, "fields": [], "rows": []})
                for fld in ext["fields"]:
                    if fld not in g["fields"]:
                        g["fields"].append(fld)
                g["rows"].append({"_파일명": fname, "_제목": title, **row})
                tcount[ext["name"]] = tcount.get(ext["name"], 0) + 1
            for tname, cnt in tcount.items():
                match_info.append({"name": uf.filename, "template": tname,
                                   "bundles": cnt})
            if unmatched:
                match_info.append({"name": uf.filename, "template": "버림(맞는 양식 없음)",
                                   "bundles": len(unmatched)})
                for ip in unmatched:
                    t = page_title(ip) or "(제목 없음)"
                    discarded[t] = discarded.get(t, 0) + 1
        except Exception as e:  # noqa: BLE001
            failed.append({"name": uf.filename, "error": str(e)})

    if not groups:
        return JSONResponse(
            {"error": "처리된 파일이 없습니다. 양식과 입력 파일이 맞는지 확인하세요.",
             "failed": failed}, status_code=400)
    if "" in groups:  # 제목이 없는 조사표: 전부 무제면 시트 하나, 섞였으면 별도 시트
        groups[""]["label"] = "추출결과" if len(groups) == 1 else "(제목없음)"
    group_list = list(groups.values())

    # 이상치 탐지 → 행에 부착(엑셀 셀 서식용) → 엑셀 저장
    by_form, outlier_total = [], 0
    for g in group_list:
        og = find_outliers([{f: r.get(f, "") for f in g["fields"]} for r in g["rows"]])
        for r, o in zip(g["rows"], og):
            if o:
                r["_이상치"] = o
        cnt = sum(len(o) for o in og)
        outlier_total += cnt
        by_form.append({"form": g["label"], "count": len(g["rows"]), "outliers": cnt})
    excel_path = config.OUTPUT_DIR / f"조사데이터_추출_{stamp}.xlsx"
    write_bundle_excel(group_list, str(excel_path))

    _PDF_APPLY["excel_path"] = str(excel_path)
    _PDF_APPLY["groups"] = group_list
    _PDF_APPLY["rows"] = [r for g in group_list for r in g["rows"]]
    _PDF_APPLY["fields"] = []
    return JSONResponse({"auto_classify": True, "forms": len(group_list),
                         "ok_count": sum(len(g["rows"]) for g in group_list),
                         "by_form": by_form, "failed": failed, "match_info": match_info,
                         "discarded": [{"title": t, "pages": n}
                                       for t, n in discarded.items()],
                         "outlier_count": outlier_total, "report_used": False})


@app.post("/api/pdf/apply")
async def pdf_apply(files: list[UploadFile], boxes: str = Form(""),
                    report_id: str = Form(""), report_edits: str = Form(""),
                    sheet_name_field: str = Form(""), auto_classify: str = Form(""),
                    doc_id: str = Form(""),
                    report_template: UploadFile | None = None) -> JSONResponse:
    import json as _json
    auto = auto_classify.strip().lower() in ("1", "true", "on", "yes")
    try:
        box_list = _json.loads(boxes) if boxes else []
    except _json.JSONDecodeError:
        return JSONResponse({"error": "박스 형식 오류"}, status_code=400)
    if not box_list and not auto:
        return JSONResponse({"error": "추출할 박스가 없습니다."}, status_code=400)

    req_dir = config.UPLOAD_DIR / ("pdfapply_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    stamp0 = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 기본 흐름: 자동 대조 + 제목별 시트. 보고서 양식(5번)을 쓸 때만 기존 경로로.
    has_report = bool(report_id) or (report_template is not None
                                     and bool(report_template.filename))
    if auto and not has_report:
        entry = _PDF_DOCS.get(doc_id) if doc_id else None
        cur_pdf = entry["pdf_path"] if entry else None
        return _pdf_apply_auto(files, req_dir, stamp0, box_list, cur_pdf)

    # 중복 이름은 접미사로 유일화(엑셀 열 충돌 방지). 사용자가 이름을 안 바꾼 경우 대비.
    box_list, fields = _dedup_box_fields(box_list)

    # '제목별 분류' — 제목(위계) 박스 값으로 같은 양식끼리 시트를 묶는다.
    # 제목 박스가 없는(예전) 템플릿이면 입력 문서의 큰 글씨 제목을 감지해 폴백.
    group_field = None
    if sheet_name_field == "__group_title__":
        title_box = next((b for b in sorted(box_list, key=lambda z: z.get("order", 0))
                          if b.get("mode") == "title"), None)
        group_field = title_box["field"] if title_box else "_제목"
        sheet_name_field = group_field  # 보고서 양식 경로에선 제목이 시트 이름이 됨

    rows, failed, match_info = [], [], []
    n_tmpl_pages = len({int(b["page"]) for b in box_list})
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        try:
            pdf_path = to_pdf(str(dest), str(config.PDF_CACHE_DIR))
            doc = read_pdf(pdf_path)
            # 페이지 자동 매칭 — 한 파일에 같은 서식이 여러 묶음이면 묶음마다 한 행
            bundle_maps = match_bundles(box_list, doc.pages)
            if not bundle_maps:
                bundle_maps = [match_pages(box_list, doc.pages)]  # 기존 동작(1행) 유지
            for bi, page_map in enumerate(bundle_maps, start=1):
                row = apply_pixel_template(doc.pages, box_list, page_map=page_map,
                                           pdf_path=pdf_path)  # 유기적(라벨 칸 기준) 추출
                row["_파일명"] = (uf.filename if len(bundle_maps) == 1
                                  else f"{uf.filename} #{bi}")
                # 제목별 분류 폴백: 제목 값이 비면 이 묶음 첫 페이지의 큰 글씨를 제목으로
                if group_field and not (row.get(group_field) or "").strip():
                    from core.pdf_pipeline import detect_title
                    first_ip = min(page_map.values()) if page_map else 0
                    t = detect_title(pdf_path, first_ip)
                    if t and t.get("text"):
                        row[group_field] = t["text"]
                rows.append(row)
            match_info.append({"name": uf.filename,
                               "matched": len(bundle_maps[0]) if bundle_maps[0] else 0,
                               "bundles": len(bundle_maps),
                               "template_pages": n_tmpl_pages, "input_pages": len(doc.pages)})
        except Exception as e:  # noqa: BLE001
            failed.append({"name": uf.filename, "error": str(e)})

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_used = False

    # 이상치(오추출 의심) — 여러 파일(행) 교차비교. 엑셀 저장 전에 행에 부착해
    # 해당 칸이 주황 서식 + 사유 메모로 표시되게 한다.
    from core.analysis import find_outliers
    outliers = find_outliers([{f: r.get(f, "") for f in fields} for r in rows])
    for r, o in zip(rows, outliers):
        if o:
            r["_이상치"] = o

    # 편집된 양식(report_id) 우선, 없으면 직접 업로드한 양식(backward compat)
    tpl_path = None
    if report_id and report_id in _REPORT_DOCS:
        try:
            from core.report import save_with_edits
            edits = _json.loads(report_edits) if report_edits else {}
            tpl_path = str(req_dir / "_tpl_edited.xlsx")
            save_with_edits(_REPORT_DOCS[report_id], edits, tpl_path)
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": f"보고서 양식 편집 반영 실패: {e}"}, status_code=400)
    elif report_template is not None and report_template.filename:
        tpl_path = str(req_dir / ("_tpl_" + report_template.filename))
        with open(tpl_path, "wb") as f:
            shutil.copyfileobj(report_template.file, f)

    if tpl_path:
        excel_path = config.OUTPUT_DIR / f"조사데이터_보고서_{stamp}.xlsx"
        try:
            from core.report import build_report_workbook
            build_report_workbook(tpl_path, rows, fields, str(excel_path),
                                  sheet_name_field=sheet_name_field or None)
            report_used = True
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": f"보고서 양식 처리 실패(엑셀 양식이 맞는지 확인): {e}"},
                                status_code=400)
    else:
        excel_path = config.OUTPUT_DIR / f"조사데이터_추출_{stamp}.xlsx"
        write_template_excel(rows, fields, str(excel_path),
                             sheet_name_field=(None if group_field else (sheet_name_field or None)),
                             group_field=group_field)

    _PDF_APPLY["excel_path"] = str(excel_path)
    _PDF_APPLY["rows"] = rows            # AI 분석용 보관
    _PDF_APPLY["fields"] = fields
    _PDF_APPLY["groups"] = [{"label": "템플릿 추출", "fields": fields, "rows": rows}]
    return JSONResponse({"rows": rows, "fields": fields, "ok_count": len(rows),
                         "failed": failed, "match_info": match_info,
                         "report_used": report_used,
                         "outliers": outliers,
                         "outlier_count": sum(len(o) for o in outliers)})


@app.post("/api/pdf/analyze")
def pdf_analyze() -> JSONResponse:
    """템플릿 대량추출 결과(엑셀 표)를 AI가 종합·추세 분석 → 마크다운."""
    from core.analysis import analyze_records
    from core.vision_extract import available
    ok, msg = available()
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)
    groups = _PDF_APPLY.get("groups") or []
    if not groups:
        rows = _PDF_APPLY.get("rows") or []
        fields = _PDF_APPLY.get("fields") or []
        groups = [{"label": "템플릿 추출", "fields": fields, "rows": rows}] if rows else []
    if not groups or not any(g["rows"] for g in groups):
        return JSONResponse({"error": "먼저 템플릿 추출을 실행하세요."}, status_code=400)
    try:
        text = analyze_records(groups)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": _friendly_vision_error(e)}, status_code=502)
    return JSONResponse({"analysis": text})


@app.post("/api/report/ai_draft")
def report_ai_draft(payload: dict = Body(...)) -> JSONResponse:
    """AI 보고서 양식 초안 — 추출 항목·샘플값·제목 위계로 초안 xlsx 생성.

    생성 즉시 편집기(report_id)로 장착되고, 다운로드해 엑셀에서 편집 후
    다시 업로드하는 왕복 흐름을 지원한다.
    """
    entry = _PDF_DOCS.get((payload.get("doc_id") or "").strip())
    box_list = payload.get("boxes") or []
    if not box_list:
        return JSONResponse({"error": "추출 항목(박스)이 없습니다."}, status_code=400)
    from core.llm_understand import available as _ai_ok
    ok, msg = _ai_ok()
    if not ok:
        return JSONResponse({"error": msg}, status_code=400)

    # 필드 정리(중복 유일화, 순서 유지) + 제목 위계
    _seen: dict[str, int] = {}
    for b in sorted(box_list, key=lambda z: z.get("order", 0)):
        f = (b.get("field") or "항목").strip()
        if f in _seen:
            _seen[f] += 1
            b["field"] = f"{f} ({_seen[f]})"
        else:
            _seen[f] = 1
    fields = pdf_field_order(box_list)
    title_fields = [b["field"] for b in sorted(box_list, key=lambda z: z.get("order", 0))
                    if b.get("mode") == "title"]
    # 샘플값: 현재 불러온 기준 양식에서 1건 추출(없으면 빈 샘플)
    sample: dict = {}
    if entry:
        try:
            sample = apply_pixel_template(entry["doc"].pages, box_list,
                                          pdf_path=entry["pdf_path"])
        except Exception:  # noqa: BLE001
            sample = {}

    rid = uuid.uuid4().hex[:10]
    path = config.REPORT_CACHE_DIR / f"{rid}.xlsx"
    try:
        from core.report_draft import make_draft
        make_draft(fields, sample, title_fields, str(path))
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"초안 생성 실패: {e}"}, status_code=502)
    _REPORT_DOCS[rid] = str(path)
    from core.report import list_placeholders, read_grid
    grid = read_grid(str(path))
    grid["report_id"] = rid
    grid["placeholders"] = list_placeholders(str(path))
    grid["filename"] = "AI초안_보고서양식.xlsx"
    grid["download_url"] = f"/api/report/draft_download/{rid}"
    return JSONResponse(grid)


@app.get("/api/report/draft_download/{rid}")
def report_draft_download(rid: str):
    path = _REPORT_DOCS.get(rid)
    if not path:
        return JSONResponse({"error": "초안을 찾을 수 없습니다."}, status_code=404)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="AI초안_보고서양식.xlsx")


_REPORT_RESULT: dict[str, str] = {}   # 5번 '보고서 양식으로 정리' 결과 파일


@app.post("/api/report/generate")
def report_generate(payload: dict = Body(...)) -> JSONResponse:
    """5번: 4번 일괄 처리 '결과'를 보고서 양식에 채워 정리한다(재추출 없음)."""
    report_id = (payload.get("report_id") or "").strip()
    edits = payload.get("edits") or {}
    rows = _PDF_APPLY.get("rows") or []
    if not rows:
        return JSONResponse(
            {"error": "먼저 4번 일괄 처리를 실행하세요 — 그 결과로 보고서를 만듭니다."},
            status_code=400)
    src = _REPORT_DOCS.get(report_id)
    if not src:
        return JSONResponse(
            {"error": "보고서 양식을 먼저 올리거나 AI 초안을 만들어 주세요."},
            status_code=400)

    req_dir = config.UPLOAD_DIR / ("rptgen_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = str(req_dir / "_tpl_edited.xlsx")
    try:
        from core.report import build_report_workbook, save_with_edits
        save_with_edits(src, edits, tpl_path)
        fields = _PDF_APPLY.get("fields") or []
        if not fields:  # 자동 분류 결과 — 그룹 필드 합집합(순서 보존)
            for g in _PDF_APPLY.get("groups") or []:
                for f in g.get("fields", []):
                    if f not in fields:
                        fields.append(f)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = config.OUTPUT_DIR / f"조사데이터_보고서_{stamp}.xlsx"
        sheet_field = ("_제목" if any((r.get("_제목") or "").strip() for r in rows)
                       else None)
        build_report_workbook(tpl_path, rows, fields, str(excel_path),
                              sheet_name_field=sheet_field)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"보고서 양식 처리 실패(엑셀 양식이 맞는지 확인): {e}"},
                            status_code=400)
    _REPORT_RESULT["path"] = str(excel_path)
    return JSONResponse({"ok": True, "rows": len(rows),
                         "download": "/api/report/result"})


@app.get("/api/report/result")
def report_result():
    path = _REPORT_RESULT.get("path")
    if not path or not Path(path).exists():
        return JSONResponse({"error": "정리된 보고서가 없습니다. 먼저 실행하세요."},
                            status_code=404)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(path).name)


@app.post("/api/report/load")
async def report_load(file: UploadFile) -> JSONResponse:
    """보고서 엑셀 양식 업로드 → 격자 데이터 반환(화면 편집용). 원본은 서버 보관."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        return JSONResponse({"error": "엑셀(.xlsx) 양식만 지원합니다."}, status_code=400)
    rid = uuid.uuid4().hex[:10]
    path = config.REPORT_CACHE_DIR / f"{rid}.xlsx"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    _REPORT_DOCS[rid] = str(path)
    try:
        from core.report import list_placeholders, read_grid
        grid = read_grid(str(path))
        grid["report_id"] = rid
        grid["placeholders"] = list_placeholders(str(path))
        grid["filename"] = file.filename
        return JSONResponse(grid)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"양식을 읽지 못했습니다(엑셀 파일이 맞는지 확인): {e}"},
                            status_code=400)


@app.get("/api/pdf/download")
def pdf_download() -> FileResponse:
    path = _PDF_APPLY.get("excel_path")
    if not path:
        return JSONResponse({"error": "먼저 추출을 실행하세요."}, status_code=404)  # type: ignore[return-value]
    fname = str(path).replace("\\", "/").split("/")[-1]
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=fname)


@app.get("/api/download")
def download() -> FileResponse:
    path = _LAST.get("excel_path")
    if not path:
        return JSONResponse({"error": "먼저 변환을 실행하세요."}, status_code=404)  # type: ignore[return-value]
    fname = str(path).replace("\\", "/").split("/")[-1]
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=fname,
    )


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
