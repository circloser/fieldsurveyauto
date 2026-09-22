// 오토다타 웹 — 정적 시작 페이지(field-survey-db/web) + 디지털 입력 양식 서버.
//
// 디지털 입력 양식(데이터 입력 관리):
//   · 이 PC의 도우미가 템플릿을 '양식 정의(JSON)'로 바꿔 POST /api/forms 로 올리면 양식 하나가 만들어진다.
//   · 현장 조사자는 공유 링크 /f/<id>?k=<입력 키> 를 휴대전화로 열어 기록한다(인터넷이 끊기면 기기에 저장했다가 다시 보냄).
//   · 도우미는 관리 키로 기록을 가져와 조사표 PDF·엑셀로 만든다. 관리 키는 만든 PC에만 있다.
//   · 양식마다 Durable Object(SQLite) 하나 — 기록 순서(seq)가 보장되어 '이 번호 뒤의 새 기록'만 받아 갈 수 있다.
//   · 사진은 기기에서 줄여(긴 변 1280px, JPEG) 보내고 기록과 따로 저장한다(행당 2MB 한도).
import { DurableObject } from "cloudflare:workers";

const ID_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";   // 헷갈리는 글자(0 o 1 l i) 제외
const MAX_ENTRY_JSON = 8 * 1024 * 1024;
const MAX_PHOTO_BYTES = 1500 * 1024;
const MAX_PHOTOS = 8;

function randomId(n) {
  const buf = new Uint8Array(n);
  crypto.getRandomValues(buf);
  let s = "";
  for (const b of buf) s += ID_ALPHABET[b % ID_ALPHABET.length];
  return s;
}

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra },
  });
}

