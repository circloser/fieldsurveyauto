"""교정 저장소 — 사람이 고친 값을 안정 키로 보관하고 레코드에 다시 적용.

키 = (record_key, field). record_key = 파일명::보코드::서식 (R11 안정 키).
같은 파일을 다시 올려도 교정이 재적용된다. JSON 파일로 영속화.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.extraction.mapper import Record


class CorrectionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        # { record_key: { field: value } }
        self._data: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def set(self, record_key: str, field: str, value: str) -> None:
        self._data.setdefault(record_key, {})[field] = value
        self._save()

    def get(self, record_key: str) -> dict[str, str]:
        return self._data.get(record_key, {})

    def apply_to(self, records: list[Record]) -> None:
        """저장된 교정을 레코드에 반영하고, 해당 필드의 플래그를 해제."""
        for rec in records:
            corrections = self._data.get(rec.record_key)
            if not corrections:
                continue
            for field, value in corrections.items():
                rec.values[field] = value
                rec.flags.pop(field, None)  # 사람이 확인했으므로 플래그 해제
