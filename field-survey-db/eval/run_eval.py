"""정확도 평가 실행기 — 골드셋 각 항목을 Vision으로 추출해 정답과 비교, 정확도 리포트.

사용(프록시 설정 후):
  .venv/Scripts/python.exe eval/run_eval.py

골드셋: eval/gold/*.json  (형식은 eval/README.md 참고)
결과:   콘솔 표 + eval/REPORT.md
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import vision_extract  # noqa: E402
from core.eval_score import aggregate, score_record  # noqa: E402
from core.extraction.form_detector import FORM_LABELS_KO  # noqa: E402
from core.extraction.schema.vision_schemas import vision_schema  # noqa: E402

GOLD_DIR = ROOT / "eval" / "gold"
REPORT = ROOT / "eval" / "REPORT.md"


def _load_gold() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLD_DIR.glob("*.json"))]


def main() -> int:
    ok, msg = vision_extract.available()
    if not ok:
        print("❌ Vision 사용 불가:", msg)
        return 1

    gold = _load_gold()
    if not gold:
        print(f"골드셋이 비었습니다: {GOLD_DIR} 에 *.json 을 추가하세요 (eval/README.md 참고).")
        return 1

    rows, results, by_form = [], [], {}
    unverified = 0
    for g in gold:
        if not g.get("verified", False):
            unverified += 1
        schema, hint = vision_schema(g["form"])
        if schema is None:
            print(f"⚠ 스키마 없는 서식 건너뜀: {g['form']} ({g['file']})")
            continue
        pdf = str(ROOT / g["file"])
        pred = vision_extract.extract_page(pdf, int(g.get("page", 0)), schema, hint)
        r = score_record(g["values"], pred, numeric_tol=float(g.get("numeric_tol", 0.0)))
        results.append(r)
        by_form.setdefault(g["form"], []).append(r)
        rows.append((g["file"], g["form"], r))
        tag = "" if g.get("verified") else "  (미검증 골드)"
        print(f"• {Path(g['file']).name} [{g['form']}] {r.correct}/{r.total} = {r.accuracy:.1%}{tag}")
        for fld, gv, pv in r.mismatches:
            print(f"    ✗ {fld}: 정답 '{gv}' ≠ 추출 '{pv}'")

    overall = aggregate(results)
    print(f"\n=== 전체 정확도: {overall.correct}/{overall.total} = {overall.accuracy:.1%} ===")
    for form, rs in by_form.items():
        a = aggregate(rs)
        print(f"  - {FORM_LABELS_KO.get(form, form)}: {a.accuracy:.1%} ({a.correct}/{a.total})")
    if unverified:
        print(f"\n⚠ 미검증 골드 {unverified}건 포함 — 사람이 정답을 확인해야 정확도가 신뢰됩니다.")

    _write_report(rows, overall, by_form, unverified)
    print(f"\n리포트 저장: {REPORT}")
    return 0


def _write_report(rows, overall, by_form, unverified) -> None:
    lines = ["# 정확도 평가 리포트", ""]
    lines.append(f"**전체 정확도: {overall.accuracy:.1%}** ({overall.correct}/{overall.total})")
    if unverified:
        lines.append(f"> ⚠ 미검증 골드 {unverified}건 포함 — 잠정 수치")
    lines += ["", "## 서식별", ""]
    for form, rs in by_form.items():
        a = aggregate(rs)
        lines.append(f"- {FORM_LABELS_KO.get(form, form)}: {a.accuracy:.1%} ({a.correct}/{a.total})")
    lines += ["", "## 파일별", "", "| 파일 | 서식 | 정확도 |", "|---|---|---|"]
    for f, form, r in rows:
        lines.append(f"| {Path(f).name} | {form} | {r.accuracy:.1%} ({r.correct}/{r.total}) |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