function bad(msg, status = 400) {
  return json({ error: msg }, status);
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function decodeDataUrl(s) {
  const m = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/.exec(s || "");
  if (!m) return null;
  const bin = atob(m[2]);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return { mime: m[1], bytes };
}

// ---------------------------------------------------------------- 양식 하나 = Durable Object 하나
export class FormRoom extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => this._schema());
  }

  _schema() {
    this.ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)`);
    this.ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS entries (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, created TEXT NOT NULL,
      received TEXT NOT NULL, client_id TEXT, values_json TEXT NOT NULL, meta_json TEXT NOT NULL)`);
    this.ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS photos (
      entry_id TEXT NOT NULL, field TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
      PRIMARY KEY (entry_id, field))`);
  }

  _meta(k) {
    const rows = this.ctx.storage.sql.exec("SELECT v FROM meta WHERE k = ?", k).toArray();
    return rows.length ? rows[0].v : null;
  }

  _setMeta(k, v) {
    this.ctx.storage.sql.exec("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", k, v);
  }

  exists() {
    return this._meta("definition") !== null;
  }

  create(definition, writeKey, adminKey) {
    if (this.exists()) return { error: "이미 있는 양식입니다." };
    this._setMeta("definition", JSON.stringify(definition));
    this._setMeta("write_key", writeKey);
    this._setMeta("admin_key", adminKey);
    this._setMeta("created", new Date().toISOString());
    this._setMeta("closed", "0");
    return { ok: true };
  }

  _checkWrite(key) { return timingSafeEqual(this._meta("write_key") || "", key || ""); }
  _checkAdmin(key) { return timingSafeEqual(this._meta("admin_key") || "", key || ""); }

  /** 입력 페이지용 — 양식 정의와 닫힘 여부(입력 키 필요). */
  getPublic(writeKey) {
    if (!this.exists()) return { error: "없는 양식입니다.", status: 404 };
    if (!this._checkWrite(writeKey)) return { error: "링크의 키가 맞지 않습니다.", status: 403 };
    return { definition: JSON.parse(this._meta("definition")), closed: this._meta("closed") === "1",
             created: this._meta("created") };
  }

  /** 현장에서 보낸 기록 하나 저장 — 같은 id 가 다시 오면(재전송) 기존 번호를 돌려준다. */
  submit(writeKey, entry) {
    if (!this.exists()) return { error: "없는 양식입니다.", status: 404 };
    if (!this._checkWrite(writeKey)) return { error: "링크의 키가 맞지 않습니다.", status: 403 };
    if (this._meta("closed") === "1") return { error: "입력이 닫힌 양식입니다. 담당자에게 문의하세요.", status: 409 };
    const id = String(entry.id || "").slice(0, 64);
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(id)) return { error: "기록 id 형식 오류", status: 400 };
    const dup = this.ctx.storage.sql.exec("SELECT seq FROM entries WHERE id = ?", id).toArray();
    if (dup.length) return { ok: true, seq: dup[0].seq, duplicate: true };
    const values = entry.values && typeof entry.values === "object" ? entry.values : {};
    const meta = entry.meta && typeof entry.meta === "object" ? entry.meta : {};
    const photos = entry.photos && typeof entry.photos === "object" ? entry.photos : {};
    const photoRows = [];
    for (const [field, dataUrl] of Object.entries(photos)) {
      if (photoRows.length >= MAX_PHOTOS) break;
      const dec = decodeDataUrl(dataUrl);
      if (!dec || dec.bytes.byteLength > MAX_PHOTO_BYTES) return { error: `사진(${field})이 너무 크거나 형식이 맞지 않습니다.`, status: 400 };
      photoRows.push([field, dec.mime, dec.bytes.buffer]);
    }
    const now = new Date().toISOString();
    const created = typeof entry.created === "string" && entry.created.length <= 40 ? entry.created : now;
    const seq = this.ctx.storage.sql.exec(
      "INSERT INTO entries (id, created, received, client_id, values_json, meta_json) VALUES (?, ?, ?, ?, ?, ?) RETURNING seq",
      id, created, now, String(entry.client_id || "").slice(0, 64), JSON.stringify(values), JSON.stringify(meta)).one().seq;
    for (const [field, mime, buf] of photoRows) {
      this.ctx.storage.sql.exec("INSERT OR REPLACE INTO photos (entry_id, field, mime, data) VALUES (?, ?, ?, ?)", id, field, mime, buf);
    }
    return { ok: true, seq };
  }

  /** 관리용 — since 번호 뒤의 기록들(사진은 목록만, 내용은 photo 로 따로). */
  list(adminKey, since) {
    if (!this.exists()) return { error: "없는 양식입니다.", status: 404 };
    if (!this._checkAdmin(adminKey)) return { error: "관리 키가 맞지 않습니다.", status: 403 };
    const rows = this.ctx.storage.sql.exec(
      "SELECT seq, id, created, received, client_id, values_json, meta_json FROM entries WHERE seq > ? ORDER BY seq LIMIT 500",
      Number(since) || 0).toArray();
    const entries = rows.map((r) => ({ seq: r.seq, id: r.id, created: r.created, received: r.received, client_id: r.client_id,
                                       values: JSON.parse(r.values_json), meta: JSON.parse(r.meta_json), photos: [] }));
    if (entries.length) {
      const byId = new Map(entries.map((e) => [e.id, e]));
      const ph = this.ctx.storage.sql.exec("SELECT entry_id, field, mime, length(data) AS size FROM photos").toArray();
      for (const p of ph) { const e = byId.get(p.entry_id); if (e) e.photos.push({ field: p.field, mime: p.mime, size: p.size }); }
    }
    const total = this.ctx.storage.sql.exec("SELECT COUNT(*) AS n, COALESCE(MAX(seq), 0) AS last FROM entries").one();
    return { entries, total: total.n, last_seq: total.last, closed: this._meta("closed") === "1",
             definition: JSON.parse(this._meta("definition")), created: this._meta("created") };
  }

  photo(adminKey, entryId, field) {
    if (!this._checkAdmin(adminKey)) return { error: "관리 키가 맞지 않습니다.", status: 403 };
    const rows = this.ctx.storage.sql.exec("SELECT mime, data FROM photos WHERE entry_id = ? AND field = ?", entryId, field).toArray();
    if (!rows.length) return { error: "사진 없음", status: 404 };
    return { mime: rows[0].mime, data: rows[0].data };
  }

  setClosed(adminKey, closed) {
    if (!this.exists()) return { error: "없는 양식입니다.", status: 404 };
    if (!this._checkAdmin(adminKey)) return { error: "관리 키가 맞지 않습니다.", status: 403 };
    this._setMeta("closed", closed ? "1" : "0");
    return { ok: true, closed: !!closed };
  }

  async destroy(adminKey) {
    if (!this.exists()) return { error: "없는 양식입니다.", status: 404 };
    if (!this._checkAdmin(adminKey)) return { error: "관리 키가 맞지 않습니다.", status: 403 };
    await this.ctx.storage.deleteAll();   // 표까지 지워지므로 빈 표를 다시 만들어 둔다(다음 요청이 404 로 답하게)
    this._schema();
    return { ok: true };
  }
}

// ---------------------------------------------------------------- 라우팅
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    let m;
    try {
      if (path === "/api/forms" && request.method === "POST") return await createForm(request, env, url);
      if ((m = /^\/f\/([a-z0-9]{6,32})\/?$/.exec(path))) return await formPage(env, m[1], url);
      if ((m = /^\/api\/forms\/([a-z0-9]{6,32})(?:\/(.*))?$/.exec(path))) return await formApi(request, env, m[1], m[2] || "", url);
    } catch (e) {
      return bad("서버 오류: " + (e && e.message ? e.message : String(e)), 500);
    }
    return new Response("Not found", { status: 404 });
  },
};

async function createForm(request, env, url) {
  if (env.PUBLISH_KEY && !timingSafeEqual(request.headers.get("x-publish-key") || "", env.PUBLISH_KEY)) {
    return bad("양식 만들기 키가 맞지 않습니다.", 403);
  }
  let body;
  try { body = await request.json(); } catch (e) { return bad("JSON 본문이 필요합니다."); }
  const def = body && body.definition;
  if (!def || typeof def !== "object" || !Array.isArray(def.fields) || !def.fields.length) return bad("양식 정의(fields)가 필요합니다.");
  if (JSON.stringify(def).length > 512 * 1024) return bad("양식 정의가 너무 큽니다.");
  const id = randomId(10), writeKey = randomId(16), adminKey = randomId(32);
  const stub = env.FORMS.getByName(id);
  const r = await stub.create(def, writeKey, adminKey);
  if (r.error) return bad(r.error, 500);
  const share = `${url.origin}/f/${id}?k=${writeKey}`;
  return json({ id, write_key: writeKey, admin_key: adminKey, share_url: share }, 201);
}

async function formApi(request, env, id, rest, url) {
  let m;
  const stub = env.FORMS.getByName(id);
  const adminKey = request.headers.get("x-admin-key") || url.searchParams.get("admin") || "";
  const writeKey = request.headers.get("x-write-key") || url.searchParams.get("k") || "";
  if (rest === "" && request.method === "GET") {              // 입력 페이지가 쓰는 공개 정의
    const r = await stub.getPublic(writeKey);
    return r.error ? bad(r.error, r.status) : json(r);
  }
  if (rest === "entries" && request.method === "POST") {      // 현장 기록 보내기
    const len = Number(request.headers.get("content-length") || 0);
    if (len > MAX_ENTRY_JSON) return bad("기록이 너무 큽니다(사진을 줄여 주세요).", 413);
    let entry;
    try { entry = await request.json(); } catch (e) { return bad("JSON 본문이 필요합니다."); }
    const r = await stub.submit(writeKey, entry || {});
    return r.error ? bad(r.error, r.status) : json(r, r.duplicate ? 200 : 201);
  }
  if (rest === "entries" && request.method === "GET") {       // 도우미가 가져가기
    const r = await stub.list(adminKey, url.searchParams.get("since") || 0);
    return r.error ? bad(r.error, r.status) : json(r);
  }
  if ((m = /^photos\/([A-Za-z0-9_-]{8,64})\/(.{1,200})$/.exec(rest)) && request.method === "GET") {
    const r = await stub.photo(adminKey, m[1], decodeURIComponent(m[2]));
    if (r.error) return bad(r.error, r.status);
    return new Response(r.data, { headers: { "content-type": r.mime, "cache-control": "private, max-age=0" } });
  }
  if ((rest === "close" || rest === "open") && request.method === "POST") {
    const r = await stub.setClosed(adminKey, rest === "close");
    return r.error ? bad(r.error, r.status) : json(r);
  }
  if (rest === "" && request.method === "DELETE") {
    const r = await stub.destroy(adminKey);
    return r.error ? bad(r.error, r.status) : json(r);
  }
  return bad("없는 주소입니다.", 404);
}

// ---------------------------------------------------------------- 현장 입력 페이지(휴대전화)
async function formPage(env, id, url) {
  const stub = env.FORMS.getByName(id);
  const r = await stub.getPublic(url.searchParams.get("k") || "");
  const headers = {
    "content-type": "text/html; charset=utf-8",
    "cache-control": "no-store",
    "content-security-policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'; form-action 'none'; base-uri 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
  };
  if (r.error) {
    return new Response(shellHtml("오토다타 입력 양식", `<div class="card"><h1>양식을 열 수 없습니다</h1><p>${escapeHtml(r.error)}</p><p class="muted">링크를 보낸 담당자에게 확인해 주세요.</p></div>`),
      { status: r.status || 400, headers });
  }
  const payload = JSON.stringify({ id, key: url.searchParams.get("k"), definition: r.definition, closed: r.closed }).replace(/</g, "\\u003c");
  return new Response(shellHtml(r.definition.title || "오토다타 입력 양식", FORM_BODY, `window.__FORM__ = ${payload};` + FORM_SCRIPT), { headers });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function shellHtml(title, body, script = "") {
  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${escapeHtml(title)}</title>
<style>
  :root { --ink:#1e2126; --line:#dfe5da; --muted:#6b7480; --green:#4e9f2f; --green-dark:#3f8425; --lime:#7dc242; --soft:#eef7e5; --warn:#fff4d6; --err:#ffe3e3; }
  * { box-sizing: border-box; }
  body { margin:0; background:#f2f5ee; color:var(--ink); font-family:-apple-system, "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; font-size:16px; line-height:1.5; word-break:keep-all; }
  .band { background:#1e2126; color:#fff; padding:14px 16px calc(14px + env(safe-area-inset-top)); position:sticky; top:0; z-index:5; }
  .band h1 { font-size:17px; margin:0; font-weight:700; }
  .band .tag { font-size:12px; color:#aeb6ad; margin-top:2px; }
  .wrap { max-width:640px; margin:0 auto; padding:12px 12px 120px; }
  .card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px; margin:0 0 12px; }
  .card h1 { font-size:18px; margin:0 0 8px; }
  .muted { color:var(--muted); font-size:13px; }
  .sec { font-size:13px; font-weight:700; color:var(--green-dark); margin:14px 0 6px; letter-spacing:.02em; }
  .sec.ttl { font-size:15px; color:var(--ink); margin-top:4px; }
  .f { margin:0 0 12px; }
  .f label.l { display:block; font-size:14px; font-weight:600; margin:0 0 4px; }
  input[type=text], input[type=number], textarea, select { width:100%; font:inherit; padding:11px 12px; border:1px solid var(--line); border-radius:10px; background:#fff; }
  input[type=number] { font-variant-numeric: tabular-nums; }
  input:focus, textarea:focus { outline:2px solid var(--lime); border-color:var(--lime); }
  textarea { min-height:72px; resize:vertical; }
  .chk { display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px solid var(--line); border-radius:10px; font-size:15px; }
  .chk input { width:22px; height:22px; }
  .photo { display:flex; align-items:center; gap:10px; }
  .photo img { width:84px; height:84px; object-fit:cover; border-radius:10px; border:1px solid var(--line); background:#f6f6f6; }
  .photo .pbtn { flex:1; }
  .btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:12px 16px; border-radius:12px; border:1px solid var(--green); background:var(--green); color:#fff; font:inherit; font-weight:700; cursor:pointer; }
  .btn.ghost { background:#fff; color:var(--green-dark); }
  .btn.small { padding:8px 12px; font-size:14px; }
  .btn:disabled { opacity:.5; }
  table.tbl { width:100%; border-collapse:collapse; font-size:14px; }
  table.tbl th, table.tbl td { border:1px solid var(--line); padding:4px; vertical-align:top; }
  table.tbl th { background:#f6f8f3; font-weight:600; text-align:left; font-size:12px; }
  table.tbl input { padding:8px; border-radius:6px; }
  .row-x { border:none; background:none; color:#c92a2a; font-size:16px; cursor:pointer; }
  .bar { position:fixed; left:0; right:0; bottom:0; background:#fff; border-top:1px solid var(--line); padding:10px 12px calc(10px + env(safe-area-inset-bottom)); display:flex; gap:8px; align-items:center; z-index:5; }
  .bar .btn { flex:1; }
  .status { font-size:13px; padding:8px 10px; border-radius:10px; margin:0 0 10px; }
  .status.ok { background:var(--soft); color:#2f6e18; }
  .status.warn { background:var(--warn); color:#7a5b00; }
  .status.err { background:var(--err); color:#b42323; }
  .hist { font-size:13px; }
  .hist li { padding:6px 0; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:8px; }
  .gps { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .gps span { font-size:13px; color:var(--muted); }
</style>
</head>
<body>
<div class="band"><h1 id="ttl">${escapeHtml(title)}</h1><div class="tag">오토다타 현장 입력 · 기록은 팀 담당자의 컴퓨터로 모입니다</div></div>
<div class="wrap">${body}</div>
<script>${script}</script>
</body>
</html>`;
}

