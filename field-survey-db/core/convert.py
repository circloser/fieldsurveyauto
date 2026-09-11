"""hwpx → PDF 변환 (한글/pyhwpx 사용).

한글 인스턴스를 재사용해 여러 파일을 빠르게 변환한다(첫 실행만 느림).
한글이 없거나 실패하면 명확한 오류를 던진다.

보이지 않게 띄운 한글(visible=False)은 파이썬이 끝나도 스스로 닫히지 않는다(실측: 하루에 15개 누적).
그래서 이 프로그램이 띄운 한글만 '(띄운 프로그램 번호, 한글 번호)'로 파일에 적어 두고
  · 정상 종료 때(atexit) 그 한글을 끝내고
  · 창을 닫아 강제로 끝난 경우는 다음 실행 때(cleanup_orphans) 띄운 프로그램이 이미 없는 것만 정리한다.
사용자가 직접 연 한글, 지금 실행 중인 다른 오토다타가 쓰는 한글은 건드리지 않는다.
"""
from __future__ import annotations

import atexit
import csv
import os
import subprocess
import tempfile
from pathlib import Path

_HWP = None  # 재사용 한글 인스턴스
_OWN_PIDS: set[int] = set()  # 이 프로세스가 띄운 한글 프로세스 번호
PID_FILE = Path(tempfile.gettempdir()) / "autodata_hwp_pids.txt"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _tasklist(filter_expr: str) -> list[list[str]]:
    try:
        out = subprocess.run(["tasklist", "/FI", filter_expr, "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, errors="replace", timeout=15,
                             creationflags=_NO_WINDOW).stdout
    except Exception:  # noqa: BLE001
        return []
    return [row for row in csv.reader(out.splitlines()) if len(row) > 1]


def _hwp_pids() -> set[int]:
    """지금 떠 있는 한글(Hwp.exe) 프로세스 번호들."""
    return {int(r[1]) for r in _tasklist("IMAGENAME eq Hwp.exe")
            if r[0].lower() == "hwp.exe" and r[1].strip().isdigit()}


def _alive(pid: int) -> bool:
    rows = _tasklist(f"PID eq {pid}")
    return any(r[1].strip() == str(pid) for r in rows)


def _kill(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=15,
                       creationflags=_NO_WINDOW)
    except Exception:  # noqa: BLE001
        pass


def _read_entries() -> list[tuple[int, int]]:
    try:
        lines = PID_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        parts = ln.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            out.append((int(parts[0]), int(parts[1])))
    return out


def _write_entries(entries: list[tuple[int, int]]) -> None:
    try:
        if entries:
            PID_FILE.write_text("\n".join(f"{o} {p}" for o, p in entries), encoding="utf-8")
        elif PID_FILE.exists():
            PID_FILE.unlink()
    except OSError:
        pass


def cleanup_orphans() -> int:
    """지난 실행이 강제로 끝나 남은, 이 프로그램이 띄웠던 한글을 끈다. 반환: 끈 개수."""
    entries = _read_entries()
    if not entries:
        return 0
    running = _hwp_pids()
    keep: list[tuple[int, int]] = []
    killed = 0
    for owner, pid in entries:
        if owner != os.getpid() and _alive(owner):
            keep.append((owner, pid))       # 지금 실행 중인 다른 오토다타가 쓰는 한글
            continue
        if pid in running and pid not in _OWN_PIDS:
            _kill(pid)
            killed += 1
    _write_entries(keep + [(o, p) for o, p in entries if o == os.getpid() and p in _OWN_PIDS])
    return killed


def _kill_own() -> None:
    """이 프로세스가 띄운 한글을 끝낸다(COM을 쓰지 않아 어느 스레드·종료 단계에서도 안전)."""
    if not _OWN_PIDS:
        return
    running = _hwp_pids()
    for pid in list(_OWN_PIDS):
        if pid in running:
            _kill(pid)
    _write_entries([(o, p) for o, p in _read_entries() if p not in _OWN_PIDS])
    _OWN_PIDS.clear()


atexit.register(_kill_own)


def _ensure_security_module() -> None:
    """한글 보안승인모듈을 레지스트리에 직접 등록.

    pyhwpx의 자동 등록(register_regedit)은 내부적으로 `pip show`를 실행하는데,
    start.bat 실행 환경에서 pip 경로 문제로 'location' 오류가 나며 실패한다.
    미리 레지스트리 키를 넣어두면 pyhwpx가 그 버그 경로를 건너뛴다.
    """
    try:
        import winreg

        import pyhwpx
        dll = os.path.join(os.path.dirname(pyhwpx.__file__), "FilePathCheckerModule.dll")
        if not os.path.exists(dll):
            return
        # check_registry_key 가 확인하는 경로에 값 등록
        for path in (r"Software\HNC\HwpAutomation\Modules",
                     r"Software\Hnc\HwpUserAction\Modules"):
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, "FilePathCheckerModule", 0, winreg.REG_SZ, dll)
                winreg.CloseKey(key)
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass  # 등록 실패해도 진행(경고만)


def _get_hwp():
    global _HWP
    if _HWP is not None:
        return _HWP
    try:
        from pyhwpx import Hwp
    except ImportError as e:
        raise RuntimeError(
            "한글 자동화 라이브러리(pyhwpx)가 없습니다. hwpx 변환에는 한글(HWP)과 pyhwpx가 필요합니다."
        ) from e
    _ensure_security_module()  # 버그 회피: 보안모듈 레지스트리 선등록
    before = _hwp_pids()
    try:
        _HWP = Hwp(visible=False, new=True)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"한글을 시작할 수 없습니다(한글 설치 필요): {e}") from e
    started = _hwp_pids() - before
    if started:
        _OWN_PIDS.update(started)
        _write_entries(_read_entries() + [(os.getpid(), p) for p in sorted(started)])
    # 보안 승인 모듈을 COM으로 명시 등록. 이걸 안 하면 파일 열기/저장 때 숨겨진
    # '보안 승인' 대화상자가 떠서 프로그램이 멈춘다(visible=False라 안 보임).
    try:
        _HWP.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:  # noqa: BLE001
        pass
    return _HWP


def hwpx_to_pdf(src: str, out_pdf: str) -> str:
    """hwpx(또는 hwp)를 PDF로 변환하고 경로를 반환."""
    src = os.path.abspath(src)
    out_pdf = os.path.abspath(out_pdf)
    Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(out_pdf):
        os.remove(out_pdf)
    hwp = _get_hwp()
    hwp.open(src)
    hwp.save_as(out_pdf, "PDF")
    if not os.path.exists(out_pdf):
        raise RuntimeError("PDF 변환에 실패했습니다.")
    return out_pdf


def shutdown() -> None:
    """한글 인스턴스 종료(배치 끝·프로그램 종료). 한글이 응답하지 않아도 이 프로그램이 띄운 한글은 끝낸다."""
    global _HWP
    if _HWP is not None:
        try:
            _HWP.quit()
        except Exception:  # noqa: BLE001
            pass
        _HWP = None
    _kill_own()
