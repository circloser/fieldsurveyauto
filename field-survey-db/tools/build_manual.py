# -*- coding: utf-8 -*-
"""사용 설명서 만들기.

원고 docs/manual.md → docs/오토다타_사용설명서.html (그림까지 한 파일 — web/manual.html 로 복사: 웹 시작 페이지와
                                                 프로그램의 '📖 사용 설명서'(/manual)가 같은 파일을 쓴다)
                   → docs/오토다타_사용설명서.hwpx (한글 문서, 그림 포함 — core/hwpx_doc.py 로 한글 없이 생성)
그림(docs/manual_img/*.png)은 먼저 tools/manual_shots.py 로 만든다.

    python tools/build_manual.py [--no-copy] [--hwpx 경로]

원고 문법(마크다운 일부): # ## ### 제목({#id} 가능), 문단, 1. 번호 목록, - 목록, > 알림 상자(**알아두기**/**주의** 로 시작),
| 표 |, ![설명](그림), {{1}} 그림 번호 설명, **굵게**, `코드`, {정상} {주의} {불가} {참고} 상태 표시, [[메뉴 이름]]
"""
from __future__ import annotations

import argparse
import base64
import html
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import APP_VERSION  # noqa: E402
from core.hwpx_doc import HwpxWriter, Table  # noqa: E402

VERSION = APP_VERSION.split(" ")[0]
DOCS = ROOT / "docs"
SRC = DOCS / "manual.md"
OUT_HTML = DOCS / "오토다타_사용설명서.html"
OUT_HWPX = DOCS / "오토다타_사용설명서.hwpx"
COPIES = (ROOT / "web" / "manual.html",)          # 앱의 /manual 도 이 파일을 읽는다(빌드 때 static 으로 복사)
CHIP = {"정상": "ok", "주의": "warn", "불가": "fail", "참고": "info"}


# ---------------------------------------------------------------------------
# 원고 읽기
# ---------------------------------------------------------------------------
@dataclass
class Block:
    kind: str                     # h | p | ul | ol | callouts | note | table | img
    text: str = ""
    level: int = 0
    id: str = ""
    items: list = field(default_factory=list)
    src: str = ""


