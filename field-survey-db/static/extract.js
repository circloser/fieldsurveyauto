// 데이터 추출 관리 — 저장된 템플릿으로 조사표 파일들을 일괄 처리해 엑셀·보고서로(템플릿 디자이너의 4~6번을 옮김).
// 템플릿을 고르지 않으면 저장된 템플릿 전체로 자동 분류한다. '기준 템플릿'을 고르면 그 박스가 현재 양식이 되어
// 제목이 없는 스캔 문서의 폴백과 같은 양식의 중복 템플릿 우선순위에 쓰인다.
const $ = (id) => document.getElementById(id);
let BOXES = [], DOC_ID = null;      // 기준 템플릿(선택)의 박스·양식 PDF
let ALL_BOXES = [];                 // 저장된 템플릿 전체 박스(보고서 자리표시자 목록용)
let TPL_NAMES = [];
function showOverlay(m) { $("overlayMsg").textContent = m || "처리 중…"; $("overlay").hidden = false; }
function hideOverlay() { $("overlay").hidden = true; }
function reindex() { [...BOXES].sort((a, b) => a.order - b.order).forEach((b, i) => (b.order = i + 1)); }

async function loadTemplateList() {
  try {
    const d = await (await fetch("/api/designer/templates")).json();
    TPL_NAMES = d.templates || [];
  } catch (e) { TPL_NAMES = []; }
  const host = $("tplUsed"); host.innerHTML = "";
  if (!TPL_NAMES.length) {
    host.innerHTML = `<li class="empty-hint">저장된 템플릿이 없습니다 — 먼저 <a href="/pdf-designer">템플릿 디자이너</a>에서 양식에 박스를 지정하고 저장하세요. (설문지는 템플릿 없이 인식됩니다)</li>`;
  } else {
    TPL_NAMES.forEach((n) => {
      const li = document.createElement("li"); li.className = "tpl-item";
      li.innerHTML = `<span class="tpl-name">📄 ${n}</span>`;
      host.appendChild(li);
    });
  }
  const sel = $("baseTplSel");
  sel.innerHTML = `<option value="">자동 — 저장된 템플릿 전체로 분류</option>` + TPL_NAMES.map((n) => `<option value="${n}">${n}</option>`).join("");
  // 보고서 자리표시자·AI 초안용으로 템플릿 박스를 모아 둔다
  ALL_BOXES = [];
  for (const n of TPL_NAMES) {
    try {
      const d = await (await fetch("/api/designer/template?name=" + encodeURIComponent(n))).json();
      (d.boxes || []).forEach((b) => ALL_BOXES.push({ ...b }));
    } catch (e) {}
  }
  fillFieldSelect();
}

$("baseTplSel").addEventListener("change", async () => {
  const name = $("baseTplSel").value;
  BOXES = []; DOC_ID = null;
  if (name) {
    try {
      const d = await (await fetch("/api/designer/template?name=" + encodeURIComponent(name))).json();
      if (d.error) throw new Error(d.error);
      BOXES = (d.boxes || []).map((b) => ({ ...b }));
      DOC_ID = d.doc_id || null;
    } catch (e) { alert("템플릿을 불러오지 못했습니다: " + e.message); }
  }
  $("baseTplMsg").textContent = name ? `기준 템플릿 '${name}' (${BOXES.length}개 항목)` : "";
  fillFieldSelect();
});

