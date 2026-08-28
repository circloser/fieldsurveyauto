# -*- mode: python ; coding: utf-8 -*-
"""포터블(OCR 포함) 빌드 스펙 — 스캔(이미지) PDF 글자 인식까지 되는 큰 버전.

빌드:  .venv\\Scripts\\python.exe -m PyInstaller --noconfirm FieldSurveyDB_OCR.spec
결과:  dist/FieldSurveyDB_OCR/  (용량 큼: torch CPU + EasyOCR 한국어 모델 동봉)
- EasyOCR 모델(craft/korean)을 함께 넣어 다른 PC에서 인터넷 없이 OCR 동작.
- 기본(가벼운) 버전은 FieldSurveyDB.spec 사용.
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("static", "static")]
binaries = []
hiddenimports = []

for pkg in ("uvicorn", "anthropic", "pdfplumber", "pdfminer", "pyhwpx", "fitz", "pymupdf",
            # OCR 스택
            "easyocr", "torch", "torchvision", "cv2", "skimage", "shapely", "pyclipper"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    "win32com", "win32com.client", "win32timezone",
    "pythoncom", "pywintypes", "win32api", "win32con",
    "win32crypt",   # DPAPI 키 암호화(settings_store, 지연 임포트)
    "httpx",        # 멀티 AI 제공자(ai_providers) REST 호출
]

# EasyOCR 한국어 모델 동봉(~/.EasyOCR/model) → 오프라인 OCR
_model_dir = os.path.expanduser(r"~\.EasyOCR\model")
if os.path.isdir(_model_dir):
    for f in os.listdir(_model_dir):
        if f.endswith(".pth"):
            datas.append((os.path.join(_model_dir, f), "easyocr_models"))

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FieldSurveyDB_OCR",
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FieldSurveyDB_OCR",
)
