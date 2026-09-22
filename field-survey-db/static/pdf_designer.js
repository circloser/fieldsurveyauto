// PDF 통합 픽셀박스 디자이너
const $ = (id) => document.getElementById(id);
let DOC_ID = null, PAGES = [], BOXES = [], selected = null;

// ---------- 여러 박스 선택 ----------
// selected = 대표 박스(인덱스). SEL = 함께 선택된 박스 객체들(Ctrl 클릭 토글 · Shift 클릭 범위 · Shift/Ctrl 드래그 영역).
// 인덱스가 아니라 객체로 기억해, 박스를 지우거나 순서를 바꿔도 선택이 어긋나지 않는다.
const SEL = new Set();
let selAnchor = null;   // Shift 범위 선택의 기준(마지막으로 단독 선택한 박스)
function isSel(idx) { return idx === selected || SEL.has(BOXES[idx]); }
function selectOnly(idx) {
  SEL.clear(); selected = (idx != null && BOXES[idx]) ? idx : null; selAnchor = selected;
  if (selected != null) SEL.add(BOXES[selected]);
}
function clearSel() { SEL.clear(); selected = null; selAnchor = null; }
function selectToggle(idx) {
  const b = BOXES[idx]; if (!b) return;
  if (selected != null && BOXES[selected]) SEL.add(BOXES[selected]);
  if (SEL.has(b)) {
    SEL.delete(b);
    if (selected === idx) { const rest = [...SEL]; selected = rest.length ? BOXES.indexOf(rest[rest.length - 1]) : null; }
  } else { SEL.add(b); selected = idx; selAnchor = idx; }
}
function listOrder() {   // 오른쪽 목록과 같은 순서(현재 쪽, 템플릿 모드면 전체)
  return [...BOXES].filter((b) => TPL_MODE || b.page === activePage).sort((a, b) => a.order - b.order);
}
function selectRange(idx) {
  const from = (selAnchor != null && BOXES[selAnchor]) ? selAnchor : selected;
  if (from == null || !BOXES[from]) { selectOnly(idx); return; }
  const seq = listOrder();
  const i1 = seq.indexOf(BOXES[from]), i2 = seq.indexOf(BOXES[idx]);
  if (i1 < 0 || i2 < 0) { selectOnly(idx); return; }
  if (selected != null && BOXES[selected]) SEL.add(BOXES[selected]);
  seq.slice(Math.min(i1, i2), Math.max(i1, i2) + 1).forEach((b) => SEL.add(b));
  selected = idx;
}
function pickSelect(idx, e) {
  if (e && (e.ctrlKey || e.metaKey)) selectToggle(idx);
  else if (e && e.shiftKey) selectRange(idx);
  else selectOnly(idx);
}
function selectedIdxs() {
  const s = new Set([...SEL].map((b) => BOXES.indexOf(b)).filter((i) => i >= 0));
  if (selected != null && BOXES[selected]) s.add(selected);
  return [...s].sort((a, b) => a - b);
}
// 항목의 버튼(유형·라벨 기준)을 눌렀을 때 적용 대상: 그 항목이 여러 선택에 들어 있으면 선택 전체
function targetsOf(idx) { const all = selectedIdxs(); return (all.length > 1 && all.includes(idx)) ? all : [idx]; }

// 되돌리기(Ctrl+Z) — 지우기·한꺼번에 바꾸기·여러 개 이동 전의 박스 목록 스냅샷
const UNDO = [];
function pushUndo() { UNDO.push(JSON.stringify(BOXES)); if (UNDO.length > 30) UNDO.shift(); }
function undoBoxes() {
  if (!UNDO.length) return;
  BOXES = JSON.parse(UNDO.pop()); clearSel(); renderPageNav(); renderPage(); renderBoxes();
}
let TPL_MODE = false;   // 양식 없이 템플릿만 불러온 상태(캔버스 없음)
let activePage = 0;
let zoomW = 700;            // 페이지 표시 너비(px) = 확대/축소 상태
const ZOOM_MIN = 420, ZOOM_MAX = 1800, ZOOM_STEP = 1.25;
let dragState = null;

function scaleOf(p) { return zoomW / p.width; }
function setZoom(w) { zoomW = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(w))); renderPage(); updateZoomLabel(); }
function updateZoomLabel() {
  const p = PAGES[activePage]; if (!p) return;
  const el = $("zoomLabel"); if (el) el.textContent = Math.round(zoomW / p.width * 100) + "%";
}

// ---------- 불러오기 ----------
const dz = $("dropzone"), fi = $("fileInput");
dz.addEventListener("click", () => fi.click());
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files[0]) loadForm(e.dataTransfer.files[0]); });
fi.addEventListener("change", () => { if (fi.files[0]) loadForm(fi.files[0]); });

