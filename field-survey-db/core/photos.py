"""사진 경계 찾기 — 조사표의 사진 칸을 사진 테두리에 맞춰 자르고, 사진만 모은 쪽의 사진·설명을 꺼낸다.

· 글자 PDF(한글 변환 등): 사진이 별도 그림으로 박혀 있어 그림 위치가 곧 경계.
· 스캔 PDF: 사진이 쪽 그림의 일부 → 쪽을 렌더해
    ① 엄격한 기준(뚜렷이 어둡거나 색 있음)으로 사진 '핵심'을 찾아 이웃 사진끼리 붙지 않게 하고
    ② 민감한 기준(종이보다 조금이라도 어둡거나 옅은 색)으로 핵심의 변을 한 줄씩 넓혀 옅은 하늘까지 포함.
    흰 틈·설명 줄·다른 사진을 만나면 넓히기를 멈춘다.
실측(저어새 샘플 스캔 6쪽): 사진 22장 중 21장, 설명 20장 짝지음. 템플릿의 이미지 박스로 자리를 알면
박스 둘레만 민감하게 다시 찾아 옅은 사진도 보완한다.
"""
from __future__ import annotations

import os

from core.normalize import normalize

_DPI = 100
_CACHE: dict[tuple, list[tuple[float, float, float, float]]] = {}


def _scan_like(page) -> bool:
    """쪽 전체(90% 이상)를 그림 한 장이 덮는 쪽 — 스캔(글자 레이어가 덧씌워져 있어도)."""
    pr = page.rect
    for info in page.get_images(full=True):
        for r in page.get_image_rects(info[0]):
            if r.width * r.height >= 0.9 * pr.width * pr.height:
                return True
    return False


def embedded_photo_rects(page) -> list[tuple[float, float, float, float]]:
    """글자 PDF에 박힌 그림(쪽 전체 스캔 그림·작은 아이콘 제외)의 위치(pt)."""
    pr = page.rect
    out = []
    for info in page.get_images(full=True):
        for r in page.get_image_rects(info[0]):
            if r.width * r.height >= 0.9 * pr.width * pr.height:
                continue
            if r.width >= 40 and r.height >= 30:
                out.append((r.x0, r.y0, r.x1, r.y1))
    return out


def _render(page, dpi: int, clip=None):
    import cv2
    import fitz
    import numpy as np

    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False, clip=clip)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _masks(bgr, paper: float | None = None):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    strict = ((gray < 228) | (sat > 28)).astype(np.uint8)
    blur = cv2.medianBlur(bgr, 5)                       # 스캔 잡티 제거(옅은 하늘을 종이와 가르기 위해)
    gray_b = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
    sat_b = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)[:, :, 1]
    if paper is None:
        paper = float(np.percentile(gray_b, 90))        # 쪽 대부분이 종이 → 상위 10% 밝기 ≈ 종이색
    sens = ((gray_b < paper - 10) | (sat_b > 16)).astype(np.uint8)
    return strict, sens


def _blobs(mask, dpi: int, min_area: float, min_w: float, min_h: float):
    """채워진 큰 사각형 덩어리들(px) — 작은 틈은 닫고, 5mm보다 가는 것(표 선·글자 줄)은 지운다."""
    import cv2
    import numpy as np

    k1 = max(3, int(dpi / 25))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k1, k1), np.uint8))
    k2 = max(5, int(dpi / 5))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((k2, k2), np.uint8))
    cnts, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < min_area or w < min_w or h < min_h:
            continue
        if float(mask[y:y + h, x:x + w].mean()) < 0.5 or cv2.contourArea(c) / float(w * h) < 0.8:
            continue
        out.append((x, y, x + w, y + h))
    return out


def _grow(rect, sens, cores, need: float = 0.8):
    """핵심 사각형의 변을 민감 마스크가 거의 꽉 찬(need) 줄이 이어지는 동안 넓힌다(한 변당 원래 크기만큼까지 —
    사진 위쪽 40%가 옅은 하늘인 경우도 있음). 흰 틈·설명 줄은 채움이 낮아 멈추고, 다른 사진과는 겹치지 않는다."""
    H, W = sens.shape
    x0, y0, x1, y1 = rect
    others = [c for c in cores if c != rect]

    def hits(a0, b0, a1, b1):
        return any(a0 < c[2] and a1 > c[0] and b0 < c[3] and b1 > c[1] for c in others)

    ly, lx = y1 - y0, x1 - x0
    while y0 > 0 and rect[1] - y0 < ly and sens[y0 - 1, x0:x1].mean() >= need and not hits(x0, y0 - 1, x1, y0):
        y0 -= 1
    while y1 < H and y1 - rect[3] < ly and sens[y1, x0:x1].mean() >= need and not hits(x0, y1, x1, y1 + 1):
        y1 += 1
    while x0 > 0 and rect[0] - x0 < lx and sens[y0:y1, x0 - 1].mean() >= need and not hits(x0 - 1, y0, x0, y1):
        x0 -= 1
    while x1 < W and x1 - rect[2] < lx and sens[y0:y1, x1].mean() >= need and not hits(x1, y0, x1 + 1, y1):
        x1 += 1
    return (x0, y0, x1, y1)


