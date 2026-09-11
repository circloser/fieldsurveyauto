"""보이지 않게 띄운 한글이 쌓이지 않게 — 이 프로그램이 띄운 한글만 끝내고, 남은 것은 다음 실행 때 정리.

실제 사례: 한글 변환 후 한글을 닫지 않아 창 없는 Hwp.exe 가 하루 사이 15개 쌓였다.
사용자가 직접 연 한글과 지금 실행 중인 다른 오토다타가 쓰는 한글은 건드리면 안 된다.
"""
import os
import sys
import types

import core.convert as conv


def _fake_env(monkeypatch, tmp_path, running: set[int], alive: set[int]):
    killed: list[int] = []
    monkeypatch.setattr(conv, "PID_FILE", tmp_path / "pids.txt")
    monkeypatch.setattr(conv, "_hwp_pids", lambda: set(running))
    monkeypatch.setattr(conv, "_alive", lambda pid: pid in alive)

    def kill(pid):
        killed.append(pid)
        running.discard(pid)
    monkeypatch.setattr(conv, "_kill", kill)
    monkeypatch.setattr(conv, "_HWP", None)
    monkeypatch.setattr(conv, "_OWN_PIDS", set())
    return killed


def test_own_hangul_killed_on_shutdown_user_hangul_kept(tmp_path, monkeypatch):
    running = {100}                                     # 100 = 사용자가 직접 연 한글
    killed = _fake_env(monkeypatch, tmp_path, running, alive={os.getpid()})

    class FakeHwp:
        def __init__(self, visible=False, new=True):
            running.add(4242)                           # 변환용 한글이 새로 뜸

        def RegisterModule(self, *a):
            pass

        def quit(self):
            pass

    monkeypatch.setitem(sys.modules, "pyhwpx", types.SimpleNamespace(Hwp=FakeHwp))
    monkeypatch.setattr(conv, "_ensure_security_module", lambda: None)

    conv._get_hwp()
    assert conv._OWN_PIDS == {4242}
    assert conv._read_entries() == [(os.getpid(), 4242)]
    conv.shutdown()
    assert killed == [4242] and 100 in running
    assert conv._read_entries() == [] and conv._HWP is None


def test_cleanup_orphans_only_for_owners_no_longer_running(tmp_path, monkeypatch):
    running = {100, 555, 666}
    killed = _fake_env(monkeypatch, tmp_path, running, alive={22222})
    conv._write_entries([(11111, 555), (22222, 666), (33333, 777)])   # 777은 이미 꺼짐
    assert conv.cleanup_orphans() == 1
    assert killed == [555]                                # 끝난 프로그램(11111)이 띄웠던 것만
    assert conv._read_entries() == [(22222, 666)]         # 실행 중인 다른 오토다타의 한글은 유지
    assert 100 in running