async function loadForm(file) {
  showOverlay(/\.hwpx?$/i.test(file.name || "")
    ? "한글 양식을 PDF로 변환·분석하는 중… (첫 파일은 다소 걸립니다)"
    : "양식을 분석하는 중…");
  const fd = new FormData(); fd.append("file", file);
  // 템플릿 모드에서 양식을 올리면: 자동제안 대신 불러온 템플릿 박스를 유지(편집 이어가기)
  const keepBoxes = (TPL_MODE && BOXES.length) ? BOXES : null;
  try {
    const res = await fetch("/api/pdf/load", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    DOC_ID = data.doc_id; PAGES = data.pages;
    BOXES = keepBoxes || data.boxes.map((b, i) => ({ ...b, order: b.order ?? i + 1 }));
    exitTplMode();
    // 설문지(문항 번호 목록·척도표)로 인식되면: 칸 박스 없이 안내 배너 — 데이터 추출 관리에서 바로 처리.
    // 인식된 문항은 문서 위에 점선 상자로, 오른쪽 목록에 열 이름으로 보여 준다.
    if (data.survey) {
      const s = data.survey;
      SURVEY = s.items || [];
      $("surveyBannerInfo").textContent =
        `${s.pages.length}쪽, 문항 ${s.questions}개${s.likert ? " (척도표 포함)" : ""} 인식 — 문서 위 점선 상자가 인식된 문항입니다.`;
      $("surveyBanner").hidden = false;
    } else {
      SURVEY = [];
      $("surveyBanner").hidden = true;
    }
    activePage = PAGES.length ? PAGES[0].page_no : 0; clearSel(); UNDO.length = 0;  // 항상 1페이지부터
    $("main").hidden = false;
    renderPageNav(); renderPage(); renderBoxes(); loadTemplates();
    fitZoom();  // 너비에 맞춰 시작
    const setup = data.ocr_setup;
    if (data.ocr_missing && setup && !setup.ready && !setup.bundled) showOcrSetup(setup);
    else if (!data.ocr_missing) document.getElementById("ocrSetup")?.remove();
  } catch (e) { alert("불러오기 실패: " + e.message); }
  finally { hideOverlay(); }
}

let SURVEY = [];   // 설문지로 인식된 문항들 [{page, key, text, choices, x0,y0,x1,y1}] — 표시 전용

function exitTplMode() {
  TPL_MODE = false;
  $("tplBanner").hidden = true;
  $("surveyBanner").hidden = true;
  SURVEY = [];
  document.querySelector(".grid-pane").style.display = "";
}
let EDIT_VER = 0;   // 페이지 편집(삭제/추가) 시 증가 — 페이지 이미지 캐시 무효화

function renderPageNav() {
  const host = $("pageNav"); host.innerHTML = "";
  const c = {}; BOXES.forEach((b) => (c[b.page] = (c[b.page] || 0) + 1));
  PAGES.forEach((p) => {
    const b = document.createElement("button");
    b.className = "tp-btn" + (p.page_no === activePage ? " active" : "");
    b.innerHTML = `${p.page_no + 1}쪽<span class="n">${c[p.page_no] ? c[p.page_no] + "개" : ""}</span>` +
      (p.page_no === activePage && PAGES.length > 1
        ? `<span class="tp-del" title="이 페이지를 양식에서 삭제">✕</span>` : "");
    b.addEventListener("click", (e) => {
      if (e.target.classList.contains("tp-del")) { deletePage(p.page_no); return; }
      activePage = p.page_no; clearSel(); renderPageNav(); renderPage(); renderBoxes();
    });
    host.appendChild(b);
  });
  if (DOC_ID) {   // 다른 파일의 페이지를 뒤에 추가
    const add = document.createElement("button");
    add.className = "tp-btn tp-add";
    add.textContent = "＋쪽 추가";
    add.title = "다른 파일(hwpx/pdf)의 페이지를 이 양식 뒤에 추가";
    add.addEventListener("click", () => $("addPageInput").click());
    host.appendChild(add);
  }
}

async function deletePage(pno) {
  if (!confirm(`${pno + 1}쪽을 양식에서 삭제할까요?\n(이 쪽의 추출 항목 ${BOXES.filter((b) => b.page === pno).length}개도 함께 삭제됩니다)`)) return;
  showOverlay("페이지 삭제 중…");
  try {
    const d = await (await fetch("/api/pdf/pages/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: DOC_ID, page_no: pno }),
    })).json();
    if (d.error) throw new Error(d.error);
    PAGES = d.pages; EDIT_VER++;
    BOXES = BOXES.filter((b) => b.page !== pno)
                 .map((b) => (b.page > pno ? { ...b, page: b.page - 1 } : b));
    sortBoxesByPosition();
    if (activePage >= PAGES.length) activePage = PAGES.length - 1;
    clearSel();
    renderPageNav(); renderPage(); renderBoxes();
  } catch (e) { alert("페이지 삭제 실패: " + e.message); }
  finally { hideOverlay(); }
}

async function addPagesFile(file) {
  showOverlay(/\.hwpx?$/i.test(file.name || "")
    ? "페이지 추가 중… (한글 파일은 PDF 변환에 시간이 걸립니다)"
    : "페이지 추가 중…");
  const fd = new FormData(); fd.append("file", file); fd.append("doc_id", DOC_ID);
  try {
    const d = await (await fetch("/api/pdf/pages/add", { method: "POST", body: fd })).json();
    if (d.error) throw new Error(d.error);
    PAGES = d.pages; EDIT_VER++;
    const start = Math.max(0, ...BOXES.map((b) => b.order || 0));
    (d.new_boxes || []).forEach((b, i) => BOXES.push({ ...b, order: start + i + 1 }));
    activePage = d.first_new_page; clearSel();
    renderPageNav(); renderPage(); renderBoxes();
  } catch (e) { alert("페이지 추가 실패: " + e.message); }
  finally { hideOverlay(); }
}