def detect_photo_rects(bgr, dpi: int = _DPI, min_frac: float = 0.015,
                       paper: float | None = None) -> list[tuple[int, int, int, int]]:
    """그림(px)에서 사진 사각형들(px) — 위→아래, 왼→오른쪽."""
    H, W = bgr.shape[:2]
    strict, sens = _masks(bgr, paper)
    cores = _blobs(strict, dpi, min_frac * W * H, W * 0.1, H * 0.05)
    rects = [_grow(c, sens, cores) for c in cores]
    return sorted(rects, key=lambda r: (round(r[1] / max(1, H * 0.05)), r[0]))


def page_photos(pdf_path: str, page_no: int) -> list[tuple[float, float, float, float]]:
    """쪽의 사진 위치들(pt). 그림이 하나도 없는 글자 PDF 쪽은 빈 목록."""
    import fitz

    try:
        key = (os.path.abspath(pdf_path), os.path.getmtime(pdf_path), page_no)
    except OSError:
        return []
    if key in _CACHE:
        return _CACHE[key]
    out: list[tuple[float, float, float, float]] = []
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no]
        if _scan_like(page):
            s = 72.0 / _DPI
            out = [(x0 * s, y0 * s, x1 * s, y1 * s)
                   for x0, y0, x1, y1 in detect_photo_rects(_render(page, _DPI))]
        else:
            out = embedded_photo_rects(page)
    finally:
        doc.close()
    _CACHE[key] = out
    return out


def _overlap(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def snap_photo_box(pdf_path: str, page_no: int, bb: dict) -> dict:
    """이미지 박스를 실제 사진 테두리에 맞춘다 — 박스와 가장 많이 겹치는 사진(겹침이 둘 중 작은 쪽의 30% 이상).
    쪽 전체에서 못 찾은 옅은 사진은 박스 둘레(35% 여유)만 다시 찾는다. 못 찾으면 박스 그대로."""
    box = (float(bb["x0"]), float(bb["y0"]), float(bb["x1"]), float(bb["y1"]))
    barea = (box[2] - box[0]) * (box[3] - box[1])
    if barea <= 0:
        return bb

    def best(cands):
        scored = [(c, _overlap(box, c)) for c in cands]
        scored = [(c, ov) for c, ov in scored
                  if ov >= 0.3 * min(barea, (c[2] - c[0]) * (c[3] - c[1]))]
        return max(scored, key=lambda t: t[1])[0] if scored else None

    try:
        hit = best(page_photos(pdf_path, page_no))
        if hit is None:
            hit = _search_near(pdf_path, page_no, box)
    except Exception:  # noqa: BLE001  (찾기 실패는 박스 그대로 자름)
        hit = None
    if hit is None:
        return bb
    nb = dict(bb)
    nb["x0"], nb["y0"], nb["x1"], nb["y1"] = hit
    return nb


def _search_near(pdf_path: str, page_no: int, box):
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no]
        if not _scan_like(page):
            return None
        mx, my = (box[2] - box[0]) * 0.35, (box[3] - box[1]) * 0.35
        pr = page.rect
        clip = fitz.Rect(max(0, box[0] - mx), max(0, box[1] - my), min(pr.width, box[2] + mx), min(pr.height, box[3] + my))
        full = _render(page, 40)                          # 종이색은 쪽 전체에서 잰다(창 안은 사진이 대부분)
        import cv2
        paper = float(np.percentile(cv2.cvtColor(cv2.medianBlur(full, 5), cv2.COLOR_BGR2GRAY), 90))
        img = _render(page, _DPI, clip=clip)
    finally:
        doc.close()
    H, W = img.shape[:2]
    _, sens = _masks(img, paper)
    rects = _blobs(sens, _DPI, 0.25 * W * H, W * 0.3, H * 0.3)
    if not rects:
        return None
    s = 72.0 / _DPI
    cands = [(clip.x0 + x0 * s, clip.y0 + y0 * s, clip.x0 + x1 * s, clip.y0 + y1 * s) for x0, y0, x1, y1 in rects]
    return max(cands, key=lambda c: _overlap(box, c))


def caption_below(words, rect, gap: float = 24) -> str:
    """사진 바로 아래 줄의 글 — 스캔 경계 오차로 사진 아래끝과 조금 겹쳐도 잡고, '설명'이 든 줄을 우선.
    쪽 꼬리말('NIE / 이름 / 팀 / 날짜')은 설명이 아님."""
    x0, _, x1, y1 = rect
    ws = [w for w in words if y1 - 14 <= w.y0 <= y1 + gap and x0 - 5 <= w.cx <= x1 + 5]
    rows: dict[int, list] = {}
    for w in ws:
        rows.setdefault(round(w.cy / 6), []).append(w)
    texts = [normalize(" ".join(w.text for w in sorted(rows[k], key=lambda w: w.x0))) for k in sorted(rows)]
    texts = [t for t in texts if t and "NIE" not in t]
    return next((t for t in texts if "설명" in t), texts[0] if texts else "")


def photo_page_items(pdf_path: str, page, min_photos: int = 2, min_cover: float = 0.35) -> list[dict] | None:
    """사진만 모은 쪽이면 [{rect(pt), caption}] (읽는 순서), 아니면 None.
    사진이 min_photos장 이상이고 쪽 면적의 min_cover 이상을 덮을 때."""
    rects = page_photos(pdf_path, page.page_no)
    if len(rects) < min_photos:
        return None
    cover = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects) / (page.width * page.height)
    if cover < min_cover:
        return None
    return [{"rect": r, "caption": caption_below(page.words, r)} for r in rects]
