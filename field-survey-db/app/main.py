"""FastAPI 앱 진입점 — 업로드/처리/검수/다운로드 라우트.

화면은 core.pipeline.run() 파사드만 호출한다(엔진과 화면 분리).
"""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime

from fastapi import Body, FastAPI, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from core.excel.writer import write_excel
from core.extraction.form_detector import FORM_LABELS_KO
from core.parsers.hwpx_parser import parse_hwpx
from core.pipeline import ExtractionResult, run
from core.review.store import CorrectionStore
from core.pdf_pipeline import (
    apply_pixel_template,
    field_order as pdf_field_order,
    match_pages,
    suggest_cells_maximal,
    suggest_pixel_boxes,
    to_pdf,
)
from core.pdf_reader import read_pdf, render_page_png
from core.template.apply import apply_template, field_order
from core.template.designer import grid_dto, suggest_boxes
from core.template.store import TemplateStore
from core.template.writer import write_template_excel

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


def _regenerate_excel() -> str:
    result: ExtractionResult = _LAST["result"]  # type: ignore[assignment]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = config.OUTPUT_DIR / f"현장조사표_DB_{stamp}.xlsx"
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
    # 메인 화면 = 템플릿 디자이너
    return FileResponse(config.STATIC_DIR / "pdf_designer.html")


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
    boxes: list[dict] = []
    for page in doc.pages:
        # 표 칸 전체에 박스 생성(최대) → 사용자가 삭제. 칸 없으면(스캔) 단어 방식.
        cell_boxes = suggest_cells_maximal(pdf_path, page.page_no)
        boxes.extend(cell_boxes if cell_boxes else suggest_pixel_boxes(page))
    # 문서 위치(페이지→위→왼쪽) 순서로 번호 부여
    boxes.sort(key=lambda b: (b["page"], b["y0"], b["x0"]))
    for i, b in enumerate(boxes):
        b["order"] = i + 1
    return boxes


@app.get("/api/pdf/suggest/{doc_id}")
def pdf_suggest(doc_id: str) -> JSONResponse:
    """자동 제안(표 테두리 기반) 다시 계산."""
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    return JSONResponse({"boxes": _suggest_all(entry["doc"], entry["pdf_path"])})


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


@app.get("/api/pdf/page/{doc_id}/{page_no}")
def pdf_page_image(doc_id: str, page_no: int):
    entry = _PDF_DOCS.get(doc_id)
    if not entry:
        return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
    png = render_page_png(entry["pdf_path"], page_no, dpi=170)
    from fastapi.responses import Response
    return Response(content=png, media_type="image/png")


@app.post("/api/pdf/apply")
async def pdf_apply(files: list[UploadFile], boxes: str = Form(""),
                    report_id: str = Form(""), report_edits: str = Form(""),
                    report_template: UploadFile | None = None) -> JSONResponse:
    import json as _json
    try:
        box_list = _json.loads(boxes) if boxes else []
    except _json.JSONDecodeError:
        return JSONResponse({"error": "박스 형식 오류"}, status_code=400)
    if not box_list:
        return JSONResponse({"error": "추출할 박스가 없습니다."}, status_code=400)

    # 중복 이름은 접미사로 유일화(엑셀 열 충돌 방지). 사용자가 이름을 안 바꾼 경우 대비.
    _seen: dict[str, int] = {}
    for b in sorted(box_list, key=lambda z: z.get("order", 0)):
        f = (b.get("field") or "항목").strip()
        if f in _seen:
            _seen[f] += 1
            b["field"] = f"{f} ({_seen[f]})"
        else:
            _seen[f] = 1

    fields = pdf_field_order(box_list)
    req_dir = config.UPLOAD_DIR / ("pdfapply_" + uuid.uuid4().hex[:8])
    req_dir.mkdir(parents=True, exist_ok=True)
    rows, failed, match_info = [], [], []
    n_tmpl_pages = len({int(b["page"]) for b in box_list})
    for uf in files:
        dest = req_dir / (uf.filename or "unnamed")
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        try:
            pdf_path = to_pdf(str(dest), str(config.PDF_CACHE_DIR))
            doc = read_pdf(pdf_path)
            # 페이지 자동 매칭: 템플릿 페이지 ↔ 입력 파일의 비슷한 페이지
            page_map = match_pages(box_list, doc.pages)
            row = apply_pixel_template(doc.pages, box_list, page_map=page_map)
            row["_파일명"] = uf.filename
            rows.append(row)
            match_info.append({"name": uf.filename, "matched": len(page_map),
                               "template_pages": n_tmpl_pages, "input_pages": len(doc.pages)})
        except Exception as e:  # noqa: BLE001
            failed.append({"name": uf.filename, "error": str(e)})

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_used = False

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
        excel_path = config.OUTPUT_DIR / f"현장조사표_보고서_{stamp}.xlsx"
        try:
            from core.report import build_report_workbook
            build_report_workbook(tpl_path, rows, fields, str(excel_path))
            report_used = True
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": f"보고서 양식 처리 실패(엑셀 양식이 맞는지 확인): {e}"},
                                status_code=400)
    else:
        excel_path = config.OUTPUT_DIR / f"현장조사표_추출_{stamp}.xlsx"
        write_template_excel(rows, fields, str(excel_path))
    _PDF_APPLY["excel_path"] = str(excel_path)
    return JSONResponse({"rows": rows, "fields": fields, "ok_count": len(rows),
                         "failed": failed, "match_info": match_info,
                         "report_used": report_used})


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