// ---------- 페이지 렌더 ----------
function renderPage() {
  const p = PAGES[activePage] || PAGES.find((x) => x.page_no === activePage);
  const host = $("pageHost"); host.innerHTML = "";
  if (!p) return;   // 템플릿 모드(양식 없음) 등 페이지가 없으면 빈 캔버스
  const sc = scaleOf(p);
  const wrap = document.createElement("div");
  wrap.className = "pdf-page";
  wrap.style.width = zoomW + "px";
  wrap.style.height = (p.height * sc) + "px";   // 비율 유지(폭*페이지비율)
  const img = document.createElement("img");
  img.src = `/api/pdf/page/${DOC_ID}/${p.page_no}?v=${EDIT_VER}`;
  img.draggable = false;
  wrap.appendChild(img);

  // 박스 오버레이 (이동/크기조절 가능)
  BOXES.forEach((box) => {
    if (box.page !== p.page_no) return;
    const idx = BOXES.indexOf(box);
    const d = document.createElement("div");
    d.className = "pbox" + (isSel(idx) ? " sel" : "") + (idx === selected ? " primary" : "") + (box.mode === "title" ? " title-mode" : "")
      + (box.mode === "table" ? " table-mode" : "");
    d.style.left = (box.x0 * sc) + "px";
    d.style.top = (box.y0 * sc) + "px";
    d.style.width = ((box.x1 - box.x0) * sc) + "px";
    d.style.height = ((box.y1 - box.y0) * sc) + "px";
    const mark = box.mode === "bold" ? "𝐁 " : box.mode === "check" ? "☑ " : box.mode === "title" ? "📑 "
      : box.mode === "number" ? "# " : box.mode === "image" ? "🖼 " : box.mode === "table" ? "▤ " : "";
    const tagText = box.mode === "table" && box.columns && box.columns.length
      ? `${box.field} · 줄마다 한 행 (${box.columns.length}열: ${box.columns.join(", ")})`
      : box.field;
    d.innerHTML = `<span class="pbox-tag">${mark}${tagText}<span class="pbox-x">✕</span></span>` +
                  `<span class="pbox-resize" title="크기 조절"></span>`;
    d.querySelector(".pbox-x").addEventListener("click", (e) => { e.stopPropagation(); deleteBox(idx); });
    d.querySelector(".pbox-x").addEventListener("mousedown", (e) => e.stopPropagation());
    d.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;  // 가운데/오른쪽 버튼은 패닝으로(박스 위에서도)
      e.stopPropagation();  // 새 박스 그리기 방지
      const kind = e.target.classList.contains("pbox-resize") ? "resize" : "move";
      startBoxDrag(e, idx, p, kind);
    });
    wrap.appendChild(d);
  });

  // 설문지로 인식된 문항 — 점선 상자(표시 전용, 편집 불가)
  SURVEY.forEach((it) => {
    if (it.page !== p.page_no) return;
    const d = document.createElement("div");
    d.className = "sbox";
    d.style.left = ((it.x0 - 3) * sc) + "px";
    d.style.top = ((it.y0 - 2) * sc) + "px";
    d.style.width = ((it.x1 - it.x0 + 6) * sc) + "px";
    d.style.height = ((it.y1 - it.y0 + 4) * sc) + "px";
    d.title = `${it.key}${it.choices ? ` · 선택지 ${it.choices}개` : " · 주관식"}`;
    d.innerHTML = `<span class="sbox-tag">${it.qid}</span>`;
    wrap.appendChild(d);
  });

  // 드래그로 새 박스
  wrap.addEventListener("mousedown", (e) => startDraw(e, wrap, p));
  host.appendChild(wrap);
  updateZoomLabel();
}

function startDraw(e, wrap, p) {
  if (e.button !== 0) return;   // 왼쪽 버튼만 박스 그리기(가운데/오른쪽은 패닝)
  const marquee = e.shiftKey || e.ctrlKey || e.metaKey;   // Shift/Ctrl + 빈 곳 드래그 = 영역 선택
  const rect = wrap.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const ghost = document.createElement("div");
  ghost.className = "pbox drawing" + (marquee ? " marquee" : "");
  wrap.appendChild(ghost);
  dragState = { wrap, p, sx, sy, ghost, rect };
  const move = (ev) => {
    const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
    const x0 = Math.min(sx, x), y0 = Math.min(sy, y);
    ghost.style.left = x0 + "px"; ghost.style.top = y0 + "px";
    ghost.style.width = Math.abs(x - sx) + "px"; ghost.style.height = Math.abs(y - sy) + "px";
  };
  const up = (ev) => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
    ghost.remove();
    if (marquee) finishMarquee(p, sx, sy, x, y, e.ctrlKey || e.metaKey);
    else finishDraw(p, sx, sy, x, y);
    dragState = null;
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
}

// 영역 선택: 끌어 놓은 사각형에 걸치는 이 쪽의 박스들을 선택(Ctrl 이면 기존 선택에 더함)
function finishMarquee(p, sx, sy, ex, ey, add) {
  const sc = scaleOf(p);
  const x0 = Math.min(sx, ex) / sc, y0 = Math.min(sy, ey) / sc;
  const x1 = Math.max(sx, ex) / sc, y1 = Math.max(sy, ey) / sc;
  if ((x1 - x0) < 4 || (y1 - y0) < 4) { renderPage(); return; }
  if (!add) clearSel();
  else if (selected != null && BOXES[selected]) SEL.add(BOXES[selected]);
  let last = null;
  BOXES.forEach((b, i) => {
    if (b.page !== p.page_no) return;
    if (b.x1 < x0 || b.x0 > x1 || b.y1 < y0 || b.y0 > y1) return;
    SEL.add(b); last = i;
  });
  if (last != null) { selected = last; selAnchor = last; }
  renderPage(); renderBoxes();
}

