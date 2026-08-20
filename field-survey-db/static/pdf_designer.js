// PDF 통합 픽셀박스 디자이너
const $ = (id) => document.getElementById(id);
let DOC_ID = null, PAGES = [], BOXES = [], selected = null;
let TPL_MODE = false;   // 양식 없이 템플릿만 불러온 상태(캔버스 없음, 일괄 처리 중심)
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
  showOverlay("양식을 PDF로 변환·분석하는 중… (첫 파일은 다소 걸립니다)");
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
    activePage = PAGES.length ? PAGES[0].page_no : 0; selected = null;  // 항상 1페이지부터
    $("main").hidden = false;
    renderPageNav(); renderPage(); renderBoxes(); loadTemplates();
    fitZoom();  // 너비에 맞춰 시작
  } catch (e) { alert("불러오기 실패: " + e.message); }
  finally { hideOverlay(); }
}

function exitTplMode() {
  TPL_MODE = false;
  $("tplBanner").hidden = true;
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
      activePage = p.page_no; selected = null; renderPageNav(); renderPage(); renderBoxes();
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
    selected = null;
    renderPageNav(); renderPage(); renderBoxes(); fillFieldSelect();
  } catch (e) { alert("페이지 삭제 실패: " + e.message); }
  finally { hideOverlay(); }
}

