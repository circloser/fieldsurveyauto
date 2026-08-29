# -*- coding: utf-8 -*-
"""오토다타 경진대회 발표 슬라이드 20장 생성기 (16:9, 1280x720).

블라인드 심사: 조직명·개인명 없음. 제품 디자인 토큰(#191F28/#3182f6/화이트) 사용.
"""
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))

HEAD = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
  <style>
    body { margin:0; font-family:'Noto Sans KR','Malgun Gothic',sans-serif; color:#191F28;
           -webkit-font-smoothing:antialiased; word-break:keep-all; }
    a { color:#3182f6; } a:hover { color:#1b64da; }
    .slide { width:1280px; height:720px; background:#ffffff; position:relative;
             box-sizing:border-box; padding:52px 64px 44px; display:flex; flex-direction:column; overflow:hidden; }
    .top { display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; }
    .sec { font-size:14px; font-weight:700; color:#8b95a1; letter-spacing:2px; }
    .chips { display:flex; gap:8px; }
    .chip { font-size:13px; font-weight:700; padding:5px 12px; border-radius:999px; }
    h1 { font-size:42px; font-weight:900; letter-spacing:-1.2px; line-height:1.25; margin:0 0 14px; }
    h1 .em { color:#3182f6; }
    .lead { font-size:19px; color:#4e5968; line-height:1.65; margin:0 0 10px; }
    .foot { margin-top:auto; padding-top:16px; border-top:1px solid #e5e8eb;
            display:flex; justify-content:space-between; font-size:12.5px; color:#8b95a1; font-weight:500; }
    .grow { flex:1; min-height:0; }
    .card { background:#ffffff; border:1px solid #e5e8eb; border-radius:14px; padding:20px 22px; box-sizing:border-box; }
    .tint { background:#f7f8fa; border:1px solid #eef1f4; }
    .ct { font-size:17px; font-weight:700; margin:10px 0 6px; }
    .cd { font-size:14px; color:#6b7684; line-height:1.6; }
    .big { font-size:44px; font-weight:900; letter-spacing:-1px; }
    .ic { width:40px; height:40px; border-radius:10px; background:#eaf3ff; display:flex; align-items:center; justify-content:center; }
    .arrow { color:#c4cad2; font-size:26px; font-weight:900; align-self:center; }
    .ph { background:#fff9e8; border:1.5px dashed #e2b93b; color:#8a6d1d; border-radius:8px;
          padding:2px 10px; font-weight:700; }
    .win { border:1px solid #dfe3e8; border-radius:12px; overflow:hidden; background:#fff;
           box-shadow:0 8px 24px rgba(25,31,40,.08); }
    .winbar { height:26px; background:#f2f4f6; display:flex; align-items:center; gap:6px; padding:0 12px; border-bottom:1px solid #e5e8eb; }
    .dot { width:8px; height:8px; border-radius:50%; }
    .note { font-size:13px; color:#8b95a1; line-height:1.55; }
  </style>
</helmet>
"""

TAIL = """</x-dc>
</body>
</html>
"""

CH = {
    "실용성": ("#eaf3ff", "#1b64da"),
    "효과성": ("#e7f9f0", "#04915a"),
    "범용성": ("#f1ecff", "#6d28d9"),
    "창의성": ("#fff4d6", "#a06f00"),
    "가점": ("#fdecee", "#d6303f"),
}


def chips(*names):
    out = []
    for n in names:
        bg, fg = CH[n]
        label = "국민 서비스 개선 · 가점" if n == "가점" else n
        out.append('<span class="chip" style="background:%s;color:%s">%s</span>' % (bg, fg, label))
    return '<div class="chips">%s</div>' % "".join(out)


def slide(no, sec, chip_html, body):
    return (HEAD
            + '<div class="slide">\n'
            + '<div class="top"><span class="sec">%s</span>%s</div>\n' % (sec, chip_html)
            + body
            + '\n<div class="foot"><span>오토다타 AutoData</span><span>%02d / 20</span></div>\n' % no
            + '</div>\n' + TAIL)


def svg(path_d, color="#3182f6", size=22):
    return ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="%s" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
            % (size, size, color, path_d))


I_DOC = '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6"></path><path d="M8 13h8M8 17h8"></path>'
I_GRID = '<rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M3 9h18M3 15h18M9 3v18M15 3v18"></path>'
I_AI = '<circle cx="12" cy="12" r="9"></circle><path d="M8 10h.01M16 10h.01"></path><path d="M8 15c1.2 1 2.6 1.5 4 1.5s2.8-.5 4-1.5"></path>'
I_SHIELD = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>'
I_CLOCK = '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 3"></path>'
I_CHECK = '<path d="M20 6L9 17l-5-5"></path>'
I_X = '<path d="M18 6L6 18M6 6l12 12"></path>'
I_PEOPLE = '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>'
I_USB = '<rect x="7" y="9" width="10" height="12" rx="2"></rect><path d="M10 9V5h4v4"></path><path d="M11 5V3h2v2"></path>'
I_WARN = '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path><path d="M12 9v4M12 17h.01"></path>'
I_UP = '<path d="M12 19V5"></path><path d="M5 12l7-7 7 7"></path>'
I_CYCLE = '<path d="M21 12a9 9 0 1 1-3-6.7"></path><path d="M21 3v6h-6"></path>'
I_LOCK = '<rect x="4" y="11" width="16" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path>'
I_SCAN = '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"></path><path d="M7 12h10"></path>'

S = {}

# ── 01 표지 ──────────────────────────────────────────────
S[1] = ("", "",
"""
<div class="grow" style="display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:0">
  <div style="display:flex;align-items:center;gap:10px;font-size:18px;font-weight:700;color:#3182f6;letter-spacing:1px">
    <span style="width:10px;height:10px;border-radius:50%;background:#3182f6;display:inline-block"></span> AutoData
  </div>
  <div style="font-size:64px;font-weight:900;letter-spacing:-2px;margin:14px 0 6px">오토다타</div>
  <div style="font-size:30px;font-weight:700;letter-spacing:-0.5px;margin-bottom:14px">현장 조사표, <span style="color:#3182f6">넣으면 엑셀이 됩니다</span></div>
  <div style="font-size:17px;color:#6b7684">수기 입력 없는 조사 데이터 DB화 · AI 자동 추출 플랫폼</div>
  <div style="display:flex;align-items:center;gap:22px;margin-top:44px">
    <div class="card tint" style="display:flex;align-items:center;gap:10px;padding:14px 20px">""" + svg(I_DOC, "#6b7684") + """<span style="font-size:15px;font-weight:700;color:#4e5968">종이·한글·PDF 조사표</span></div>
    <span class="arrow">→</span>
    <div class="card" style="display:flex;align-items:center;gap:10px;padding:14px 20px;border-color:#bcd7ff;background:#f0f6ff">""" + svg(I_AI) + """<span style="font-size:15px;font-weight:800;color:#1b64da">AI 자동 추출</span></div>
    <span class="arrow">→</span>
    <div class="card tint" style="display:flex;align-items:center;gap:10px;padding:14px 20px">""" + svg(I_GRID, "#04915a") + """<span style="font-size:15px;font-weight:700;color:#04915a">엑셀 DB · 보고서</span></div>
  </div>
</div>
""")

# ── 02 문제 공감 ─────────────────────────────────────────
S[2] = ("문제", chips("효과성"),
"""
<h1>조사보다 <span class="em">입력이 더 오래</span> 걸립니다</h1>
<p class="lead">현장에서 하루 종일 조사하고 돌아오면, 사무실에서는 조사표를 한 칸씩 엑셀로 옮겨 적는 일이 기다립니다.</p>
<div class="grow" style="display:flex;gap:28px;align-items:stretch;margin-top:8px">
  <div style="flex:1.2;display:flex;flex-direction:column;gap:12px">
    <div class="card tint" style="display:flex;gap:14px;align-items:center">""" + svg(I_DOC, "#6b7684", 26) + """<div><div class="ct" style="margin:0">조사표 1건 = 여러 쪽, 항목 수백 개</div><div class="cd">표 속에 글·숫자·좌표·체크박스가 뒤섞여 있습니다</div></div></div>
    <div class="card tint" style="display:flex;gap:14px;align-items:center">""" + svg(I_CLOCK, "#6b7684", 26) + """<div><div class="ct" style="margin:0">옮겨 적는 시간 = 조사만큼의 야근</div><div class="cd">건마다 수십 분씩, 연간 수백~수천 건이 수기로 입력됩니다</div></div></div>
    <div class="card tint" style="display:flex;gap:14px;align-items:center">""" + svg(I_WARN, "#d6303f", 26) + """<div><div class="ct" style="margin:0">옮겨 적다 생기는 오타</div><div class="cd">단순 실수가 그대로 데이터 품질 문제로 이어집니다</div></div></div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:0;position:relative">
    <div style="position:relative;width:250px;height:270px">
      <div style="position:absolute;left:26px;top:24px;width:190px;height:240px;background:#eef1f4;border:1px solid #dfe3e8;border-radius:8px;transform:rotate(6deg)"></div>
      <div style="position:absolute;left:14px;top:12px;width:190px;height:240px;background:#f5f7f9;border:1px solid #dfe3e8;border-radius:8px;transform:rotate(3deg)"></div>
      <div style="position:absolute;left:0;top:0;width:190px;height:240px;background:#fff;border:1px solid #d5dae0;border-radius:8px;padding:16px;box-sizing:border-box;box-shadow:0 10px 24px rgba(25,31,40,.10)">
        <div style="font-size:12px;font-weight:800;text-align:center;margin-bottom:10px">현장 조사표</div>
        <div style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:1px;background:#d5dae0;border:1px solid #d5dae0">
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
          <div style="background:#f2f4f6;height:18px"></div><div style="background:#fff;height:18px"></div>
        </div>
        <div style="margin-top:10px;font-size:10px;color:#8b95a1;text-align:center">× 수백 장…</div>
      </div>
    </div>
    <div class="note" style="margin-top:8px">쌓여 가는 조사표 — 전 부서가 겪는 공통 장면</div>
  </div>
</div>
""")

# ── 03 왜 어려운가 ───────────────────────────────────────
S[3] = ("문제", chips("창의성"),
"""
<h1>단순 자동화로는 <span class="em">풀리지 않던 문제</span></h1>
<p class="lead">그동안 자동화가 안 됐던 데에는 구조적인 이유가 있습니다.</p>
<div class="grow" style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:16px;margin-top:6px">
  <div class="card"><div class="ic">""" + svg(I_DOC) + """</div><div class="ct">양식이 제각각</div><div class="cd">서식 종류가 여러 가지인 데다 개정될 때마다 줄·칸이 달라져, 하나에 맞춘 규칙이 금방 깨집니다.</div></div>
  <div class="card"><div class="ic">""" + svg(I_SCAN) + """</div><div class="ct">한글·PDF·스캔 혼재</div><div class="cd">hwp/hwpx, PDF, 복사기 스캔본, 손글씨까지 — 파일마다 읽는 방법이 완전히 다릅니다.</div></div>
  <div class="card"><div class="ic">""" + svg(I_GRID) + """</div><div class="ct">표 속의 복잡한 구조</div><div class="cd">병합된 칸, 체크박스(√), 좌표(도·분·초), 굵은 글씨 구분 — 표를 이해해야 값을 꺼낼 수 있습니다.</div></div>
  <div class="card"><div class="ic">""" + svg(I_X, "#d6303f") + """</div><div class="ct">범용 OCR의 한계</div><div class="cd">일반 문자인식은 한국어 표 서식에 약해, 어느 칸의 값인지 뒤섞인 결과가 나오기 일쑤입니다.</div></div>
</div>
""")

# ── 04 해결 요약 ─────────────────────────────────────────
S[4] = ("해결", chips("실용성"),
"""
<h1>오토다타 — <span class="em">파일을 넣으면, 엑셀 DB가 됩니다</span></h1>
<div style="display:flex;align-items:center;gap:18px;margin:10px 0 20px">
  <div class="card tint" style="flex:1;text-align:center;padding:14px"><b>1. 조사표 파일 넣기</b><div class="cd">hwp·hwpx·PDF·스캔</div></div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1;text-align:center;padding:14px;border-color:#bcd7ff;background:#f0f6ff"><b style="color:#1b64da">2. AI가 읽고 검증</b><div class="cd">표·항목 자동 인식</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="flex:1;text-align:center;padding:14px"><b>3. 엑셀 DB·보고서</b><div class="cd">요약표 + 시트 분류</div></div>
</div>
<div class="grow" style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px">
  <div class="card"><div style="font-size:22px">🧩</div><div class="ct">템플릿 디자이너</div><div class="cd">반복되는 같은 양식을 대량 처리 — 추출 칸을 지정해 템플릿으로 저장, 수백 파일을 한 번에.</div></div>
  <div class="card"><div style="font-size:22px">🤖</div><div class="ct">AI 자동추출</div><div class="cd">처음 보는 양식도 AI(Vision)가 페이지를 사람처럼 읽고 서식을 판별해 자동으로 표를 만듭니다.</div></div>
  <div class="card"><div style="font-size:22px">⚙️</div><div class="ct">환경설정</div><div class="cd">Claude·ChatGPT·Gemini 중 선택, 연결 테스트까지 화면에서. AI 없이도 기본 기능은 동작.</div></div>
</div>
<div class="note" style="margin-top:14px">설치가 필요 없는 <b>포터블 프로그램</b> — USB 하나로 어느 PC에서든 더블클릭으로 실행됩니다.</div>
""")

# ── 05 데모1 디자이너 ────────────────────────────────────
S[5] = ("데모", chips("실용성"),
"""
<h1>양식을 올리면 <span class="em">추출 칸이 자동으로</span> 생깁니다</h1>
<div class="grow" style="display:flex;gap:30px;align-items:stretch;margin-top:4px">
  <div style="flex:1;display:flex;flex-direction:column;gap:12px;justify-content:center">
    <div class="card tint"><div class="ct" style="margin:0">① 표 칸마다 박스 자동 생성</div><div class="cd">사람은 필요 없는 것만 지우고 이름을 확인</div></div>
    <div class="card tint"><div class="ct" style="margin:0">② AI가 항목 이름까지 명명</div><div class="cd">"이 칸은 하천명, 이 칸은 보 길이" — 버튼 하나</div></div>
    <div class="card tint"><div class="ct" style="margin:0">③ 템플릿으로 저장</div><div class="cd">같은 양식 수백 개 파일에 재사용 · 양식 PDF도 함께 보관</div></div>
  </div>
  <div style="flex:1.15;display:flex;align-items:center">
    <div class="win" style="width:100%">
      <div class="winbar"><span class="dot" style="background:#f04452"></span><span class="dot" style="background:#f59f00"></span><span class="dot" style="background:#04b56a"></span><span style="font-size:11px;color:#8b95a1;margin-left:8px">템플릿 디자이너</span></div>
      <div style="padding:16px;background:#f7f8fa">
        <div style="position:relative;background:#fff;border:1px solid #dfe3e8;height:300px;padding:14px;box-sizing:border-box">
          <div style="position:absolute;left:90px;top:12px;width:190px;height:24px;border:2px solid #8b5cf6;background:rgba(139,92,246,.10)"></div>
          <div style="position:absolute;left:92px;top:-1px;font-size:9px;font-weight:800;background:#8b5cf6;color:#fff;padding:1px 6px;border-radius:4px">제목</div>
          <div style="text-align:center;font-weight:800;font-size:15px;margin-bottom:12px">○○ 현장 조사표</div>
          <div style="display:grid;grid-template-columns:90px 1fr 90px 1fr;gap:1px;background:#d5dae0;border:1px solid #d5dae0;position:relative">
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">하천명</div><div style="background:#fff;padding:6px"></div>
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">조사일</div><div style="background:#fff;padding:6px"></div>
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">위치(좌표)</div><div style="background:#fff;padding:6px"></div>
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">구조물 규모</div><div style="background:#fff;padding:6px"></div>
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">상태 점검</div><div style="background:#fff;padding:6px"></div>
            <div style="background:#f2f4f6;padding:6px;font-size:11px;font-weight:700">비고</div><div style="background:#fff;padding:6px"></div>
          </div>
          <div style="position:absolute;left:104px;top:64px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;left:360px;top:64px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;left:104px;top:93px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;left:360px;top:93px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;left:104px;top:122px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;left:360px;top:122px;width:150px;height:22px;border:2px solid #3182f6;background:rgba(49,130,246,.12)"></div>
          <div style="position:absolute;right:10px;bottom:8px;font-size:10px;color:#8b95a1">화면 모형 (실제 UI 동일 구성)</div>
        </div>
      </div>
    </div>
  </div>
</div>
""")

# ── 06 데모2 일괄 → 엑셀 ─────────────────────────────────
S[6] = ("데모", chips("실용성", "효과성"),
"""
<h1>수백 개 파일 → <span class="em">버튼 하나로 엑셀 완성</span></h1>
<div class="grow" style="display:flex;gap:30px;align-items:stretch;margin-top:4px">
  <div style="flex:1;display:flex;flex-direction:column;gap:12px;justify-content:center">
    <div class="card tint"><div class="ct" style="margin:0">요약 DB + 대상지별 시트 + 보고서</div><div class="cd">한 번의 처리로 필요한 산출물이 모두 생성</div></div>
    <div class="card tint"><div class="ct" style="margin:0">한 파일에 조사표 여러 묶음? 자동 인식</div><div class="cd">묶음마다 한 행씩 — 27쪽짜리 파일도 3건으로 정확히</div></div>
    <div class="card tint"><div class="ct" style="margin:0">제목(양식)별 시트 자동 분류</div><div class="cd">상단 큰 글씨를 제목으로 인식해 같은 양식끼리 묶음</div></div>
  </div>
  <div style="flex:1.15;display:flex;align-items:center">
    <div class="win" style="width:100%">
      <div class="winbar"><span class="dot" style="background:#f04452"></span><span class="dot" style="background:#f59f00"></span><span class="dot" style="background:#04b56a"></span><span style="font-size:11px;color:#8b95a1;margin-left:8px">결과 엑셀</span></div>
      <div style="padding:0;background:#fff">
        <div style="display:grid;grid-template-columns:34px repeat(4, minmax(0, 1fr));background:#f2f4f6;border-bottom:1px solid #dfe3e8;font-size:11px;font-weight:700;color:#6b7684;text-align:center">
          <div style="padding:6px 0"></div><div style="padding:6px 0">A</div><div style="padding:6px 0">B</div><div style="padding:6px 0">C</div><div style="padding:6px 0">D</div>
        </div>
        <div style="display:grid;grid-template-columns:34px repeat(4, minmax(0, 1fr));font-size:11px;border-bottom:1px solid #eef1f4;background:#191F28;color:#fff;font-weight:700">
          <div style="padding:7px 0;text-align:center;background:#f2f4f6;color:#6b7684">1</div><div style="padding:7px 8px">파일명</div><div style="padding:7px 8px">하천명</div><div style="padding:7px 8px">규모(m)</div><div style="padding:7px 8px">상태</div>
        </div>
        <div style="display:grid;grid-template-columns:34px repeat(4, minmax(0, 1fr));font-size:11px;border-bottom:1px solid #eef1f4">
          <div style="padding:7px 0;text-align:center;background:#f2f4f6;color:#6b7684">2</div><div style="padding:7px 8px">조사표A #1</div><div style="padding:7px 8px">샘플천</div><div style="padding:7px 8px">30</div><div style="padding:7px 8px">양호</div>
        </div>
        <div style="display:grid;grid-template-columns:34px repeat(4, minmax(0, 1fr));font-size:11px;border-bottom:1px solid #eef1f4">
          <div style="padding:7px 0;text-align:center;background:#f2f4f6;color:#6b7684">3</div><div style="padding:7px 8px">조사표A #2</div><div style="padding:7px 8px">예시천</div><div style="padding:7px 8px">25</div><div style="padding:7px 8px">보통</div>
        </div>
        <div style="display:grid;grid-template-columns:34px repeat(4, minmax(0, 1fr));font-size:11px;border-bottom:1px solid #eef1f4">
          <div style="padding:7px 0;text-align:center;background:#f2f4f6;color:#6b7684">4</div><div style="padding:7px 8px">조사표B</div><div style="padding:7px 8px">모형천</div><div style="padding:7px 8px">18</div><div style="padding:7px 8px">양호</div>
        </div>
        <div style="display:flex;gap:2px;background:#f2f4f6;padding:6px 8px;border-top:1px solid #dfe3e8;font-size:10.5px;font-weight:700">
          <span style="background:#fff;border:1px solid #dfe3e8;border-bottom:2px solid #04b56a;border-radius:4px 4px 0 0;padding:3px 10px">요약(DB)</span>
          <span style="background:#eef1f4;border-radius:4px 4px 0 0;padding:3px 10px;color:#6b7684">구조물 조사표</span>
          <span style="background:#eef1f4;border-radius:4px 4px 0 0;padding:3px 10px;color:#6b7684">어도 조사표</span>
          <span style="background:#eef1f4;border-radius:4px 4px 0 0;padding:3px 10px;color:#6b7684">대상지별…</span>
        </div>
      </div>
    </div>
  </div>
</div>
""")

# ── 07 유기적 추출 ───────────────────────────────────────
S[7] = ("핵심 기술 1", chips("창의성", "효과성"),
"""
<h1>양식이 변해도 정확한 <span class="em">'유기적 추출'</span></h1>
<p class="lead">좌표를 외우지 않습니다. <b>라벨(항목 이름)을 찾아 그 옆 칸을 읽기</b> 때문에, 줄이 추가되거나 표가 밀려도 값이 어긋나지 않습니다.</p>
<div class="grow" style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:20px;margin-top:6px">
  <div class="card" style="border-color:#f5c6cb">
    <div style="display:flex;align-items:center;gap:8px;font-weight:800;color:#d6303f;margin-bottom:10px">""" + svg(I_X, "#d6303f", 18) + """ 기존 좌표 방식</div>
    <div style="position:relative;background:#f7f8fa;border:1px solid #eef1f4;border-radius:8px;padding:14px">
      <div style="font-size:12px;color:#8b95a1;margin-bottom:8px">양식에 줄 1개 추가됨 ↓</div>
      <div style="display:grid;grid-template-columns:86px 1fr;gap:1px;background:#d5dae0;border:1px solid #d5dae0;font-size:12px">
        <div style="background:#fff4d6;padding:6px;font-weight:700">신규 항목</div><div style="background:#fff;padding:6px">…</div>
        <div style="background:#f2f4f6;padding:6px;font-weight:700">하천명</div><div style="background:#fff;padding:6px">샘플천</div>
        <div style="background:#f2f4f6;padding:6px;font-weight:700">규모</div><div style="background:#fff;padding:6px">30</div>
      </div>
      <div style="position:absolute;right:22px;top:44px;width:96px;height:26px;border:2px dashed #d6303f;border-radius:4px"></div>
      <div style="font-size:12.5px;color:#d6303f;font-weight:700;margin-top:10px">고정 좌표가 밀려 <u>엉뚱한 값</u>을 집음</div>
    </div>
  </div>
  <div class="card" style="border-color:#b6ebd2">
    <div style="display:flex;align-items:center;gap:8px;font-weight:800;color:#04915a;margin-bottom:10px">""" + svg(I_CHECK, "#04915a", 18) + """ 오토다타 유기적 추출</div>
    <div style="position:relative;background:#f7f8fa;border:1px solid #eef1f4;border-radius:8px;padding:14px">
      <div style="font-size:12px;color:#8b95a1;margin-bottom:8px">같은 변형 양식 ↓</div>
      <div style="display:grid;grid-template-columns:86px 1fr;gap:1px;background:#d5dae0;border:1px solid #d5dae0;font-size:12px">
        <div style="background:#fff4d6;padding:6px;font-weight:700">신규 항목</div><div style="background:#fff;padding:6px">…</div>
        <div style="background:#e7f9f0;padding:6px;font-weight:800;color:#04915a">하천명 ⌖</div><div style="background:#fff;padding:6px;outline:2px solid #04b56a;outline-offset:-2px;font-weight:700">샘플천</div>
        <div style="background:#f2f4f6;padding:6px;font-weight:700">규모</div><div style="background:#fff;padding:6px">30</div>
      </div>
      <div style="font-size:12.5px;color:#04915a;font-weight:700;margin-top:10px">라벨을 먼저 찾고 → 그 옆 칸을 읽음 = <u>항상 정확</u></div>
    </div>
  </div>
</div>
<div class="note" style="margin-top:12px">양식이 개정돼도 템플릿 재작업이 필요 없습니다 — 유지관리 비용이 구조적으로 낮습니다.</div>
""")

# ── 08 하이브리드 ────────────────────────────────────────
S[8] = ("핵심 기술 2", chips("창의성"),
"""
<h1>AI가 읽고, <span class="em">규칙이 검증하고</span>, 사람은 확인만</h1>
<p class="lead">AI를 맹신하지 않습니다. 3단 구조로 <b>믿을 수 있는 데이터</b>를 만듭니다.</p>
<div class="grow" style="display:flex;align-items:center;gap:16px;margin-top:8px">
  <div class="card" style="flex:1;border-color:#bcd7ff;background:#f0f6ff">
    <div class="ic">""" + svg(I_AI) + """</div>
    <div class="ct">① AI(Vision)가 읽기</div>
    <div class="cd">페이지를 사람처럼 통째로 읽어 서식을 판별하고 항목을 추출 — 스캔·손글씨도 처리</div>
  </div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1;border-color:#f5deA6;background:#fffbef">
    <div class="ic" style="background:#fff4d6">""" + svg(I_WARN, "#a06f00") + """</div>
    <div class="ct">② 규칙 엔진이 검증</div>
    <div class="cd">통계 기반 이상치 자동 경고(오추출 의심 값 표시) · 형식·범위 점검 · 신뢰도 낮은 값에 검수 플래그</div>
  </div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1;border-color:#b6ebd2;background:#f4fcf8">
    <div class="ic" style="background:#e7f9f0">""" + svg(I_CHECK, "#04915a") + """</div>
    <div class="ct">③ 사람은 확인만</div>
    <div class="cd">플래그된 값만 골라 검토 — 전수 검토가 아닌 표적 검수로 시간을 아끼면서 품질 확보</div>
  </div>
</div>
<div class="note" style="margin-top:14px">외부 전문가 관점에서도 안전한 구조 — <b>AI 출력이 그대로 확정되지 않고 반드시 검증층을 통과</b>합니다.</div>
""")

# ── 09 AI 보고서 초안 ────────────────────────────────────
S[9] = ("핵심 기술 3", chips("창의성"),
"""
<h1>보고서 양식도 <span class="em">AI가 초안부터</span></h1>
<p class="lead">추출 항목을 보고 AI가 보고서 양식(xlsx) 초안을 설계 — 편집해서 다시 올리면 데이터가 자동으로 채워집니다.</p>
<div class="grow" style="display:flex;align-items:center;justify-content:center;gap:14px;margin-top:6px">
  <div class="card" style="width:200px;text-align:center;border-color:#bcd7ff;background:#f0f6ff"><div class="ct" style="margin-top:0">🤖 AI 초안 설계</div><div class="cd">종합 비교표 + 대상지별 1장<br>합계·평균 수식 포함</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="width:170px;text-align:center"><div class="ct" style="margin-top:0">📥 다운로드</div><div class="cd">초안 xlsx 파일</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="width:170px;text-align:center"><div class="ct" style="margin-top:0">✏️ 엑셀에서 편집</div><div class="cd">우리 부서 양식으로<br>자유롭게 수정</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="width:170px;text-align:center"><div class="ct" style="margin-top:0">📤 재업로드</div><div class="cd">프로그램에 다시 올림</div></div>
  <span class="arrow">→</span>
  <div class="card" style="width:200px;text-align:center;border-color:#b6ebd2;background:#f4fcf8"><div class="ct" style="margin-top:0;color:#04915a">📊 데이터 자동 채움</div><div class="cd">{항목명} 자리마다<br>조사 값이 들어간 완성본</div></div>
</div>
<div class="card tint" style="margin-top:16px;display:flex;gap:12px;align-items:center">""" + svg(I_SHIELD, "#3182f6", 24) + """<div class="cd" style="color:#4e5968"><b>신뢰성 설계:</b> AI는 '설계도(JSON)'만 제안하고, 실제 엑셀 파일 조립은 프로그램이 결정적으로 수행 — <b>깨진 파일이 나올 수 없는 구조</b>이며, AI가 실수해도 자동 보정됩니다.</div></div>
""")

# ── 10 스캔·손글씨 ───────────────────────────────────────
S[10] = ("핵심 기술 4", chips("범용성"),
"""
<h1>과거의 스캔 자료까지 <span class="em">DB로 살립니다</span></h1>
<p class="lead">문서 종류마다 가장 잘 읽는 방법을 자동으로 골라 씁니다.</p>
<div class="grow" style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px;margin-top:8px">
  <div class="card"><div class="ic">""" + svg(I_DOC) + """</div><div class="ct">타이핑 문서 (hwp·hwpx·PDF)</div><div class="cd">글자를 그대로 추출 — 변환 오차 없는 <b>무손실</b> 데이터.</div></div>
  <div class="card"><div class="ic">""" + svg(I_SCAN) + """</div><div class="ct">스캔 PDF → 내장 OCR</div><div class="cd">한국어 인식 모델을 프로그램에 내장 — <b>인터넷 없이</b> 이 컴퓨터 안에서 글자를 인식.</div></div>
  <div class="card"><div class="ic">""" + svg(I_AI) + """</div><div class="ct">손글씨·복잡 서식 → AI Vision</div><div class="cd">AI가 이미지를 통째로 읽어 손글씨·비정형 기록까지 표로 변환.</div></div>
</div>
<div class="note" style="margin-top:14px">서랍 속에 잠자던 <b>과거 조사 자료(스캔본)</b>도 같은 파이프라인으로 축적 — 데이터 자산이 소급해서 늘어납니다.</div>
""")

# ── 11 효과: 시간 ────────────────────────────────────────
S[11] = ("효과", chips("효과성"),
"""
<h1>시간으로 증명합니다 <span style="font-size:20px;color:#8b95a1;font-weight:700">(발표 전 실측값 기입)</span></h1>
<div class="grow" style="display:flex;gap:26px;margin-top:8px">
  <div style="flex:1.3;display:flex;flex-direction:column;gap:14px;justify-content:center">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><b>수기 입력</b><span class="ph">실측 기입: 건당 __분</span></div>
      <div style="height:26px;background:#fdecee;border-radius:6px;margin-top:10px;position:relative"><div style="position:absolute;inset:0;width:100%;background:#f04452;border-radius:6px;opacity:.85"></div></div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><b style="color:#1b64da">오토다타</b><span class="ph">실측 기입: 건당 __초</span></div>
      <div style="height:26px;background:#eaf3ff;border-radius:6px;margin-top:10px;position:relative"><div style="position:absolute;left:0;top:0;bottom:0;width:7%;background:#3182f6;border-radius:6px"></div></div>
    </div>
    <div class="note">막대 길이는 실측값 비율로 수정 · <b>측정 방법 명시:</b> 동일 조사표 10건 표본, 수기 입력과 자동 처리를 같은 조건에서 실측</div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:14px">
    <div class="card" style="border-color:#bcd7ff;background:#f0f6ff;text-align:center">
      <div class="cd" style="margin-bottom:6px">연간 환산 (기관 실적 기준으로 기입)</div>
      <div style="font-size:19px;font-weight:800;line-height:1.7">연간 <span class="ph">__건</span> × 건당 절감 <span class="ph">__분</span></div>
      <div style="font-size:15px;color:#8b95a1;margin:6px 0">=</div>
      <div class="big" style="color:#1b64da">약 <span class="ph" style="font-size:34px">__인시</span> 절감</div>
    </div>
    <div class="note" style="text-align:center">부풀린 백분율 대신 <b>검증 가능한 절대값</b>만 제시합니다.</div>
  </div>
</div>
""")

# ── 12 효과: 품질 ────────────────────────────────────────
S[12] = ("효과", chips("효과성"),
"""
<h1>빠르기만 한 게 아니라, <span class="em">더 정확합니다</span></h1>
<div class="grow" style="display:grid;grid-template-columns:repeat(3, minmax(0, 1fr));gap:16px;margin-top:10px">
  <div class="card"><div class="ic" style="background:#e7f9f0">""" + svg(I_CHECK, "#04915a") + """</div><div class="ct">옮겨 적기 오타 원천 제거</div><div class="cd">원본 글자를 그대로 추출하므로 전산화 과정의 오타가 사라집니다.</div></div>
  <div class="card"><div class="ic" style="background:#fff4d6">""" + svg(I_WARN, "#a06f00") + """</div><div class="ct">이상치 자동 경고</div><div class="cd">같은 항목의 값 분포를 통계로 비교해, 튀는 값(오추출·오기재 의심)을 자동 표시합니다.</div>
    <div style="margin-top:10px;background:#fffbef;border:1px solid #f5dea6;border-radius:8px;padding:8px 10px;font-size:12px"><b style="color:#a06f00">⚠ 규모 349m</b> — 다른 조사표 평균 25m의 14배, 확인 필요</div></div>
  <div class="card"><div class="ic">""" + svg(I_UP) + """</div><div class="ct">쌓일수록 강해지는 DB</div><div class="cd">회차별 결과가 누적되어 추세 비교·연간 분석이 가능 — AI가 종합 분석 리포트까지 작성합니다.</div></div>
</div>
""")

# ── 13 보안 ──────────────────────────────────────────────
S[13] = ("신뢰", chips("실용성"),
"""
<h1>자료는 <span class="em">컴퓨터 밖으로 나가지 않습니다</span></h1>
<div class="grow" style="display:flex;gap:28px;align-items:center;margin-top:8px">
  <div style="flex:0 0 240px;display:flex;flex-direction:column;align-items:center;gap:10px">
    <div style="width:150px;height:150px;border-radius:50%;background:#f0f6ff;display:flex;align-items:center;justify-content:center">""" + svg(I_SHIELD, "#3182f6", 72) + """</div>
    <div style="font-weight:800;color:#1b64da">로컬 처리 원칙</div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:12px">
    <div class="card tint"><div class="ct" style="margin:0">기본 기능은 100% 로컬</div><div class="cd">추출·엑셀 생성·OCR 모두 이 컴퓨터 안에서 — 조사자 정보·좌표 등 민감 정보가 인터넷으로 전송되지 않습니다.</div></div>
    <div class="card tint"><div class="ct" style="margin:0">AI 기능은 선택제 + 명확한 고지</div><div class="cd">AI를 켤 때만, 무엇이 전송되는지 화면에 명시하고 동작합니다. 끄면 전송 0.</div></div>
    <div class="card tint"><div class="ct" style="margin:0">API 키는 암호화 저장</div><div class="cd">Windows 계정 단위 암호화(DPAPI) — 파일이 유출돼도 다른 PC·다른 사용자는 복호화 불가.</div></div>
  </div>
</div>
<div class="note" style="margin-top:12px">공공기관 데이터 처리 원칙에 부합하도록 처음부터 설계했습니다.</div>
""")

# ── 14 도입 비용 0 ───────────────────────────────────────
S[14] = ("도입", chips("실용성"),
"""
<h1>도입 비용·추가 장비 <span class="em">0원</span> — 오늘 바로 쓸 수 있습니다</h1>
<div class="grow" style="display:flex;gap:28px;align-items:center;margin-top:8px">
  <div style="flex:1;display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:14px">
    <div class="card"><div class="ic">""" + svg(I_USB) + """</div><div class="ct">설치 없음</div><div class="cd">압축 풀고 더블클릭 — 파이썬·라이브러리 전부 내장(약 106MB)</div></div>
    <div class="card"><div class="ic">""" + svg(I_X, "#3182f6") + """</div><div class="ct">서버·클라우드 불필요</div><div class="cd">업무 PC 1대면 충분, 유지비 없음</div></div>
    <div class="card"><div class="ic">""" + svg(I_CHECK, "#3182f6") + """</div><div class="ct">환경 자동 점검</div><div class="cd">켜질 때 이 PC에서 되는 것·안 되는 것을 스스로 확인해 안내</div></div>
    <div class="card"><div class="ic">""" + svg(I_PEOPLE, "#3182f6") + """</div><div class="ct">교육 부담 최소</div><div class="cd">사용법 1장 + 30분 시연이면 부서 배포 가능</div></div>
  </div>
  <div style="flex:0 0 300px">
    <div class="win">
      <div class="winbar"><span style="font-size:11px;color:#8b95a1">📁 AutoData_포터블</span></div>
      <div style="padding:14px;display:flex;flex-direction:column;gap:8px;font-size:13px">
        <div style="display:flex;gap:8px;align-items:center">""" + svg(I_DOC, "#3182f6", 16) + """<b>AutoData.exe</b><span style="color:#8b95a1;font-size:11px">← 더블클릭</span></div>
        <div style="display:flex;gap:8px;align-items:center">""" + svg(I_DOC, "#8b95a1", 16) + """사용법.txt</div>
        <div style="display:flex;gap:8px;align-items:center">""" + svg(I_DOC, "#8b95a1", 16) + """ai_config.txt <span style="color:#8b95a1;font-size:11px">(AI 설정·선택)</span></div>
        <div style="display:flex;gap:8px;align-items:center">""" + svg(I_GRID, "#8b95a1", 16) + """data/ <span style="color:#8b95a1;font-size:11px">(결과 엑셀 저장)</span></div>
      </div>
    </div>
    <div class="note" style="text-align:center;margin-top:8px">USB 하나로 어느 PC든 배포</div>
  </div>
</div>
""")

# ── 15 범용성 ────────────────────────────────────────────
S[15] = ("확장", chips("범용성"),
"""
<h1>표가 있는 문서는 <span class="em">모두 DB가 됩니다</span></h1>
<p class="lead">조사표에서 출발했지만, 원리는 하나 — 기관의 모든 표 기반 서식에 그대로 적용됩니다.</p>
<div class="grow" style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:12px;margin-top:8px">
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">연구·조사 야장</div><div class="cd">현장 기록 전반</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">시설 점검표</div><div class="cd">정기 점검 기록</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">안전점검 체크리스트</div><div class="cd">항목·체크 자동 집계</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">교육·행사 신청서</div><div class="cd">명단 자동 취합</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">설문지</div><div class="cd">응답 자동 표화</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">민원·접수 서식</div><div class="cd">접수 내용 DB화</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">회의·심사 기록</div><div class="cd">결과표 정리</div></div>
  <div class="card tint" style="padding:16px"><div class="ct" style="margin-top:0">각종 관리 대장</div><div class="cd">수기 대장 전산화</div></div>
</div>
<div class="note" style="margin-top:12px">템플릿만 만들면 <b>부서마다 자기 서식에 즉시 적용</b> — 처음 보는 양식은 AI 자동추출로.</div>
""")

# ── 16 국민서비스 1 ──────────────────────────────────────
S[16] = ("국민 서비스 개선", chips("가점"),
"""
<h1>조사 데이터가 <span class="em">더 빨리 국민에게</span> 갑니다</h1>
<p class="lead">현장 데이터의 병목은 '입력'이었습니다. 입력이 자동화되면 <b>공공데이터 개방과 정보 공개의 주기</b>가 짧아집니다.</p>
<div class="grow" style="display:flex;flex-direction:column;gap:16px;justify-content:center;margin-top:6px">
  <div class="card" style="border-color:#f5c6cb">
    <div style="font-weight:800;color:#d6303f;margin-bottom:10px">기존</div>
    <div style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600">
      <span class="card tint" style="padding:8px 14px">현장 조사</span><span class="arrow">→</span>
      <span class="card" style="padding:8px 14px;border-color:#f5c6cb;background:#fdecee;color:#d6303f">수기 입력 (수주~수개월)</span><span class="arrow">→</span>
      <span class="card tint" style="padding:8px 14px">검증</span><span class="arrow">→</span>
      <span class="card tint" style="padding:8px 14px">공개·개방</span>
    </div>
  </div>
  <div class="card" style="border-color:#bcd7ff;background:#f0f6ff">
    <div style="font-weight:800;color:#1b64da;margin-bottom:10px">오토다타 도입 후</div>
    <div style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600">
      <span class="card" style="padding:8px 14px;background:#fff">현장 조사</span><span class="arrow">→</span>
      <span class="card" style="padding:8px 14px;border-color:#bcd7ff;background:#fff;color:#1b64da">즉시 DB화 + 자동 검증</span><span class="arrow">→</span>
      <span class="card" style="padding:8px 14px;border-color:#b6ebd2;background:#f4fcf8;color:#04915a">신속 공개·개방</span>
    </div>
  </div>
</div>
<div class="note" style="margin-top:12px">국민·연구자·지자체가 <b>더 최신의 데이터</b>로 환경영향 검토, 정책 수립, 연구에 활용 — 데이터 개방 품질과 속도가 함께 올라갑니다.</div>
""")

# ── 17 국민서비스 2 ──────────────────────────────────────
S[17] = ("국민 서비스 개선", chips("가점"),
"""
<h1>국민이 내는 서류, <span class="em">국민이 모으는 데이터</span>까지</h1>
<div class="grow" style="display:grid;grid-template-columns:repeat(2, minmax(0, 1fr));gap:18px;margin-top:10px">
  <div class="card">
    <div class="ic">""" + svg(I_DOC) + """</div>
    <div class="ct">① 대국민 서식 자동화</div>
    <div class="cd">국민이 제출하는 신청서·참가 신청·설문(수기·스캔 포함)을 자동 DB화 →
    <b>민원 처리 대기시간 단축</b>.<br><br>
    접수 창구의 반복 입력이 사라지면, 그 시간은 <b>국민 응대의 질</b>로 돌아갑니다.</div>
  </div>
  <div class="card">
    <div class="ic">""" + svg(I_PEOPLE, "#3182f6") + """</div>
    <div class="ct">② 시민 참여형 조사 확대</div>
    <div class="cd">시민 모니터링단의 종이 야장·사진 기록을 표준 데이터로 자동 수집 →
    <b>국민 참여형 조사(시민과학)의 진입 장벽을 낮춤</b>.<br><br>
    "기록만 해 주세요, 정리는 AI가" — 참여가 늘수록 국가 생태 데이터가 풍부해집니다.</div>
  </div>
</div>
<div class="note" style="margin-top:12px">접근성·신속성·편의성 — 공공서비스 만족도를 끌어올리는 <b>구체적이고 즉시 실행 가능한</b> 개선 시나리오입니다.</div>
""")

# ── 18 직원 개발 서사 ────────────────────────────────────
S[18] = ("개발 이야기", chips("창의성"),
"""
<h1>이 도구는 <span class="em">직원이 AI와 함께 직접</span> 만들었습니다</h1>
<p class="lead">개발자가 아닌 현업 담당자가, AI와 대화하며 기획부터 배포까지 — <b>예산 0원, 외주 0건.</b></p>
<div class="grow" style="display:flex;align-items:center;gap:14px;margin-top:10px">
  <div class="card tint" style="flex:1;text-align:center;padding:16px"><div style="font-size:13px;font-weight:800;color:#8b95a1">STEP 1</div><div class="ct">업무 불편 정의</div><div class="cd">"조사표 수기 입력이 너무 오래 걸린다"</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="flex:1;text-align:center;padding:16px"><div style="font-size:13px;font-weight:800;color:#8b95a1">STEP 2</div><div class="ct">AI와 페어 개발</div><div class="cd">2주 만에 첫 동작 버전 — 대화로 기능을 쌓아 감</div></div>
  <span class="arrow">→</span>
  <div class="card tint" style="flex:1;text-align:center;padding:16px"><div style="font-size:13px;font-weight:800;color:#8b95a1">STEP 3</div><div class="ct">현장 검증·개선</div><div class="cd">실제 조사표로 시험, 자동 테스트 100여 건 구축</div></div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1;text-align:center;padding:16px;border-color:#bcd7ff;background:#f0f6ff"><div style="font-size:13px;font-weight:800;color:#1b64da">STEP 4</div><div class="ct" style="color:#1b64da">포터블 배포</div><div class="cd">설치 없이 전 부서가 쓸 수 있는 완성품</div></div>
</div>
<div class="card" style="margin-top:16px;background:#191F28;border-color:#191F28;color:#fff">
  <div style="font-size:16px;font-weight:800">"AI를 <span style="color:#9db8ff">업무에 쓰는 것</span>을 넘어, AI로 <span style="color:#9db8ff">업무 도구를 만드는</span> 조직으로"</div>
  <div style="font-size:13.5px;color:#c4cad2;margin-top:6px">이 개발 경험 자체가 복제 가능한 모델입니다 — 각 부서의 불편을, 각 부서가 AI와 함께 해결합니다.</div>
</div>
""")

# ── 19 로드맵 ────────────────────────────────────────────
S[19] = ("확산 계획", chips("범용성", "실용성"),
"""
<h1>일회성 출품작이 아닌, <span class="em">확산 로드맵</span></h1>
<div class="grow" style="display:flex;align-items:stretch;gap:14px;margin-top:12px">
  <div class="card" style="flex:1;border-color:#b6ebd2;background:#f4fcf8">
    <div style="font-size:13px;font-weight:800;color:#04915a">1단계 · 완료</div>
    <div class="ct">현업 부서 실적용</div>
    <div class="cd">실제 조사표로 운영 중 — 템플릿·AI추출·보고서까지 전체 흐름 검증 완료. 자동 테스트 100여 건으로 품질 관리.</div>
  </div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1">
    <div style="font-size:13px;font-weight:800;color:#8b95a1">2단계 · 확산</div>
    <div class="ct">유사 서식으로 확대</div>
    <div class="cd">인접 부서의 조사·점검 서식에 적용, 표준 항목 사전(항목명·단위·형식) 정리로 데이터 일관성 확보.</div>
  </div>
  <span class="arrow">→</span>
  <div class="card" style="flex:1">
    <div style="font-size:13px;font-weight:800;color:#8b95a1">3단계 · 정착</div>
    <div class="ct">전 기관 배포·연계</div>
    <div class="cd">포터블 배포(USB·공유폴더)로 전 부서 보급, 기관 데이터 시스템과 표준 스키마로 연계.</div>
  </div>
</div>
<div class="note" style="margin-top:14px">확산 비용: 프로그램 복사 + <b>사용법 1장 + 30분 시연</b>. 서버 구축·라이선스 구매가 없어 확산의 장벽 자체가 없습니다.</div>
""")

# ── 20 마무리 ────────────────────────────────────────────
S[20] = ("", "",
"""
<div class="grow" style="display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
  <div style="display:flex;align-items:center;gap:10px;font-size:16px;font-weight:700;color:#3182f6;letter-spacing:1px;margin-bottom:14px">
    <span style="width:9px;height:9px;border-radius:50%;background:#3182f6;display:inline-block"></span> AutoData
  </div>
  <div style="font-size:46px;font-weight:900;letter-spacing:-1.5px;line-height:1.3">조사는 현장에서,<br><span style="color:#3182f6">입력은 AI가.</span></div>
  <div style="display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:12px;margin-top:40px;width:100%">
    <div class="card tint" style="padding:14px"><div style="font-size:13px;font-weight:800;color:#1b64da">실용성</div><div class="cd">무설치 완성품,<br>오늘 바로 사용</div></div>
    <div class="card tint" style="padding:14px"><div style="font-size:13px;font-weight:800;color:#04915a">효과성</div><div class="cd">입력 시간 절감 실측,<br>오타 원천 제거</div></div>
    <div class="card tint" style="padding:14px"><div style="font-size:13px;font-weight:800;color:#6d28d9">범용성</div><div class="cd">표 있는 모든 서식,<br>모든 부서로</div></div>
    <div class="card tint" style="padding:14px"><div style="font-size:13px;font-weight:800;color:#d6303f">국민 서비스</div><div class="cd">더 빠른 데이터 개방,<br>민원·참여 확대</div></div>
  </div>
  <div style="margin-top:34px;font-size:18px;font-weight:800;background:#191F28;color:#fff;border-radius:999px;padding:12px 28px">지금 이 자리에서 시연 가능합니다</div>
</div>
""")

# ── 파일 생성 ────────────────────────────────────────────
TITLES = {
    1: "표지", 2: "문제 공감", 3: "왜 어려운가", 4: "해결 요약", 5: "데모 · 디자이너",
    6: "데모 · 엑셀", 7: "유기적 추출", 8: "AI+규칙 하이브리드", 9: "AI 보고서 초안",
    10: "스캔·손글씨", 11: "효과 · 시간", 12: "효과 · 품질", 13: "보안", 14: "도입 비용 0",
    15: "범용성", 16: "국민 서비스 ①", 17: "국민 서비스 ②", 18: "직원 개발", 19: "로드맵", 20: "마무리",
}

artboards = []
for no in range(1, 21):
    sec, ch, body = S[no]
    fname = "Main.dc.html" if no == 1 else "Slide%02d.dc.html" % no
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
        f.write(slide(no, sec, ch, body))
    col, row = (no - 1) % 4, (no - 1) // 4
    artboards.append({
        "file": fname,
        "title": "%02d · %s" % (no, TITLES[no]),
        "x": col * 1420, "y": row * 920, "w": 1280, "h": 720,
    })

with open(os.path.join(OUT, "canvas.json"), "w", encoding="utf-8") as f:
    json.dump({"artboards": artboards, "launch": {"view": "canvas"}}, f, ensure_ascii=False, indent=1)

print("generated", len(artboards), "artboards + canvas.json")
