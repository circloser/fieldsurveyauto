"""hwpx → PDF 변환 (한글/pyhwpx 사용).

한글 인스턴스를 재사용해 여러 파일을 빠르게 변환한다(첫 실행만 느림).
한글이 없거나 실패하면 명확한 오류를 던진다.
"""
from __future__ import annotations

import os
from pathlib import Path

_HWP = None  # 재사용 한글 인스턴스


def _ensure_security_module() -> None:
    """한글 보안승인모듈을 레지스트리에 직접 등록.

    pyhwpx의 자동 등록(register_regedit)은 내부적으로 `pip show`를 실행하는데,
    start.bat 실행 환경에서 pip 경로 문제로 'location' 오류가 나며 실패한다.
    미리 레지스트리 키를 넣어두면 pyhwpx가 그 버그 경로를 건너뛴다.
    """
    try:
        import os
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
    try:
        _HWP = Hwp(visible=False, new=True)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"한글을 시작할 수 없습니다(한글 설치 필요): {e}") from e
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
    """한글 인스턴스 종료(배치 끝날 때)."""
    global _HWP
    if _HWP is not None:
        try:
            _HWP.quit()
        except Exception:  # noqa: BLE001
            pass
        _HWP = None
