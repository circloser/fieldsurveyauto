"""pytest 공통 설정 — 프로젝트 루트를 import 경로에 추가."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "tests" / "fixtures" / "sample.hwpx"


@pytest.fixture(scope="session")
def sample_hwpx() -> Path:
    if not FIXTURE.exists():
        pytest.skip(
            f"샘플 파일이 없습니다: {FIXTURE}\n"
            "조사표 hwpx 하나를 이 경로에 sample.hwpx 로 복사하면 테스트가 실행됩니다."
        )
    return FIXTURE
