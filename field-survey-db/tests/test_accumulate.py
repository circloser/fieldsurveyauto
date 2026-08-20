"""회차 누적 저장소 — 추가/갱신/영속/초기화 검증."""
from core.accumulate import AccumulateStore


def _row(name, title, values):
    return {"_파일명": name, "form": "unknown", "form_title": title,
            "label": title, "values": values}


def test_accumulate_add_update_persist_reset(tmp_path):
    p = tmp_path / "acc.json"
    s = AccumulateStore(p)
    assert s.count() == 0

    added = s.add([_row("a p1", "수질", {"수온": "18"})])
    assert added == 1 and s.count() == 1

    # 같은 키 재추가 → 새 행 0, 값만 갱신
    added2 = s.add([_row("a p1", "수질", {"수온": "20"})])
    assert added2 == 0 and s.count() == 1
    assert s.all()[0]["values"]["수온"] == "20"

    # 디스크 영속 — 새 인스턴스로 로드
    s2 = AccumulateStore(p)
    assert s2.count() == 1
    s2.add([_row("b p1", "토양", {"토성": "사질"})])
    assert s2.count() == 2
    assert s2.label_counts() == {"수질": 1, "토양": 1}

    s2.reset()
    assert s2.count() == 0 and AccumulateStore(p).count() == 0
