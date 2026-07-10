// 템플릿 디자이너 (비율 격자 + 페이지 그룹 + 드래그 박스)
const $ = (id) => document.getElementById(id);
let TABLES = [], BOXES = [], GROUPS = [];
let activeGroup = 0;
let selected = null;
// 드래그 상태
let drag = null; // {ti, r0, c0, r1, c1}

// ---------- 불러오기 ----------
const dz = $("dropzone"), fi = $("fileInput");
dz.addEventListener("click", () => fi.click());
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files[0]) loadForm(e.dataTransfer.files[0]); });
fi.addEventListener("change", () => { if (fi.files[0]) loadForm(fi.files[0]); });

async function loadForm(file) {
  showOverlay("양식을 분석하는 중…");
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch("/api/designer/load", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    TABLES = data.tables;
    BOXES = data.boxes.map((b, i) => ({ ...b, order: b.order ?? i + 1 }));
    buildGroups();
    renumberByPosition();          // 문서 위치 순서로 (요청 ①)
    activeGroup = groupWithMostBoxes();
    selected = null;
    $("main").hidden = false;
    renderGroupTabs(); renderActiveGroup(); renderBoxes();
    loadTemplates();
  } catch (e) { alert("불러오기 실패: " + e.message); }
  finally { hideOverlay(); }
}

// 문서에 나온 위치(페이지→표→행→열) 순서대로 order 재부여 (요청 ①)
function groupIndexOfTable(ti) { return GROUPS.findIndex((g) => g.tables.includes(ti)); }
function renumberByPosition() {
  const sorted = [...BOXES].sort((a, b) => {
    const ga = groupIndexOfTable(a.table), gb = groupIndexOfTable(b.table);
    if (ga !== gb) return ga - gb;
    if (a.table !== b.table) return a.table - b.table;
    const ca = (a.cells || [])[0] || { r: 0, c: 0 }, cb = (b.cells || [])[0] || { r: 0, c: 0 };
    if (ca.r !== cb.r) return ca.r - cb.r;
    return ca.c - cb.c;
  });
  sorted.forEach((b, i) => (b.order = i + 1));
}

// ---------- 페이지(서식) 그룹 ----------
function buildGroups() {
  GROUPS = [];
  let cur = null, lastReal = null;
  for (const t of TABLES) {
    let label = t.form_label;
    // 미상/현장사진은 직전의 실제 서식에 붙인다(페이지 연속성)
    if ((label === "미상" || label === "현장사진") && lastReal) label = lastReal;
    else if (label !== "미상" && label !== "현장사진") lastReal = label;
    if (!cur || cur.label !== label) { cur = { label, tables: [] }; GROUPS.push(cur); }
    cur.tables.push(t.table);
  }
}
function groupWithMostBoxes() {
  let best = 0, max = -1;
  GROUPS.forEach((g, i) => {
    const n = BOXES.filter((b) => g.tables.includes(b.table)).length;
    if (n > max) { max = n; best = i; }
  });
  return best;
}
function tableByIndex(ti) { return TABLES.find((t) => t.table === ti); }

function renderGroupTabs() {
  const host = $("tablePicker");
  host.innerHTML = "";
  GROUPS.forEach((g, i) => {
    const n = BOXES.filter((b) => g.tables.includes(b.table)).length;
    const b = document.createElement("button");
    b.className = "tp-btn" + (i === activeGroup ? " active" : "");
    b.innerHTML = `${g.label}<span class="n">${n ? n + "칸" : ""}</span>`;
    b.addEventListener("click", () => { activeGroup = i; selected = null; renderGroupTabs(); renderActiveGroup(); renderBoxes(); });
    host.appendChild(b);
  });
}

// ---------- 좌표 도우미 ----------
function coverMap(t) {
  const m = {};
  for (const c of t.cells)
    for (let dr = 0; dr < (c.rs || 1); dr++)
      for (let dc = 0; dc < (c.cs || 1); dc++) m[`${c.r + dr},${c.c + dc}`] = c;
  return m;
}
function boxIndexAtCell(ti, r, c) {
  return BOXES.findIndex((b) => b.table === ti && (b.cells || []).some((x) => x.r === r && x.c === c));
}
function firstCellOfBox(b) { return (b.cells || [])[0]; }

