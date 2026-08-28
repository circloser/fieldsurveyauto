# -*- mode: python ; coding: utf-8 -*-
"""포터블 빌드 스펙 — 설치 없이 폴더째 복사해 실행되는 현장조사표 DB화.

빌드:  .venv\\Scripts\\python.exe -m PyInstaller --noconfirm FieldSurveyDB.spec
결과:  dist/FieldSurveyDB/  (이 폴더를 통째로 복사해서 FieldSurveyDB.exe 더블클릭)
전제:  대상 PC에 '한글(HWP)' 설치(hwpx 변환용). PDF만 쓰면 한글 없어도 됨.
제외:  OCR 스택(torch/easyocr)은 용량이 커서 제외(선택 기능이라 없어도 동작).
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("static", "static")]
binaries = []
hiddenimports = []

# 동적 임포트가 많은 패키지들은 통째로 수집(누락 방지). pyhwpx는 보안모듈 DLL 포함.
for pkg in ("uvicorn", "anthropic", "pdfplumber", "pdfminer", "pyhwpx", "fitz", "pymupdf"):
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
]

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
        "easyocr", "torch", "torchvision", "torchaudio",
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
