"""사용 설명서 — 원고(docs/manual.md)가 HTML·한글 문서로 만들어지고, 그림·번호 설명이 짝이 맞는지."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


@pytest.fixture(scope="module")
def blocks():
    from tools.build_manual import SRC, parse
    if not SRC.exists():
        pytest.skip("docs/manual.md 없음")
    return parse(SRC.read_text(encoding="utf-8"))


def test_images_exist_and_callouts_follow_figures(blocks):
    imgs = [b for b in blocks if b.kind == "img"]
    assert imgs, "그림이 하나도 없다"
    missing = [b.src for b in imgs if not (DOCS / b.src).exists()]
    assert not missing, f"그림 파일 없음: {missing} — tools/manual_shots.py 로 만든다"
    # {{n}} 설명은 그림 바로 뒤에 1부터 빠짐없이
    for i, b in enumerate(blocks):
        if b.kind == "callouts":
            nums = [int(re.match(r"^\{\{(\d+)\}\}", t).group(1)) for t in b.items]
            assert nums == list(range(1, len(nums) + 1)), f"번호 설명이 1부터 차례가 아니다: {nums}"
            assert any(x.kind == "img" for x in blocks[max(0, i - 2):i]), f"그림 없이 번호 설명만 있다: {b.items[0][:30]}"


def test_chapters_and_internal_references(blocks):
    h2 = [b.text for b in blocks if b.kind == "h" and b.level == 2]
    assert len(h2) >= 10 and h2[0].startswith("1.") and all(re.match(r"^\d+\.", t) for t in h2)
    text = "\n".join(b.text + " " + " ".join(b.items if b.kind != "table" else [" ".join(r) for r in b.items])
                     for b in blocks)
    h3 = {m.group(1) for b in blocks if b.kind == "h" and b.level == 3 for m in [re.match(r"^(\d+\.\d+)\s", b.text)] if m}
    refs = set(re.findall(r"(\d+\.\d+)절", text))
    assert refs <= h3, f"없는 절을 가리킨다: {sorted(refs - h3)}"
    chapters = {t.split(".")[0] for t in h2}
    ch_refs = set(re.findall(r"\*\*(\d+)장", text)) | set(re.findall(r"\((\d+)장", text))
    assert ch_refs <= chapters, f"없는 장을 가리킨다: {sorted(ch_refs - chapters)}"


def test_html_and_hwpx_build(blocks, tmp_path):
    from tools.build_manual import render_html, render_hwpx
    html = render_html(blocks)
    assert "<title>오토다타 사용 설명서</title>" in html and 'class="toc"' in html
    assert html.count("<figure") == sum(1 for b in blocks if b.kind == "img")
    assert "data:image/png;base64," in html                     # 그림이 파일 안에 들어 있다
    out = render_hwpx(blocks, tmp_path / "설명서.hwpx")
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "Contents/section0.xml" in names and "Contents/header.xml" in names and "mimetype" in names
        sec = z.read("Contents/section0.xml").decode("utf-8")
        assert "hp:tbl" in sec and "hp:pic" in sec and "오토다타 사용 설명서" in sec
        assert sum(1 for n in names if n.startswith("BinData/")) == sum(1 for b in blocks if b.kind == "img")
