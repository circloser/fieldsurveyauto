"""SCE(수생태계 종적 연속성 평가) 연계 — 선택 기능.

기본은 꺼짐. 환경설정에서 켜고, 필요하면 SCE 프로그램 폴더를 지정한다.
· 켜져 있고 SCE를 불러올 수 있으면 → 4번 결과 화면에 SCE 내보내기 버튼이 나온다.
· 꺼져 있으면 → 버튼이 아예 보이지 않는다(SCE를 쓰지 않는 곳에 배포할 때).
불러오는 방법(순서): 지정한 폴더(sys.path 에 추가) → 설치된 패키지(import sce).
폴더를 직접 지정한 사람의 뜻이 먼저다(설치본이 낡았을 수 있으므로).
설정은 exe 옆 sce_config.json 에 평문으로 둔다(비밀이 아니고, 폴더 경로만 담는다).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULTS = {"enabled": False, "path": ""}


def load(path) -> dict:
    out = dict(DEFAULTS)
    p = Path(path)
    if not p.exists():
        return out
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    out["enabled"] = bool(raw.get("enabled"))
    out["path"] = str(raw.get("path") or "").strip()
    return out


def save(path, enabled: bool, folder: str = "") -> dict:
    data = {"enabled": bool(enabled), "path": (folder or "").strip()}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _candidates(folder: str) -> list[Path]:
    """지정 폴더에서 'sce' 패키지가 있을 만한 위치들(폴더 자체, src/, 상위)."""
    if not folder:
        return []
    base = Path(folder)
    out = [base, base / "src"]
    if base.name.lower() == "sce":     # …\sce 를 가리켰으면 그 상위가 import 경로
        out.append(base.parent)
    return [p for p in out if p.is_dir()]


def module(opts: dict) -> tuple[object | None, str]:
    """(sce.autodata_import 모듈, 오류메시지). 못 불러오면 (None, 안내문)."""
    if not opts.get("enabled"):
        return None, "SCE 연계가 꺼져 있습니다 — 환경설정에서 켜세요."
    tried: list[str] = []
    for extra in [*_candidates(opts.get("path") or ""), None]:
        if extra is not None:
            sp = str(extra.resolve())
            if sp in sys.path:
                sys.path.remove(sp)
            sys.path.insert(0, sp)
            for name in [n for n in list(sys.modules) if n == "sce" or n.startswith("sce.")]:
                del sys.modules[name]      # 앞선 시도의 절반만 불러온 흔적 제거
        try:
            from sce import autodata_import  # type: ignore
            return autodata_import, ""
        except Exception as e:  # noqa: BLE001
            tried.append(f"{extra or '설치된 패키지'}: {type(e).__name__} {e}"[:160])
    hint = ("SCE 프로그램을 찾지 못했습니다. 환경설정에서 SCE 폴더를 지정하거나, "
            "오토다타 파이썬에 설치하세요(.venv\\Scripts\\python.exe -m pip install "
            "--no-build-isolation -e <SCE 폴더>).")
    return None, hint + " 시도: " + " / ".join(tried[-2:])


def status(path) -> dict:
    """UI 표시용 — {enabled, path, available, error}."""
    opts = load(path)
    if not opts["enabled"]:
        return {"enabled": False, "path": opts["path"], "available": False, "error": ""}
    mod, err = module(opts)
    return {"enabled": True, "path": opts["path"], "available": mod is not None, "error": err}
