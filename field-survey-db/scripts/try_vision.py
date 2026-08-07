"""Vision 실호출 시험 — 프록시가 설정되면 조사표 한 페이지를 실제로 추출해 본다.

사용:
  # 프록시 설정(환경변수) 후:
  #   FIELD_SURVEY_PROXY_URL=https://...workers.dev
  #   FIELD_SURVEY_APP_TOKEN=<앱 토큰>
  .venv/Scripts/python.exe scripts/try_vision.py                 # 기본: sample.pdf, 서식 A, 0페이지
  .venv/Scripts/python.exe scripts/try_vision.py <pdf> <form> <page>

form 코드: artificial_structure(A) / fishway(C)  (현재 스키마 등록된 것)
"""
import json
import sys
from pathlib import Path

# 윈도우 cp949 콘솔에서 이모지·한글 출력이 깨지거나 크래시하지 않도록 UTF-8로 강제.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import vision_extract  # noqa: E402
from core.extraction.form_detector import FORM_A  # noqa: E402
from core.extraction.schema.vision_schemas import vision_schema  # noqa: E402


def main() -> int:
    pdf = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "tests" / "fixtures" / "sample.pdf")
    form = sys.argv[2] if len(sys.argv) > 2 else FORM_A
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    ok, msg = vision_extract.available()
    if not ok:
        print("❌ Vision 사용 불가:", msg)
        print("   → 프록시 배포 후 FIELD_SURVEY_PROXY_URL / FIELD_SURVEY_APP_TOKEN 를 설정하세요.")
        return 1

    schema, hint = vision_schema(form)
    if schema is None:
        print(f"❌ 등록된 스키마가 없는 서식: {form}")
        return 1

    print(f"▶ 입력: {pdf}  (서식={form}, 페이지={page}, 모델={vision_extract.config.VISION_MODEL})")
    print(f"▶ 추출 항목 {len(schema['properties'])}개 요청 → Vision 호출 중...\n")
    result = vision_extract.extract_page(pdf, page, schema, hint)

    filled = {k: v for k, v in result.items() if v}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n✅ 완료 — {len(filled)}/{len(schema['properties'])} 항목에 값이 채워짐.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