// ---------- 비율 격자 렌더 ----------
function renderActiveGroup() {
  const host = $("gridHost");
  host.innerHTML = "";
  const g = GROUPS[activeGroup];
  for (const ti of g.tables) {
    const t = tableByIndex(ti);
    const wrap = document.createElement("div");
    wrap.className = "tbl-wrap";
    wrap.innerHTML = `<div class="tbl-cap">표 ${ti + 1}</div>`;
    const scroll = document.createElement("div");
    scroll.className = "grid-scroll";
    const grid = document.createElement("div");
    grid.className = "dgrid";
    grid.dataset.ti = ti;
    grid.style.gridTemplateColumns = (t.col_widths || []).map((w) => w + "px").join(" ");
    grid.style.gridTemplateRows = (t.row_heights || []).map((h) => h + "px").join(" ");

    for (const c of t.cells) {
      const cell = document.createElement("div");
      cell.className = "dcell" + (c.text.trim() ? "" : " empty");
      cell.style.gridColumn = `${c.c + 1} / span ${c.cs || 1}`;
      cell.style.gridRow = `${c.r + 1} / span ${c.rs || 1}`;
      cell.textContent = c.text || "";
      cell.title = c.text || "";
      cell.dataset.r = c.r; cell.dataset.c = c.c;
      const bi = boxIndexAtCell(ti, c.r, c.c);
      if (bi >= 0) {
        cell.classList.add("boxed");
        if (bi === selected) cell.classList.add("sel");
        const fc = firstCellOfBox(BOXES[bi]);
        if (fc && fc.r === c.r && fc.c === c.c) {
          const tag = document.createElement("span");
          tag.className = "ftag";
          const modeMark = BOXES[bi].mode === "bold" ? "𝐁 " : BOXES[bi].mode === "check" ? "☑ " : "";
          tag.innerHTML = `<span class="ft-name">${modeMark}${BOXES[bi].field}</span><span class="ft-x" title="삭제">✕</span>`;
          const x = tag.querySelector(".ft-x");
          x.addEventListener("mousedown", (e) => { e.stopPropagation(); e.preventDefault(); });
          x.addEventListener("click", (e) => { e.stopPropagation(); deleteBox(bi); });
          cell.appendChild(tag);
        }
      }
      cell.addEventListener("mousedown", (e) => startDrag(e, ti, c.r, c.c));
      cell.addEventListener("mouseenter", () => extendDrag(ti, c.r, c.c));
      grid.appendChild(cell);
    }
    scroll.appendChild(grid);
    wrap.appendChild(scroll);
    host.appendChild(wrap);
  }
}

// ---------- 드래그로 박스 ----------
function startDrag(e, ti, r, c) {
  e.preventDefault();
  drag = { ti, r0: r, c0: c, r1: r, c1: c };
  paintDrag();
}
function extendDrag(ti, r, c) {
  if (!drag || drag.ti !== ti) return;
  drag.r1 = r; drag.c1 = c;
  paintDrag();
}
function paintDrag() {
  document.querySelectorAll(".dcell.dragsel").forEach((el) => el.classList.remove("dragsel"));
  if (!drag) return;
  const [minr, maxr] = [Math.min(drag.r0, drag.r1), Math.max(drag.r0, drag.r1)];
  const [minc, maxc] = [Math.min(drag.c0, drag.c1), Math.max(drag.c0, drag.c1)];
  const grid = document.querySelector(`.dgrid[data-ti="${drag.ti}"]`);
  if (!grid) return;
  grid.querySelectorAll(".dcell").forEach((el) => {
    const r = +el.dataset.r, c = +el.dataset.c;
    if (r >= minr && r <= maxr && c >= minc && c <= maxc) el.classList.add("dragsel");
  });
}
document.addEventListener("mouseup", () => {
  if (!drag) return;
  const d = drag; drag = null;
  document.querySelectorAll(".dcell.dragsel").forEach((el) => el.classList.remove("dragsel"));
  const [minr, maxr] = [Math.min(d.r0, d.r1), Math.max(d.r0, d.r1)];
  const [minc, maxc] = [Math.min(d.c0, d.c1), Math.max(d.c0, d.c1)];
  const single = minr === maxr && minc === maxc;
  if (single) {
    const bi = boxIndexAtCell(d.ti, minr, minc);
    if (bi >= 0) {
      // 이미 선택된 박스면 해제(토글) — 요청 ②
      selected = (selected === bi) ? null : bi;
      renderActiveGroup(); renderBoxes(); return;
    }
  }
  // 범위 내 셀들의 원점을 모아 하나의 박스 생성
  const t = tableByIndex(d.ti);
  const cells = [];
  for (const c of t.cells) {
    const rr = c.r, cc = c.c, re = c.r + (c.rs || 1) - 1, ce = c.c + (c.cs || 1) - 1;
    if (rr <= maxr && re >= minr && cc <= maxc && ce >= minc && c.text.trim())
      cells.push({ r: c.r, c: c.c });
  }
  if (!cells.length) cells.push({ r: minr, c: minc });
  const order = Math.max(0, ...BOXES.map((b) => b.order)) + 1;
  const g = guessAnchor(d.ti, minr, minc);
  BOXES.push({
    order, field: g.field, table: d.ti, cells, suggested: false,
    anchor: g.anchor, use_anchor: !!g.anchor, label_cell: g.label_cell,
  });
  selected = BOXES.length - 1;
  renderActiveGroup(); renderBoxes();
  setTimeout(() => { const inp = document.querySelector(".box-item.sel input"); if (inp) inp.select(); }, 30);
});

