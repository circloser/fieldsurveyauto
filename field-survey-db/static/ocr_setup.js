// 글자 인식(OCR) 기능 받기 안내 — 템플릿 디자이너(양식 업로드)와 데이터 추출 관리(일괄 처리)에서 함께 쓴다.
// 페이지의 $() 헬퍼를 쓰지 않는다(각 페이지 스크립트보다 먼저 불러온다).
// 스캔(사진) 문서인데 글자 인식 기능이 없을 때(경량 도우미) — 받기 안내와 진행 표시.
// 받는 곳은 공개 저장소(PyPI·PyTorch·EasyOCR)이고, 파일은 이 컴퓨터에만 저장된다.
function showOcrSetup(s) {
  let el = document.getElementById("ocrSetup");
  if (!el) {
    el = document.createElement("div");
    el.id = "ocrSetup"; el.className = "env-warn";
    const badge = document.querySelector(".security-badge");
    badge.parentNode.insertBefore(el, badge.nextSibling);
  }
  el.textContent = "";
  renderOcrSetup(el, s, { intro: true, afterDone: "스캔 양식을 다시 올리면 칸 글자를 읽습니다." });
}

// 받기 안내·진행·완료를 주어진 요소 안에 그린다(양식 업로드 배너·일괄 처리 결과에서 공용).
// 받는 곳은 공개 저장소(PyPI·PyTorch·EasyOCR)이고, 파일은 이 컴퓨터에만 저장된다.
function renderOcrSetup(el, s, opts) {
  opts = opts || {};
  const fmt = (b) => b >= 1e9 ? (b / 1e9).toFixed(1) + "GB" : Math.max(1, Math.round(b / 1e6)) + "MB";
  const job = s.job || {};
  const v = s.recommended || "cpu";
  const redraw = (next) => { el.textContent = ""; renderOcrSetup(el, next, opts); };
  if (job.running) {
    const pct = job.total ? Math.min(100, job.done / job.total * 100) : 0;
    el.append(`⏬ 글자 인식 기능 받는 중… ${pct.toFixed(0)}% (${fmt(job.done)} / ${fmt(job.total)}) — 받는 동안 다른 작업을 해도 됩니다.`);
    setTimeout(async () => {
      try { redraw(await (await fetch("/api/ocr/runtime")).json()); } catch (e) {}
    }, 1500);
    return;
  }
  if (s.ready) {
    el.append("✅ 글자 인식 기능을 받았습니다 — " + (opts.afterDone || ""));
    return;
  }
  if (opts.intro) {
    const b = document.createElement("b"); b.textContent = "글자 인식 기능";
    el.append("📷 스캔(사진) PDF라 글자를 읽으려면 ", b, "이 필요합니다. ");
  }
  el.append("공개 저장소(PyPI·PyTorch·EasyOCR)에서 받아 이 컴퓨터에만 둡니다. ");
  const get = document.createElement("button");
  get.type = "button"; get.className = "btn";
  get.textContent = `받기 (${v === "gpu" ? "GPU 가속판, " : ""}${fmt((s.sizes || {})[v] || 0)})`;
  get.addEventListener("click", async () => {
    get.disabled = true;
    const d = await (await fetch("/api/ocr/runtime/install", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ variant: v }),
    })).json();
    if (d.error) { alert(d.error); get.disabled = false; return; }
    redraw(d);
  });
  const more = document.createElement("a");
  more.href = "/settings#ocr"; more.target = "_blank"; more.textContent = "자세히";
  el.append(get, " ", more);
  if (job.error) el.append(document.createElement("br"), "⚠️ 지난번 받기 실패: " + job.error);
}