let LAST_APPLY_FILES = null;   // 확인 절차(버려진 페이지 재배정)에서 같은 파일로 다시 처리
async function runApply(files, opts) {
  if (!files || !files.length) { alert("처리할 파일을 선택하세요."); return; }
  LAST_APPLY_FILES = files;
  reindex();
  // 실제 하는 일만 정확히 안내: PDF는 변환 없이 바로 읽고, 한글 파일만 변환을 거친다
  const hasHwp = [...files].some((f) => /\.hwpx?$/i.test(f.name || ""));
  showOverlay(hasHwp
    ? "추출하는 중… (한글 파일은 PDF로 변환 후 처리 — 시간이 걸릴 수 있어요)"
    : "추출하는 중…");
  const fd = new FormData(); fd.append("boxes", JSON.stringify(BOXES));
  for (const f of files) fd.append("files", f);
  // 기본 동작: 양식 자동 대조 + 제목별 시트(제목 없으면 시트 하나). 서버가 보고서 양식(5번) 사용 시 기존 경로로 처리.
  fd.append("sheet_name_field", "__group_title__");
  fd.append("auto_classify", "1");
  if (DOC_ID) fd.append("doc_id", DOC_ID);   // 현재 양식의 제목 텍스트(분류 기준)용
  if (opts && opts.overrides) fd.append("assign_overrides", JSON.stringify(opts.overrides));
  // 보고서 양식은 4번에서 쓰지 않는다 — 5번 '보고서 양식으로 정리'가 결과를 채운다
  try {
    const d = await (await fetch("/api/pdf/apply", { method: "POST", body: fd })).json();
    if (d.error) {
      // 스캔 문서인데 글자 인식 기능이 없어 아무것도 못 읽은 경우 — 경고창 대신 이유와 '받기'를 결과 자리에
      if (d.ocr_missing) { $("applyResult").innerHTML = ""; renderOcrGap(d); return; }
      throw new Error(d.error);
    }
    renderApply(d);
    // 5번(보고서)에서 실행했을 때도 결과가 바로 보이도록 스크롤
    if (opts && opts.scrollToResult) {
      const el = $("applyResult");
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (e) { alert("추출 실패: " + e.message); }
  finally { hideOverlay(); }
}

$("applyBtn").addEventListener("click", () => runApply($("applyInput").files));

// 5번: 4번 일괄 처리 '결과'를 보고서 양식에 채워 정리 → 다운로드 (재추출 없음)
$("rptGenBtn").addEventListener("click", async () => {
  if (!REPORT.report_id) { alert("먼저 보고서 양식을 올리거나 AI 초안을 만드세요."); return; }
  showOverlay("보고서 양식으로 정리하는 중…");
  try {
    const d = await (await fetch("/api/report/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_id: REPORT.report_id, edits: REPORT.edits }),
    })).json();
    if (d.error) throw new Error(d.error);
    $("rptGenMsg").textContent = `✅ ${d.rows}행을 양식에 채웠습니다 — 아래에서 다운로드하세요.`;
    $("rptGenDl").hidden = false;
  } catch (e) { alert("보고서 정리 실패: " + e.message); }
  finally { hideOverlay(); }
});
// ---------- 보고서 양식 편집기 ----------
let REPORT = { report_id: null, cells: [], nrows: 0, ncols: 0, edits: {}, focusCell: null };

function mountReport(d) {
  REPORT = { report_id: d.report_id, cells: d.cells, nrows: d.nrows, ncols: d.ncols, edits: {}, focusCell: null };
  $("reportMsg").textContent = `📋 '${d.filename}' — ${d.nrows}행 × ${d.ncols}열` +
    (d.placeholders && d.placeholders.length ? ` · 자리표시자: ${d.placeholders.slice(0, 12).join(", ")}${d.placeholders.length > 12 ? " …" : ""}` : "");
  $("reportEditor").hidden = false;
  $("rptRunRow").hidden = false;   // 양식 장착 즉시, 5번에서 바로 일괄 처리 가능
  fillFieldSelect();
  renderReportGrid();
}

$("reportInput").addEventListener("change", async () => {
  const f = $("reportInput").files[0];
  if (!f) return;
  showOverlay("양식을 불러오는 중…");
  const fd = new FormData(); fd.append("file", f);
  try {
    const d = await (await fetch("/api/report/load", { method: "POST", body: fd })).json();
    if (d.error) throw new Error(d.error);
    $("aiDraftDl").hidden = true;   // 직접 올린 양식으로 교체됨
    mountReport(d);
  } catch (e) { alert("양식 불러오기 실패: " + e.message); }
  finally { hideOverlay(); }
});

// AI 보고서 양식 초안: 만들기 → 편집기 장착 + 다운로드 링크 → (엑셀 편집 후 재업로드)
$("aiDraftBtn").addEventListener("click", async () => {
  const draftBoxes = BOXES.length ? BOXES : ALL_BOXES;
  if (!draftBoxes.length) { alert("추출 항목이 없습니다. 템플릿 디자이너에서 템플릿을 먼저 저장하세요."); return; }
  showOverlay("🤖 AI가 보고서 양식 초안을 설계하는 중…");
  try {
    const r = await fetch("/api/report/ai_draft", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: DOC_ID, boxes: draftBoxes }),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    mountReport(d);
    const dl = $("aiDraftDl");
    dl.href = d.download_url; dl.hidden = false;
    $("reportMsg").textContent = `🤖 AI 초안 장착됨 — 아래 표에서 바로 고치거나, ` +
      `초안을 다운로드해 엑셀에서 편집한 뒤 다시 올리세요. (${d.nrows}행 × ${d.ncols}열)`;
  } catch (e) { alert("AI 초안 생성 실패:\n" + e.message); }
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
  const names = [...new Set((BOXES.length ? BOXES : ALL_BOXES).map((b) => b.field).filter(Boolean))].sort();
  const opts = names.map((n) => `<option value="${n}">${n}</option>`).join("");
  $("rptFieldSel").innerHTML = `<option value="">— 추출 항목 —</option>` + opts;
}

$("rptInsertBtn").addEventListener("click", () => {
  const name = $("rptFieldSel").value;
  if (!name) { alert("삽입할 추출 항목을 선택하세요."); return; }
  const inp = REPORT.focusCell;
  if (!inp) { alert("먼저 표에서 넣을 칸을 클릭하세요."); return; }
  const idx = (($("rptIdxInput") || {}).value || "").trim();
  const token = (idx && /^\d+$/.test(idx)) ? `{${name}#${idx}}` : `{${name}}`;
  inp.value = (inp.value || "") + token;
  inp.dispatchEvent(new Event("input"));
  inp.focus();
});

// ---------- SCE(수생태계 종적 연속성 평가) 연계 — 선택 기능 ----------
// 4번 결과를 SCE 입력 양식으로 정리(서식 3장을 구조물별로 합치고 형태·낙차유무 판정, 검수 메모 포함).
// 환경설정에서 켠 경우에만 버튼이 보인다(끄면 아무것도 표시하지 않음).
let SCE_STATUS = { enabled: false, available: false, error: "" };
(async () => {
  try { SCE_STATUS = await (await fetch("/api/sce/status")).json(); } catch (e) { /* 무시 */ }
})();

function sceButtons() {
  if (!SCE_STATUS.enabled) return "";          // 꺼짐 — 버튼 없음
  if (!SCE_STATUS.available) {                 // 켰지만 SCE를 못 찾음 — 설정으로 안내
    return `<div id="sceRow" style="margin-top:10px;padding:10px 12px;background:#fff8e6;border:1px solid #ffe08a;border-radius:10px;font-size:13px">`
      + `⚠️ <b>SCE 연계</b>를 켰지만 SCE 프로그램을 찾지 못했습니다 — `
      + `<a href="/settings" target="_blank">환경설정</a>에서 SCE 폴더를 지정하세요.`
      + `<div class="muted" style="margin-top:4px">${(SCE_STATUS.error || "").replace(/</g, "&lt;").slice(0, 200)}</div></div>`;
  }
  return `<div id="sceRow" style="margin-top:10px;padding:10px 12px;background:#f1f3f5;border-radius:10px">`
    + `<span style="font-size:13px"><b>🐟 종적 연속성 평가(SCE) 연계</b> — 인공구조물 1·2, 어도, 어류 조사표를 구조물별로 합쳐 SCE 입력 양식으로 정리합니다.</span><br/>`
    + `<button class="mini-btn" id="sceExportBtn" style="margin-top:6px">📋 SCE 입력양식 내보내기</button> `
    + `<button class="mini-btn" id="sceEvalBtn" style="margin-top:6px">📈 SCE 평가까지 실행 (zip)</button>`
    + `<div id="sceResult" style="margin-top:6px"></div></div>`;
}
function bindSce() {
  const a = $("sceExportBtn"), b = $("sceEvalBtn");
  if (a) a.addEventListener("click", () => sceExport(false));
  if (b) b.addEventListener("click", () => sceExport(true));
}
async function sceExport(evaluate) {
  const river = prompt("하천명 (비우면 조사표에서 자동으로 찾습니다)", "");
  if (river === null) return;
  let length_km = null;
  if (evaluate) {
    const s = prompt("하천연장(km) — 하천 단위 평가에 필요합니다. 모르면 비워 두세요(구조물 단위 평가만 수행).", "");
    if (s === null) return;
    if (s.trim()) length_km = parseFloat(s);
  }
  const box = $("sceResult");
  showOverlay(evaluate ? "SCE 입력 양식 변환 + 평가 실행 중…" : "SCE 입력 양식으로 변환하는 중…");
  try {
    const d = await (await fetch("/api/sce/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ river, length_km, evaluate }),
    })).json();
    if (d.error) throw new Error(d.error);
    let html = `<p style="margin:4px 0;font-size:13px">✅ 하천 <b>${d.river || "(미확인)"}</b> · 구조물 <b>${d.n_struct}</b>개 · 조사 ${d.n_surveys}건 · 어류 ${d.n_fish}행 · 검수 항목 <b style="color:#b0870b">${d.n_notes}</b>건</p>`;
    if (d.evaluation) {
      const ev = d.evaluation, c = ev.counts || {};
      html += `<p style="margin:4px 0;font-size:13px">📈 하천 단위: <b>${ev.river_rating}</b>`
        + (ev.secured_km != null ? ` (확보구간 ${ev.secured_km} km, ${ev.secured_pct != null ? ev.secured_pct.toFixed(1) : "-"} %)` : "")
        + ` · 구조물: 연속 ${c["연속"] || 0} / 훼손 ${c["훼손"] || 0} / 단절 ${c["단절"] || 0} / 없음 ${c["없음"] || 0}</p>`;
      if (ev.warnings && ev.warnings.length) html += `<p class="muted">⚠️ ${ev.warnings.slice(0, 5).join(" · ")}</p>`;
    }
    if (d.evaluation_error) html += `<p class="muted">⚠️ ${d.evaluation_error}</p>`;
    html += `<a class="draft-dl" href="${d.download}">📥 ${d.filename}</a>`;
    if (d.notes && d.notes.length) {
      html += `<details style="margin-top:6px"><summary style="cursor:pointer;font-size:13px">🔎 검수 항목 ${d.n_notes}건 보기 (엑셀 '연계검수' 시트에도 있음)</summary>`
        + `<table class="apply-table"><thead><tr><th>구조물</th><th>차수</th><th>확인 사항</th></tr></thead><tbody>`
        + d.notes.slice(0, 60).map((n) => `<tr><td>${n.structure}</td><td>${n.round}</td><td>${n.message}</td></tr>`).join("")
        + `</tbody></table></details>`;
    }
    html += `<p class="muted" style="margin-top:6px">다음 단계: 엑셀의 <b>구조물목록</b> 시트에 상류→하류 순서와 종점거리 Li(km), <b>하천정보</b>에 하천연장을 입력한 뒤 SCE에서 평가를 실행하세요.</p>`;
    box.innerHTML = html;
  } catch (e) { box.innerHTML = `<p class="muted">❌ ${e.message}</p>`; }
  finally { hideOverlay(); }
}

