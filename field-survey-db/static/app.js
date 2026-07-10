// 현장 조사표 DB화 - 프론트 로직
const $ = (id) => document.getElementById(id);
let selectedFiles = [];

// 버전 표시
fetch("/health").then((r) => r.json()).then((d) => {
  $("footVersion").textContent = d.version;
}).catch(() => {});

const dropzone = $("dropzone");
const fileInput = $("fileInput");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag");
  addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => addFiles(fileInput.files));

function addFiles(fileList) {
  for (const f of fileList) selectedFiles.push(f);
  renderFileList();
}

function renderFileList() {
  const ul = $("filelist");
  ul.innerHTML = "";
  selectedFiles.forEach((f, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>📄 ${f.name}</span><button data-i="${i}" class="rm">✕</button>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll(".rm").forEach((b) =>
    b.addEventListener("click", () => {
      selectedFiles.splice(Number(b.dataset.i), 1);
      renderFileList();
    })
  );
  $("processBtn").disabled = selectedFiles.length === 0;
}

$("processBtn").addEventListener("click", async () => {
  if (!selectedFiles.length) return;
  const fd = new FormData();
  selectedFiles.forEach((f) => fd.append("files", f));
  $("overlay").hidden = false;
  try {
    const res = await fetch("/api/process", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    renderResult(data);
  } catch (e) {
    alert("변환 중 문제가 발생했습니다: " + e.message);
  } finally {
    $("overlay").hidden = true;
  }
});

function tile(label, value, accent) {
  return `<div class="tile ${accent || ""}"><div class="tile-num">${value}</div><div class="tile-label">${label}</div></div>`;
}

function renderResult(data) {
  $("resultCard").hidden = false;
  const s = data.stats;
  $("stats").innerHTML =
    tile("성공 파일", s.files_ok) +
    tile("실패 파일", s.files_failed, s.files_failed ? "warn" : "") +
    tile("추출 레코드", s.records, "ok") +
    tile("검수 필요", s.flagged, s.flagged ? "warn" : "");

  const rows = data.records;
  let html =
    "<thead><tr><th>파일</th><th>서식</th><th>보명칭</th><th>보코드</th><th>완성도</th><th>검수</th></tr></thead><tbody>";
  for (const r of rows) {
    const pct = Math.round((r["완성도"] || 0) * 100);
    const flag = r["검수필요"]
      ? `<span class="badge warn">${r["검수필요"]}건</span>`
      : `<span class="badge ok">완료</span>`;
    html += `<tr><td>${r["파일명"]}</td><td>${r["서식"]}</td><td>${r["보명칭"] || "-"}</td><td>${r["보코드"] || "-"}</td><td>${pct}%</td><td>${flag}</td></tr>`;
  }
  html += "</tbody>";
  $("previewTable").innerHTML = html;

  const failed = data.files.filter((f) => !f.ok);
  $("flagNote").innerHTML = failed.length
    ? "⚠️ 처리 못한 파일: " + failed.map((f) => `${f.name} (${f.error})`).join(", ")
    : "노란색으로 표시된 칸은 자동 추출이 애매해 사람이 확인이 필요한 값입니다.";

  renderReview(data.records);
  $("resultCard").scrollIntoView({ behavior: "smooth" });
}

function renderReview(records) {
  const box = $("reviewList");
  box.innerHTML = "";
  const withValues = records.filter((r) => Object.keys(r.values || {}).length);
  if (!withValues.length) {
    $("reviewCard").hidden = true;
    return;
  }
  $("reviewCard").hidden = false;

  for (const rec of withValues) {
    const block = document.createElement("div");
    block.className = "rev-block";
    const flagCount = Object.keys(rec.flags || {}).length;
    block.innerHTML =
      `<div class="rev-head">${rec["서식"]} · <b>${rec["보명칭"] || "이름없음"}</b>` +
      `<span class="rev-code">${rec["보코드"] || ""}</span>` +
      (flagCount ? `<span class="badge warn">검수 ${flagCount}건</span>` : `<span class="badge ok">완료</span>`) +
      `</div>`;

    const grid = document.createElement("div");
    grid.className = "rev-grid";
    for (const [field, value] of Object.entries(rec.values)) {
      const flagged = rec.flags && field in rec.flags;
      const cell = document.createElement("div");
      cell.className = "rev-field" + (flagged ? " flagged" : "");
      cell.innerHTML =
        `<label>${field}${flagged ? " ⚠️" : ""}</label>` +
        `<input type="text" value="${(value ?? "").replace(/"/g, "&quot;")}" data-key="${rec.key}" data-field="${field}" />`;
      grid.appendChild(cell);
    }
    // 플래그인데 값이 비어있는 필드도 편집칸 제공
    for (const field of Object.keys(rec.flags || {})) {
      if (!(field in rec.values)) {
        const cell = document.createElement("div");
        cell.className = "rev-field flagged";
        cell.innerHTML =
          `<label>${field} ⚠️</label>` +
          `<input type="text" value="" placeholder="값 입력" data-key="${rec.key}" data-field="${field}" />`;
        grid.appendChild(cell);
      }
    }
    block.appendChild(grid);
    box.appendChild(block);
  }

  box.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("change", () => saveCorrection(inp));
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") inp.blur(); });
  });
}

async function saveCorrection(inp) {
  const key = inp.dataset.key;
  const field = inp.dataset.field;
  const value = inp.value;
  inp.classList.add("saving");
  try {
    const res = await fetch("/api/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, field, value }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    inp.classList.remove("saving");
    inp.classList.add("saved");
    // 수정하면 검수필요 해제(노란 표시 제거)
    inp.closest(".rev-field").classList.remove("flagged");
    const lbl = inp.closest(".rev-field").querySelector("label");
    if (lbl) lbl.textContent = lbl.textContent.replace(" ⚠️", "");
    if (typeof data.flagged === "number") {
      const tiles = document.querySelectorAll("#stats .tile");
      if (tiles[3]) tiles[3].querySelector(".tile-num").textContent = data.flagged;
    }
    setTimeout(() => inp.classList.remove("saved"), 1200);
  } catch (e) {
    inp.classList.remove("saving");
    alert("저장 실패: " + e.message);
  }
}

$("downloadBtn").addEventListener("click", () => {
  window.location.href = "/api/download";
});