async function addPagesFile(file) {
  showOverlay("페이지 추가 중… (hwpx는 PDF 변환에 시간이 걸립니다)");
  const fd = new FormData(); fd.append("file", file); fd.append("doc_id", DOC_ID);
  try {
    const d = await (await fetch("/api/pdf/pages/add", { method: "POST", body: fd })).json();
    if (d.error) throw new Error(d.error);
    PAGES = d.pages; EDIT_VER++;
    const start = Math.max(0, ...BOXES.map((b) => b.order || 0));
    (d.new_boxes || []).forEach((b, i) => BOXES.push({ ...b, order: start + i + 1 }));
    activePage = d.first_new_page; selected = null;
    renderPageNav(); renderPage(); renderBoxes(); fillFieldSelect();
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
    d.className = "pbox" + (idx === selected ? " sel" : "");
    d.style.left = (box.x0 * sc) + "px";
    d.style.top = (box.y0 * sc) + "px";
    d.style.width = ((box.x1 - box.x0) * sc) + "px";
    d.style.height = ((box.y1 - box.y0) * sc) + "px";
    const mark = box.mode === "bold" ? "𝐁 " : box.mode === "check" ? "☑ " : "";
    d.innerHTML = `<span class="pbox-tag">${mark}${box.field}<span class="pbox-x">✕</span></span>` +
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

  // 드래그로 새 박스
  wrap.addEventListener("mousedown", (e) => startDraw(e, wrap, p));
  host.appendChild(wrap);
  updateZoomLabel();
}

function startDraw(e, wrap, p) {
  if (e.button !== 0) return;   // 왼쪽 버튼만 박스 그리기(가운데/오른쪽은 패닝)
  const rect = wrap.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const ghost = document.createElement("div");
  ghost.className = "pbox drawing";
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
    finishDraw(p, sx, sy, x, y);
    dragState = null;
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
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
  selected = BOXES.length - 1;
  sortBoxesByPosition();  // 그린 위치에 맞춰 목록 순서 자동 배치 (요청 ②)
  renderPage(); renderBoxes();
  setTimeout(() => { const inp = document.querySelector(".box-item.sel input"); if (inp) inp.select(); }, 30);
}

// 박스 이동/크기조절 (요청 ③)
function startBoxDrag(e, idx, p, kind) {
  const box = BOXES[idx];
  const sc = scaleOf(p);
  const startX = e.clientX, startY = e.clientY;
  const o = { x0: box.x0, y0: box.y0, x1: box.x1, y1: box.y1 };
  let moved = false;
  const move = (ev) => {
    const dx = (ev.clientX - startX) / sc, dy = (ev.clientY - startY) / sc;
    if (Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) > 3) moved = true;
    if (kind === "resize") {
      box.x1 = Math.max(o.x0 + 4, o.x1 + dx);
      box.y1 = Math.max(o.y0 + 4, o.y1 + dy);
    } else {
      box.x0 = o.x0 + dx; box.y0 = o.y0 + dy;
      box.x1 = o.x1 + dx; box.y1 = o.y1 + dy;
    }
    box.use_anchor = false;  // 직접 조정하면 위치(좌표) 기준으로
    renderPage();
  };
  const up = () => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    if (!moved) { // 클릭(이동 없음) → 선택(재클릭해도 유지). 해제는 Esc.
      selected = idx; renderPage(); renderBoxes(); return;
    }
    [box.x0, box.y0, box.x1, box.y1] = [+box.x0.toFixed(1), +box.y0.toFixed(1), +box.x1.toFixed(1), +box.y1.toFixed(1)];
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
const MODES = [["text", "일반"], ["bold", "굵게"], ["check", "체크"]];
const REL = { right: "오른쪽", below: "아래", self: "그 칸" };
function anchorChip(box) {
  if (!box.anchor || !box.anchor.label) return "";
  if (!box.use_anchor) return `<button class="anchor-tg" title="라벨 기준 켜기/관계 변경">📍 위치</button>`;
  return `<button class="anchor-tg on" title="관계 변경(오른쪽→아래→위치)">🔗 ${box.anchor.label.slice(0,7)} ${REL[box.anchor.relation] || "오른쪽"}</button>`;
}

function renderBoxes() {
  $("boxCount").textContent = BOXES.length;
  const list = $("boxList"); list.innerHTML = "";
  const page = activePage;
  // 템플릿 모드: 캔버스가 없으므로 전체 항목을 한 목록으로 보여준다
  const pageBoxes = TPL_MODE
    ? [...BOXES].sort((a, b) => a.order - b.order)
    : [...BOXES].filter((b) => b.page === page).sort((a, b) => a.order - b.order);
  if (!pageBoxes.length) { list.innerHTML = `<li class="empty-hint">이 쪽에는 항목이 없습니다. 문서에서 드래그해 추가하세요.</li>`; return; }
  pageBoxes.forEach((box) => {
    const idx = BOXES.indexOf(box);
    const mode = box.mode || "text";
    const li = document.createElement("li");
    li.className = "box-item" + (idx === selected ? " sel" : "");
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
        anchorChip(box) + `<span class="loc">${box.page + 1}쪽</span>` +
      `</div>`;
    const input = li.querySelector("input");
    input.addEventListener("input", () => { box.field = input.value; renderPage(); });
    input.addEventListener("focus", () => { selected = idx; renderPage(); });
    li.querySelector(".del").addEventListener("click", () => deleteBox(idx));
    li.querySelectorAll(".mode").forEach((mb) => mb.addEventListener("click", () => { box.mode = mb.dataset.m; renderBoxes(); renderPage(); }));
    const atg = li.querySelector(".anchor-tg");
    if (atg) atg.addEventListener("click", () => cycleAnchor(idx));
    li.addEventListener("click", (e) => { if (!["INPUT", "BUTTON"].includes(e.target.tagName) && !e.target.classList.contains("drag-h")) { selected = idx; renderPage(); renderBoxes(); } });
    const h = li.querySelector(".drag-h");
    h.addEventListener("dragstart", () => { dragBoxIdx = idx; });
    li.addEventListener("dragover", (e) => { if (dragBoxIdx !== null) { e.preventDefault(); li.classList.add("over"); } });
    li.addEventListener("dragleave", () => li.classList.remove("over"));
    li.addEventListener("drop", (e) => { e.preventDefault(); li.classList.remove("over"); if (dragBoxIdx !== null) reorderBox(dragBoxIdx, idx); dragBoxIdx = null; });
    list.appendChild(li);
  });
  scrollSelectedItemIntoView();  // 선택된 박스 항목으로 스크롤
}

// 선택된 박스에 해당하는 목록 항목을 보이도록 스크롤
function scrollSelectedItemIntoView() {
  if (selected == null) return;
  const list = $("boxList");
  const el = list.querySelector(`.box-item[data-boxidx="${selected}"]`);
  if (!el) return;
  const top = el.offsetTop - list.offsetTop;
  if (top < list.scrollTop) list.scrollTop = top - 4;
  else if (top + el.offsetHeight > list.scrollTop + list.clientHeight)
    list.scrollTop = top + el.offsetHeight - list.clientHeight + 4;
}
let dragBoxIdx = null;
function reorderBox(from, to) {
  if (from === to) return;
  const seq = [...BOXES].sort((a, b) => a.order - b.order);
  const dp = seq.indexOf(BOXES[from]); const dragged = seq.splice(dp, 1)[0];
  const tp = seq.indexOf(BOXES[to]); seq.splice(tp, 0, dragged);
  seq.forEach((b, i) => (b.order = i + 1)); renderBoxes(); renderPage();
}
function cycleAnchor(idx) {
  const box = BOXES[idx]; if (!box.anchor) return;
  const seq = ["right", "below", "off"];
  const cur = box.use_anchor ? (box.anchor.relation || "right") : "off";
  const next = seq[(seq.indexOf(cur) + 1) % seq.length];
  if (next === "off") box.use_anchor = false;
  else { box.use_anchor = true; box.anchor.relation = next; }
  renderBoxes();
}
function deleteBox(idx) {
  BOXES.splice(idx, 1);
  if (selected === idx) selected = null; else if (selected > idx) selected--;
  reindex(); renderPage(); renderBoxes();
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

// 키보드: Delete/Backspace 삭제, Esc 선택 해제
document.addEventListener("keydown", (e) => {
  const tag = (document.activeElement && document.activeElement.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") return;  // 입력 중이면 무시
  if (e.key === "Escape") { if (selected != null) { selected = null; renderPage(); renderBoxes(); } return; }
  if (e.key !== "Delete" && e.key !== "Backspace") return;
  if (selected != null && BOXES[selected]) { e.preventDefault(); deleteBox(selected); }
});

$("clearBtn").addEventListener("click", () => {
  if (!BOXES.length || confirm("이 문서의 박스를 모두 지울까요?")) { BOXES = []; selected = null; renderPageNav(); renderPage(); renderBoxes(); }
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
    BOXES = (d.boxes || []).map((b, i) => ({ ...b, order: b.order ?? i + 1 }));
    selected = null;
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
  BOXES = (d.boxes || []).map((b) => ({ ...b })); selected = null;
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
  $("tplName").value = name; renderPageNav(); renderPage(); renderBoxes(); fillFieldSelect();
  if (!TPL_MODE) fitZoom();
  $("saveMsg").textContent = `📄 '${name}' 불러옴 (${BOXES.length}개${d.doc_id ? " · 양식 PDF 표시" : ""})`;
}
async function deleteTemplate(name) {
  if (!confirm(`'${name}' 삭제할까요?`)) return;
  const d = await (await fetch("/api/designer/template/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) })).json();
  renderTplList(d.templates || []);
}

$("applyBtn").addEventListener("click", async () => {
  const files = $("applyInput").files;
  if (!files.length) { alert("처리할 파일을 선택하세요."); return; }
  reindex();
  showOverlay("추출하는 중… (파일마다 PDF 변환)");
  const fd = new FormData(); fd.append("boxes", JSON.stringify(BOXES));
  for (const f of files) fd.append("files", f);
  fd.append("sheet_name_field", $("sheetNameSel").value || "");
  if (REPORT.report_id) {
    fd.append("report_id", REPORT.report_id);
    fd.append("report_edits", JSON.stringify(REPORT.edits));
  }
  try {
    const d = await (await fetch("/api/pdf/apply", { method: "POST", body: fd })).json();
    if (d.error) throw new Error(d.error);
    renderApply(d);
  } catch (e) { alert("추출 실패: " + e.message); }
  finally { hideOverlay(); }
});
// ---------- 보고서 양식 편집기 ----------
let REPORT = { report_id: null, cells: [], nrows: 0, ncols: 0, edits: {}, focusCell: null };

$("reportInput").addEventListener("change", async () => {
  const f = $("reportInput").files[0];
  if (!f) return;
  showOverlay("양식을 불러오는 중…");
  const fd = new FormData(); fd.append("file", f);
  try {
    const d = await (await fetch("/api/report/load", { method: "POST", body: fd })).json();
    if (d.error) throw new Error(d.error);
    REPORT = { report_id: d.report_id, cells: d.cells, nrows: d.nrows, ncols: d.ncols, edits: {}, focusCell: null };
    $("reportMsg").textContent = `📋 '${d.filename}' — ${d.nrows}행 × ${d.ncols}열` +
      (d.placeholders && d.placeholders.length ? ` · 자리표시자: ${d.placeholders.join(", ")}` : "");
    $("reportEditor").hidden = false;
    fillFieldSelect();
    renderReportGrid();
  } catch (e) { alert("양식 불러오기 실패: " + e.message); }
  finally { hideOverlay(); }
});

function colLetter(n) { let s = ""; n++; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }

function renderReportGrid() {
  const t = $("rptGrid"); t.innerHTML = "";
  // 헤더(열문자)
  let head = "<thead><tr><th></th>";
  for (let c = 0; c < REPORT.ncols; c++) head += `<th>${colLetter(c)}</th>`;
  head += "</tr></thead>";
  let body = "<tbody>";
  for (let r = 0; r < REPORT.nrows; r++) {
    body += `<tr><th>${r + 1}</th>`;
    for (let c = 0; c < REPORT.ncols; c++) {
      const v = (REPORT.cells[r] && REPORT.cells[r][c]) || "";
      const cls = v.startsWith("=") ? "formula" : (v.includes("{") ? "ph" : "");
      body += `<td><input class="${cls}" data-r="${r + 1}" data-c="${c + 1}" value="${v.replace(/"/g, "&quot;")}" /></td>`;
    }
    body += "</tr>";
  }
  body += "</tbody>";
  t.innerHTML = head + body;
  t.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("focus", () => { REPORT.focusCell = inp; });
    inp.addEventListener("input", () => {
      const key = `${inp.dataset.r},${inp.dataset.c}`;
      REPORT.edits[key] = inp.value;
      inp.className = inp.value.startsWith("=") ? "formula" : (inp.value.includes("{") ? "ph" : "");
    });
  });
}

function fillFieldSelect() {
  const names = [...new Set(BOXES.map((b) => b.field).filter(Boolean))].sort();
  const opts = names.map((n) => `<option value="${n}">${n}</option>`).join("");
  $("rptFieldSel").innerHTML = `<option value="">— 추출 항목 —</option>` + opts;
  // 대상지별 시트 이름 선택(일괄 처리)도 같은 항목으로 채움 — 선택 유지
  const ss = $("sheetNameSel");
  const keep = ss.value;
  ss.innerHTML = `<option value="">사용 안 함 (요약표만)</option>` + opts;
  if (names.includes(keep)) ss.value = keep;
}

$("rptInsertBtn").addEventListener("click", () => {
  const name = $("rptFieldSel").value;
  if (!name) { alert("삽입할 추출 항목을 선택하세요."); return; }
  const inp = REPORT.focusCell;
  if (!inp) { alert("먼저 표에서 넣을 칸을 클릭하세요."); return; }
  inp.value = (inp.value || "") + `{${name}}`;
  inp.dispatchEvent(new Event("input"));
  inp.focus();
});

function renderApply(d) {
  let html = `<p class="muted">✅ ${d.ok_count}개 처리` + (d.failed.length ? ` · ⚠️ ${d.failed.length}개 실패` : "") + `</p>`;
  if (d.report_used) html += `<p class="muted">📋 보고서 양식 반영됨 (요약표 + 파일별 보고서 시트)</p>`;
  if (d.match_info && d.match_info.length) {
    const mi = d.match_info;
    const multi = mi.filter((m) => (m.bundles || 1) > 1);
    if (multi.length) {
      html += `<p class="muted">📚 묶음 인식: ` +
        multi.map((m) => `${m.name} → <b>${m.bundles}묶음(${m.bundles}행)</b>`).join(", ") + `</p>`;
    }
    const anyPartial = mi.some((m) => m.matched < m.template_pages);
    if (anyPartial) {
      html += `<p class="muted">📄 페이지 자동 매칭: ` +
        mi.map((m) => `${m.name}(${m.input_pages}장 중 ${m.matched}개 서식 매칭)`).join(", ") + `</p>`;
    }
  }
  html += `<button class="btn btn-download" onclick="window.location.href='/api/pdf/download'">📥 엑셀 다운로드</button>`;
  // 빈칸·이상치 요약(#3)
  const OL = d.outliers || [];
  const totalCells = d.rows.length * d.fields.length;
  let blanks = 0;
  d.rows.forEach((row) => d.fields.forEach((f) => { if (!String(row[f] || "").trim()) blanks++; }));
  html += `<p style="margin:10px 0 4px;font-size:13px">📊 <b>${d.rows.length}행 × ${d.fields.length}항목 = ${totalCells}칸</b> 중 · `
    + `빈칸 <b style="color:#b0870b">${blanks}개</b> · 이상치 <b style="color:#e8590c">${d.outlier_count || 0}건</b>`
    + (d.outlier_count ? ` <span class="muted">(주황 칸 확인)</span>` : ``)
    + ` <span class="muted">— 자세한 해석은 아래 6번 ‘AI 결과 해석’</span></p>`;
  html += `<div style="overflow:auto"><table class="apply-table"><thead><tr><th>파일</th>` + d.fields.map((f) => `<th>${f}</th>`).join("") + `</tr></thead><tbody>`;
  d.rows.forEach((row, i) => {
    const ol = OL[i] || {};
    html += `<tr><td>${row["_파일명"] || ""}</td>` + d.fields.map((f) => {
      const v = (row[f] || "").slice(0, 18);
      return ol[f]
        ? `<td style="background:#fff0e0;border:1px solid #ff922b" title="${ol[f]}">⚠️ ${v}</td>`
        : `<td>${v}</td>`;
    }).join("") + `</tr>`;
  });
  html += `</tbody></table></div>`; $("applyResult").innerHTML = html;
}

async function pdfAnalyze() {
  const btn = $("pdfAnalyzeBtn"), panel = $("pdfAnalysis"), old = btn.textContent;
  btn.disabled = true; btn.textContent = "분석 중…";
  panel.style.display = "block"; panel.textContent = "⏳ AI가 추출된 데이터를 분석하는 중…";
  try {
    const d = await (await fetch("/api/pdf/analyze", { method: "POST" })).json();
    if (d.error) { panel.textContent = "오류: " + d.error; return; }
    const esc = (d.analysis || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    panel.innerHTML = esc.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  } catch (e) { panel.textContent = "분석 실패: " + e; }
  finally { btn.disabled = false; btn.textContent = old; }
}
$("pdfAnalyzeBtn").addEventListener("click", pdfAnalyze);   // 6. AI 결과 해석(정적 버튼)

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