function renderApplyAuto(d) {
  let html = `<p class="muted">✅ ${d.ok_count}행 처리 · <b>시트 ${d.forms}개</b>로 정리`
    + (d.failed && d.failed.length ? ` · ⚠️ ${d.failed.length}개 미분류/실패` : "") + `</p>`;
  if ((d.ok_count || 0) > 0) {
    html += `<button class="btn btn-download" onclick="window.location.href='/api/pdf/download'">📥 엑셀 다운로드</button>`;
    html += sceButtons();
  } else {
    html += `<p class="muted">추출된 행이 없습니다 — 아래 '버려진 페이지 확인'에서 처리 방법을 정하거나, 해당 양식을 템플릿에 추가하세요.</p>`;
  }
  html += `<p style="margin:10px 0 4px;font-size:13px">📊 이상치 <b style="color:#e8590c">${d.outlier_count || 0}건</b>`
    + ` <span class="muted">— 자세한 해석은 아래 ‘AI 결과 해석’</span></p>`;
  html += `<table class="apply-table"><thead><tr><th>시트(제목)</th><th>행 수</th><th>이상치</th></tr></thead><tbody>`;
  (d.by_form || []).forEach((g) => {
    html += `<tr><td>${g.form}</td><td>${g.count}</td><td>${g.outliers ? `<b style="color:#e8590c">${g.outliers}</b>` : 0}</td></tr>`;
  });
  html += `</tbody></table>`;
  if (d.match_info && d.match_info.length) {
    html += `<p class="muted" style="margin-top:8px">🔎 분류 결과: `
      + d.match_info.map((m) => `${m.name} → <b>${m.template}</b>` + ((m.bundles || 1) > 1 ? `×${m.bundles}` : ``)).join(", ") + `</p>`;
  }
  if (d.discarded && d.discarded.length) {
    html += `<p class="muted">🗑 버림 — 맞는 양식(템플릿)이 없는 페이지: `
      + d.discarded.map((x) => `<b>${x.title}</b> ${x.pages}쪽`).join(", ")
      + ` <span class="muted">(이 양식도 추출하려면 템플릿에 추가하세요)</span></p>`;
    // 확인 절차 — 버려진 페이지를 어떻게 처리할지 사용자가 확정(기본: 버림)
    const uopts = (d.units || []).map((u) => `<option value="${u.key}">${u.label}</option>`).join("");
    html += `<div class="discard-confirm"><p style="margin:10px 0 6px;font-size:13px"><b>🔎 버려진 페이지 확인</b> — 처리 방법을 정해 주세요 (기본: 버림)</p>`
      + `<table class="apply-table"><thead><tr><th>페이지 제목</th><th>쪽수</th><th>처리</th></tr></thead><tbody>`
      + d.discarded.map((x) => `<tr><td>${x.title}</td><td>${x.pages}</td><td><select class="dc-sel" data-title="${encodeURIComponent(x.title)}">`
        + `<option value="__discard__">버림 (기본)</option>${uopts}</select></td></tr>`).join("")
      + `</tbody></table><button class="mini-btn" id="dcApplyBtn" style="margin-top:8px">✔ 확인 후 다시 처리</button></div>`;
  }
  if (d.failed && d.failed.length) {
    html += `<p class="muted">⚠️ 미분류/실패: ` + d.failed.map((f) => `${f.name} (${f.error})`).join(", ") + `</p>`;
  }
  $("applyResult").innerHTML = html;
  renderOcrGap(d);
  bindSce();
  const dcBtn = $("dcApplyBtn");
  if (dcBtn) dcBtn.addEventListener("click", () => {
    const overrides = {};
    document.querySelectorAll(".dc-sel").forEach((s) => {
      overrides[decodeURIComponent(s.dataset.title)] = s.value;
    });
    const changed = Object.values(overrides).some((v) => v !== "__discard__");
    if (!changed) { alert("모두 '버림'으로 확정되었습니다. (결과 엑셀은 그대로 사용하시면 됩니다)"); return; }
    if (!LAST_APPLY_FILES) { alert("다시 처리할 파일이 없습니다. 파일을 다시 선택해 주세요."); return; }
    runApply(LAST_APPLY_FILES, { overrides, scrollToResult: true });
  });
}

