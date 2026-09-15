// 오토다타 웹 시작 페이지 — 이 컴퓨터의 도우미(로컬 오토다타)를 찾고 준비 상태를 보여 준다.
// 파일 처리는 하지 않는다: 도우미의 상태 주소(/api/local/hello, /api/system/check)만 읽고,
// 실제 작업은 도우미 화면(http://127.0.0.1:포트/)을 새 창으로 연다.
(() => {
  "use strict";
  const PORTS = Array.from({ length: 15 }, (_, i) => 8765 + i);   // 도우미가 여는 포트(8765부터 빈 포트)
  const params = new URLSearchParams(location.search);
  const testPort = parseInt(params.get("port") || "", 10);        // 개발 확인용 ?port=8791
  if (testPort > 0 && testPort < 65536 && !PORTS.includes(testPort)) PORTS.unshift(testPort);

  const row = key => document.querySelector(`.checks li[data-key="${key}"]`);
  const openBtn = document.getElementById("open");
  const retryBtn = document.getElementById("retry");
  const install = document.getElementById("install");
  const update = document.getElementById("update");

  function setRow(key, state, text) {
    const li = row(key);
    li.dataset.state = state;
    li.querySelector(".detail").textContent = text;
  }

  async function getJson(url, ms) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(url, { signal: ctl.signal, cache: "no-store" });
      if (!r.ok) return null;
      return await r.json();
    } catch (_) {
      return null;
    } finally {
      clearTimeout(timer);
    }
  }

  async function hello(port) {
    const d = await getJson(`http://127.0.0.1:${port}/api/local/hello`, 2500);
    return d && d.app === "autodata" ? { ...d, port } : null;
  }

  // 도우미는 거의 항상 첫 포트(8765)에서 뜬다 — 먼저 확인하고, 없을 때만 나머지 포트를 한꺼번에 찾는다
  // (빈 포트마다 브라우저 콘솔에 연결 실패가 찍히므로 불필요한 확인을 줄임)
  async function findHelper() {
    const first = await hello(PORTS[0]);
    if (first) return first;
    const hits = await Promise.all(PORTS.slice(1).map(hello));
    return hits.find(Boolean) || null;
  }

  // 버전 비교 '1.4.10' > '1.4.9'
  function newer(a, b) {
    const pa = String(a).split(".").map(n => parseInt(n, 10) || 0);
    const pb = String(b).split(".").map(n => parseInt(n, 10) || 0);
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
      if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) > (pb[i] || 0);
    }
    return false;
  }

  const LEVEL = { ok: "ok", info: "ok", warn: "warn", fail: "off" };

  function showCheck(key, item, fallback) {
    if (!item) { setRow(key, "idle", fallback); return; }
    const text = item.detail + (item.status !== "ok" && item.fix ? ` — ${item.fix}` : "");
    setRow(key, LEVEL[item.status] || "warn", text);
  }

  async function run() {
    retryBtn.disabled = true;
    update.hidden = true;
    openBtn.setAttribute("aria-disabled", "true");
    openBtn.href = "#";
    setRow("helper", "wait", "이 컴퓨터에서 찾는 중…");
    for (const k of ["hwp", "ocr", "ai"]) setRow(k, "idle", "도우미를 찾으면 확인합니다");

    const [helper, latest] = await Promise.all([findHelper(), getJson("version.json", 4000)]);
    retryBtn.disabled = false;

    if (!helper) {
      setRow("helper", "off",
        "찾지 못했습니다 — 아래 순서대로 받아서 실행한 뒤 ‘다시 찾기’를 눌러 주세요. " +
        "켜 두었는데도 못 찾으면 브라우저의 로컬 네트워크 접근 허용을 확인해 주세요.");
      install.dataset.focus = "true";
      return;
    }
    install.dataset.focus = "false";
    setRow("helper", "ok", `켜져 있음 · 버전 ${helper.version} · 이 컴퓨터 ${helper.port}번 포트`);
    openBtn.href = `http://127.0.0.1:${helper.port}${helper.ui || "/"}`;
    openBtn.setAttribute("aria-disabled", "false");

    if (latest && latest.helper && newer(latest.helper, helper.version)) {
      update.innerHTML = "";
      update.append(`새 도우미 ${latest.helper}이(가) 나왔습니다. `);
      const a = document.createElement("a");
      a.href = latest.download || document.getElementById("download").href;
      a.textContent = "내려받기";
      update.append(a);
      update.append(" 후 압축을 풀어 새 폴더의 FieldSurveyDB.exe 로 실행해 주세요.");
      update.hidden = false;
    }

    // 도우미를 막 켠 직후엔 첫 점검이 수~십 초 걸린다(GPU·라이브러리 확인) — 넉넉히 기다린다
    const check = await getJson(`http://127.0.0.1:${helper.port}/api/system/check?quick=1`, 30000);
    const items = {};
    for (const it of (check && check.items) || []) items[it.id] = it;
    showCheck("hwp", items.hwp, "확인하지 못했습니다");
    showCheck("ocr", items.ocr, "확인하지 못했습니다");
    showCheck("ai", items.ai, "확인하지 못했습니다");
  }

  retryBtn.addEventListener("click", run);
  getJson("version.json", 4000).then(v => {
    if (v && v.helper) document.getElementById("web-version").textContent = `도우미 최신 ${v.helper}`;
  });
  run();
})();