function finishDraw(p, sx, sy, ex, ey) {
  const sc = scaleOf(p);
  const x0 = Math.min(sx, ex) / sc, y0 = Math.min(sy, ey) / sc;
  const x1 = Math.max(sx, ex) / sc, y1 = Math.max(sy, ey) / sc;
  if ((x1 - x0) < 4 || (y1 - y0) < 4) { renderPage(); return; } // 너무 작으면 무시
  BOXES.push({
    order: 0, field: "새 항목", page: p.page_no,
    x0: +x0.toFixed(1), y0: +y0.toFixed(1), x1: +x1.toFixed(1), y1: +y1.toFixed(1),
    mode: "text", anchor: null, use_anchor: false, suggested: false,
  });
  selectOnly(BOXES.length - 1);
  sortBoxesByPosition();  // 그린 위치에 맞춰 목록 순서 자동 배치 (요청 ②)
  renderPage(); renderBoxes();
  setTimeout(() => { const inp = document.querySelector(".box-item.sel input"); if (inp) inp.select(); }, 30);
}

// 박스 이동/크기조절 (요청 ③) — 여러 개 선택된 상태에서 그중 하나를 끌면 선택 전체가 함께 움직인다
function startBoxDrag(e, idx, p, kind) {
  const box = BOXES[idx];
  const sc = scaleOf(p);
  const startX = e.clientX, startY = e.clientY;
  const group = (kind === "move" && isSel(idx) && selectedIdxs().length > 1) ? selectedIdxs() : [idx];
  const orig = group.map((i) => { const b = BOXES[i]; return { b, x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 }; });
  const o = orig.find((g) => g.b === box);
  let moved = false, undoPushed = false;
  const move = (ev) => {
    const dx = (ev.clientX - startX) / sc, dy = (ev.clientY - startY) / sc;
    if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 3) moved = true;
    if (moved && group.length > 1 && !undoPushed) {   // 여러 개를 함께 옮기기 전 상태를 되돌리기용으로
      undoPushed = true; UNDO.push(JSON.stringify(orig.map((g) => ({ ...g.b, x0: g.x0, y0: g.y0, x1: g.x1, y1: g.y1 }))
        .concat(BOXES.filter((b) => !group.includes(BOXES.indexOf(b))))));
    }
    if (kind === "resize") {
      box.x1 = Math.max(o.x0 + 4, o.x1 + dx);
      box.y1 = Math.max(o.y0 + 4, o.y1 + dy);
      box.use_anchor = false;  // 직접 조정하면 위치(좌표) 기준으로
    } else {
      orig.forEach((g) => { g.b.x0 = g.x0 + dx; g.b.y0 = g.y0 + dy; g.b.x1 = g.x1 + dx; g.b.y1 = g.y1 + dy; g.b.use_anchor = false; });
    }
    renderPage();
  };
  const up = () => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    if (!moved) { // 클릭(이동 없음) → 선택. Ctrl 클릭 = 추가/제외, Shift 클릭 = 범위. 해제는 Esc.
      pickSelect(idx, e); renderPage(); renderBoxes(); return;
    }
    orig.forEach((g) => { const b = g.b; [b.x0, b.y0, b.x1, b.y1] = [+b.x0.toFixed(1), +b.y0.toFixed(1), +b.x1.toFixed(1), +b.y1.toFixed(1)]; });
    sortBoxesByPosition();  // 위치 바뀌면 목록 순서도 갱신
    renderPage(); renderBoxes();
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
}

// 문서 위치(페이지→위→왼쪽) 순서로 order 재부여 (요청 ②)
function sortBoxesByPosition() {
  [...BOXES].sort((a, b) => (a.page - b.page) || (a.y0 - b.y0) || (a.x0 - b.x0))
    .forEach((b, i) => (b.order = i + 1));
}

// ---------- 박스 목록 ----------
const MODES = [["text", "일반"], ["number", "숫자"], ["bold", "굵게"], ["check", "체크"],
               ["image", "이미지"], ["title", "제목"], ["table", "표(여러 행)"]];
const REL = { right: "오른쪽", below: "아래", self: "그 칸" };
function anchorChip(box) {
  if (!box.anchor || !box.anchor.label) return "";
  if (!box.use_anchor) return `<button class="anchor-tg" title="라벨 기준 켜기/관계 변경">📍 위치</button>`;
  return `<button class="anchor-tg on" title="관계 변경(오른쪽→아래→위치)">🔗 ${box.anchor.label.slice(0,7)} ${REL[box.anchor.relation] || "오른쪽"}</button>`;
}