function renderApply(d) {
  if (d.auto_classify) return renderApplyAuto(d);
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
  html += sceButtons();
  // 빈칸·이상치 요약(#3)
  const OL = d.outliers || [];
  const totalCells = d.rows.length * d.fields.length;
  let blanks = 0;
  d.rows.forEach((row) => d.fields.forEach((f) => { if (!String(row[f] || "").trim()) blanks++; }));
  html += `<p style="margin:10px 0 4px;font-size:13px">📊 <b>${d.rows.length}행 × ${d.fields.length}항목 = ${totalCells}칸</b> 중 · `
    + `빈칸 <b style="color:#b0870b">${blanks}개</b> · 이상치 <b style="color:#e8590c">${d.outlier_count || 0}건</b>`
    + (d.outlier_count ? ` <span class="muted">(주황 칸 확인)</span>` : ``)
    + ` <span class="muted">— 자세한 해석은 아래 ‘AI 결과 해석’</span></p>`;
  html += `<div style="overflow:auto"><table class="apply-table"><thead><tr><th>파일</th>` + d.fields.map((f) => `<th>${f}</th>`).join("") + `</tr></thead><tbody>`;
  d.rows.forEach((row, i) => {
    const ol = OL[i] || {};
    html += `<tr><td>${row["_파일명"] || ""}</td>` + d.fields.map((f) => {
      const raw = row[f] || "";
      const v = raw.startsWith("__IMG__:") ? "🖼 이미지" : raw.slice(0, 18);
      return ol[f]
        ? `<td style="background:#fff0e0;border:1px solid #ff922b" title="${ol[f]}">⚠️ ${v}</td>`
        : `<td>${v}</td>`;
    }).join("") + `</tr>`;
  });
  html += `</tbody></table></div>`; $("applyResult").innerHTML = html;
  renderOcrGap(d);
  bindSce();
}