// 값 칸 왼쪽/위 라벨을 찾아 이름 + 앵커(라벨 기준) 추정
function guessAnchor(ti, r, c) {
  const m = coverMap(tableByIndex(ti));
  const left = m[`${r},${c - 1}`];
  if (left && left.text.trim())
    return { field: left.text.trim().slice(0, 20), anchor: { label: left.text.trim(), relation: "right" }, label_cell: { r: left.r, c: left.c } };
  const up = m[`${r - 1},${c}`];
  if (up && up.text.trim())
    return { field: up.text.trim().slice(0, 20), anchor: { label: up.text.trim(), relation: "below" }, label_cell: { r: up.r, c: up.c } };
  return { field: "새 항목", anchor: null, label_cell: null };
}

// 라벨 칸 + 관계로 값 칸 좌표를 다시 계산 (관계를 바꿀 때 사용)
function valueCellFor(ti, labelCell, relation) {
  const t = tableByIndex(ti);
  const lc = (t.cells || []).find((x) => x.r === labelCell.r && x.c === labelCell.c) || labelCell;
  if (relation === "self") return { r: lc.r, c: lc.c };
  if (relation === "below") return { r: lc.r + (lc.rs || 1), c: lc.c };
  return { r: lc.r, c: lc.c + (lc.cs || 1) }; // right
}

// 앵커 관계 순환: right → below → off(위치 기준) → right
function cycleAnchor(idx) {
  const box = BOXES[idx];
  if (!box.anchor) return;
  const seq = ["right", "below", "off"];
  const cur = box.use_anchor ? (box.anchor.relation || "right") : "off";
  const next = seq[(seq.indexOf(cur) + 1) % seq.length];
  if (next === "off") { box.use_anchor = false; }
  else {
    box.use_anchor = true;
    box.anchor.relation = next;
    if (box.label_cell) box.cells = [valueCellFor(box.table, box.label_cell, next)];
  }
  renderBoxes(); renderActiveGroup();
}

