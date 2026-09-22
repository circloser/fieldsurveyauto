// 데이터 입력 관리 — 템플릿 → 디지털 입력 양식(공유 링크·QR) → 실시간 기록 → 엑셀·현장조사표 PDF.
// 기록은 오토다타 웹(클라우드플레어)에 모였다가 이 PC의 도우미가 관리 키로 가져온다(/api/forms/…, core/forms.py).
const $ = (id) => document.getElementById(id);
let FORMS = [], SELECTED = null, TIMER = null, SYNCING = false;
const POLL_MS = 5000;

function showOverlay(m) { $("overlayMsg").textContent = m || "처리 중…"; $("overlay").hidden = false; }
function hideOverlay() { $("overlay").hidden = true; }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function nowText() { const d = new Date(); const p = (n) => String(n).padStart(2, "0"); return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; }

async function api(url, opts) {
  const r = await fetch(url, opts);
  let d = {};
  try { d = await r.json(); } catch (e) { /* JSON 아님 */ }
  if (!r.ok || d.error) throw new Error(d.error || ("오류 " + r.status));
  return d;
}

// ---- 1. 템플릿 목록 → 양식 만들기
async function loadTemplates() {
  let names = [];
  try { names = (await api("/api/designer/templates")).templates || []; } catch (e) { names = []; }
  $("tplSel").innerHTML = names.length
    ? names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("")
    : `<option value="">저장된 템플릿이 없습니다 — 템플릿 디자이너에서 먼저 저장하세요</option>`;
  $("publishBtn").disabled = !names.length;
}

$("publishBtn").addEventListener("click", async () => {
  const template = $("tplSel").value;
  if (!template) { alert("템플릿을 고르세요."); return; }
  showOverlay("오토다타 웹에 양식을 만드는 중…");
  $("publishMsg").textContent = "";
  try {
    const d = await api("/api/forms/publish", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template, title: $("titleInput").value.trim(), gps: $("gpsChk").checked }),
    });
    $("publishMsg").textContent = `만들었습니다 — 아래 2번에서 공유 링크·QR 을 조사자에게 전하세요.` + (d.form.has_pdf ? "" : " (이 템플릿은 양식 PDF 가 없어 현장조사표 PDF 는 만들 수 없고 엑셀만 됩니다)");
    $("titleInput").value = "";
    await loadForms(d.form.id);
    $("formDetail").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    $("publishMsg").textContent = "만들지 못했습니다: " + e.message;
  } finally { hideOverlay(); }
});

// ---- 2. 만든 양식 목록·공유
async function loadForms(selectId) {
  try { FORMS = (await api("/api/forms")).forms || []; } catch (e) { FORMS = []; }
  if (selectId) SELECTED = selectId;
  if (SELECTED && !FORMS.find((f) => f.id === SELECTED)) SELECTED = null;
  renderList();
  renderDetail();
  if (SELECTED) refreshEntries(true);
}

function renderList() {
  const host = $("formList"); host.innerHTML = "";
  if (!FORMS.length) {
    host.innerHTML = `<li class="empty-hint">아직 만든 양식이 없습니다 — 1번에서 템플릿을 골라 만드세요.</li>`;
    return;
  }
  FORMS.forEach((f) => {
    const li = document.createElement("li"); li.className = "tpl-item" + (f.id === SELECTED ? " on" : "");
    li.innerHTML = `<span class="tpl-name">📲 ${esc(f.title)}</span>
      <span class="tpl-sub">${esc(f.template)} · ${esc((f.created || "").slice(0, 10))} · ${f.count || 0}건</span>
      <span class="form-state ${f.closed ? "closed" : ""}">${f.closed ? "입력 닫힘" : "입력 열림"}</span>
      <button class="tpl-load" data-id="${esc(f.id)}">${f.id === SELECTED ? "보는 중" : "선택"}</button>`;
    li.querySelector(".tpl-load").addEventListener("click", () => selectForm(f.id));
    host.appendChild(li);
  });
}

function selectForm(id) {
  SELECTED = id;
  renderList();
  renderDetail();
  refreshEntries(true);
}

function current() { return FORMS.find((f) => f.id === SELECTED) || null; }