function renderBoxes() {
  $("boxCount").textContent = BOXES.length;
  renderSelBar();
  const list = $("boxList");
  const keepScroll = list.scrollTop;   // 다시 그려도 스크롤 위치는 유지(선택 항목이 안 보일 때만 옮긴다)
  list.innerHTML = "";
  const page = activePage;
  // 템플릿 모드: 캔버스가 없으므로 전체 항목을 한 목록으로 보여준다
  const pageBoxes = TPL_MODE
    ? [...BOXES].sort((a, b) => a.order - b.order)
    : [...BOXES].filter((b) => b.page === page).sort((a, b) => a.order - b.order);
  if (!pageBoxes.length) {
    const sv = SURVEY.filter((it) => it.page === page);
    if (sv.length) {
      // 설문지: 인식된 문항을 열 이름으로 보여 준다(편집 불가 — 데이터 추출 관리에서 그대로 열이 됨)
      list.innerHTML = `<li class="empty-hint">📋 설문지 문항 ${sv.length}개 인식 (엑셀 열 이름)</li>` +
        sv.map((it) => `<li class="survey-item"><span class="sq">${it.qid}</span>` +
          `<span class="st">${(it.text || it.key).replace(/</g, "&lt;")}</span>` +
          `<span class="sc">${it.choices ? "선택지 " + it.choices : "주관식"}</span></li>`).join("");
      return;
    }
    list.innerHTML = `<li class="empty-hint">이 쪽에는 항목이 없습니다. 문서에서 드래그해 추가하세요.</li>`; return;
  }
  pageBoxes.forEach((box) => {
    const idx = BOXES.indexOf(box);
    const mode = box.mode || "text";
    const li = document.createElement("li");
    li.className = "box-item" + (isSel(idx) ? " sel" : "") + (idx === selected ? " primary" : "");
    li.dataset.boxidx = idx;
    li.innerHTML =
      `<div class="bi-top">` +
        `<span class="drag-h" draggable="true">⠿</span>` +
        `<span class="ord">${box.order}</span>` +
        `<input type="text" value="${(box.field || "").replace(/"/g, "&quot;")}" />` +
        `<button class="del">✕</button>` +
      `</div>` +
      `<div class="bi-modes">` +
        MODES.map(([m, l]) => `<button class="mode ${mode === m ? "on" : ""}" data-m="${m}">${l}</button>`).join("") +
        anchorChip(box) +
        `<button class="swap-lbl" title="항목명을 위쪽 ↔ 왼쪽 칸 이름으로 전환합니다">⇄ 항목명</button>` +
        `<span class="loc">${box.page + 1}쪽</span>` +
      `</div>`;
    const input = li.querySelector("input");
    input.addEventListener("input", () => { box.field = input.value; renderPage(); });
    input.addEventListener("focus", () => {   // 이름을 고치려고 클릭 — 여러 선택 중이면 선택은 두고 대표만 바꾼다
      if (!isSel(idx)) selectOnly(idx); else selected = idx;
      renderPage();
    });
    li.querySelector(".del").addEventListener("click", () => deleteBox(idx));
    li.querySelectorAll(".mode").forEach((mb) => mb.addEventListener("click", () => {
      const targets = targetsOf(idx);            // 여러 개 선택 중이면 선택 전체의 유형을 한꺼번에
      if (targets.length > 1) pushUndo();
      targets.forEach((i) => (BOXES[i].mode = mb.dataset.m));
      renderBoxes(); renderPage();
    }));
    const atg = li.querySelector(".anchor-tg");
    if (atg) atg.addEventListener("click", () => cycleAnchor(idx));
    li.querySelector(".swap-lbl").addEventListener("click", () => swapLabel(idx));
    li.addEventListener("click", (e) => {
      if (["INPUT", "BUTTON", "SELECT"].includes(e.target.tagName) || e.target.classList.contains("drag-h")) return;
      pickSelect(idx, e); renderPage(); renderBoxes(); scrollCanvasToBox(idx);
    });
    const h = li.querySelector(".drag-h");
    h.addEventListener("dragstart", () => { dragBoxIdx = idx; });
    li.addEventListener("dragover", (e) => { if (dragBoxIdx !== null) { e.preventDefault(); li.classList.add("over"); } });
    li.addEventListener("dragleave", () => li.classList.remove("over"));
    li.addEventListener("drop", (e) => { e.preventDefault(); li.classList.remove("over"); if (dragBoxIdx !== null) reorderBox(dragBoxIdx, idx); dragBoxIdx = null; });
    list.appendChild(li);
  });
  list.scrollTop = keepScroll;
  scrollSelectedItemIntoView();  // 선택된 박스 항목으로 스크롤
}

// 선택된 박스에 해당하는 목록 항목이 안 보이면 목록 가운데로 스크롤하고, 선택이 바뀐 직후엔 잠깐 깜빡여 눈에 띄게
let lastSelObj = null;
function scrollSelectedItemIntoView() {
  if (selected == null) { lastSelObj = null; return; }
  const list = $("boxList");
  const el = list.querySelector(`.box-item[data-boxidx="${selected}"]`);
  if (!el) return;
  const top = el.offsetTop, h = el.offsetHeight;   // .box-list 가 position:relative 라 offsetTop 은 목록 기준
  if (top < list.scrollTop + 2 || top + h > list.scrollTop + list.clientHeight - 2)
    list.scrollTop = Math.max(0, top - (list.clientHeight - h) / 2);
  if (BOXES[selected] !== lastSelObj) {
    lastSelObj = BOXES[selected];
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 900);
  }
}

// 목록 항목을 클릭했을 때 — 캔버스에서 그 박스가 안 보이면 보이도록 스크롤
function scrollCanvasToBox(idx) {
  const b = BOXES[idx], host = $("pageHost");
  const page = host && host.querySelector(".pdf-page");
  const p = PAGES.find((x) => x.page_no === (b && b.page));
  if (!b || !page || !p) return;
  const sc = scaleOf(p), hr = host.getBoundingClientRect(), pr = page.getBoundingClientRect();
  const x = pr.left - hr.left + host.scrollLeft + b.x0 * sc, y = pr.top - hr.top + host.scrollTop + b.y0 * sc;
  const w = (b.x1 - b.x0) * sc, h = (b.y1 - b.y0) * sc;
  if (y < host.scrollTop || y + h > host.scrollTop + host.clientHeight)
    host.scrollTop = Math.max(0, y - (host.clientHeight - h) / 2);
  if (x < host.scrollLeft || x + w > host.scrollLeft + host.clientWidth)
    host.scrollLeft = Math.max(0, x - (host.clientWidth - w) / 2);
}