// ---------- 박스 목록 (현재 페이지만) ----------
const MODES = [["text", "일반"], ["bold", "굵게"], ["check", "체크"]];
const REL_ARROW = { right: "오른쪽", below: "아래", self: "그 칸" };
function anchorChip(box) {
  if (!box.anchor || !box.anchor.label) return "";
  const lbl = box.anchor.label.slice(0, 7);
  const title = "클릭하면 관계 변경(오른쪽→아래→그칸→위치기준). 라벨 기준이면 양식 편차·PDF에도 대응됩니다.";
  if (!box.use_anchor) return `<button class="anchor-tg" title="${title}">📍 위치 기준</button>`;
  const rel = REL_ARROW[box.anchor.relation] || "오른쪽";
  return `<button class="anchor-tg on" title="${title}">🔗 ${lbl} ${rel}</button>`;
}
function renderBoxes() {
  $("boxCount").textContent = BOXES.length;
  const list = $("boxList");
  list.innerHTML = "";
  const gTables = GROUPS[activeGroup] ? GROUPS[activeGroup].tables : [];
  // 현재 페이지의 박스만, 순서대로
  const pageBoxes = [...BOXES].filter((b) => gTables.includes(b.table)).sort((a, b) => a.order - b.order);
  if (!pageBoxes.length) { list.innerHTML = `<li class="empty-hint">이 페이지에는 추출 항목이 없습니다. 표에서 드래그해 추가하세요.</li>`; return; }

  pageBoxes.forEach((box) => {
    const idx = BOXES.indexOf(box);
    const mode = box.mode || "text";
    const li = document.createElement("li");
    li.className = "box-item" + (idx === selected ? " sel" : "");
    li.dataset.idx = idx;
    li.innerHTML =
      `<div class="bi-top">` +
        `<span class="drag-h" draggable="true" title="드래그로 순서 변경">⠿</span>` +
        `<span class="ord">${box.order}</span>` +
        `<input type="text" value="${(box.field || "").replace(/"/g, "&quot;")}" />` +
        `<button class="up" title="위로">▲</button><button class="down" title="아래로">▼</button><button class="del" title="삭제">✕</button>` +
      `</div>` +
      `<div class="bi-modes">` +
        MODES.map(([m, lbl]) => `<button class="mode ${mode === m ? "on" : ""}" data-m="${m}">${lbl}</button>`).join("") +
        anchorChip(box) +
        `<span class="loc">표${box.table + 1}</span>` +
      `</div>`;
    const input = li.querySelector("input");
    input.addEventListener("input", () => { box.field = input.value; renderActiveGroup(); });
    input.addEventListener("focus", () => { selected = idx; renderActiveGroup(); highlightSelList(); });
    li.querySelector(".up").addEventListener("click", () => move(box, -1));
    li.querySelector(".down").addEventListener("click", () => move(box, +1));
    li.querySelector(".del").addEventListener("click", () => deleteBox(idx));
    li.querySelectorAll(".mode").forEach((mb) =>
      mb.addEventListener("click", () => { box.mode = mb.dataset.m; renderBoxes(); }));
    const atg = li.querySelector(".anchor-tg");
    if (atg) atg.addEventListener("click", () => cycleAnchor(idx));
    li.addEventListener("click", (e) => { if (!["INPUT", "BUTTON"].includes(e.target.tagName) && !e.target.classList.contains("drag-h")) selectBox(idx); });
    // 드래그 재정렬 (요청 ③)
    const handle = li.querySelector(".drag-h");
    handle.addEventListener("dragstart", (e) => { dragBoxIdx = idx; e.dataTransfer.effectAllowed = "move"; li.classList.add("dragging"); });
    handle.addEventListener("dragend", () => { li.classList.remove("dragging"); document.querySelectorAll(".box-item.over").forEach((x) => x.classList.remove("over")); });
    li.addEventListener("dragover", (e) => { if (dragBoxIdx !== null) { e.preventDefault(); li.classList.add("over"); } });
    li.addEventListener("dragleave", () => li.classList.remove("over"));
    li.addEventListener("drop", (e) => { e.preventDefault(); li.classList.remove("over"); if (dragBoxIdx !== null) reorderBox(dragBoxIdx, idx); dragBoxIdx = null; });
    list.appendChild(li);
  });
  scrollSelectedToTop();
}

let dragBoxIdx = null;
// dragged 박스를 target 앞으로 이동시키고 order 재정렬
function reorderBox(fromIdx, toIdx) {
  if (fromIdx === toIdx) return;
  const dragged = BOXES[fromIdx], target = BOXES[toIdx];
  const seq = [...BOXES].sort((a, b) => a.order - b.order);
  const dpos = seq.indexOf(dragged);
  seq.splice(dpos, 1);
  const tpos = seq.indexOf(target);
  seq.splice(tpos, 0, dragged);
  seq.forEach((b, i) => (b.order = i + 1));
  renderBoxes(); renderActiveGroup();
}

function deleteBox(idx) {
  BOXES.splice(idx, 1);
  if (selected === idx) selected = null;
  else if (selected > idx) selected--;
  reindex(); renderActiveGroup(); renderBoxes();
}

function highlightSelList() {
  document.querySelectorAll(".box-item").forEach((el) => el.classList.remove("sel"));
  scrollSelectedToTop();
}

// 선택된 항목을 목록 맨 위로 스크롤 (요청 ①)
function scrollSelectedToTop() {
  if (selected == null) return;
  const list = $("boxList");
  const items = [...list.querySelectorAll(".box-item")];
  const box = BOXES[selected];
  const el = items.find((li) => li.querySelector(".ord") && +li.querySelector(".ord").textContent === (box ? box.order : -1));
  if (el) list.scrollTop = el.offsetTop - list.offsetTop;
}
function selectBox(idx) {
  // 이미 선택된 항목을 다시 클릭하면 해제(토글) — 요청 ②
  if (selected === idx) { selected = null; renderActiveGroup(); renderBoxes(); return; }
  selected = idx;
  const box = BOXES[idx];
  const gi = GROUPS.findIndex((g) => g.tables.includes(box.table));
  if (gi >= 0 && gi !== activeGroup) { activeGroup = gi; renderGroupTabs(); }
  renderActiveGroup(); renderBoxes();
}
function move(box, dir) {
  const sorted = [...BOXES].sort((a, b) => a.order - b.order);
  const pos = sorted.indexOf(box), swap = sorted[pos + dir];
  if (!swap) return;
  const t = box.order; box.order = swap.order; swap.order = t;
  renderBoxes();
}
function reindex() { [...BOXES].sort((a, b) => a.order - b.order).forEach((b, i) => (b.order = i + 1)); }