const FORM_BODY = `
<div id="status" class="status" hidden></div>
<form id="form" class="card" autocomplete="off"></form>
<div class="card">
  <div class="sec" style="margin-top:0">보낸 기록</div>
  <ul id="hist" class="hist muted" style="list-style:none;padding:0;margin:0"><li>아직 없음</li></ul>
</div>
<div class="bar">
  <button class="btn ghost small" type="button" id="resetBtn">새로 쓰기</button>
  <button class="btn" type="button" id="sendBtn">기록 보내기</button>
</div>`;

const FORM_SCRIPT = String.raw`
(() => {
  const F = window.__FORM__;
  const def = F.definition, fields = def.fields || [];
  const API = "/api/forms/" + F.id + "/entries?k=" + encodeURIComponent(F.key || "");
  const QKEY = "autodata_q_" + F.id, HKEY = "autodata_h_" + F.id, CKEY = "autodata_client";
  const $ = (id) => document.getElementById(id);
  const form = $("form");
  const photos = {};
  let clientId = null;
  try { clientId = localStorage.getItem(CKEY); if (!clientId) { clientId = rid(12); localStorage.setItem(CKEY, clientId); } } catch (e) { clientId = rid(12); }

  function ftime(iso) { const d = new Date(iso); if (isNaN(d)) return String(iso || ""); const p = (n) => String(n).padStart(2, "0"); return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()); }
  function rid(n) { const a = "abcdefghjkmnpqrstuvwxyz23456789"; let s = ""; const b = new Uint8Array(n); crypto.getRandomValues(b); for (const x of b) s += a[x % a.length]; return s; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function status(msg, kind) { const el = $("status"); if (!msg) { el.hidden = true; return; } el.hidden = false; el.className = "status " + (kind || "ok"); el.textContent = msg; }

  // ---- 양식 그리기(쪽 단위로 묶고, 유형별 입력칸)
  function render() {
    let html = "";
    if (F.closed) html += '<div class="status warn">이 양식은 입력이 닫혔습니다. 담당자에게 문의하세요.</div>';
    let page = null;
    const multiPage = new Set(fields.map((x) => x.page)).size > 1;
    for (const f of fields) {
      if (f.page !== page) { page = f.page; if (multiPage) html += '<div class="sec">' + (page + 1) + "쪽</div>"; }
      if (f.type === "title") { html += '<div class="sec ttl">' + esc(f.value || f.label) + "</div>"; continue; }
      const k = esc(f.key), l = esc(f.label || f.key);
      if (f.type === "check") html += '<div class="f"><label class="chk"><input type="checkbox" data-k="' + k + '"> ' + l + "</label></div>";
      else if (f.type === "number") html += '<div class="f"><label class="l">' + l + '</label><input type="number" inputmode="decimal" step="any" data-k="' + k + '"></div>';
      else if (f.type === "image") html += '<div class="f"><label class="l">' + l + '</label><div class="photo"><img data-prev="' + k + '" alt=""><label class="btn ghost small pbtn">📷 사진 찍기/고르기<input type="file" accept="image/*" capture="environment" data-photo="' + k + '" hidden></label></div></div>';
      else if (f.type === "table") {
        const cols = (f.columns && f.columns.length) ? f.columns : ["값"];
        html += '<div class="f" data-table="' + k + '"><label class="l">' + l + '</label><table class="tbl"><thead><tr>' + cols.map((c) => "<th>" + esc(c) + "</th>").join("") + '<th></th></tr></thead><tbody></tbody></table><button type="button" class="btn ghost small" data-addrow="' + k + '" style="margin-top:6px">＋ 줄 추가</button></div>';
      } else {
        const long = (f.label || f.key).length > 12 || /설명|비고|특이|내용|메모/.test(f.label || f.key);
        html += '<div class="f"><label class="l">' + l + "</label>" + (long ? '<textarea data-k="' + k + '"></textarea>' : '<input type="text" data-k="' + k + '">') + "</div>";
      }
    }
    if (def.gps) html += '<div class="f gps"><button type="button" class="btn ghost small" id="gpsBtn">📍 현재 위치 넣기</button><span id="gpsOut">위치 없음</span></div>';
    form.innerHTML = html;
    form.querySelectorAll("[data-addrow]").forEach((b) => b.addEventListener("click", () => addRow(b.dataset.addrow)));
    fields.filter((f) => f.type === "table").forEach((f) => addRow(f.key));
    form.querySelectorAll("[data-photo]").forEach((inp) => inp.addEventListener("change", () => takePhoto(inp)));
    const g = $("gpsBtn"); if (g) g.addEventListener("click", getGps);
  }
  function addRow(key) {
    const f = fields.find((x) => x.key === key); const cols = (f.columns && f.columns.length) ? f.columns : ["값"];
    const tb = form.querySelector('[data-table="' + CSS.escape(key) + '"] tbody');
    const tr = document.createElement("tr");
    tr.innerHTML = cols.map((c) => '<td><input type="text" data-col="' + esc(c) + '"></td>').join("") + '<td><button type="button" class="row-x" title="줄 삭제">✕</button></td>';
    tr.querySelector(".row-x").addEventListener("click", () => tr.remove());
    tb.appendChild(tr);
  }
  async function takePhoto(inp) {
    const file = inp.files && inp.files[0]; if (!file) return;
    const key = inp.dataset.photo;
    try {
      const dataUrl = await shrink(file, 1280, 0.8);
      photos[key] = dataUrl;
      form.querySelector('img[data-prev="' + CSS.escape(key) + '"]').src = dataUrl;
    } catch (e) { status("사진을 읽지 못했습니다: " + e.message, "err"); }
  }
  function shrink(file, max, q) {
    return new Promise((res, rej) => {
      const url = URL.createObjectURL(file); const im = new Image();
      im.onload = () => {
        const s = Math.min(1, max / Math.max(im.width, im.height));
        const c = document.createElement("canvas"); c.width = Math.round(im.width * s); c.height = Math.round(im.height * s);
        c.getContext("2d").drawImage(im, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url); res(c.toDataURL("image/jpeg", q));
      };
      im.onerror = () => rej(new Error("이미지 형식")); im.src = url;
    });
  }
  let gps = null;
  function getGps() {
    if (!navigator.geolocation) { $("gpsOut").textContent = "이 기기에서 위치를 쓸 수 없습니다"; return; }
    $("gpsOut").textContent = "위치 찾는 중…";
    navigator.geolocation.getCurrentPosition((p) => {
      gps = { lat: +p.coords.latitude.toFixed(6), lon: +p.coords.longitude.toFixed(6), acc: Math.round(p.coords.accuracy || 0) };
      $("gpsOut").textContent = gps.lat + ", " + gps.lon + " (±" + gps.acc + "m)";
    }, (e) => { $("gpsOut").textContent = "위치를 얻지 못했습니다(" + e.message + ")"; }, { enableHighAccuracy: true, timeout: 15000 });
  }

  // ---- 값 모으기 / 보내기 / 오프라인 대기열
  function collect() {
    const values = {};
    for (const f of fields) {
      if (f.type === "title") continue;
      if (f.type === "table") {
        const rows = [];
        form.querySelectorAll('[data-table="' + CSS.escape(f.key) + '"] tbody tr').forEach((tr) => {
          const r = {}; let any = false;
          tr.querySelectorAll("input[data-col]").forEach((i) => { r[i.dataset.col] = i.value.trim(); if (i.value.trim()) any = true; });
          if (any) rows.push(r);
        });
        values[f.key] = rows; continue;
      }
      const el = form.querySelector('[data-k="' + CSS.escape(f.key) + '"]');
      if (!el) continue;
      values[f.key] = f.type === "check" ? el.checked : (f.type === "number" ? (el.value === "" ? "" : Number(el.value)) : el.value.trim());
    }
    return values;
  }
  function loadQ() { try { return JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch (e) { return []; } }
  function saveQ(q) { try { localStorage.setItem(QKEY, JSON.stringify(q)); } catch (e) { status("기기 저장 공간이 부족해 대기열에 넣지 못했습니다.", "err"); } }
  function hist(item) {
    let h = []; try { h = JSON.parse(localStorage.getItem(HKEY) || "[]"); } catch (e) {}
    if (item) { h.unshift(item); h = h.slice(0, 30); try { localStorage.setItem(HKEY, JSON.stringify(h)); } catch (e) {} }
    const q = loadQ(); const ul = $("hist");
    ul.innerHTML = (q.map((e) => '<li><span>⏳ ' + esc(ftime(e.created)) + " · 전송 대기</span><span>" + esc(e.summary || "") + "</span></li>").join("")
      + h.map((x) => '<li><span>✅ ' + esc(x.t) + "</span><span>" + esc(x.s) + "</span></li>").join("")) || "<li>아직 없음</li>";
  }
  function summary(values) {
    const first = fields.find((f) => f.type === "text" && values[f.key]);
    return first ? String(values[first.key]).slice(0, 20) : "";
  }
  async function post(entry) {
    const r = await fetch(API, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(entry) });
    let d = {}; try { d = await r.json(); } catch (e) {}
    if (r.status === 409 || r.status === 403 || r.status === 404 || r.status === 400 || r.status === 413) throw Object.assign(new Error(d.error || ("오류 " + r.status)), { fatal: true });
    if (!r.ok) throw new Error(d.error || ("오류 " + r.status));
    return d;
  }
  async function flush() {
    const q = loadQ(); if (!q.length) return;
    status("대기 중인 기록 " + q.length + "건을 보내는 중…", "warn");
    while (q.length) {
      const e = q[0];
      try { await post(e); q.shift(); saveQ(q); hist({ t: ftime(e.created), s: e.summary || "" }); }
      catch (err) { if (err.fatal) { q.shift(); saveQ(q); status("보낼 수 없는 기록을 버렸습니다: " + err.message, "err"); continue; } status("인터넷이 연결되면 자동으로 보냅니다 (대기 " + q.length + "건)", "warn"); hist(); return; }
    }
    status("대기 중이던 기록을 모두 보냈습니다.", "ok"); hist();
  }
  async function send() {
    const values = collect();
    const filled = Object.values(values).some((v) => v === true || (typeof v === "number") || (typeof v === "string" && v) || (Array.isArray(v) && v.length));
    if (!filled && !Object.keys(photos).length) { status("입력한 내용이 없습니다.", "warn"); return; }
    const entry = { id: rid(16), client_id: clientId, created: new Date().toISOString(), values, photos: { ...photos }, meta: gps ? { gps } : {}, summary: summary(values) };
    $("sendBtn").disabled = true;
    try {
      await post(entry);
      hist({ t: ftime(entry.created), s: entry.summary });
      status("보냈습니다. 계속 다음 기록을 쓰세요.", "ok");
      reset();
    } catch (err) {
      if (err.fatal) status(err.message, "err");
      else { const q = loadQ(); q.push(entry); saveQ(q); status("인터넷이 없어 이 기기에 저장했습니다 — 연결되면 자동으로 보냅니다 (대기 " + q.length + "건)", "warn"); reset(); hist(); }
    } finally { $("sendBtn").disabled = false; }
  }
  function reset() {
    for (const k of Object.keys(photos)) delete photos[k];
    render(); gps = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  $("sendBtn").addEventListener("click", send);
  $("resetBtn").addEventListener("click", () => { if (confirm("입력한 내용을 지우고 새로 쓸까요?")) reset(); });
  window.addEventListener("online", flush);
  render(); hist(); flush();
  if (F.closed) $("sendBtn").disabled = true;
})();
`;
