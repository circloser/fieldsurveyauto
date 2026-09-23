# -*- mode: python ; coding: utf-8 -*-
"""경량 포터블 빌드 스펙 — 글자 인식(OCR) 엔진을 넣지 않은 작은 도우미(웹 시작 페이지의 기본 내려받기).

빌드:  .venv\\Scripts\\python.exe scripts\\make_portable.py --lite
결과:  dist/FieldSurveyDB/  (이 폴더를 통째로 복사해서 FieldSurveyDB.exe 더블클릭)
전제:  대상 PC에 '한글(HWP)' 설치(hwpx 변환용). PDF만 쓰면 한글 없어도 됨.
OCR:   torch·EasyOCR 은 넣지 않는다 — 스캔 문서를 처음 쓸 때 공개 저장소에서 받아 붙인다(core/ocr_runtime.py).
       받은 패키지가 함께 쓰는 numpy·OpenCV·Pillow 는 통째로, 표준 라이브러리는 전부 넣는다
       (분석으로 안 보이는 모듈이 빠져 있으면 받은 torch 가 불러오다 멈춘다).
"""
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("static", "static"), ("web/manual.html", "static")]   # 사용 설명서(/manual)
binaries = []
hiddenimports = []

# 동적 임포트가 많은 패키지들은 통째로 수집(누락 방지). pyhwpx는 보안모듈 DLL 포함.
for pkg in ("uvicorn", "anthropic", "pdfplumber", "pdfminer", "pyhwpx", "fitz", "pymupdf",
            "numpy", "cv2", "PIL", "fontTools"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("uvicorn")
# 한글 COM 자동화(win32) — 지연 임포트라 명시 필요
hiddenimports += [
    "win32com", "win32com.client", "win32timezone",
    "pythoncom", "pywintypes", "win32api", "win32con",
    "win32crypt",   # DPAPI 키 암호화(settings_store, 지연 임포트)
    "httpx",        # 멀티 AI 제공자(ai_providers) REST 호출
    "segno",        # 디지털 입력 양식 공유 링크 QR(core/forms, 지연 임포트)
]

# 표준 라이브러리 전체(테스트·GUI·유닉스 전용 제외) — 내려받은 torch·scikit-image 등이 쓰는 모듈 대비
_STDLIB_SKIP = {
    "antigravity", "this", "idlelib", "tkinter", "turtle", "turtledemo", "test", "lib2to3", "ensurepip",
    "venv", "pydoc_data", "curses", "readline", "tty", "pty", "termios", "fcntl", "grp", "pwd", "posix",
    "resource", "syslog", "nis", "spwd", "crypt", "ossaudiodev", "_tkinter", "_curses", "_curses_panel",
    "_posixsubprocess", "_posixshmem", "_scproxy", "_gdbm", "_dbm", "_crypt",
}
for _m in sorted(set(sys.stdlib_module_names) - _STDLIB_SKIP):
    try:
        hiddenimports += collect_submodules(_m, filter=lambda n: ".test" not in n and "idle_test" not in n)
    except Exception:
        hiddenimports.append(_m)

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 글자 인식 기능(필요할 때 내려받음) — 일부만 들어가면 받은 패키지를 가려 오류가 난다
        "easyocr", "torch", "torchvision", "torchaudio", "scipy", "skimage", "shapely", "pyclipper",
        "sympy", "mpmath", "networkx", "imageio", "tifffile", "lazy_loader", "ninja", "bidi",
        "rapidocr_onnxruntime", "onnxruntime",
        "matplotlib", "IPython", "notebook",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FieldSurveyDB",
    console=True,          # 상태·종료안내가 보이는 콘솔 창 유지
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FieldSurveyDB",
)
