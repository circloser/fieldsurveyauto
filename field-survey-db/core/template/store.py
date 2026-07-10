"""템플릿 저장소 — 사용자가 만든 추출 템플릿을 JSON으로 영속화."""
from __future__ import annotations

import json
from pathlib import Path


class TemplateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
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

    def save(self, name: str, boxes: list[dict]) -> None:
        self._data[name] = {"name": name, "boxes": boxes}
        self._save()

    def get(self, name: str) -> dict | None:
        return self._data.get(name)

    def list_names(self) -> list[str]:
        return list(self._data.keys())

    def delete(self, name: str) -> None:
        self._data.pop(name, None)
        self._save()
