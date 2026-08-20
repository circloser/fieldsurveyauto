"""회차 누적 저장소 — AI 자동추출 결과를 세션(회차)을 넘어 양식별로 축적한다.

각 행은 core.bundle.group_rows 가 이해하는 형태로 저장한다:
  {"_파일명": key, "form": form, "form_title": title, "label": label, "values": {..}}
→ 다운로드 시 group_rows 로 양식별 시트를 만든다. 같은 _파일명(파일 pN) 키는
재추가/검수수정 시 갱신되어 중복 누적을 막는다.
"""
from __future__ import annotations

import json
from pathlib import Path


class AccumulateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._rows: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._rows = data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                self._rows = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, rows: list[dict]) -> int:
        """행들을 누적. _파일명 키가 이미 있으면 갱신(중복 방지). 새로 추가된 행 수 반환."""
        index = {r.get("_파일명"): i for i, r in enumerate(self._rows)}
        added = 0
        for r in rows:
            key = r.get("_파일명")
            if key in index:
                self._rows[index[key]] = r
            else:
                index[key] = len(self._rows)
                self._rows.append(r)
                added += 1
        self._save()
        return added

    def all(self) -> list[dict]:
        return list(self._rows)

    def count(self) -> int:
        return len(self._rows)

    def label_counts(self) -> dict[str, int]:
        """양식(label)별 누적 행 수 — 상태 표시용."""
        out: dict[str, int] = {}
        for r in self._rows:
            lbl = (r.get("label") or r.get("form_title") or r.get("form") or "기타")
            out[lbl] = out.get(lbl, 0) + 1
        return out

    def reset(self) -> None:
        self._rows = []
        self._save()
