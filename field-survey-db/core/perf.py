"""실행 성능 프로필 — 이 PC의 CPU·RAM·GPU를 감지해 가장 빠른 처리 방식을 고른다.

- GPU(NVIDIA, CUDA)가 있고 동봉된 torch가 CUDA 빌드면 글자 인식(OCR)을 GPU로 돌린다(5~10배 빠름).
- 아니면 CPU 스레드를 모두 써서 처리한다.
- 결과는 한 번만 계산해 캐시하고, 시작 배너·시스템 점검 화면에서 같은 값을 보여준다.
"""
from __future__ import annotations

import functools
import os
import platform
import subprocess


def _run(cmd: list[str], timeout: float = 6.0) -> str:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=flags, encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""


def _nvidia_gpus() -> list[dict]:
    """nvidia-smi 로 NVIDIA GPU 목록 → [{name, vram_gb, driver}]. 드라이버 없으면 []."""
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0]:
            try:
                vram = round(float(parts[1]) / 1024, 1)
            except ValueError:
                vram = 0.0
            gpus.append({"name": parts[0], "vram_gb": vram,
                         "driver": parts[2] if len(parts) > 2 else ""})
    return gpus


def _all_gpu_names() -> list[str]:
    """내장 그래픽 포함 모든 GPU 이름(Windows WMI). 실패하면 []."""
    if platform.system() != "Windows":
        return []
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '|'"],
               timeout=10.0)
    return [n.strip() for n in out.strip().split("|") if n.strip()]


def _cpu_name() -> str:
    if platform.system() == "Windows":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            try:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
            finally:
                winreg.CloseKey(k)
        except OSError:
            pass
    return platform.processor() or "알 수 없음"


def ram_gb() -> tuple[float, float]:
    """(전체 GB, 사용 가능 GB). 못 구하면 (0, 0)."""
    if platform.system() == "Windows":
        try:
            import ctypes

            class _Mem(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _Mem()
            m.dwLength = ctypes.sizeof(_Mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.ullTotalPhys / 1024 ** 3, 1), round(m.ullAvailPhys / 1024 ** 3, 1)
        except Exception:  # noqa: BLE001
            return 0.0, 0.0
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return round(total / 1024 ** 3, 1), 0.0
    except (ValueError, OSError, AttributeError):
        return 0.0, 0.0


def _torch_info() -> dict:
    try:
        import torch
    except Exception:  # noqa: BLE001
        return {"installed": False, "version": "", "cuda_build": "", "cuda_available": False,
                "device": "", "threads": 0}
    avail = False
    device = ""
    try:
        avail = bool(torch.cuda.is_available())
        if avail:
            device = torch.cuda.get_device_name(0)
    except Exception:  # noqa: BLE001
        avail = False
    return {"installed": True, "version": torch.__version__,
            "cuda_build": torch.version.cuda or "", "cuda_available": avail,
            "device": device, "threads": int(torch.get_num_threads())}


@functools.lru_cache(maxsize=1)
def profile() -> dict:
    """이 PC의 성능 프로필(한 번만 계산)."""
    total, avail = ram_gb()
    nvidia = _nvidia_gpus()
    torch = _torch_info()
    names = _all_gpu_names() or [g["name"] for g in nvidia]
    mode = "gpu" if torch["cuda_available"] else "cpu"
    logical = os.cpu_count() or 1
    if mode == "gpu":
        advice = f"GPU 가속 사용 중({torch['device']}) — 스캔 문서 글자 인식이 GPU에서 처리됩니다."
    elif nvidia:
        advice = (f"NVIDIA GPU({nvidia[0]['name']})가 있지만 이 배포판은 CPU 처리판입니다. "
                  "GPU판(FieldSurveyDB_GPU)을 쓰면 스캔 문서 글자 인식이 5~10배 빨라집니다.")
    elif torch["installed"]:
        advice = f"NVIDIA GPU가 없어 CPU {torch['threads']}스레드로 처리합니다(GPU 가속 불가)."
    else:
        advice = "글자 인식(OCR) 엔진이 없는 경량판입니다(스캔 문서는 처리 불가)."
    rel = platform.release()
    try:   # Windows 11도 release()는 '10' — 빌드 번호(22000↑)로 구분
        if platform.system() == "Windows" and int(platform.version().split(".")[-1]) >= 22000:
            rel = "11"
    except ValueError:
        pass
    return {
        "os": f"{platform.system()} {rel} ({platform.version()})",
        "arch": platform.machine(),
        "cpu": _cpu_name(),
        "logical_cores": logical,
        "ram_total_gb": total,
        "ram_avail_gb": avail,
        "gpus": names,
        "nvidia": nvidia,
        "torch": torch,
        "mode": mode,
        "advice": advice,
    }


def use_gpu() -> bool:
    """글자 인식(OCR)을 GPU로 돌릴 수 있는가 — CUDA 빌드 torch + NVIDIA GPU."""
    return bool(profile()["torch"]["cuda_available"])


_APPLIED = False


def apply() -> dict:
    """가장 빠른 설정을 적용(한 번만): GPU면 cuDNN 자동 튜닝, CPU면 스레드 수 확인."""
    global _APPLIED
    p = profile()
    if _APPLIED:
        return p
    _APPLIED = True
    try:
        import torch
        if p["mode"] == "gpu":
            torch.backends.cudnn.benchmark = True
        else:
            # torch 기본값은 물리 코어 수 — 0이나 1로 잡혀 있으면 논리 코어 절반 이상으로
            want = max(1, p["logical_cores"] // 2)
            if torch.get_num_threads() < want:
                torch.set_num_threads(want)
                p["torch"]["threads"] = want
    except Exception:  # noqa: BLE001
        pass
    return p


def summary_lines() -> list[str]:
    """시작 배너용 한 줄 요약들."""
    p = profile()
    lines = [f"[성능] CPU {p['logical_cores']}스레드 · RAM {p['ram_total_gb']}GB"
             + (f" · GPU {', '.join(p['gpus'])}" if p["gpus"] else " · GPU 없음")]
    if p["mode"] == "gpu":
        lines.append(f"[성능] 글자 인식(OCR): GPU 가속 — {p['torch']['device']}")
    elif p["nvidia"]:
        lines.append(f"[성능] 글자 인식(OCR): CPU 처리 — GPU({p['nvidia'][0]['name']})는 GPU판에서만 사용")
    elif p["torch"]["installed"]:
        lines.append(f"[성능] 글자 인식(OCR): CPU {p['torch']['threads']}스레드 처리")
    return lines