// 여러 개 선택됐을 때 목록 위 막대: 개수 · 한꺼번에 삭제 · 유형 바꾸기 · 라벨/위치 기준 · 선택 해제
function renderSelBar() {
  const bar = $("selBar"); if (!bar) return;
  const idxs = selectedIdxs();
  if (idxs.length < 2) { bar.hidden = true; bar.innerHTML = ""; return; }
  bar.hidden = false;
  bar.innerHTML = `<b>${idxs.length}개 선택</b>` +
    `<button class="mini-btn" id="selDel" title="선택한 박스를 모두 지웁니다 (Delete 키 · Ctrl+Z 로 되돌리기)">🗑 선택 삭제</button>` +
    `<select id="selMode" title="선택한 박스의 유형을 한꺼번에 바꿉니다"><option value="">유형 바꾸기…</option>` +
      MODES.map(([m, l]) => `<option value="${m}">${l}</option>`).join("") + `</select>` +
    `<button class="mini-btn" id="selAnchorOn" title="칸 이름(라벨)을 따라가 값을 찾도록 켭니다">🔗 라벨 기준</button>` +
    `<button class="mini-btn" id="selAnchorOff" title="좌표(위치) 기준으로 값을 찾도록 바꿉니다">📍 위치 기준</button>` +
    `<button class="mini-btn" id="selClear" title="선택 해제 (Esc)">선택 해제</button>`;
  $("selDel").addEventListener("click", deleteSelected);
  $("selMode").addEventListener("change", (e) => {
    const m = e.target.value; if (!m) return;
    pushUndo(); idxs.forEach((i) => (BOXES[i].mode = m)); renderBoxes(); renderPage();
  });
  $("selAnchorOn").addEventListener("click", () => {
    pushUndo();
    idxs.forEach((i) => { const b = BOXES[i]; if (b.anchor && b.anchor.label) { b.use_anchor = true; if (!b.anchor.relation) b.anchor.relation = "right"; } });
    renderBoxes();
  });
  $("selAnchorOff").addEventListener("click", () => { pushUndo(); idxs.forEach((i) => (BOXES[i].use_anchor = false)); renderBoxes(); });
  $("selClear").addEventListener("click", () => { clearSel(); renderPage(); renderBoxes(); });
}
let dragBoxIdx = null;
function reorderBox(from, to) {
  if (from === to) return;
  const seq = [...BOXES].sort((a, b) => a.order - b.order);
  const dp = seq.indexOf(BOXES[from]); const dragged = seq.splice(dp, 1)[0];
  const tp = seq.indexOf(BOXES[to]); seq.splice(tp, 0, dragged);
  seq.forEach((b, i) => (b.order = i + 1)); renderBoxes(); renderPage();
}
// 항목명 전환 — 박스(값 칸)의 이름을 위쪽 라벨 ↔ 왼쪽 라벨로 바꾼다.
// 추출 기준(앵커 라벨·방향)도 함께 바뀌어 유기적 추출이 새 라벨을 따라간다.
async function swapLabel(idx) {
  const b = BOXES[idx];
  if (!DOC_ID) { alert("양식 문서를 불러온 상태에서만 전환할 수 있습니다."); return; }
  try {
    const d = await (await fetch("/api/pdf/neighbor_labels", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: DOC_ID, page: b.page,
                             x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1 }),
    })).json();
    if (d.error) throw new Error(d.error);
    const left = (d.left || "").trim(), top = (d.top || "").trim();
    const curRel = (b.anchor && b.anchor.relation) || "right";  // 기본 = 왼쪽 라벨
    const next = curRel === "right"
      ? (top ? { label: top, relation: "below" } : null)
      : (left ? { label: left, relation: "right" } : null);
    if (!next) {
      alert(curRel === "right" ? "위쪽 칸에서 이름을 찾지 못했습니다." : "왼쪽 칸에서 이름을 찾지 못했습니다.");
      return;
    }
    b.field = next.label.slice(0, 20);
    b.anchor = { label: next.label, relation: next.relation };
    renderBoxes(); renderPage();
  } catch (e) { alert("항목명 전환 실패: " + e.message); }
}

function cycleAnchor(idx) {
  const box = BOXES[idx]; if (!box.anchor) return;
  const seq = ["right", "below", "off"];
  const cur = box.use_anchor ? (box.anchor.relation || "right") : "off";
  const next = seq[(seq.indexOf(cur) + 1) % seq.length];
  const targets = targetsOf(idx);           // 여러 개 선택 중이면 라벨이 있는 선택 전체를 같은 상태로
  if (targets.length > 1) pushUndo();
  targets.forEach((i) => {
    const b = BOXES[i]; if (!b.anchor || !b.anchor.label) return;
    if (next === "off") b.use_anchor = false;
    else { b.use_anchor = true; b.anchor.relation = next; }
  });
  renderBoxes();
}
function deleteBox(idx) {
  const b = BOXES[idx]; if (!b) return;
  pushUndo();
  SEL.delete(b);
  BOXES.splice(idx, 1);
  if (selected === idx) selected = null; else if (selected > idx) selected--;
  if (selAnchor === idx) selAnchor = null; else if (selAnchor > idx) selAnchor--;
  reindex(); renderPage(); renderBoxes();
}
// 선택한 박스 전부 삭제 (Delete 키 · 선택 막대) — Ctrl+Z 로 되돌릴 수 있다
function deleteSelected() {
  const idxs = selectedIdxs(); if (!idxs.length) return;
  pushUndo();
  const gone = new Set(idxs.map((i) => BOXES[i]));
  BOXES = BOXES.filter((b) => !gone.has(b));
  clearSel(); reindex(); renderPage(); renderBoxes();
}
function reindex() { [...BOXES].sort((a, b) => a.order - b.order).forEach((b, i) => (b.order = i + 1)); }

$("sortPosBtn").addEventListener("click", () => {
  [...BOXES].sort((a, b) => (a.page - b.page) || (a.y0 - b.y0) || (a.x0 - b.x0)).forEach((b, i) => (b.order = i + 1));
  renderBoxes();
});