function renderDetail() {
  const f = current();
  const on = !!f;
  $("formDetail").hidden = !on; $("entriesCard").hidden = !on; $("exportCard").hidden = !on;
  if (!on) { stopTimer(); return; }
  $("qrImg").src = `/api/forms/${f.id}/qr.svg?t=${Date.now()}`;
  $("shareTitle").textContent = f.title;
  $("shareLink").value = f.share_url;
  $("openLink").href = f.share_url;
  $("shareMeta").textContent = `템플릿 ${f.template} · 만든 날 ${(f.created || "").replace("T", " ").slice(0, 16)}`
    + (f.gps ? " · 위치(GPS) 기록" : "") + ` · ${f.closed ? "입력 닫힘" : "입력 열림"}`
    + (f.synced ? ` · 마지막 가져오기 ${f.synced.replace("T", " ").slice(0, 16)}` : "");
  $("closeBtn").textContent = f.closed ? "▶ 입력 다시 열기" : "⏸ 입력 닫기";
  $("excelBtn").href = `/api/forms/${f.id}/excel`;
  $("pdfBtn").href = `/api/forms/${f.id}/pdf`;
  $("pdfBtn").setAttribute("aria-disabled", f.has_pdf ? "false" : "true");
  $("pdfBtn").title = f.has_pdf ? "" : "이 양식의 템플릿에는 양식 PDF 가 없어 조사표 PDF 를 만들 수 없습니다";
  $("exportMsg").textContent = f.has_pdf ? "" : "이 템플릿은 양식 PDF 없이 저장되어 현장조사표 PDF 는 만들 수 없습니다. 템플릿 디자이너에서 양식 PDF 를 연 채로 저장한 뒤 양식을 다시 만들면 됩니다.";
  startTimer();
}

$("copyBtn").addEventListener("click", async () => {
  const v = $("shareLink").value;
  try { await navigator.clipboard.writeText(v); $("copyBtn").textContent = "✅ 복사됨"; }
  catch (e) { $("shareLink").select(); document.execCommand("copy"); $("copyBtn").textContent = "✅ 복사됨"; }
  setTimeout(() => ($("copyBtn").textContent = "📋 복사"), 1500);
});

$("printQrBtn").addEventListener("click", () => {
  const f = current(); if (!f) return;
  const w = window.open("", "_blank");
  if (!w) { alert("팝업이 막혀 있습니다. 브라우저에서 팝업을 허용하세요."); return; }
  w.document.write(`<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>${esc(f.title)} — 입력 QR</title>
    <style>body{font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;text-align:center;padding:40px;color:#1e2126}
    h1{font-size:24px;margin:0 0 6px}p{color:#555;margin:6px 0}img{width:320px;height:320px;margin:18px 0}.u{font-size:12px;word-break:break-all;color:#333}</style></head>
    <body><h1>${esc(f.title)}</h1><p>휴대전화 카메라로 QR 을 찍어 현장 기록을 입력하세요</p>
    <img src="/api/forms/${f.id}/qr.svg" onload="setTimeout(()=>window.print(),300)"><p class="u">${esc(f.share_url)}</p>
    <p>오토다타 디지털 입력 양식 · 템플릿 ${esc(f.template)}</p></body></html>`);
  w.document.close();
});

$("closeBtn").addEventListener("click", async () => {
  const f = current(); if (!f) return;
  const closing = !f.closed;
  if (closing && !confirm("입력을 닫으면 조사자가 더 이상 기록을 보낼 수 없습니다(나중에 다시 열 수 있음). 닫을까요?")) return;
  showOverlay(closing ? "입력을 닫는 중…" : "입력을 여는 중…");
  try {
    const d = await api(`/api/forms/${f.id}/${closing ? "close" : "open"}`, { method: "POST" });
    Object.assign(f, d.form);
    renderList(); renderDetail();
  } catch (e) { alert(e.message); } finally { hideOverlay(); }
});

$("deleteBtn").addEventListener("click", async () => {
  const f = current(); if (!f) return;
  if (!confirm(`'${f.title}' 양식과 웹에 모인 기록 ${f.count || 0}건을 모두 지웁니다.\n내보낸 엑셀·PDF 는 남지만 아직 내보내지 않은 기록은 되살릴 수 없습니다. 지울까요?`)) return;
  showOverlay("양식을 지우는 중…");
  try {
    const d = await api(`/api/forms/${f.id}/delete`, { method: "POST" });
    FORMS = d.forms || []; SELECTED = null;
    renderList(); renderDetail();
  } catch (e) { alert(e.message); } finally { hideOverlay(); }
});

// ---- 3. 실시간 기록
function startTimer() {
  if (TIMER) return;
  TIMER = setInterval(() => {
    if ($("autoChk").checked && document.visibilityState === "visible" && SELECTED) refreshEntries(true);
  }, POLL_MS);
}
function stopTimer() { if (TIMER) { clearInterval(TIMER); TIMER = null; } }

