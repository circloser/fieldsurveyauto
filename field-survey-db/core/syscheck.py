"""배포용 시스템 점검 — 이 PC에서 프로그램이 제대로 돌아갈 조건을 항목별로 확인한다.

항목마다 상태(ok/warn/fail/info)와 설명, 해결 방법을 돌려준다.
· ok   : 정상
· warn : 동작은 하지만 일부 기능·속도에 제약(예: 한글 미설치 → hwpx 변환 불가)
· fail : 이대로는 쓸 수 없음(예: data 폴더에 쓰기 불가)
· info : 참고 정보(예: GPU 없음 → CPU 처리)
quick=True 면 오래 걸리는 OCR 엔진 로드는 건너뛴다(시작 배너용).
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

HWP_DOWNLOAD = "https://www.hancom.com/cs_center/csDownload.do"


@dataclass
class Item:
    id: str
    name: str
    status: str       # ok | warn | fail | info
    detail: str
    fix: str = ""


def hwp_installed() -> bool:
    """한글(HWP) 설치 여부 — COM ProgID 레지스트리로 빠르게 확인(한글 실행 안 함)."""
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "HWPFrame.HwpObject"))
        return True
    except OSError:
        return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _writable(d: Path) -> tuple[bool, str]:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / f".write_test_{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, ""
    except OSError as e:
        return False, str(e)


def _check_os() -> Item:
    sysname = platform.system()
    if sysname != "Windows":
        return Item("os", "운영체제", "warn", f"{sysname} {platform.release()}",
                    "Windows 10/11(64비트)에서 검증된 프로그램입니다. 한글(hwpx) 변환은 Windows에서만 됩니다.")
    is64 = platform.machine().lower() in ("amd64", "x86_64", "arm64")
    try:
        build = int(platform.version().split(".")[-1])
    except ValueError:
        build = 0
    rel = "11" if build >= 22000 else platform.release()   # Windows 11도 release()는 '10'으로 나옴
    label = f"Windows {rel} (빌드 {platform.version()}) · {'64비트' if is64 else '32비트'}"
    if not is64:
        return Item("os", "운영체제", "fail", label, "64비트 Windows가 필요합니다.")
    if build and build < 17763:
        return Item("os", "운영체제", "warn", label, "Windows 10 1809 이상을 권장합니다.")
    return Item("os", "운영체제", "ok", label)


def _check_cpu(p: dict) -> Item:
    n = p["logical_cores"]
    label = f"{p['cpu']} · {n}스레드"
    if n < 4:
        return Item("cpu", "CPU", "warn", label, "4스레드 이상을 권장합니다(스캔 문서 인식이 느릴 수 있음).")
    return Item("cpu", "CPU", "ok", label)


def _check_ram(p: dict) -> Item:
    total, avail = p["ram_total_gb"], p["ram_avail_gb"]
    label = f"전체 {total}GB · 사용 가능 {avail}GB"
    if total and total < 4:
        return Item("ram", "메모리(RAM)", "fail", label, "4GB 이상이 필요합니다.")
    if total and total < 8:
        return Item("ram", "메모리(RAM)", "warn", label, "8GB 이상을 권장합니다(스캔 문서 여러 장 처리 시).")
    return Item("ram", "메모리(RAM)", "ok", label)


def _check_disk(base: Path) -> Item:
    try:
        u = shutil.disk_usage(str(base))
        free = round(u.free / 1024 ** 3, 1)
    except OSError as e:
        return Item("disk", "디스크 여유 공간", "warn", f"확인 실패: {e}")
    label = f"{base.drive or str(base)} 여유 {free}GB"
    if free < 0.5:
        return Item("disk", "디스크 여유 공간", "fail", label, "0.5GB 미만 — 작업 파일을 만들 수 없습니다. 공간을 확보하세요.")
    if free < 2:
        return Item("disk", "디스크 여유 공간", "warn", label, "2GB 이상을 권장합니다(변환 PDF·엑셀이 data 폴더에 쌓임).")
    return Item("disk", "디스크 여유 공간", "ok", label)


def _check_gpu(p: dict) -> Item:
    t = p["torch"]
    names = ", ".join(p["gpus"]) if p["gpus"] else "없음"
    if t["cuda_available"]:
        return Item("gpu", "GPU 가속", "ok", f"{t['device']} — 글자 인식(OCR) GPU 처리")
    if p["nvidia"]:
        g = p["nvidia"][0]
        return Item("gpu", "GPU 가속", "info",
                    f"{g['name']} {g['vram_gb']}GB 감지(드라이버 {g['driver']}) — 현재 CPU 처리판",
                    "GPU판(FieldSurveyDB_GPU 배포본)을 쓰면 스캔 문서 글자 인식이 5~10배 빨라집니다. "
                    "NVIDIA 드라이버 580 이상 필요.")
    if not t["installed"]:
        return Item("gpu", "GPU 가속", "info", f"GPU: {names} — 경량판(OCR 없음)")
    return Item("gpu", "GPU 가속", "info", f"GPU: {names} — NVIDIA GPU가 없어 CPU {t['threads']}스레드로 처리")


def _check_hwp() -> Item:
    if hwp_installed():
        return Item("hwp", "한글(HWP)", "ok", "설치됨 — hwpx 파일 변환 가능")
    return Item("hwp", "한글(HWP)", "warn", "없음 — hwpx 파일은 변환할 수 없음(PDF 파일은 그대로 사용 가능)",
                f"hwpx도 쓰려면 한글을 설치하세요: {HWP_DOWNLOAD} — 또는 한글에서 [PDF로 저장]한 뒤 PDF를 올리세요.")


def _check_browser() -> Item:
    try:
        import webbrowser
        b = webbrowser.get()
        name = getattr(b, "name", "") or type(b).__name__
        return Item("browser", "웹 브라우저", "ok", f"기본 브라우저 사용 가능({name})")
    except Exception:  # noqa: BLE001
        return Item("browser", "웹 브라우저", "warn", "기본 브라우저를 찾지 못함",
                    "프로그램 창에 표시되는 주소(http://127.0.0.1:포트)를 브라우저에 직접 입력하세요.")


def _check_port(port: int) -> Item:
    if _port_free(port):
        return Item("port", "네트워크 포트", "ok", f"{port} 사용 가능(이 컴퓨터 안에서만 통신)")
    return Item("port", "네트워크 포트", "info", f"{port} 사용 중 — 시작 시 다음 빈 포트를 자동으로 씀",
                "프로그램이 이미 켜져 있는지 확인하세요(두 번 켜도 문제없음).")


def _check_write(data_dir: Path) -> Item:
    ok, err = _writable(data_dir)
    if ok:
        return Item("write", "작업 폴더 쓰기", "ok", f"{data_dir} 쓰기 가능")
    return Item("write", "작업 폴더 쓰기", "fail", f"{data_dir} 쓰기 불가({err})",
                "프로그램 폴더를 '문서'나 바탕화면 등 쓰기 가능한 곳으로 옮기세요(Program Files·네트워크 드라이브 X).")


def _check_import(mod: str, id_: str, name: str, what: str) -> Item:
    try:
        __import__(mod)
        return Item(id_, name, "ok", f"{what} 사용 가능")
    except Exception as e:  # noqa: BLE001
        return Item(id_, name, "fail", f"{what} 모듈 없음({e})", "배포 폴더가 손상됐을 수 있습니다. zip을 다시 풀어 주세요.")


def _check_ocr(p: dict) -> Item:
    try:
        from core import ocr
        t0 = time.time()
        ok = ocr.available()
        dt = time.time() - t0
    except Exception as e:  # noqa: BLE001
        return Item("ocr", "글자 인식(OCR)", "fail", f"엔진 로드 실패({e})", "OCR 포함 배포판을 사용하세요.")
    if not ok:
        return Item("ocr", "글자 인식(OCR)", "warn", "엔진 없음 — 스캔·사진 PDF는 처리 불가(글자 있는 PDF는 가능)",
                    "스캔 문서도 처리하려면 OCR 포함 배포판(기본판)을 사용하세요.")
    dev = "GPU" if p["torch"]["cuda_available"] else "CPU"
    return Item("ocr", "글자 인식(OCR)", "ok",
                f"EasyOCR(한국어·영어) 로드 {dt:.1f}초 · {dev} 처리 · 인터넷 불필요")


def _check_ai() -> Item:
    try:
        from app import config
        keys = {"claude": config.CLAUDE_API_KEY, "openai": config.OPENAI_API_KEY,
                "gemini": config.GEMINI_API_KEY}
        if keys.get(config.AI_PROVIDER) or config.PROXY_BASE_URL:
            return Item("ai", "AI 기능(선택)", "ok", f"설정됨 — 제공자 {config.AI_PROVIDER}")
        return Item("ai", "AI 기능(선택)", "info", "미설정 — 템플릿 디자이너 등 기본 기능은 AI 없이 동작",
                    "AI 자동 추출을 쓰려면 환경설정에서 API 키를 넣으세요.")
    except Exception as e:  # noqa: BLE001
        return Item("ai", "AI 기능(선택)", "info", f"확인 불가({e})")


def run_checks(quick: bool = False) -> dict:
    """전체 점검 실행 → {overall, counts, items, profile, ...}. quick=True 면 OCR 로드 생략."""
    from app import config
    from core import perf

    p = perf.profile()
    base = config.BASE_DIR
    items = [
        _check_os(),
        _check_cpu(p),
        _check_ram(p),
        _check_disk(base),
        _check_gpu(p),
        _check_hwp(),
        _check_browser(),
        _check_port(config.DEFAULT_PORT),
        _check_write(config.DATA_DIR),
        _check_import("fitz", "pdf", "PDF 엔진", "PDF 읽기·변환"),
        _check_import("openpyxl", "excel", "엑셀 출력", "엑셀(xlsx) 쓰기"),
    ]
    if not quick:
        items.append(_check_ocr(p))
    items.append(_check_ai())
    counts = {"ok": 0, "warn": 0, "fail": 0, "info": 0}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    overall = "fail" if counts["fail"] else ("warn" if counts["warn"] else "ok")
    return {
        "overall": overall,
        "counts": counts,
        "items": [asdict(i) for i in items],
        "profile": p,
        "quick": quick,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app_version": getattr(config, "APP_VERSION", ""),
        "base_dir": str(base),
        "frozen": bool(getattr(sys, "frozen", False)),
    }


_MARK = {"ok": "[정상]", "warn": "[주의]", "fail": "[불가]", "info": "[참고]"}
_OVERALL = {"ok": "모든 항목 정상 — 바로 사용할 수 있습니다.",
            "warn": "동작하지만 일부 기능·속도에 제약이 있습니다(주의 항목 참고).",
            "fail": "이대로는 사용할 수 없는 항목이 있습니다(불가 항목을 먼저 해결하세요)."}


def report_text(result: dict) -> str:
    """사람이 읽고 복사해 전달할 수 있는 점검 결과 텍스트(IT 담당자 문의용)."""
    p = result["profile"]
    lines = [
        "오토다타 (AutoData) 시스템 점검 결과",
        f"점검 시각: {result['checked_at']} · 버전 {result['app_version']} · "
        f"{'포터블(exe)' if result['frozen'] else '개발 실행'}",
        f"설치 위치: {result['base_dir']}",
        f"종합: {_OVERALL[result['overall']]}",
        "",
    ]
    for it in result["items"]:
        lines.append(f"{_MARK[it['status']]} {it['name']}: {it['detail']}")
        if it["fix"] and it["status"] != "ok":
            lines.append(f"        → {it['fix']}")
    lines += ["",
              f"CPU: {p['cpu']} ({p['logical_cores']}스레드) · RAM {p['ram_total_gb']}GB · "
              f"GPU: {', '.join(p['gpus']) or '없음'}",
              f"처리 방식: {p['advice']}"]
    return "\n".join(lines)