// ---------- 확대/축소 ----------
$("zoomIn").addEventListener("click", () => setZoom(zoomW * ZOOM_STEP));
$("zoomOut").addEventListener("click", () => setZoom(zoomW / ZOOM_STEP));
$("zoomFit").addEventListener("click", () => fitZoom());
function fitZoom() {
  const host = $("pageHost");
  // #pageHost 좌우 패딩(16+16)만큼 빼서 페이지가 캔버스 안에 여백을 두고 딱 맞게.
  const w = (host && host.clientWidth) ? host.clientWidth - 36 : 700;
  setZoom(w);
}
// Ctrl + 휠로도 확대/축소
$("pageHost").addEventListener("wheel", (e) => {
  if (!e.ctrlKey) return;
  e.preventDefault();
  setZoom(e.deltaY < 0 ? zoomW * 1.1 : zoomW / 1.1);
}, { passive: false });

// 패닝: 휠 버튼(가운데) 또는 오른쪽 버튼 드래그 (요청 ②)
(() => {
  const host = $("pageHost");
  host.addEventListener("contextmenu", (e) => e.preventDefault());  // 오른쪽 메뉴 방지
  host.addEventListener("mousedown", (e) => {
    if (e.button !== 1 && e.button !== 2) return;  // 가운데/오른쪽만
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY, sl = host.scrollLeft, st = host.scrollTop;
    host.classList.add("panning");
    const move = (ev) => { host.scrollLeft = sl - (ev.clientX - sx); host.scrollTop = st - (ev.clientY - sy); };
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); host.classList.remove("panning"); };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
})();

// 키보드: Delete/Backspace 선택 삭제, Esc 선택 해제, Ctrl+A 이 쪽 전체 선택, Ctrl+Z 되돌리기
document.addEventListener("keydown", (e) => {
  const tag = (document.activeElement && document.activeElement.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;  // 입력 중이면 무시
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === "z") { if (UNDO.length) { e.preventDefault(); undoBoxes(); } return; }
  if (mod && e.key.toLowerCase() === "a") {
    const seq = listOrder();
    if (!seq.length || !$("main") || $("main").hidden) return;
    e.preventDefault(); clearSel(); seq.forEach((b) => SEL.add(b)); selected = BOXES.indexOf(seq[seq.length - 1]);
    renderPage(); renderBoxes(); return;
  }
  if (e.key === "Escape") { if (selected != null || SEL.size) { clearSel(); renderPage(); renderBoxes(); } return; }
  if (e.key !== "Delete" && e.key !== "Backspace") return;
  if (selectedIdxs().length) { e.preventDefault(); deleteSelected(); }
});

$("clearBtn").addEventListener("click", () => {
  if (!BOXES.length || confirm("이 문서의 박스를 모두 지울까요?")) { pushUndo(); BOXES = []; clearSel(); renderPageNav(); renderPage(); renderBoxes(); }
});

$("suggestBtn").addEventListener("click", async () => {
  if (!DOC_ID) return;
  showOverlay("자동 제안 계산 중…");
  try {
    const d = await (await fetch("/api/pdf/suggest/" + DOC_ID)).json();
    if (d.error) throw new Error(d.error);
    const start = Math.max(0, ...BOXES.map((b) => b.order));
    (d.boxes || []).forEach((b, i) => BOXES.push({ ...b, order: start + i + 1 }));
    renderPageNav(); renderPage(); renderBoxes();
    if (!(d.boxes || []).length) alert("자동 제안할 항목을 찾지 못했습니다. 직접 그려주세요.");
  } catch (e) { alert("자동 제안 실패: " + e.message); }
  finally { hideOverlay(); }
});

$("aiBtn").addEventListener("click", async () => {
  if (!DOC_ID) { alert("먼저 양식을 불러오세요."); return; }
  if (BOXES.length && !confirm(
    "🤖 AI가 양식을 읽고 추출 항목을 새로 제안합니다. 현재 박스는 이 결과로 교체됩니다.\n\n" +
    "※ 이 기능은 인터넷으로 Claude(외부 API)에 이 양식의 '칸 글자'를 보냅니다. " +
    "대량 실데이터 추출은 계속 이 PC 안에서만 처리됩니다.\n\n계속할까요?")) return;
  showOverlay("🤖 AI가 양식을 이해하는 중… (수십 초 걸릴 수 있어요)");
  try {
    const r = await fetch("/api/pdf/ai_understand/" + DOC_ID, { method: "POST" });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    pushUndo();
    BOXES = (d.boxes || []).map((b, i) => ({ ...b, order: b.order ?? i + 1 }));
    clearSel();
    renderPageNav(); renderPage(); renderBoxes();
    alert(`🤖 AI가 추출 항목 ${BOXES.length}개를 찾아 이름을 붙였습니다. 확인 후 필요하면 수정하세요.`);
  } catch (e) { alert("AI 자동 이해 실패:\n" + e.message); }
  finally { hideOverlay(); }
});