def parse(md: str) -> list[Block]:
    lines = md.splitlines()
    out: list[Block] = []
    para: list[str] = []

    def flush():
        if para:
            out.append(Block("p", " ".join(para)))
            para.clear()

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            flush()
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*?)(?:\s*\{#([\w-]+)\})?$", s)
        if m:
            flush()
            out.append(Block("h", m.group(2), level=len(m.group(1)), id=m.group(3) or ""))
            i += 1
            continue
        m = re.match(r"^!\[(.*)\]\(([^)]+)\)$", s)
        if m:
            flush()
            out.append(Block("img", m.group(1), src=m.group(2)))
            i += 1
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(Block("table", items=rows))
            continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(Block("note", " ".join(buf)))
            continue
        kind = ("ol" if re.match(r"^\d+\.\s", s) else "ul" if s.startswith("- ")
                else "callouts" if re.match(r"^\{\{\d+\}\}", s) else "")
        if kind:
            flush()
            items = []
            while i < len(lines):
                t = lines[i].strip()
                if kind == "ol" and re.match(r"^\d+\.\s", t):
                    items.append(re.sub(r"^\d+\.\s+", "", t))
                elif kind == "ul" and t.startswith("- "):
                    items.append(t[2:])
                elif kind == "callouts" and re.match(r"^\{\{\d+\}\}", t):
                    items.append(t)
                else:
                    break
                i += 1
            out.append(Block(kind, items=items))
            continue
        para.append(s)
        i += 1
    flush()
    return out


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def inline_html(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\{\{(\d+)\}\}", r'<span class="co">\1</span>', s)
    s = re.sub(r"\{(정상|주의|불가|참고)\}", lambda m: f'<span class="chip {CHIP[m.group(1)]}">{m.group(1)}</span>', s)
    s = re.sub(r"\[\[(.+?)\]\]", r'<span class="tab">\1</span>', s)
    return s


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600'
         '&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">')

_DARK = """--ground:#0F1512;--paper:#161D19;--ink:#E3E9E4;--ink-2:#A8B3AB;--ink-3:#82908A;--rule:#2B362F;
--accent:#8CCB6A;--accent-ink:#A9DC8C;--accent-soft:#1E2E1F;--callout:#F0679A;
--note:#1B2620;--warn:#2E211B;--warn-ink:#F2A57D;--code:#1F2A24;
--ok-bg:#1E3A1B;--ok-fg:#A3D98F;--warn-bg:#3A2F0F;--warn-fg:#EBC35E;--fail-bg:#41201A;--fail-fg:#F39C86;
--info-bg:#2A2F35;--info-fg:#BAC1C8;"""

CSS = """:root{--ground:#EEF2EC;--paper:#FFFFFF;--ink:#1E2126;--ink-2:#4A5760;--ink-3:#6E7C84;--rule:#D9E0D6;
--accent:#3F8425;--accent-ink:#2F6E18;--accent-soft:#EEF7E5;--callout:#C2255C;
--note:#EEF4EA;--warn:#FBEEE6;--warn-ink:#8C3A12;--code:#EEF2EC;
--ok-bg:#D9EFD0;--ok-fg:#2E6B1F;--warn-bg:#FFEFC0;--warn-fg:#7A5600;--fail-bg:#F8CDBF;--fail-fg:#A8321A;
--info-bg:#E3E5E8;--info-fg:#4F555B;
--sans:"IBM Plex Sans KR","Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;
--mono:"IBM Plex Mono",Consolas,"D2Coding",ui-monospace,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){%DARK%}}
:root[data-theme="dark"]{%DARK%}
*,*::before,*::after{box-sizing:border-box}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
body{margin:0;background:var(--ground);color:var(--ink);font:15.5px/1.78 var(--sans);word-break:keep-all;
overflow-wrap:anywhere;font-variant-numeric:tabular-nums;-webkit-text-size-adjust:100%}
a{color:var(--accent-ink);text-underline-offset:3px}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.shell{display:grid;grid-template-columns:268px minmax(0,1fr);max-width:1380px;margin:0 auto;min-height:100vh}
.toc{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:40px 22px 40px 30px;font-size:13.5px;line-height:1.5}
.toc .brand{font-weight:700;font-size:15px;margin:0}
.toc .ver{color:var(--ink-3);font:12px/1.5 var(--mono);margin:2px 0 24px}
.toc ol{list-style:none;margin:0;padding:0;display:grid;gap:1px}
.toc a{display:grid;grid-template-columns:2.1em 1fr;padding:6px 10px;border-radius:6px;color:var(--ink-2);text-decoration:none}
.toc a:hover{background:var(--paper);color:var(--ink)}
.toc .n{font-family:var(--mono);color:var(--accent)}
.doc{background:var(--paper);padding:60px clamp(22px,5.5vw,88px) 120px;min-width:0;border-left:1px solid var(--rule)}
.cover{margin-bottom:12px}
.cover .kicker{margin:0;color:var(--accent-ink);font-weight:600;font-size:13.5px;letter-spacing:.04em}
.cover h1{font-size:clamp(30px,4vw,42px);line-height:1.2;margin:10px 0 16px;letter-spacing:-.01em;text-wrap:balance}
.cover .lead{margin:0 0 26px;color:var(--ink-2);max-width:44rem;font-size:16.5px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:0;margin:0;max-width:56rem;
border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.meta div{padding:12px 16px 12px 0}
.meta dt{font:500 12px/1.4 var(--mono);color:var(--ink-3);letter-spacing:.03em}
.meta dd{margin:3px 0 0;font-size:14px;font-weight:500}
.doc>p,.doc>ul,.doc>ol,.doc>h2,.doc>h3,.doc>.note{max-width:46rem}
h2{font-size:25px;line-height:1.3;margin:80px 0 16px;padding-top:28px;border-top:1px solid var(--rule);display:flex;
gap:14px;align-items:baseline;text-wrap:balance;scroll-margin-top:12px}
h2 .num{font:500 17px/1 var(--mono);color:var(--accent);flex:none}
h3{font-size:18px;line-height:1.45;margin:42px 0 10px;text-wrap:balance}
h3 .num{font:500 14px/1 var(--mono);color:var(--ink-3);margin-right:10px}
p{margin:0 0 14px}
ul,ol{margin:0 0 20px;padding-left:1.4em}
li{margin:5px 0;padding-left:.2em}
ol>li::marker{font:600 .9em var(--mono);color:var(--accent)}
ul>li::marker{color:var(--ink-3)}
strong{font-weight:600}
code{font:.86em/1.4 var(--mono);background:var(--code);padding:.12em .38em;border-radius:4px;white-space:nowrap}
.tab{display:inline-block;font-weight:600;font-size:.93em;line-height:1.5;padding:0 .45em;border-radius:4px;
background:var(--accent-soft);color:var(--accent-ink);white-space:nowrap}
.chip{display:inline-block;font-weight:600;font-size:.9em;line-height:1.5;padding:0 .45em;border-radius:3px}
.chip.ok{background:var(--ok-bg);color:var(--ok-fg)}.chip.warn{background:var(--warn-bg);color:var(--warn-fg)}
.chip.fail{background:var(--fail-bg);color:var(--fail-fg)}.chip.info{background:var(--info-bg);color:var(--info-fg)}
.co{display:inline-grid;place-items:center;flex:none;width:1.55em;height:1.55em;border-radius:50%;background:var(--callout);
color:#fff;font:600 12px/1 var(--mono)}
.note{background:var(--note);border-radius:8px;padding:14px 18px;margin:18px 0 24px;font-size:14.5px}
.note b{color:var(--accent-ink);margin-right:.6em}
.note.warn{background:var(--warn)}.note.warn b{color:var(--warn-ink)}
.tbl{overflow-x:auto;margin:14px 0 28px;max-width:58rem}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.62}
th{text-align:left;font-weight:600;background:var(--accent-soft);padding:9px 14px;white-space:nowrap}
td{padding:9px 14px;border-bottom:1px solid var(--rule);vertical-align:top}
td:first-child{font-weight:500}
figure{margin:30px 0 12px;max-width:66rem}
figure img{display:block;width:100%;height:auto;border:1px solid var(--rule);border-radius:8px;background:#fff}
figure.phone img{max-width:36rem}
figcaption{font-size:13.5px;color:var(--ink-2);margin-top:10px}
.callouts{list-style:none;padding:0;margin:8px 0 34px;max-width:66rem;display:grid;
grid-template-columns:repeat(auto-fill,minmax(20rem,1fr));gap:7px 30px;font-size:14px;line-height:1.55}
.callouts li{display:flex;gap:10px;align-items:baseline;margin:0;padding:0}
.foot{margin-top:96px;padding-top:18px;border-top:1px solid var(--rule);color:var(--ink-3);font-size:13px;max-width:46rem}
@media (max-width:980px){.shell{grid-template-columns:1fr}.toc{position:static;height:auto;padding:26px 22px 10px}
.toc ol{grid-template-columns:repeat(auto-fill,minmax(15rem,1fr))}.doc{border-left:0}}
@media print{body{background:#fff}.toc{display:none}.shell{display:block}.doc{padding:0;border:0}
h2{break-before:page;border-top:0}figure,table,.note{break-inside:avoid}}
""".replace("%DARK%", _DARK)


def render_html(blocks: list[Block]) -> str:
    title = next(b.text for b in blocks if b.kind == "h" and b.level == 1)
    lead_i = next(i for i, b in enumerate(blocks) if b.kind == "p")
    toc, body = [], []
    n_img = 0
    for i, b in enumerate(blocks):
        if (b.kind == "h" and b.level == 1) or i == lead_i:
            continue
        if b.kind == "h" and b.level == 2:
            m = re.match(r"^(\d+)\.\s*(.*)$", b.text)
            num, text = (m.group(1), m.group(2)) if m else ("", b.text)
            hid = b.id or f"ch{len(toc) + 1}"
            toc.append(f'<li><a href="#{hid}"><span class="n">{num}</span><span>{inline_html(text)}</span></a></li>')
            body.append(f'<h2 id="{hid}"><span class="num">{num}</span><span>{inline_html(text)}</span></h2>')
        elif b.kind == "h":
            m = re.match(r"^(\d+\.\d+)\s+(.*)$", b.text)
            inner = (f'<span class="num">{m.group(1)}</span>{inline_html(m.group(2))}' if m else inline_html(b.text))
            body.append(f"<h3>{inner}</h3>")
        elif b.kind == "p":
            body.append(f"<p>{inline_html(b.text)}</p>")
        elif b.kind in ("ul", "ol"):
            body.append(f"<{b.kind}>" + "".join(f"<li>{inline_html(t)}</li>" for t in b.items) + f"</{b.kind}>")
        elif b.kind == "callouts":
            lis = []
            for t in b.items:
                m = re.match(r"^\{\{(\d+)\}\}\s*(.*)$", t)
                lis.append(f'<li><span class="co">{m.group(1)}</span><span>{inline_html(m.group(2))}</span></li>')
            body.append(f'<ol class="callouts">{"".join(lis)}</ol>')
        elif b.kind == "note":
            m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", b.text)
            label, text = (m.group(1), m.group(2)) if m else ("알아두기", b.text)
            cls = "note warn" if label == "주의" else "note"
            body.append(f'<aside class="{cls}"><b>{html.escape(label)}</b>{inline_html(text)}</aside>')
        elif b.kind == "table":
            head, *rows = b.items
            th = "".join(f"<th>{inline_html(c)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline_html(c)}</td>" for c in r) + "</tr>" for r in rows)
            body.append(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
        elif b.kind == "img":
            n_img += 1
            data = base64.b64encode((DOCS / b.src).read_bytes()).decode("ascii")
            alt = re.sub(r"\[\[|\]\]", "", b.text)
            cls = ' class="phone"' if "phone" in b.src else ""
            body.append(f'<figure{cls}><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'
                        f"<figcaption>그림 {n_img}. {inline_html(b.text)}</figcaption></figure>")
    cover = (f'<header class="cover"><p class="kicker">오토다타 (AutoData) — 현장 조사 데이터 자동 DB화</p>'
             f'<h1>{html.escape(title)}</h1>'
             f'<p class="lead">{inline_html(blocks[lead_i].text)}</p><dl class="meta">'
             f'<div><dt>프로그램</dt><dd>오토다타 도우미 {VERSION}</dd></div>'
             f'<div><dt>웹 시작 페이지</dt><dd>autodata.singlena.workers.dev</dd></div>'
             f'<div><dt>필요 환경</dt><dd>Windows 10·11 (64비트)</dd></div>'
             f'<div><dt>설명서 작성</dt><dd>{date.today():%Y. %m. %d.}</dd></div></dl></header>')
    nav = (f'<nav class="toc" aria-label="차례"><p class="brand">{html.escape(title)}</p>'
           f'<p class="ver">오토다타 {VERSION}</p><ol>{"".join(toc)}</ol></nav>')
    foot = ('<footer class="foot">이 설명서는 프로그램 소스의 <code>docs/manual.md</code> 원고를 '
            '<code>tools/build_manual.py</code>로 변환해 만들었습니다. 한글 문서판은 <code>오토다타_사용설명서.hwpx</code>입니다. '
            '그림의 장소·이름·수치는 모두 지어낸 예제입니다.</footer>')
    main = f'<div class="shell">{nav}<main class="doc">{cover}{"".join(body)}{foot}</main></div>'
    head = f"<title>{html.escape(title)}</title>\n{FONTS}\n<style>\n{CSS}</style>"
    return (f'<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n{head}\n</head>\n'
            f"<body>\n{main}\n</body>\n</html>\n")


# ---------------------------------------------------------------------------
# 한글(hwpx)
# ---------------------------------------------------------------------------
_EMOJI = re.compile("[🀀-🫿️]")     # 한글 글꼴에 없는 그림문자(📖 📲 …)는 한글 문서에서 뺀다


def plain(s: str) -> str:
    s = _EMOJI.sub("", s).replace("  ", " ").strip()
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\{\{(\d+)\}\}", r"[\1]", s)
    s = re.sub(r"\{(정상|주의|불가|참고)\}", r"“\1”", s)
    s = re.sub(r"\[\[(.+?)\]\]", r"「\1」", s)
    return s


def segments(s: str) -> list[tuple[str, bool]]:
    parts = re.split(r"(\*\*.+?\*\*)", plain(s))
    return [(p[2:-2], True) if p.startswith("**") and p.endswith("**") else (p, False) for p in parts if p]


def render_hwpx(blocks: list[Block], out: Path) -> Path:
    title = next(b.text for b in blocks if b.kind == "h" and b.level == 1)
    lead_i = next(i for i, b in enumerate(blocks) if b.kind == "p")
    w = HwpxWriter(title)
    w.para(f"오토다타 도우미 {VERSION} · 현장 조사 데이터 자동 DB화 · {date.today():%Y. %m. %d.}", "caption")
    w.rich(segments(blocks[lead_i].text))
    w.heading("차례", 1)
    for b in blocks:
        if b.kind == "h" and b.level == 2:
            w.rich([(plain(b.text), False)])
    n_img = 0
    for i, b in enumerate(blocks):
        if (b.kind == "h" and b.level == 1) or i == lead_i:
            continue
        if b.kind == "h":
            w.heading(plain(b.text).replace("**", ""), 1 if b.level == 2 else 2, page_break=b.level == 2)
        elif b.kind == "p":
            w.rich(segments(b.text))
        elif b.kind == "ul":
            for t in b.items:
                w.rich([("• ", False)] + segments(t))
        elif b.kind == "ol":
            for k, t in enumerate(b.items, 1):
                w.rich([(f"{k}. ", True)] + segments(t))
        elif b.kind == "callouts":
            for t in b.items:
                m = re.match(r"^\{\{(\d+)\}\}\s*(.*)$", t)
                w.rich([(f"[{m.group(1)}] ", True)] + segments(m.group(2)))
        elif b.kind == "note":
            w.table(Table(header=[], body=[[plain(b.text).replace("**", "").strip()]], widths=[1.0], kind="box"))
        elif b.kind == "table":
            head, *rows = [[plain(c).replace("**", "") for c in r] for r in b.items]
            ncol = len(head)
            weights = [max(4, min(40, max(len(r[c]) for r in [head] + rows if c < len(r)))) for c in range(ncol)]
            w.table(Table(header=[head], body=rows, widths=weights, kind="text"))
        elif b.kind == "img":
            n_img += 1
            w.image(DOCS / b.src, 90 if "phone" in b.src else 160)
            w.para(f"그림 {n_img}. {plain(b.text)}", "caption")
    return w.save(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="사용 설명서(HTML·hwpx) 만들기")
    ap.add_argument("--no-copy", action="store_true", help="web/manual.html 에 복사하지 않음")
    ap.add_argument("--hwpx", default=None, help="한글 문서를 이 경로에 저장(기본 docs/오토다타_사용설명서.hwpx)")
    a = ap.parse_args(argv)
    blocks = parse(SRC.read_text(encoding="utf-8"))
    missing = [b.src for b in blocks if b.kind == "img" and not (DOCS / b.src).exists()]
    if missing:
        raise SystemExit("그림 파일이 없습니다. 먼저 python tools/manual_shots.py 를 실행하세요: " + ", ".join(missing))
    OUT_HTML.write_text(render_html(blocks), encoding="utf-8")
    hwpx = Path(a.hwpx) if a.hwpx else OUT_HWPX
    render_hwpx(blocks, hwpx)
    print(f"HTML: {OUT_HTML} ({OUT_HTML.stat().st_size // 1024} KB)")
    print(f"한글: {hwpx} ({hwpx.stat().st_size // 1024} KB)")
    if not a.no_copy:
        for dst in COPIES:
            shutil.copyfile(OUT_HTML, dst)
            print(f"복사: {dst}")


if __name__ == "__main__":
    main()
