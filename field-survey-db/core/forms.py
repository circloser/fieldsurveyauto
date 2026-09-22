"""데이터 입력 관리 — 템플릿을 현장 입력용 디지털 양식으로 바꿔 오토다타 웹에 올리고, 모인 기록을 이 PC로 가져온다.

흐름
  템플릿(박스) → 양식 정의(항목 이름·유형·표 열) → POST {웹}/api/forms → 공유 링크(/f/<id>?k=입력키) + 관리 키
  현장 조사자: 링크를 휴대전화로 열어 기록한다(사진은 기기에서 줄여 보내고, 인터넷이 없으면 기기에 저장했다가 보냄)
  이 PC: 관리 키로 '아직 안 받은 기록'(seq 기준)만 받아 data/forms/<id>/ 에 쌓고 → 엑셀·현장조사표 PDF

무엇이 어디에 있나
  · 오토다타 웹(클라우드플레어 Durable Object): 양식 정의·기록·사진 — 양식을 지울 때까지 남는다
  · 이 PC(data/): forms.json(양식 목록 + 입력 키·관리 키), forms/<id>/template.json(박스 스냅숏)·template.pdf·entries.json·photos/
  관리 키는 만든 PC에만 있다 — 링크를 아는 사람은 기록을 보낼 수만 있고 남의 기록을 볼 수 없다.
  템플릿을 나중에 고쳐도 이미 만든 양식은 만들 때의 박스(스냅숏)로 PDF 를 채운다.
서버 주소: 기본 web_access.WEB_HOME. 바꾸려면 환경변수 AUTODATA_FORMS_ORIGIN 또는 exe 옆 forms_config.txt(ORIGIN=, PUBLISH_KEY=).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from core import web_access

CONFIG_FILE = "forms_config.txt"
_ID = re.compile(r"^[a-z0-9]{6,32}$")
_ENTRY_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_UNSAFE = re.compile(r'[\\/:*?"<>|\s]+')
_TYPE = {"text": "text", "bold": "text", "number": "number", "check": "check",
         "image": "image", "table": "table", "title": "title"}
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
PAGE = 500          # 웹이 한 번에 주는 기록 수(worker/index.js 의 LIMIT 와 같음)


class FormsError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 실패 이유."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def valid_id(form_id: str) -> bool:
    return bool(form_id) and _ID.match(form_id) is not None


def settings(base_dir) -> dict:
    """서버 주소·양식 만들기 키 — 환경변수 → forms_config.txt → 기본(배포 주소)."""
    cfg: dict[str, str] = {}
    try:
        for line in (Path(base_dir) / CONFIG_FILE).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip().upper()] = v.strip()
    except OSError:
        pass
    origin = (os.environ.get("AUTODATA_FORMS_ORIGIN") or cfg.get("ORIGIN") or web_access.WEB_HOME).rstrip("/")
    key = os.environ.get("AUTODATA_FORMS_PUBLISH_KEY") or cfg.get("PUBLISH_KEY") or ""
    return {"origin": origin, "publish_key": key}


# ---------------------------------------------------------------- 템플릿 → 양식 정의

def field_label(box: dict) -> str:
    """현장 조사자가 보는 이름 — 라벨 기준 박스면 양식에 인쇄된 라벨, 아니면 박스 이름(쪽 접두어 제거)."""
    anchor = box.get("anchor") or {}
    if box.get("use_anchor") and str(anchor.get("label") or "").strip():
        return str(anchor["label"]).strip()
    name = re.sub(r"^P\d+_", "", str(box.get("field") or "").strip())
    return name or "항목"


_PLACEHOLDER = {"새 항목", "항목", "제목", "title"}


def dedup_boxes(boxes: list[dict]) -> list[dict]:
    """박스 이름을 유일하게(일괄 처리와 같은 규칙: 두 번째부터 '이름 (2)'). 복사본을 돌려준다."""
    import copy
    out = copy.deepcopy(boxes)
    seen: dict[str, int] = {}
    for b in sorted(out, key=lambda z: z.get("order", 0)):
        f = str(b.get("field") or "항목").strip() or "항목"
        if f in seen:
            seen[f] += 1
            b["field"] = f"{f} ({seen[f]})"
        else:
            seen[f] = 1
    return out


def build_definition(name: str, boxes: list[dict], *, title: str = "", gps: bool = False) -> dict:
    """박스 목록 → 휴대전화 입력 페이지가 그리는 양식 정의. 좌표는 넣지 않는다(PDF 채우기는 이 PC의 스냅숏으로).

    박스 이름은 dedup_boxes 로 먼저 유일하게 해 두어야 기록값이 박스와 1:1 로 맞는다.
    """
    fields: list[dict] = []
    seen: set[str] = set()
    for b in sorted(boxes, key=lambda z: z.get("order", 0)):
        key = str(b.get("field") or "").strip()
        if not key or key in seen:
            continue
        ftype = _TYPE.get(b.get("mode") or "text", "text")
        f = {"key": key, "label": field_label(b), "type": ftype, "page": int(b.get("page", 0) or 0)}
        if ftype == "title":       # 인쇄된 제목 — 입력 페이지에서는 쪽 머리글로만 보인다
            value = str((b.get("anchor") or {}).get("label") or "").strip() or re.sub(r"^P\d+_", "", key)
            if re.sub(r"\s*\(\d+\)$", "", value).strip() in _PLACEHOLDER:   # 이름 없는 제목 박스('새 항목')는 머리글로 쓸 게 없다
                continue
            f["value"] = value
        seen.add(key)
        if ftype == "table":
            cols = [str(c).strip() for c in (b.get("columns") or []) if str(c).strip()]
            f["columns"] = cols or ["값"]
        fields.append(f)
    if not any(f["type"] != "title" for f in fields):
        raise FormsError("템플릿에 입력할 항목(박스)이 없습니다. 템플릿 디자이너에서 박스를 지정해 저장하세요.")
    return {"title": (title or name).strip() or name, "template": name, "gps": bool(gps),
            "fields": fields, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ---------------------------------------------------------------- 오토다타 웹(클라우드) 호출

USER_AGENT = "AutoData-helper"      # 클라우드플레어가 파이썬 기본 UA(Python-urllib)를 봇으로 막는다(403, error code 1010)


class CloudClient:
    def __init__(self, origin: str, publish_key: str = "", timeout: float = 30.0, user_agent: str = USER_AGENT):
        self.origin = origin.rstrip("/")
        self.publish_key = publish_key
        self.timeout = timeout
        self.user_agent = user_agent or USER_AGENT

    def _request(self, method: str, path: str, body=None, headers: dict | None = None) -> tuple[int, str, bytes]:
        data = None
        h = {"accept": "application/json", "user-agent": self.user_agent, **(headers or {})}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h["content-type"] = "application/json"
        req = urllib.request.Request(self.origin + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.headers.get("content-type", ""), r.read()
        except urllib.error.HTTPError as e:
            payload = e.read()
            try:
                msg = json.loads(payload.decode("utf-8")).get("error") or f"오토다타 웹 오류 {e.code}"
            except Exception:  # noqa: BLE001
                msg = f"오토다타 웹 오류 {e.code}"
            raise FormsError(str(msg), e.code) from None
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            raise FormsError(f"오토다타 웹({self.origin})에 연결할 수 없습니다 — 인터넷 연결을 확인하세요. ({reason})") from None

    def _json(self, method: str, path: str, body=None, headers: dict | None = None) -> dict:
        _, _, payload = self._request(method, path, body, headers)
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise FormsError("오토다타 웹의 응답을 읽을 수 없습니다(서버 주소가 맞는지 확인하세요).") from None

    def create(self, definition: dict) -> dict:
        h = {"x-publish-key": self.publish_key} if self.publish_key else {}
        return self._json("POST", "/api/forms", {"definition": definition}, h)

    def entries(self, form_id: str, admin_key: str, since: int = 0) -> dict:
        return self._json("GET", f"/api/forms/{form_id}/entries?since={int(since)}",
                          headers={"x-admin-key": admin_key})

    def photo(self, form_id: str, admin_key: str, entry_id: str, field: str) -> tuple[str, bytes]:
        _, ct, payload = self._request("GET", f"/api/forms/{form_id}/photos/{entry_id}/{urllib.parse.quote(field)}",
                                       headers={"x-admin-key": admin_key})
        return ct.split(";")[0].strip(), payload

    def set_closed(self, form_id: str, admin_key: str, closed: bool) -> dict:
        return self._json("POST", f"/api/forms/{form_id}/{'close' if closed else 'open'}",
                          headers={"x-admin-key": admin_key})

    def delete(self, form_id: str, admin_key: str) -> dict:
        try:
            return self._json("DELETE", f"/api/forms/{form_id}", headers={"x-admin-key": admin_key})
        except FormsError as e:
            if e.code == 404:            # 이미 없음 — 지운 것과 같다
                return {"ok": True, "already_gone": True}
            raise


# ---------------------------------------------------------------- 이 PC의 양식 목록·기록 보관

class FormRegistry:
    """data/forms.json(목록) + data/forms/<id>/(스냅숏·기록·사진)."""

    def __init__(self, path, root):
        self.path = Path(path)
        self.root = Path(root)
        self._forms: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._forms = [f for f in raw.get("forms", []) if isinstance(f, dict) and valid_id(str(f.get("id", "")))]
        except (OSError, ValueError):
            self._forms = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.path, json.dumps({"forms": self._forms}, ensure_ascii=False, indent=1))

    def list(self) -> list[dict]:
        return [dict(f) for f in self._forms]

    def get(self, form_id: str) -> dict | None:
        return next((dict(f) for f in self._forms if f["id"] == form_id), None)

    def add(self, form: dict) -> None:
        self._forms.insert(0, dict(form))
        self._save()

    def update(self, form_id: str, **changes) -> dict | None:
        for f in self._forms:
            if f["id"] == form_id:
                f.update(changes)
                self._save()
                return dict(f)
        return None

    def remove(self, form_id: str) -> None:
        self._forms = [f for f in self._forms if f["id"] != form_id]
        self._save()
        shutil.rmtree(self.root / form_id, ignore_errors=True)

    def folder(self, form_id: str) -> Path:
        p = self.root / form_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def snapshot_path(self, form_id: str) -> Path:
        return self.root / form_id / "template.json"

    def template_pdf(self, form_id: str) -> Path | None:
        p = self.root / form_id / "template.pdf"
        return p if p.exists() else None

    def load_snapshot(self, form_id: str) -> dict:
        try:
            return json.loads(self.snapshot_path(form_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def load_entries(self, form_id: str) -> list[dict]:
        try:
            return json.loads((self.root / form_id / "entries.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def save_entries(self, form_id: str, entries: list[dict]) -> None:
        _atomic_write(self.folder(form_id) / "entries.json", json.dumps(entries, ensure_ascii=False, indent=1))

    def photo_path(self, form_id: str, entry_id: str, field: str, mime: str = "image/jpeg") -> Path:
        d = self.folder(form_id) / "photos"
        d.mkdir(exist_ok=True)
        return d / f"{entry_id}__{_UNSAFE.sub('_', field)[:40]}{_EXT.get(mime, '.jpg')}"


def _atomic_write(path: Path, text: str) -> None:
    """임시 파일에 쓴 뒤 바꿔치기 — 화면이 5초마다 가져오는 동안 내보내기가 같은 파일을 읽어도 반쯤 쓰인 파일을 보지 않게."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def public_dto(form: dict) -> dict:
    """화면에 주는 정보 — 관리 키는 빼고(가져오기 권한은 이 PC 안에서만)."""
    return {k: v for k, v in form.items() if k != "admin_key"}