// ---------- 저장/적용/템플릿 ----------
$("saveBtn").addEventListener("click", async () => {
  const name = $("tplName").value.trim();
  if (!name) { alert("템플릿 이름을 입력하세요."); return; }
  reindex();
  const d = await (await fetch("/api/designer/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, boxes: BOXES, doc_id: DOC_ID }) })).json();
  $("saveMsg").textContent = d.ok
    ? `✅ '${name}' 저장됨 (${BOXES.length}개${d.pdf_saved ? " · 양식 PDF 포함" : ""})`
    : "저장 실패";
  // 같은 양식을 다른 이름으로 이미 저장해 둔 경우 — 일괄 처리는 방금 저장한 것을 우선 쓰지만 예전 것은 지우는 게 안전
  if (d.ok && d.duplicates && d.duplicates.length) {
    $("saveMsg").textContent += ` · ⚠️ 같은 양식의 템플릿 ${d.duplicates.map((n) => `'${n}'`).join(", ")}이(가) 이미 있습니다.`
      + ` 일괄 처리는 방금 저장한 '${name}'을 씁니다. 예전 것은 3번 목록에서 ✕로 지우세요. (데이터 추출 관리도 방금 저장한 것을 씁니다)`;
  }
  if (d.ok) loadTemplates();
});
async function loadTemplates() {
  try {
    const d = await (await fetch("/api/designer/templates")).json();
    const names = d.templates || [];
    renderTplList(names);
    // 진입 화면의 '템플릿으로 바로 시작' 선택지도 함께 갱신
    const sel = $("startTplSel");
    if (sel) {
      sel.innerHTML = `<option value="">— 저장된 템플릿 선택 —</option>` +
        names.map((n) => `<option value="${n}">${n}</option>`).join("");
      $("tplStart").hidden = names.length === 0;
    }
  } catch (e) {}
}
function renderTplList(names) {
  const host = $("tplList"); host.innerHTML = "";
  if (!names.length) { host.innerHTML = `<li class="empty-hint">저장된 템플릿이 없습니다.</li>`; return; }
  names.forEach((name) => {
    const li = document.createElement("li"); li.className = "tpl-item";
    li.innerHTML = `<span class="tpl-name">📄 ${name}</span><button class="tpl-load">불러오기</button><button class="tpl-del">✕</button>`;
    li.querySelector(".tpl-load").addEventListener("click", () => loadTemplate(name));
    li.querySelector(".tpl-del").addEventListener("click", () => deleteTemplate(name));
    host.appendChild(li);
  });
}
async function loadTemplate(name) {
  const d = await (await fetch("/api/designer/template?name=" + encodeURIComponent(name))).json();
  if (d.error) { alert(d.error); return; }
  BOXES = (d.boxes || []).map((b) => ({ ...b })); clearSel(); UNDO.length = 0;
  if (d.doc_id && d.pages && d.pages.length) {
    // 템플릿과 함께 저장된 양식 PDF가 있으면 캔버스에 그대로 보여준다
    DOC_ID = d.doc_id; PAGES = d.pages;
    exitTplMode();
    activePage = PAGES.length ? PAGES[0].page_no : 0;  // 항상 1페이지부터
  } else if (!DOC_ID) {  // PDF 없는(옛) 템플릿을 양식 없이 불러오면 템플릿 모드로
    TPL_MODE = true; PAGES = []; activePage = 0;
    $("tplBannerName").textContent = `'${name}'`;
    $("tplBanner").hidden = false;
    document.querySelector(".grid-pane").style.display = "none";
  }
  $("main").hidden = false;
  $("tplName").value = name; renderPageNav(); renderPage(); renderBoxes();
  if (!TPL_MODE) fitZoom();
  $("saveMsg").textContent = `📄 '${name}' 불러옴 (${BOXES.length}개${d.doc_id ? " · 양식 PDF 표시" : ""})`;
}
async function deleteTemplate(name) {
  if (!confirm(`'${name}' 삭제할까요?`)) return;
  const d = await (await fetch("/api/designer/template/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) })).json();
  renderTplList(d.templates || []);
}

function showOverlay(m) { $("overlayMsg").textContent = m || "처리 중…"; $("overlay").hidden = false; }
function hideOverlay() { $("overlay").hidden = true; }

// ---------- 템플릿으로 바로 시작(양식 업로드 없이) ----------
$("startTplBtn").addEventListener("click", async () => {
  const name = $("startTplSel").value;
  if (!name) { alert("시작할 템플릿을 선택하세요."); return; }
  showOverlay("템플릿과 양식을 불러오는 중…");
  try {
    DOC_ID = null; PAGES = []; activePage = 0;   // 진입 화면에서 새로 시작
    await loadTemplate(name);                     // PDF 있으면 캔버스, 없으면 템플릿 모드
    loadTemplates();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } finally { hideOverlay(); }
});
$("tplEditBtn").addEventListener("click", () => fi.click());
$("tplHomeBtn").addEventListener("click", () => location.reload());
$("addPageInput").addEventListener("change", () => {
  const f = $("addPageInput").files[0];
  if (f && DOC_ID) addPagesFile(f);
  $("addPageInput").value = "";
});

// 첫 화면에서도 저장된 템플릿을 바로 보여준다
loadTemplates();

// 실행 환경 자동 점검 — 한글(HWP) 없으면 안내(설치 없이 PDF는 그대로 가능)
(async () => {
  try {
    const s = await (await fetch("/api/env_status")).json();
    if (s.hwp === false) {
      const el = document.createElement("div");
      el.className = "env-warn";
      el.innerHTML = `⚠️ 이 컴퓨터에는 <b>한글(HWP)</b>이 없어 hwpx 변환은 사용할 수 없습니다. ` +
        `<b>PDF 파일은 그대로 사용 가능</b>합니다. hwpx도 쓰려면 ` +
        `<a href="${s.hwp_download}" target="_blank" rel="noopener">한컴 다운로드 페이지</a>에서 한글을 설치하세요.`;
      const badge = document.querySelector(".security-badge");
      badge.parentNode.insertBefore(el, badge.nextSibling);
    }
  } catch (e) {}
})();

// AI 기능 준비 상태 표시(패키지+API키). 준비 안 됐으면 버튼에 안내.
(async () => {
  try {
    const s = await (await fetch("/api/pdf/ai_status")).json();
    const btn = $("aiBtn"); if (!btn) return;
    if (!s.available) {
      btn.textContent = "🤖 AI 자동 이해 (설정 필요)";
      btn.style.opacity = ".6";
      btn.title = s.message || "AI 기능을 쓰려면 추가 설정이 필요합니다.";
    }
  } catch (e) {}
})();