// 일괄 처리 결과에 '글자를 못 읽은 스캔 쪽'이 있으면 결과 맨 위에 이유와 받기 버튼을 붙인다.
// (경량 도우미에서 글자 인식 기능을 아직 안 받았을 때 — 빈 행만 조용히 내려가지 않게)
function renderOcrGap(d) {
  if (!d.ocr_missing) return;
  const box = document.createElement("div");
  box.className = "env-warn";
  box.style.marginTop = "0";
  const files = (d.ocr_gap || []).map((g) => `${g.name}(${g.pages}/${g.total}쪽)`).join(", ");
  const s = d.ocr_setup || {};
  if (s.ready || s.bundled) {
    box.append(`⚠️ 스캔(사진) 쪽의 글자를 읽지 못했습니다: ${files}. 글자 인식 엔진을 불러오지 못한 것 같습니다 — `);
    const a = document.createElement("a"); a.href = "/system"; a.target = "_blank"; a.textContent = "시스템 점검";
    box.append(a, "에서 확인하거나 도우미를 다시 켜 주세요.");
  } else {
    box.append(`⚠️ 스캔(사진) 쪽의 글자를 읽지 못해 값이 비었습니다: ${files}. `);
    renderOcrSetup(box, s, { afterDone: "받기가 끝나면 ‘추출 + 엑셀 만들기’를 다시 눌러 주세요." });
  }
  $("applyResult").prepend(box);
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

// 경량 도우미에서 글자 인식 기능을 아직 안 받았으면 4번(일괄 처리) 설명 아래에 미리 알려 준다
(async () => {
  try {
    const s = await (await fetch("/api/ocr/runtime")).json();
    if (s.bundled || s.ready) return;
    const p = document.createElement("p");
    p.className = "muted"; p.style.margin = "0 0 8px";
    p.append("📷 스캔(사진) 문서도 처리하려면 글자 인식 기능이 필요합니다 — ");
    const a = document.createElement("a"); a.href = "/settings#ocr"; a.target = "_blank"; a.textContent = "환경설정에서 받기";
    p.append(a, ". 글자 있는 PDF·한글 파일은 지금도 됩니다.");
    $("applyInput").parentNode.insertBefore(p, $("applyInput"));
  } catch (e) {}
})();

loadTemplateList();