$("syncBtn").addEventListener("click", () => refreshEntries(true));

async function refreshEntries(sync) {
  const id = SELECTED;
  if (!id || SYNCING) return;
  SYNCING = true;
  try {
    if (sync) {
      const r = await api(`/api/forms/${id}/sync`, { method: "POST" });
      const f = FORMS.find((x) => x.id === id);
      if (f) Object.assign(f, r.form);
      $("syncMsg").textContent = `${nowText()} 가져옴 · 새 기록 ${r.new}건 · 전체 ${r.total}건` + (r.closed ? " · 입력 닫힘" : "");
      if (f && f.count !== undefined) renderList();
    }
    const d = await api(`/api/forms/${id}/entries`);
    if (SELECTED === id) renderEntries(d.form, d.entries || []);
  } catch (e) {
    $("syncMsg").textContent = "가져오기 실패: " + e.message;
  } finally { SYNCING = false; }
}

function cellValue(f, e) {
  const v = (e.values || {})[f.key];
  if (f.type === "image") {
    const url = (e.photos || {})[f.key];
    return url ? `<a href="${esc(url)}" target="_blank" rel="noopener"><img class="thumb" src="${esc(url)}" alt="사진"></a>` : "";
  }
  if (f.type === "check") return v === true ? "☑" : "";
  if (f.type === "table") {
    const rows = Array.isArray(v) ? v : [];
    const cols = f.columns || [];
    const txt = rows.map((r) => cols.map((c) => r[c] || "").filter(Boolean).join(" / ")).join("\n");
    return rows.length ? `<span title="${esc(txt)}">${rows.length}줄</span>` : "";
  }
  return esc(v == null ? "" : v);
}

function renderEntries(form, entries) {
  const def = form.definition || { fields: [] };
  const fields = (def.fields || []).filter((f) => f.type !== "title");
  $("countPill").textContent = `${entries.length}건`;
  const head = ["#", "기록 시각"].concat(def.gps ? ["위치"] : []).concat(fields.map((f) => f.label || f.key));
  const rows = entries.slice().sort((a, b) => (b.seq || 0) - (a.seq || 0)).map((e) => {
    const g = ((e.meta || {}).gps) || null;
    const cells = [`<td>${e.seq}</td>`, `<td>${esc(e.created_local || e.created)}</td>`];
    if (def.gps) cells.push(`<td>${g && g.lat != null ? `<a href="https://map.kakao.com/link/map/${g.lat},${g.lon}" target="_blank" rel="noopener">${g.lat}, ${g.lon}</a>` : ""}</td>`);
    fields.forEach((f) => cells.push(`<td title="${esc(String((e.values || {})[f.key] ?? ""))}">${cellValue(f, e)}</td>`));
    return `<tr>${cells.join("")}</tr>`;
  });
  $("entryTable").innerHTML = `<thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.join("") || `<tr><td colspan="${head.length}" class="empty-hint">아직 받은 기록이 없습니다 — 조사자가 링크로 보내면 여기에 나타납니다.</td></tr>`}</tbody>`;
}

// ---- 4. 내보내기(오류는 JSON 으로 오므로 링크 대신 fetch 로 받아 저장)
async function download(url, btn) {
  if (btn.getAttribute("aria-disabled") === "true") return;
  showOverlay("파일을 만드는 중…");
  $("exportMsg").textContent = "";
  try {
    const r = await fetch(url);
    if ((r.headers.get("content-type") || "").includes("application/json")) {
      const d = await r.json(); throw new Error(d.error || ("오류 " + r.status));
    }
    if (!r.ok) throw new Error("오류 " + r.status);
    const m = /filename\*=UTF-8''([^;]+)/i.exec(r.headers.get("content-disposition") || "");
    const name = m ? decodeURIComponent(m[1]) : (url.endsWith("/pdf") ? "현장조사표.pdf" : "디지털입력.xlsx");
    const blob = await r.blob();
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    $("exportMsg").textContent = `${name} 을(를) 내려받았습니다 (data/output 에도 저장).`;
  } catch (e) {
    $("exportMsg").textContent = "만들지 못했습니다: " + e.message;
  } finally { hideOverlay(); }
}
$("excelBtn").addEventListener("click", (ev) => { ev.preventDefault(); download($("excelBtn").getAttribute("href"), $("excelBtn")); });
$("pdfBtn").addEventListener("click", (ev) => { ev.preventDefault(); download($("pdfBtn").getAttribute("href"), $("pdfBtn")); });

document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && SELECTED) refreshEntries(true); });

loadTemplates();
loadForms();
