"""OCR 엔진 로드는 한 번만, 그리고 로드 중 요청은 기다린다.

잠금이 없으면 로드(수~십 초) 중에 들어온 두 번째 요청이 '엔진 없음'으로 보고 OCR을 건너뛴다
— 스캔 문서의 칸 글자가 비어 항목명이 '칸'으로 나오는 증상. 실제 엔진 없이 재현·검증한다.
"""
import threading
import time

from core import ocr


def _reset(monkeypatch, load_seconds: float):
    """엔진 로드를 '느리게 성공하는 가짜'로 바꾸고 상태를 초기화."""
    monkeypatch.setattr(ocr, "_TRIED", False, raising=False)
    monkeypatch.setattr(ocr, "_ENGINE", None, raising=False)
    monkeypatch.setattr(ocr, "_ENGINE_KIND", None, raising=False)
    monkeypatch.setattr(ocr, "_LOCK", threading.Lock(), raising=False)
    calls: list[float] = []

    def fake_locked():
        calls.append(time.time())
        time.sleep(load_seconds)          # 느린 로드(모델 읽기) 흉내
        ocr._ENGINE = "fake"
        ocr._ENGINE_KIND = "easyocr"
        ocr._TRIED = True
        return "easyocr"

    monkeypatch.setattr(ocr, "_load_engine_locked", fake_locked)
    return calls


def test_concurrent_available_waits_for_load(monkeypatch):
    """로드 중에 available()을 부른 스레드도 True를 받고, 로드는 한 번만 실행된다."""
    calls = _reset(monkeypatch, load_seconds=0.4)
    results: list[bool] = []

    def worker():
        results.append(ocr.available())

    ts = [threading.Thread(target=worker) for _ in range(5)]
    for t in ts:
        t.start()
        time.sleep(0.05)      # 첫 스레드가 로드하는 중에 나머지가 들어오게
    for t in ts:
        t.join(timeout=10)

    assert results == [True] * 5      # 로드 중에 들어온 요청도 '엔진 있음'
    assert len(calls) == 1            # 로드는 한 번만


def test_failed_load_is_not_retried(monkeypatch):
    """엔진이 정말 없으면 False 를 돌려주고, 매번 다시 시도하지 않는다(느린 재시도 방지)."""
    monkeypatch.setattr(ocr, "_TRIED", False, raising=False)
    monkeypatch.setattr(ocr, "_ENGINE_KIND", None, raising=False)
    monkeypatch.setattr(ocr, "_LOCK", threading.Lock(), raising=False)
    calls: list[int] = []

    def fake_locked():
        calls.append(1)
        ocr._ENGINE_KIND = None
        ocr._TRIED = True
        return None

    monkeypatch.setattr(ocr, "_load_engine_locked", fake_locked)
    assert ocr.available() is False
    assert ocr.available() is False
    assert len(calls) == 1