// ---------- 저장 / 적용 ----------
$("saveBtn").addEventListener("click", async () => {
  const name = $("tplName").value.trim();
  if (!name) { alert("템플릿 이름을 입력하세요."); return; }
  reindex();
  const res = await fetch("/api/designer/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, boxes: BOXES }) });
  const d = await res.json();
  $("saveMsg").textContent = d.ok ? `✅ '${name}' 저장됨 (${BOXES.length}개 항목)` : "저장 실패: " + (d.error || "");
  if (d.ok) loadTemplates();
});

// 문서 순서로 정렬 (요청 ①)
$("sortPosBtn").addEventListener("click", () => { renumberByPosition(); renderBoxes(); });

// ---------- 템플릿 관리 (요청 ④) ----------
async function loadTemplates() {
  try {
    const d = await (await fetch("/api/designer/templates")).json();
    renderTplList(d.templates || []);
  } catch (e) { /* noop */ }
}
function renderTplList(names) {
  const host = $("tplList");
  host.innerHTML = "";
  if (!names.length) { host.innerHTML = `<li class="empty-hint">저장된 템플릿이 없습니다.</li>`; return; }
  names.forEach((name) => {
    const li = document.createElement("li");
    li.className = "tpl-item";
    li.innerHTML = `<span class="tpl-name">📄 ${name}</span>` +
      `<button class="tpl-load">불러오기</button><button class="tpl-del" title="삭제">✕</button>`;
    li.querySelector(".tpl-load").addEventListener("click", () => loadTemplate(name));
    li.querySelector(".tpl-del").addEventListener("click", () => deleteTemplate(name));
    host.appendChild(li);
  });
}
async function loadTemplate(name) {
  if (!TABLES.length) { alert("먼저 양식을 불러온 뒤 템플릿을 적용하세요."); return; }
  const d = await (await fetch("/api/designer/template?name=" + encodeURIComponent(name))).json();
  if (d.error) { alert(d.error); return; }
  BOXES = (d.boxes || []).map((b) => ({ ...b }));
  selected = null;
  $("tplName").value = name;
  renderGroupTabs(); renderActiveGroup(); renderBoxes();
  $("saveMsg").textContent = `📄 '${name}' 불러옴 (${BOXES.length}개 항목)`;
}
async function deleteTemplate(name) {
  if (!confirm(`'${name}' 템플릿을 삭제할까요?`)) return;
  const d = await (await fetch("/api/designer/template/delete", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  })).json();
  renderTplList(d.templates || []);
}
// 페이지 열릴 때 템플릿 목록 미리 로드
loadTemplates();

$("applyBtn").addEventListener("click", async () => {
  const files = $("applyInput").files;
  if (!files.length) { alert("처리할 파일을 선택하세요."); return; }
  reindex();
  showOverlay("추출하는 중…");
  const fd = new FormData(); fd.append("boxes", JSON.stringify(BOXES));
  for (const f of files) fd.append("files", f);
  try {
    const res = await fetch("/api/designer/apply", { method: "POST", body: fd });
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    renderApply(d);
  } catch (e) { alert("추출 실패: " + e.message); }
  finally { hideOverlay(); }
});
function renderApply(d) {
  let html = `<p class="muted">✅ ${d.ok_count}개 파일 처리` + (d.failed.length ? ` · ⚠️ ${d.failed.length}개 실패` : "") + `</p>`;
  html += `<button class="btn btn-download" onclick="window.location.href='/api/designer/download'">📥 엑셀 다운로드</button>`;
  html += `<div style="overflow:auto"><table class="apply-table"><thead><tr><th>파일</th>` + d.fields.map((f) => `<th>${f}</th>`).join("") + `</tr></thead><tbody>`;
  for (const row of d.rows) html += `<tr><td>${row["_파일명"] || ""}</td>` + d.fields.map((f) => `<td>${(row[f] || "").slice(0, 20)}</td>`).join("") + `</tr>`;
  html += `</tbody></table></div>`;
  $("applyResult").innerHTML = html;
}

function showOverlay(m) { $("overlayMsg").textContent = m || "처리 중…"; $("overlay").hidden = false; }
function hideOverlay() { $("overlay").hidden = true; }