# ---------------------------------------------------------------- 만들기 · 가져오기

def publish(registry: FormRegistry, client: CloudClient, name: str, boxes: list[dict],
            template_pdf: str | Path | None, *, title: str = "", gps: bool = False) -> dict:
    boxes = dedup_boxes(boxes)
    definition = build_definition(name, boxes, title=title, gps=gps)
    r = client.create(definition)
    if not all(r.get(k) for k in ("id", "write_key", "admin_key", "share_url")) or not valid_id(str(r["id"])):
        raise FormsError("오토다타 웹의 응답이 올바르지 않습니다(서버가 아직 새 버전이 아닐 수 있습니다).")
    form = {"id": r["id"], "title": definition["title"], "template": name, "gps": bool(gps),
            "origin": client.origin, "share_url": r["share_url"], "write_key": r["write_key"],
            "admin_key": r["admin_key"], "created": definition["created"], "closed": False,
            "count": 0, "last_seq": 0, "synced": "", "definition": definition,
            "has_pdf": bool(template_pdf and Path(template_pdf).exists())}
    folder = registry.folder(form["id"])
    (folder / "template.json").write_text(
        json.dumps({"name": name, "boxes": boxes, "definition": definition}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    if form["has_pdf"]:
        shutil.copyfile(template_pdf, folder / "template.pdf")
    registry.save_entries(form["id"], [])
    registry.add(form)
    return public_dto(form)


def sync(registry: FormRegistry, client: CloudClient, form_id: str) -> dict:
    """아직 안 받은 기록(seq > last_seq)과 그 사진을 받아 이 PC에 보탠다. 반환: 새 기록 수·전체 수·닫힘 여부."""
    form = registry.get(form_id)
    if not form:
        raise FormsError("없는 양식입니다.")
    entries = registry.load_entries(form_id)
    known = {e["id"] for e in entries}
    last = int(form.get("last_seq") or 0)
    new = 0
    closed = bool(form.get("closed"))
    while True:
        r = client.entries(form_id, form["admin_key"], since=last)
        closed = bool(r.get("closed"))
        batch = r.get("entries") or []
        for e in batch:
            last = max(last, int(e.get("seq") or 0))
            if e.get("id") in known or not _ENTRY_ID.match(str(e.get("id") or "")):
                continue
            rec = {"seq": int(e.get("seq") or 0), "id": e["id"], "created": str(e.get("created") or ""),
                   "received": str(e.get("received") or ""), "client_id": str(e.get("client_id") or ""),
                   "values": e.get("values") if isinstance(e.get("values"), dict) else {},
                   "meta": e.get("meta") if isinstance(e.get("meta"), dict) else {}, "photos": {}}
            for p in e.get("photos") or []:
                field = str(p.get("field") or "")
                try:
                    ct, data = client.photo(form_id, form["admin_key"], e["id"], field)
                    path = registry.photo_path(form_id, e["id"], field, p.get("mime") or ct)
                    path.write_bytes(data)
                    rec["photos"][field] = "photos/" + path.name
                except FormsError:
                    rec["photos"][field] = ""          # 사진만 못 받음 — 기록은 보관
            entries.append(rec)
            known.add(e["id"])
            new += 1
        if len(batch) < PAGE:
            break
    if new:
        entries.sort(key=lambda z: z.get("seq", 0))
        registry.save_entries(form_id, entries)
    registry.update(form_id, last_seq=last, count=len(entries), closed=closed,
                    synced=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return {"new": new, "total": len(entries), "closed": closed}


def set_closed(registry: FormRegistry, client: CloudClient, form_id: str, closed: bool) -> dict:
    form = registry.get(form_id)
    if not form:
        raise FormsError("없는 양식입니다.")
    client.set_closed(form_id, form["admin_key"], closed)
    return public_dto(registry.update(form_id, closed=closed) or form)


def delete(registry: FormRegistry, client: CloudClient, form_id: str) -> None:
    """웹의 양식·기록을 지우고 이 PC의 보관 폴더도 지운다(내보낸 엑셀·PDF 는 output 에 남음)."""
    form = registry.get(form_id)
    if not form:
        raise FormsError("없는 양식입니다.")
    client.delete(form_id, form["admin_key"])
    registry.remove(form_id)


# ---------------------------------------------------------------- 내보내기

def local_time(iso: str) -> str:
    """웹이 준 UTC 시각 → 이 PC 시간대의 'YYYY-MM-DD HH:MM'."""
    try:
        s = str(iso).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError):
        return str(iso or "")


def _photo_file(registry: FormRegistry, form_id: str, entry: dict, field: str) -> str | None:
    rel = (entry.get("photos") or {}).get(field)
    if not rel:
        return None
    p = registry.root / form_id / rel
    return str(p) if p.exists() else None


def entry_rows(registry: FormRegistry, form_id: str, definition: dict,
               entries: list[dict]) -> tuple[list[str], list[dict], list[str]]:
    """기록 → 엑셀 행. 표(여러 행) 값은 일괄 처리와 같은 방식으로 줄마다 한 행으로 펼친다."""
    from core.table_rows import TABLE_MARK, explode_rows
    from core.template.writer import IMG_PREFIX

    gps = bool(definition.get("gps"))
    base = ["기록일시"] + (["위도", "경도", "위치오차m"] if gps else [])
    fields = base + [f["key"] for f in definition.get("fields", [])]
    num_fields = ["위도", "경도", "위치오차m"] if gps else []
    num_fields += [f["key"] for f in definition.get("fields", []) if f.get("type") == "number"]
    out_fields: list[str] = []
    rows: list[dict] = []
    for e in entries:
        values = e.get("values") or {}
        row: dict = {"_파일명": f"기록 {e.get('seq', '')}", "기록일시": local_time(e.get("created", ""))}
        if gps:
            g = (e.get("meta") or {}).get("gps") or {}
            row["위도"] = "" if g.get("lat") is None else str(g["lat"])
            row["경도"] = "" if g.get("lon") is None else str(g["lon"])
            row["위치오차m"] = "" if g.get("acc") is None else str(g["acc"])
        for f in definition.get("fields", []):
            k, t = f["key"], f.get("type")
            v = values.get(k)
            if t == "title":
                row[k] = f.get("value", "")
            elif t == "check":
                row[k] = f.get("label", k) if v is True or str(v).lower() in ("true", "1") else ""
            elif t == "image":
                p = _photo_file(registry, form_id, e, k)
                row[k] = (IMG_PREFIX + p) if p else ""
            elif t == "table":
                cols = list(f.get("columns") or ["값"])
                trs = [{c: _text(r.get(c)) for c in cols} for r in (v or []) if isinstance(r, dict)]
                row[k] = {TABLE_MARK: True, "columns": cols, "rows": trs}
            else:
                row[k] = _text(v)
        exploded, ef = explode_rows(row, fields)
        for x in exploded[1:]:                     # 표 줄마다 펼친 행 — 사진은 첫 행에만(파일이 커지지 않게)
            for k, v in list(x.items()):
                if isinstance(v, str) and v.startswith(IMG_PREFIX):
                    x[k] = ""
        for x in ef:
            if x not in out_fields:
                out_fields.append(x)
        rows.extend(exploded)
    return out_fields or list(fields), rows, num_fields


def _text(v) -> str:
    if v is None or v is False:
        return ""
    if v is True:
        return "√"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def export_excel(registry: FormRegistry, form_id: str, out_path: str | Path) -> str:
    from core.template.writer import write_bundle_excel
    form = registry.get(form_id)
    if not form:
        raise FormsError("없는 양식입니다.")
    definition = form.get("definition") or registry.load_snapshot(form_id).get("definition") or {}
    entries = registry.load_entries(form_id)
    fields, rows, nums = entry_rows(registry, form_id, definition, entries)
    write_bundle_excel([{"label": form.get("title") or "디지털입력", "fields": fields, "rows": rows,
                         "num_fields": nums}], str(out_path), first_col="기록")
    return str(out_path)


def export_pdf(registry: FormRegistry, form_id: str, out_path: str | Path, entry_id: str | None = None) -> dict:
    """기록마다 양식 한 벌씩 채운 현장조사표 PDF. entry_id 를 주면 그 기록 하나만."""
    from core.form_fill import fill_pdf
    form = registry.get(form_id)
    if not form:
        raise FormsError("없는 양식입니다.")
    tpl_pdf = registry.template_pdf(form_id)
    if tpl_pdf is None:
        raise FormsError("이 양식에는 함께 저장된 양식 PDF 가 없어 조사표 PDF 를 만들 수 없습니다 — "
                         "템플릿 디자이너에서 양식 PDF 를 연 채로 템플릿을 저장한 뒤 양식을 다시 만드세요. (엑셀은 됩니다)")
    snap = registry.load_snapshot(form_id)
    boxes = snap.get("boxes") or []
    entries = registry.load_entries(form_id)
    if entry_id:
        entries = [e for e in entries if e.get("id") == entry_id]
    if not entries:
        raise FormsError("아직 받은 기록이 없습니다.")
    return fill_pdf(str(tpl_pdf), boxes, entries, str(out_path),
                    photo_path=lambda e, field: _photo_file(registry, form_id, e, field),
                    gps=bool(form.get("gps")))


def qr_svg(url: str) -> str:
    """공유 링크 QR(SVG 문자열) — 현장 조사자가 휴대전화 카메라로 찍어 연다."""
    import io as _io
    import segno
    buf = _io.BytesIO()          # svg_inline 은 xmlns 를 빼므로 <img src> 로는 안 그려진다 — 온전한 문서로
    segno.make(url, error="m").save(buf, kind="svg", scale=6, border=2, dark="#1e2126", xmldecl=False, svgns=True)
    return buf.getvalue().decode("utf-8")


def safe_name(s: str) -> str:
    return _UNSAFE.sub("_", str(s or "")).strip("_")[:40] or "양식"
