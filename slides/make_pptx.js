// 오토다타 경진대회 발표 슬라이드 20장 — 편집 가능한 네이티브 PPTX (16:9 WIDE)
// 디자인 토큰: 제품(오토다타)과 동일. 블라인드: 조직·개인명 없음.
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
const W = 13.333, H = 7.5;

// 색 (hex, # 없음)
const INK = "191F28", MUTED = "8B95A1", SUB = "6B7684", LINE = "E5E8EB",
  BLUE = "3182F6", BLUE_D = "1B64DA", BLUE_BG = "EAF3FF", BLUE_BG2 = "F0F6FF",
  GREEN = "04915A", GREEN_BG = "E7F9F0", GREEN_BG2 = "F4FCF8",
  PURPLE = "6D28D9", PURPLE_BG = "F1ECFF",
  AMBER = "A06F00", AMBER_BG = "FFF4D6", AMBER_BG2 = "FFFBEF",
  RED = "D6303F", RED_BG = "FDECEE",
  TINT = "F7F8FA", TLINE = "EEF1F4", GRIDL = "D5DAE0", CELL = "F2F4F6";
const F = "Malgun Gothic";
const ML = 0.67, MR = 0.67; // 좌우 여백
const CW = W - ML - MR;

const CHIP = {
  "실용성": [BLUE_BG, BLUE_D], "효과성": [GREEN_BG, GREEN],
  "범용성": [PURPLE_BG, PURPLE], "창의성": [AMBER_BG, AMBER],
  "가점": [RED_BG, RED],
};

function txt(s, str, o) {
  s.addText(str, Object.assign({ fontFace: F, color: INK, isTextBox: true, margin: 0, align: "left", valign: "top" }, o));
}
function rect(s, o) { s.addShape("rect", o); }
function rrect(s, o) { s.addShape("roundRect", Object.assign({ rectRadius: 0.08 }, o)); }
function card(s, x, y, w, h, opts) {
  rrect(s, Object.assign({ x, y, w, h, fill: { color: "FFFFFF" }, line: { color: LINE, width: 1 } }, opts || {}));
}
function chipRow(s, names) {
  let x = W - MR;
  const items = names.slice().reverse();
  for (const n of items) {
    const [bg, fg] = CHIP[n];
    const label = n === "가점" ? "국민 서비스 개선 · 가점" : n;
    const w = label.length > 6 ? 2.15 : 0.95;
    x -= w;
    rrect(s, { x, y: 0.42, w, h: 0.32, rectRadius: 0.16, fill: { color: bg }, line: { type: "none" } });
    txt(s, label, { x, y: 0.42, w, h: 0.32, fontSize: 11, bold: true, color: fg, align: "center", valign: "middle" });
    x -= 0.12;
  }
}
function topbar(s, sec, chips) {
  if (sec) txt(s, sec, { x: ML, y: 0.44, w: 3.5, h: 0.3, fontSize: 11.5, bold: true, color: MUTED, charSpacing: 2 });
  if (chips && chips.length) chipRow(s, chips);
}
function foot(s, no) {
  s.addShape("line", { x: ML, y: 7.02, w: CW, h: 0, line: { color: LINE, width: 1 } });
  txt(s, "오토다타 AutoData", { x: ML, y: 7.09, w: 3, h: 0.28, fontSize: 9.5, color: MUTED });
  txt(s, String(no).padStart(2, "0") + " / 20", { x: W - MR - 1.2, y: 7.09, w: 1.2, h: 0.28, fontSize: 9.5, color: MUTED, align: "right" });
}
function h1(s, runs, y) {
  s.addText(runs.map(r => ({ text: r[0], options: { color: r[1] || INK, breakLine: false } })),
    { x: ML, y: y || 0.86, w: CW, h: 0.62, fontFace: F, fontSize: 27, bold: true, isTextBox: true, margin: 0, valign: "top", charSpacing: -0.5 });
}
function lead(s, str, y) {
  txt(s, str, { x: ML, y: y || 1.5, w: CW, h: 0.42, fontSize: 13.5, color: "4E5968" });
}
function note(s, str, y) {
  txt(s, str, { x: ML, y, w: CW, h: 0.35, fontSize: 10.5, color: MUTED });
}
function iconCircle(s, x, y, glyph, bg, fg, d) {
  const dd = d || 0.42;
  s.addShape("ellipse", { x, y, w: dd, h: dd, fill: { color: bg }, line: { type: "none" } });
  txt(s, glyph, { x, y: y - 0.015, w: dd, h: dd, fontSize: dd > 0.5 ? 22 : 14, bold: true, color: fg, align: "center", valign: "middle", fontFace: "Segoe UI Symbol" });
}
// 카드 + 제목 + 설명 (아이콘 원 포함)
function infoCard(s, x, y, w, h, glyph, title, desc, opt) {
  const o = opt || {};
  card(s, x, y, w, h, { fill: { color: o.bg || "FFFFFF" }, line: { color: o.border || LINE, width: 1 } });
  if (glyph) iconCircle(s, x + 0.2, y + 0.2, glyph, o.iconBg || BLUE_BG, o.iconFg || BLUE_D);
  txt(s, title, { x: x + 0.2, y: y + (glyph ? 0.72 : 0.2), w: w - 0.4, h: 0.32, fontSize: 13, bold: true, color: o.titleColor || INK });
  txt(s, desc, { x: x + 0.2, y: y + (glyph ? 1.04 : 0.52), w: w - 0.4, h: h - (glyph ? 1.2 : 0.68), fontSize: 10.5, color: SUB, lineSpacing: 15 });
}
function arrow(s, x, y) {
  txt(s, "→", { x, y, w: 0.34, h: 0.4, fontSize: 20, bold: true, color: "C4CAD2", align: "center", valign: "middle" });
}

// ───────────────────────── 01 표지 ─────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addShape("ellipse", { x: W / 2 - 0.85, y: 1.02, w: 0.12, h: 0.12, fill: { color: BLUE }, line: { type: "none" } });
  txt(s, "AutoData", { x: W / 2 - 0.65, y: 0.9, w: 1.6, h: 0.35, fontSize: 14, bold: true, color: BLUE, charSpacing: 1 });
  txt(s, "오토다타", { x: 0, y: 1.45, w: W, h: 1.0, fontSize: 48, bold: true, align: "center", charSpacing: -1 });
  s.addText([
    { text: "현장 조사표, ", options: { color: INK, breakLine: false } },
    { text: "넣으면 엑셀이 됩니다", options: { color: BLUE, breakLine: false } },
  ], { x: 0, y: 2.5, w: W, h: 0.6, fontFace: F, fontSize: 23, bold: true, align: "center", isTextBox: true, margin: 0 });
  txt(s, "수기 입력 없는 조사 데이터 DB화 · AI 자동 추출 플랫폼", { x: 0, y: 3.15, w: W, h: 0.4, fontSize: 13, color: SUB, align: "center" });
  // 하단 플로우
  const fy = 4.35, fw = 3.1, fh = 0.85, gap = 0.55;
  const fx = (W - fw * 3 - gap * 2) / 2;
  card(s, fx, fy, fw, fh, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
  txt(s, "종이·한글·PDF 조사표", { x: fx, y: fy, w: fw, h: fh, fontSize: 12.5, bold: true, color: "4E5968", align: "center", valign: "middle" });
  arrow(s, fx + fw + 0.1, fy + 0.22);
  card(s, fx + fw + gap, fy, fw, fh, { fill: { color: BLUE_BG2 }, line: { color: "BCD7FF", width: 1 } });
  txt(s, "AI 자동 추출", { x: fx + fw + gap, y: fy, w: fw, h: fh, fontSize: 13.5, bold: true, color: BLUE_D, align: "center", valign: "middle" });
  arrow(s, fx + fw * 2 + gap * 2 - 0.45, fy + 0.22);
  card(s, fx + fw * 2 + gap * 2, fy, fw, fh, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
  txt(s, "엑셀 DB · 보고서", { x: fx + fw * 2 + gap * 2, y: fy, w: fw, h: fh, fontSize: 12.5, bold: true, color: GREEN, align: "center", valign: "middle" });
  foot(s, 1);
  s.addNotes("현장 조사표를 넣으면 엑셀 DB가 되는 자동화 도구, 오토다타를 소개합니다.");
}

// ───────────────────────── 02 문제 공감 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "문제", ["효과성"]);
  h1(s, [["조사보다 ", INK], ["입력이 더 오래", BLUE], [" 걸립니다", INK]]);
  lead(s, "현장에서 하루 종일 조사하고 돌아오면, 사무실에서는 조사표를 한 칸씩 엑셀로 옮겨 적는 일이 기다립니다.");
  const y0 = 2.15, ch = 1.28, gap = 0.22, lw = 7.0;
  const rows = [
    ["▤", "조사표 1건 = 여러 쪽, 항목 수백 개", "표 속에 글·숫자·좌표·체크박스가 뒤섞여 있습니다", MUTED],
    ["◷", "옮겨 적는 시간 = 조사만큼의 야근", "건마다 수십 분씩, 연간 수백~수천 건이 수기로 입력됩니다", MUTED],
    ["⚠", "옮겨 적다 생기는 오타", "단순 실수가 그대로 데이터 품질 문제로 이어집니다", RED],
  ];
  rows.forEach((r, i) => {
    const y = y0 + i * (ch + gap);
    card(s, ML, y, lw, ch, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    iconCircle(s, ML + 0.22, y + 0.4, r[0], "FFFFFF", r[3], 0.48);
    txt(s, r[1], { x: ML + 0.9, y: y + 0.24, w: lw - 1.1, h: 0.34, fontSize: 13.5, bold: true });
    txt(s, r[2], { x: ML + 0.9, y: y + 0.62, w: lw - 1.1, h: 0.5, fontSize: 11, color: SUB });
  });
  // 우측: 조사표 더미 일러스트
  const px = 8.6, py = 2.3, pw = 2.4, ph = 3.1;
  rect(s, { x: px + 0.5, y: py + 0.35, w: pw, h: ph, fill: { color: "EEF1F4" }, line: { color: "DFE3E8", width: 1 }, rotate: 6 });
  rect(s, { x: px + 0.28, y: py + 0.18, w: pw, h: ph, fill: { color: "F5F7F9" }, line: { color: "DFE3E8", width: 1 }, rotate: 3 });
  rect(s, { x: px, y: py, w: pw, h: ph, fill: { color: "FFFFFF" }, line: { color: GRIDL, width: 1 } });
  txt(s, "현장 조사표", { x: px, y: py + 0.15, w: pw, h: 0.3, fontSize: 10.5, bold: true, align: "center" });
  for (let r = 0; r < 6; r++) {
    rect(s, { x: px + 0.2, y: py + 0.55 + r * 0.36, w: 0.85, h: 0.28, fill: { color: CELL }, line: { color: GRIDL, width: 0.75 } });
    rect(s, { x: px + 1.05, y: py + 0.55 + r * 0.36, w: 1.15, h: 0.28, fill: { color: "FFFFFF" }, line: { color: GRIDL, width: 0.75 } });
  }
  txt(s, "× 수백 장…", { x: px, y: py + ph - 0.32, w: pw, h: 0.25, fontSize: 9, color: MUTED, align: "center" });
  txt(s, "쌓여 가는 조사표 — 전 부서가 겪는 공통 장면", { x: 8.0, y: py + ph + 0.5, w: 4.6, h: 0.3, fontSize: 10, color: MUTED, align: "center" });
  foot(s, 2);
  s.addNotes("문제 공감: 입력 병목. 조사 하루, 입력은 며칠 — 모든 부서가 겪는 장면입니다.");
}

// ───────────────────────── 03 왜 어려운가 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "문제", ["창의성"]);
  h1(s, [["단순 자동화로는 ", INK], ["풀리지 않던 문제", BLUE]]);
  lead(s, "그동안 자동화가 안 됐던 데에는 구조적인 이유가 있습니다.");
  const items = [
    ["▤", "양식이 제각각", "서식 종류가 여러 가지인 데다 개정될 때마다 줄·칸이 달라져, 하나에 맞춘 규칙이 금방 깨집니다.", BLUE_BG, BLUE_D],
    ["⧉", "한글·PDF·스캔 혼재", "hwp/hwpx, PDF, 복사기 스캔본, 손글씨까지 — 파일마다 읽는 방법이 완전히 다릅니다.", BLUE_BG, BLUE_D],
    ["⊞", "표 속의 복잡한 구조", "병합된 칸, 체크박스(√), 좌표(도·분·초), 굵은 글씨 구분 — 표를 이해해야 값을 꺼낼 수 있습니다.", BLUE_BG, BLUE_D],
    ["✕", "범용 OCR의 한계", "일반 문자인식은 한국어 표 서식에 약해, 어느 칸의 값인지 뒤섞인 결과가 나오기 일쑤입니다.", RED_BG, RED],
  ];
  const cw2 = (CW - 0.3) / 2, chh = 1.95;
  items.forEach((it, i) => {
    const x = ML + (i % 2) * (cw2 + 0.3), y = 2.15 + Math.floor(i / 2) * (chh + 0.25);
    infoCard(s, x, y, cw2, chh, it[0], it[1], it[2], { iconBg: it[3], iconFg: it[4] });
  });
  foot(s, 3);
  s.addNotes("왜 어려웠나: 양식 다양성, 파일 형식 혼재, 표 구조, 한국어 OCR 한계 — 4중 장벽.");
}

// ───────────────────────── 04 해결 요약 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "해결", ["실용성"]);
  h1(s, [["오토다타 — ", INK], ["파일을 넣으면, 엑셀 DB가 됩니다", BLUE]]);
  const fy = 1.65, fh = 0.95, fw3 = (CW - 0.9) / 3;
  const flow = [["1. 조사표 파일 넣기", "hwp·hwpx·PDF·스캔", TINT, TLINE, INK],
    ["2. AI가 읽고 검증", "표·항목 자동 인식", BLUE_BG2, "BCD7FF", BLUE_D],
    ["3. 엑셀 DB·보고서", "요약표 + 시트 분류", TINT, TLINE, INK]];
  flow.forEach((f, i) => {
    const x = ML + i * (fw3 + 0.45);
    card(s, x, fy, fw3, fh, { fill: { color: f[2] }, line: { color: f[3], width: 1 } });
    txt(s, f[0], { x, y: fy + 0.16, w: fw3, h: 0.32, fontSize: 13.5, bold: true, color: f[4], align: "center" });
    txt(s, f[1], { x, y: fy + 0.52, w: fw3, h: 0.3, fontSize: 10.5, color: SUB, align: "center" });
    if (i < 2) arrow(s, x + fw3 + 0.05, fy + 0.28);
  });
  const cy = 2.95, ch3 = 2.6, cw3 = (CW - 0.6) / 3;
  const modes = [
    ["🧩", "템플릿 디자이너", "반복되는 같은 양식을 대량 처리 — 추출 칸을 지정해 템플릿으로 저장, 수백 파일을 한 번에."],
    ["🤖", "AI 자동추출", "처음 보는 양식도 AI(Vision)가 페이지를 사람처럼 읽고 서식을 판별해 자동으로 표를 만듭니다."],
    ["⚙️", "환경설정", "Claude·ChatGPT·Gemini 중 선택, 연결 테스트까지 화면에서. AI 없이도 기본 기능은 동작."],
  ];
  modes.forEach((m, i) => {
    const x = ML + i * (cw3 + 0.3);
    card(s, x, cy, cw3, ch3, {});
    txt(s, m[0], { x: x + 0.22, y: cy + 0.2, w: 0.6, h: 0.5, fontSize: 22 });
    txt(s, m[1], { x: x + 0.22, y: cy + 0.78, w: cw3 - 0.44, h: 0.34, fontSize: 14, bold: true });
    txt(s, m[2], { x: x + 0.22, y: cy + 1.16, w: cw3 - 0.44, h: 1.3, fontSize: 11, color: SUB, lineSpacing: 16 });
  });
  note(s, "설치가 필요 없는 포터블 프로그램 — USB 하나로 어느 PC에서든 더블클릭으로 실행됩니다.", 5.85);
  foot(s, 4);
  s.addNotes("해결책 한 장 요약: 3단계 흐름과 3가지 모드. 설치 없는 포터블이 핵심 실용 포인트.");
}

// ───────────────────────── 05 데모: 디자이너 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "데모", ["실용성"]);
  h1(s, [["양식을 올리면 ", INK], ["추출 칸이 자동으로", BLUE], [" 생깁니다", INK]]);
  const steps = [
    ["① 표 칸마다 박스 자동 생성", "사람은 필요 없는 것만 지우고 이름을 확인"],
    ["② AI가 항목 이름까지 명명", "“이 칸은 하천명, 이 칸은 보 길이” — 버튼 하나"],
    ["③ 템플릿으로 저장", "같은 양식 수백 개 파일에 재사용 · 양식 PDF도 함께 보관"],
  ];
  steps.forEach((st, i) => {
    const y = 1.95 + i * 1.42;
    card(s, ML, y, 5.5, 1.2, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, st[0], { x: ML + 0.22, y: y + 0.18, w: 5.1, h: 0.32, fontSize: 13, bold: true });
    txt(s, st[1], { x: ML + 0.22, y: y + 0.56, w: 5.1, h: 0.5, fontSize: 10.5, color: SUB });
  });
  // 우측 화면 모형
  const wx = 6.7, wy = 1.9, ww = 5.95, wh = 4.35;
  card(s, wx, wy, ww, wh, { rectRadius: 0.12, line: { color: "DFE3E8", width: 1 } });
  rect(s, { x: wx + 0.04, y: wy + 0.04, w: ww - 0.08, h: 0.3, fill: { color: CELL }, line: { type: "none" } });
  txt(s, "● ● ●   템플릿 디자이너", { x: wx + 0.15, y: wy + 0.06, w: 3, h: 0.26, fontSize: 8.5, color: MUTED });
  rect(s, { x: wx + 0.3, y: wy + 0.5, w: ww - 0.6, h: wh - 0.8, fill: { color: "FFFFFF" }, line: { color: "DFE3E8", width: 1 } });
  txt(s, "○○ 현장 조사표", { x: wx + 0.3, y: wy + 0.62, w: ww - 0.6, h: 0.3, fontSize: 12, bold: true, align: "center" });
  // 제목 박스(보라)
  rect(s, { x: wx + 1.9, y: wy + 0.58, w: 2.1, h: 0.36, fill: { color: "8B5CF6", transparency: 88 }, line: { color: "8B5CF6", width: 1.5 } });
  txt(s, "제목", { x: wx + 1.9, y: wy + 0.34, w: 0.6, h: 0.22, fontSize: 8, bold: true, color: "FFFFFF", fill: { color: "8B5CF6" }, align: "center" });
  // 표 + 파란 박스
  const labels = ["하천명", "조사일", "위치(좌표)", "구조물 규모", "상태 점검", "비고"];
  for (let i = 0; i < 6; i++) {
    const col = i % 2, row = Math.floor(i / 2);
    const cx = wx + 0.45 + col * 2.75, cyy = wy + 1.15 + row * 0.62;
    rect(s, { x: cx, y: cyy, w: 1.0, h: 0.5, fill: { color: CELL }, line: { color: GRIDL, width: 0.75 } });
    txt(s, labels[i], { x: cx + 0.05, y: cyy + 0.12, w: 0.95, h: 0.3, fontSize: 8.5, bold: true });
    rect(s, { x: cx + 1.0, y: cyy, w: 1.55, h: 0.5, fill: { color: "FFFFFF" }, line: { color: GRIDL, width: 0.75 } });
    rect(s, { x: cx + 1.06, y: cyy + 0.06, w: 1.42, h: 0.38, fill: { color: BLUE, transparency: 86 }, line: { color: BLUE, width: 1.5 } });
  }
  txt(s, "화면 모형 (실제 UI 동일 구성)", { x: wx + ww - 2.3, y: wy + wh - 0.32, w: 2.1, h: 0.24, fontSize: 8, color: MUTED, align: "right" });
  foot(s, 5);
  s.addNotes("데모 1: 양식 업로드 → 파란 추출 박스 자동 생성 → AI 명명 → 템플릿 저장. 실제 라이브 시연 가능.");
}

// ───────────────────────── 06 데모: 엑셀 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "데모", ["실용성", "효과성"]);
  h1(s, [["수백 개 파일 → ", INK], ["버튼 하나로 엑셀 완성", BLUE]]);
  const steps = [
    ["요약 DB + 대상지별 시트 + 보고서", "한 번의 처리로 필요한 산출물이 모두 생성"],
    ["한 파일에 조사표 여러 묶음? 자동 인식", "묶음마다 한 행씩 — 27쪽짜리 파일도 3건으로 정확히"],
    ["제목(양식)별 시트 자동 분류", "상단 큰 글씨를 제목으로 인식해 같은 양식끼리 묶음"],
  ];
  steps.forEach((st, i) => {
    const y = 1.95 + i * 1.42;
    card(s, ML, y, 5.5, 1.2, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, st[0], { x: ML + 0.22, y: y + 0.18, w: 5.1, h: 0.32, fontSize: 13, bold: true });
    txt(s, st[1], { x: ML + 0.22, y: y + 0.56, w: 5.1, h: 0.5, fontSize: 10.5, color: SUB });
  });
  // 우측 엑셀 모형
  const wx = 6.7, wy = 1.9, ww = 5.95, wh = 4.35;
  card(s, wx, wy, ww, wh, { rectRadius: 0.12, line: { color: "DFE3E8", width: 1 } });
  rect(s, { x: wx + 0.04, y: wy + 0.04, w: ww - 0.08, h: 0.3, fill: { color: CELL }, line: { type: "none" } });
  txt(s, "● ● ●   결과 엑셀", { x: wx + 0.15, y: wy + 0.06, w: 3, h: 0.26, fontSize: 8.5, color: MUTED });
  const tRows = [
    ["파일명", "하천명", "규모(m)", "상태", true],
    ["조사표A #1", "샘플천", "30", "양호", false],
    ["조사표A #2", "예시천", "25", "보통", false],
    ["조사표B", "모형천", "18", "양호", false],
  ];
  const colW = [1.65, 1.35, 1.2, 1.1];
  tRows.forEach((row, r) => {
    let cx = wx + 0.3;
    const cyy = wy + 0.55 + r * 0.52;
    for (let c = 0; c < 4; c++) {
      rect(s, { x: cx, y: cyy, w: colW[c], h: 0.5, fill: { color: row[4] ? INK : "FFFFFF" }, line: { color: TLINE, width: 0.75 } });
      txt(s, row[c], { x: cx + 0.08, y: cyy + 0.12, w: colW[c] - 0.16, h: 0.3, fontSize: 9.5, bold: !!row[4], color: row[4] ? "FFFFFF" : INK });
      cx += colW[c];
    }
  });
  // 시트 탭
  const tabs = [["요약(DB)", true], ["구조물 조사표", false], ["어도 조사표", false], ["대상지별…", false]];
  let tx = wx + 0.3;
  const ty = wy + 0.55 + 4 * 0.52 + 0.25;
  txt(s, "시트:", { x: tx, y: ty + 0.05, w: 0.5, h: 0.28, fontSize: 9, color: MUTED });
  tx += 0.55;
  tabs.forEach(t => {
    const tw2 = t[0].length * 0.11 + 0.35;
    rrect(s, { x: tx, y: ty, w: tw2, h: 0.34, rectRadius: 0.05, fill: { color: t[1] ? "FFFFFF" : "EEF1F4" }, line: { color: t[1] ? GREEN : "DFE3E8", width: t[1] ? 1.5 : 0.75 } });
    txt(s, t[0], { x: tx, y: ty + 0.05, w: tw2, h: 0.26, fontSize: 8.5, bold: true, color: t[1] ? INK : SUB, align: "center" });
    tx += tw2 + 0.08;
  });
  txt(s, "제목별 시트 자동 분류 ↑", { x: wx + 0.3, y: ty + 0.5, w: 4, h: 0.26, fontSize: 9, color: GREEN, bold: true });
  foot(s, 6);
  s.addNotes("데모 2: 결과 엑셀 — 요약 DB와 양식별 시트 분류, 묶음 자동 인식(#1, #2).");
}

// ───────────────────────── 07 유기적 추출 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "핵심 기술 1", ["창의성", "효과성"]);
  h1(s, [["양식이 변해도 정확한 ", INK], ["‘유기적 추출’", BLUE]]);
  lead(s, "좌표를 외우지 않습니다. 라벨(항목 이름)을 찾아 그 옆 칸을 읽기 때문에, 줄이 추가되거나 표가 밀려도 값이 어긋나지 않습니다.");
  const py = 2.15, pw = (CW - 0.4) / 2, ph = 3.65;
  // 좌: 기존 방식
  card(s, ML, py, pw, ph, { line: { color: "F5C6CB", width: 1.25 } });
  txt(s, "✕  기존 좌표 방식", { x: ML + 0.25, y: py + 0.2, w: pw - 0.5, h: 0.34, fontSize: 13.5, bold: true, color: RED });
  txt(s, "양식에 줄 1개 추가됨 ↓", { x: ML + 0.25, y: py + 0.62, w: pw - 0.5, h: 0.28, fontSize: 10, color: MUTED });
  const rows1 = [["신규 항목", "…", AMBER_BG], ["하천명", "샘플천", CELL], ["규모", "30", CELL]];
  rows1.forEach((r, i) => {
    const y = py + 0.95 + i * 0.5;
    rect(s, { x: ML + 0.25, y, w: 1.3, h: 0.46, fill: { color: r[2] }, line: { color: GRIDL, width: 0.75 } });
    txt(s, r[0], { x: ML + 0.33, y: y + 0.1, w: 1.2, h: 0.3, fontSize: 10, bold: true });
    rect(s, { x: ML + 1.55, y, w: 2.6, h: 0.46, fill: { color: "FFFFFF" }, line: { color: GRIDL, width: 0.75 } });
    txt(s, r[1], { x: ML + 1.65, y: y + 0.1, w: 2.4, h: 0.3, fontSize: 10 });
  });
  // 어긋난 좌표 박스 (점선)
  rect(s, { x: ML + 1.62, y: py + 0.98, w: 1.6, h: 0.4, fill: { type: "none" }, line: { color: RED, width: 1.5, dashType: "dash" } });
  txt(s, "고정 좌표가 밀려 엉뚱한 값을 집음", { x: ML + 0.25, y: py + 2.65, w: pw - 0.5, h: 0.3, fontSize: 11, bold: true, color: RED });
  // 우: 유기적
  const rx = ML + pw + 0.4;
  card(s, rx, py, pw, ph, { line: { color: "B6EBD2", width: 1.25 } });
  txt(s, "✓  오토다타 유기적 추출", { x: rx + 0.25, y: py + 0.2, w: pw - 0.5, h: 0.34, fontSize: 13.5, bold: true, color: GREEN });
  txt(s, "같은 변형 양식 ↓", { x: rx + 0.25, y: py + 0.62, w: pw - 0.5, h: 0.28, fontSize: 10, color: MUTED });
  const rows2 = [["신규 항목", "…", AMBER_BG, false], ["하천명 ⌖", "샘플천", GREEN_BG, true], ["규모", "30", CELL, false]];
  rows2.forEach((r, i) => {
    const y = py + 0.95 + i * 0.5;
    rect(s, { x: rx + 0.25, y, w: 1.3, h: 0.46, fill: { color: r[2] }, line: { color: GRIDL, width: 0.75 } });
    txt(s, r[0], { x: rx + 0.33, y: y + 0.1, w: 1.2, h: 0.3, fontSize: 10, bold: true, color: r[3] ? GREEN : INK });
    rect(s, { x: rx + 1.55, y, w: 2.6, h: 0.46, fill: { color: "FFFFFF" }, line: r[3] ? { color: GREEN, width: 2 } : { color: GRIDL, width: 0.75 } });
    txt(s, r[1], { x: rx + 1.65, y: y + 0.1, w: 2.4, h: 0.3, fontSize: 10, bold: r[3] });
  });
  txt(s, "라벨을 먼저 찾고 → 그 옆 칸을 읽음 = 항상 정확", { x: rx + 0.25, y: py + 2.65, w: pw - 0.5, h: 0.3, fontSize: 11, bold: true, color: GREEN });
  note(s, "양식이 개정돼도 템플릿 재작업이 필요 없습니다 — 유지관리 비용이 구조적으로 낮습니다.", 6.15);
  foot(s, 7);
  s.addNotes("핵심 기술 1: 유기적 추출. 좌표가 아니라 라벨 기준이라 양식 변형에 강건 — 좌우 비교로 설명.");
}

// ───────────────────────── 08 하이브리드 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "핵심 기술 2", ["창의성"]);
  h1(s, [["AI가 읽고, ", INK], ["규칙이 검증하고", BLUE], [", 사람은 확인만", INK]]);
  lead(s, "AI를 맹신하지 않습니다. 3단 구조로 믿을 수 있는 데이터를 만듭니다.");
  const cy = 2.2, ch3 = 3.0, cw3 = (CW - 1.2) / 3;
  const stages = [
    ["◉", "① AI(Vision)가 읽기", "페이지를 사람처럼 통째로 읽어 서식을 판별하고 항목을 추출 — 스캔·손글씨도 처리", BLUE_BG2, "BCD7FF", BLUE_BG, BLUE_D],
    ["⚠", "② 규칙 엔진이 검증", "통계 기반 이상치 자동 경고(오추출 의심 값 표시) · 형식·범위 점검 · 신뢰도 낮은 값에 검수 플래그", AMBER_BG2, "F5DEA6", AMBER_BG, AMBER],
    ["✓", "③ 사람은 확인만", "플래그된 값만 골라 검토 — 전수 검토가 아닌 표적 검수로 시간을 아끼면서 품질 확보", GREEN_BG2, "B6EBD2", GREEN_BG, GREEN],
  ];
  stages.forEach((st, i) => {
    const x = ML + i * (cw3 + 0.6);
    infoCard(s, x, cy, cw3, ch3, st[0], st[1], st[2], { bg: st[3], border: st[4], iconBg: st[5], iconFg: st[6] });
    if (i < 2) arrow(s, x + cw3 + 0.12, cy + 1.3);
  });
  note(s, "외부 전문가 관점에서도 안전한 구조 — AI 출력이 그대로 확정되지 않고 반드시 검증층을 통과합니다.", 5.65);
  foot(s, 8);
  s.addNotes("핵심 기술 2: AI+규칙 하이브리드 3단 구조. AI 맹신이 아닌 검증 설계 — 심사위원 신뢰 포인트.");
}

// ───────────────────────── 09 AI 보고서 초안 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "핵심 기술 3", ["창의성"]);
  h1(s, [["보고서 양식도 ", INK], ["AI가 초안부터", BLUE]]);
  lead(s, "추출 항목을 보고 AI가 보고서 양식(xlsx) 초안을 설계 — 편집해서 다시 올리면 데이터가 자동으로 채워집니다.");
  const cy = 2.3, chh = 2.1;
  const cyc = [
    ["🤖 AI 초안 설계", "종합 비교표 + 대상지별 1장\n합계·평균 수식 포함", BLUE_BG2, "BCD7FF", 2.35],
    ["📥 다운로드", "초안 xlsx 파일", TINT, TLINE, 1.85],
    ["✏️ 엑셀에서 편집", "우리 부서 양식으로\n자유롭게 수정", TINT, TLINE, 1.95],
    ["📤 재업로드", "프로그램에 다시 올림", TINT, TLINE, 1.85],
    ["📊 데이터 자동 채움", "{항목명} 자리마다\n조사 값이 든 완성본", GREEN_BG2, "B6EBD2", 2.35],
  ];
  let x = ML;
  cyc.forEach((c, i) => {
    card(s, x, cy, c[4], chh, { fill: { color: c[2] }, line: { color: c[3], width: 1 } });
    txt(s, c[0], { x: x + 0.15, y: cy + 0.3, w: c[4] - 0.3, h: 0.34, fontSize: 12.5, bold: true, align: "center", color: i === 4 ? GREEN : (i === 0 ? BLUE_D : INK) });
    txt(s, c[1], { x: x + 0.15, y: cy + 0.75, w: c[4] - 0.3, h: 1.1, fontSize: 10, color: SUB, align: "center", lineSpacing: 14 });
    x += c[4];
    if (i < 4) { arrow(s, x - 0.02, cy + 0.85); x += 0.32; }
  });
  card(s, ML, 5.0, CW, 1.0, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
  s.addText([
    { text: "신뢰성 설계:  ", options: { bold: true, color: INK, breakLine: false } },
    { text: "AI는 '설계도(JSON)'만 제안하고, 실제 엑셀 파일 조립은 프로그램이 결정적으로 수행 — 깨진 파일이 나올 수 없는 구조이며, AI가 실수해도 자동 보정됩니다.", options: { color: "4E5968", breakLine: false } },
  ], { x: ML + 0.25, y: 5.2, w: CW - 0.5, h: 0.62, fontFace: F, fontSize: 11.5, isTextBox: true, margin: 0, lineSpacing: 16 });
  foot(s, 9);
  s.addNotes("핵심 기술 3: AI 보고서 초안 왕복. 사람-AI 협업 루프 + 깨질 수 없는 조립 구조.");
}

// ───────────────────────── 10 스캔·손글씨 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "핵심 기술 4", ["범용성"]);
  h1(s, [["과거의 스캔 자료까지 ", INK], ["DB로 살립니다", BLUE]]);
  lead(s, "문서 종류마다 가장 잘 읽는 방법을 자동으로 골라 씁니다.");
  const cy = 2.2, ch3 = 2.9, cw3 = (CW - 0.6) / 3;
  const paths = [
    ["▤", "타이핑 문서 (hwp·hwpx·PDF)", "글자를 그대로 추출 — 변환 오차 없는 무손실 데이터."],
    ["⧉", "스캔 PDF → 내장 OCR", "한국어 인식 모델을 프로그램에 내장 — 인터넷 없이 이 컴퓨터 안에서 글자를 인식."],
    ["◉", "손글씨·복잡 서식 → AI Vision", "AI가 이미지를 통째로 읽어 손글씨·비정형 기록까지 표로 변환."],
  ];
  paths.forEach((p, i) => {
    infoCard(s, ML + i * (cw3 + 0.3), cy, cw3, ch3, p[0], p[1], p[2], {});
  });
  note(s, "서랍 속에 잠자던 과거 조사 자료(스캔본)도 같은 파이프라인으로 축적 — 데이터 자산이 소급해서 늘어납니다.", 5.5);
  foot(s, 10);
  s.addNotes("입력 형식별 3경로: 무손실 텍스트 / 내장 OCR(오프라인) / AI Vision. 과거 자료 소급 축적.");
}

// ───────────────────────── 11 효과: 시간 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "효과", ["효과성"]);
  h1(s, [["시간으로 증명합니다  ", INK], ["(발표 전 실측값 기입)", MUTED]]);
  // 좌: 비교 막대
  const ly = 2.0, lw = 6.9;
  card(s, ML, ly, lw, 1.35, {});
  txt(s, "수기 입력", { x: ML + 0.25, y: ly + 0.18, w: 2, h: 0.32, fontSize: 13.5, bold: true });
  rrect(s, { x: ML + lw - 2.6, y: ly + 0.16, w: 2.35, h: 0.36, rectRadius: 0.06, fill: { color: "FFF9E8" }, line: { color: "E2B93B", width: 1, dashType: "dash" } });
  txt(s, "실측 기입: 건당 __분", { x: ML + lw - 2.6, y: ly + 0.2, w: 2.35, h: 0.3, fontSize: 10.5, bold: true, color: "8A6D1D", align: "center" });
  rect(s, { x: ML + 0.25, y: ly + 0.72, w: lw - 0.5, h: 0.4, fill: { color: "F04452" }, line: { type: "none" } });
  card(s, ML, ly + 1.6, lw, 1.35, {});
  txt(s, "오토다타", { x: ML + 0.25, y: ly + 1.78, w: 2, h: 0.32, fontSize: 13.5, bold: true, color: BLUE_D });
  rrect(s, { x: ML + lw - 2.6, y: ly + 1.76, w: 2.35, h: 0.36, rectRadius: 0.06, fill: { color: "FFF9E8" }, line: { color: "E2B93B", width: 1, dashType: "dash" } });
  txt(s, "실측 기입: 건당 __초", { x: ML + lw - 2.6, y: ly + 1.8, w: 2.35, h: 0.3, fontSize: 10.5, bold: true, color: "8A6D1D", align: "center" });
  rect(s, { x: ML + 0.25, y: ly + 2.32, w: lw - 0.5, h: 0.4, fill: { color: BLUE_BG }, line: { type: "none" } });
  rect(s, { x: ML + 0.25, y: ly + 2.32, w: (lw - 0.5) * 0.07, h: 0.4, fill: { color: BLUE }, line: { type: "none" } });
  txt(s, "막대 길이는 실측값 비율로 수정 · 측정 방법 명시: 동일 조사표 10건 표본, 수기 입력과 자동 처리를 같은 조건에서 실측",
    { x: ML, y: ly + 3.15, w: lw, h: 0.6, fontSize: 10, color: MUTED, lineSpacing: 14 });
  // 우: 연간 환산
  const rx = ML + lw + 0.4, rw = CW - lw - 0.4;
  card(s, rx, ly, rw, 3.0, { fill: { color: BLUE_BG2 }, line: { color: "BCD7FF", width: 1 } });
  txt(s, "연간 환산 (기관 실적 기준으로 기입)", { x: rx, y: ly + 0.22, w: rw, h: 0.3, fontSize: 10.5, color: SUB, align: "center" });
  txt(s, "연간 __건 × 건당 절감 __분", { x: rx, y: ly + 0.65, w: rw, h: 0.4, fontSize: 14.5, bold: true, align: "center" });
  txt(s, "=", { x: rx, y: ly + 1.15, w: rw, h: 0.35, fontSize: 13, color: MUTED, align: "center" });
  txt(s, "약 __인시 절감", { x: rx, y: ly + 1.55, w: rw, h: 0.6, fontSize: 27, bold: true, color: BLUE_D, align: "center" });
  txt(s, "부풀린 백분율 대신\n검증 가능한 절대값만 제시합니다.", { x: rx, y: ly + 2.3, w: rw, h: 0.6, fontSize: 10, color: MUTED, align: "center", lineSpacing: 14 });
  foot(s, 11);
  s.addNotes("효과-시간: 발표 전 표본 10건 실측해 노란 기입란을 채울 것. 절대값+측정방법으로 제시.");
}

// ───────────────────────── 12 효과: 품질 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "효과", ["효과성"]);
  h1(s, [["빠르기만 한 게 아니라, ", INK], ["더 정확합니다", BLUE]]);
  const cy = 1.85, ch3 = 3.6, cw3 = (CW - 0.6) / 3;
  infoCard(s, ML, cy, cw3, ch3, "✓", "옮겨 적기 오타 원천 제거", "원본 글자를 그대로 추출하므로 전산화 과정의 오타가 사라집니다.", { iconBg: GREEN_BG, iconFg: GREEN });
  // 가운데: 이상치 + 예시
  const mx = ML + cw3 + 0.3;
  infoCard(s, mx, cy, cw3, ch3, "⚠", "이상치 자동 경고", "같은 항목의 값 분포를 통계로 비교해, 튀는 값(오추출·오기재 의심)을 자동 표시합니다.", { iconBg: AMBER_BG, iconFg: AMBER });
  rrect(s, { x: mx + 0.2, y: cy + 2.45, w: cw3 - 0.4, h: 0.9, rectRadius: 0.06, fill: { color: AMBER_BG2 }, line: { color: "F5DEA6", width: 1 } });
  s.addText([
    { text: "⚠ 규모 349m", options: { bold: true, color: AMBER, breakLine: true } },
    { text: "다른 조사표 평균 25m의 14배, 확인 필요", options: { color: SUB, breakLine: false } },
  ], { x: mx + 0.35, y: cy + 2.58, w: cw3 - 0.7, h: 0.68, fontFace: F, fontSize: 9.5, isTextBox: true, margin: 0, lineSpacing: 13 });
  infoCard(s, ML + (cw3 + 0.3) * 2, cy, cw3, ch3, "↗", "쌓일수록 강해지는 DB", "회차별 결과가 누적되어 추세 비교·연간 분석이 가능 — AI가 종합 분석 리포트까지 작성합니다.", {});
  foot(s, 12);
  s.addNotes("효과-품질: 오타 제거, 이상치 경고(예: 349m 경고), 누적 DB와 AI 분석.");
}

// ───────────────────────── 13 보안 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "신뢰", ["실용성"]);
  h1(s, [["자료는 ", INK], ["컴퓨터 밖으로 나가지 않습니다", BLUE]]);
  // 좌: 방패
  s.addShape("ellipse", { x: ML + 0.55, y: 2.5, w: 2.1, h: 2.1, fill: { color: BLUE_BG2 }, line: { type: "none" } });
  txt(s, "🛡", { x: ML + 0.55, y: 2.62, w: 2.1, h: 1.6, fontSize: 54, align: "center", valign: "middle" });
  txt(s, "로컬 처리 원칙", { x: ML, y: 4.75, w: 3.2, h: 0.35, fontSize: 13.5, bold: true, color: BLUE_D, align: "center" });
  // 우: 3개 카드
  const rx = 4.6, rw = W - MR - rx;
  const rows = [
    ["기본 기능은 100% 로컬", "추출·엑셀 생성·OCR 모두 이 컴퓨터 안에서 — 조사자 정보·좌표 등 민감 정보가 인터넷으로 전송되지 않습니다."],
    ["AI 기능은 선택제 + 명확한 고지", "AI를 켤 때만, 무엇이 전송되는지 화면에 명시하고 동작합니다. 끄면 전송 0."],
    ["API 키는 암호화 저장", "Windows 계정 단위 암호화(DPAPI) — 파일이 유출돼도 다른 PC·다른 사용자는 복호화 불가."],
  ];
  rows.forEach((r, i) => {
    const y = 1.95 + i * 1.45;
    card(s, rx, y, rw, 1.25, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, r[0], { x: rx + 0.25, y: y + 0.18, w: rw - 0.5, h: 0.32, fontSize: 13, bold: true });
    txt(s, r[1], { x: rx + 0.25, y: y + 0.55, w: rw - 0.5, h: 0.6, fontSize: 10.5, color: SUB, lineSpacing: 14 });
  });
  note(s, "공공기관 데이터 처리 원칙에 부합하도록 처음부터 설계했습니다.", 6.35);
  foot(s, 13);
  s.addNotes("보안: 기본 100% 로컬, AI 선택제, 키 암호화 — 공공기관 필수 관문 통과 설계.");
}

// ───────────────────────── 14 도입 비용 0 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "도입", ["실용성"]);
  h1(s, [["도입 비용·추가 장비 ", INK], ["0원", BLUE], [" — 오늘 바로 쓸 수 있습니다", INK]]);
  const items = [
    ["⊻", "설치 없음", "압축 풀고 더블클릭 — 파이썬·라이브러리 전부 내장(약 106MB)"],
    ["✕", "서버·클라우드 불필요", "업무 PC 1대면 충분, 유지비 없음"],
    ["✓", "환경 자동 점검", "켜질 때 이 PC에서 되는 것·안 되는 것을 스스로 확인해 안내"],
    ["◫", "교육 부담 최소", "사용법 1장 + 30분 시연이면 부서 배포 가능"],
  ];
  const cw2 = 4.35, chh = 1.85;
  items.forEach((it, i) => {
    const x = ML + (i % 2) * (cw2 + 0.3), y = 1.95 + Math.floor(i / 2) * (chh + 0.3);
    infoCard(s, x, y, cw2, chh, it[0], it[1], it[2], {});
  });
  // 우: 폴더 모형
  const fx = 10.0, fy = 2.1, fw = 2.65, fh = 3.2;
  card(s, fx, fy, fw, fh, {});
  rect(s, { x: fx + 0.03, y: fy + 0.03, w: fw - 0.06, h: 0.34, fill: { color: CELL }, line: { type: "none" } });
  txt(s, "📁 AutoData_포터블", { x: fx + 0.15, y: fy + 0.07, w: fw - 0.3, h: 0.28, fontSize: 9.5, color: SUB });
  const files = [["AutoData.exe  ← 더블클릭", true], ["사용법.txt", false], ["ai_config.txt  (AI 설정·선택)", false], ["data/  (결과 엑셀 저장)", false]];
  files.forEach((f, i) => {
    txt(s, f[0], { x: fx + 0.2, y: fy + 0.6 + i * 0.5, w: fw - 0.4, h: 0.36, fontSize: 10, bold: f[1], color: f[1] ? INK : SUB });
  });
  txt(s, "USB 하나로 어느 PC든 배포", { x: fx - 0.2, y: fy + fh + 0.15, w: fw + 0.4, h: 0.3, fontSize: 10, color: MUTED, align: "center" });
  foot(s, 14);
  s.addNotes("도입 비용 0원: 무설치·서버 불필요·자동 점검·교육 30분. 직원평가단 실용 포인트.");
}

// ───────────────────────── 15 범용성 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "확장", ["범용성"]);
  h1(s, [["표가 있는 문서는 ", INK], ["모두 DB가 됩니다", BLUE]]);
  lead(s, "조사표에서 출발했지만, 원리는 하나 — 기관의 모든 표 기반 서식에 그대로 적용됩니다.");
  const uses = [
    ["연구·조사 야장", "현장 기록 전반"], ["시설 점검표", "정기 점검 기록"],
    ["안전점검 체크리스트", "항목·체크 자동 집계"], ["교육·행사 신청서", "명단 자동 취합"],
    ["설문지", "응답 자동 표화"], ["민원·접수 서식", "접수 내용 DB화"],
    ["회의·심사 기록", "결과표 정리"], ["각종 관리 대장", "수기 대장 전산화"],
  ];
  const cw4 = (CW - 0.9) / 4, chh = 1.5;
  uses.forEach((u, i) => {
    const x = ML + (i % 4) * (cw4 + 0.3), y = 2.2 + Math.floor(i / 4) * (chh + 0.3);
    card(s, x, y, cw4, chh, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, u[0], { x: x + 0.18, y: y + 0.24, w: cw4 - 0.36, h: 0.55, fontSize: 12, bold: true, lineSpacing: 15 });
    txt(s, u[1], { x: x + 0.18, y: y + 0.88, w: cw4 - 0.36, h: 0.4, fontSize: 10, color: SUB });
  });
  note(s, "템플릿만 만들면 부서마다 자기 서식에 즉시 적용 — 처음 보는 양식은 AI 자동추출로.", 5.9);
  foot(s, 15);
  s.addNotes("범용성: 8가지 활용처 — 평가단 각 부서가 자기 업무를 떠올리게 하는 슬라이드.");
}

// ───────────────────────── 16 국민 서비스 1 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "국민 서비스 개선", ["가점"]);
  h1(s, [["조사 데이터가 ", INK], ["더 빨리 국민에게", BLUE], [" 갑니다", INK]]);
  lead(s, "현장 데이터의 병목은 '입력'이었습니다. 입력이 자동화되면 공공데이터 개방과 정보 공개의 주기가 짧아집니다.");
  // 기존
  card(s, ML, 2.2, CW, 1.5, { line: { color: "F5C6CB", width: 1.25 } });
  txt(s, "기존", { x: ML + 0.25, y: 2.38, w: 2, h: 0.3, fontSize: 12.5, bold: true, color: RED });
  const steps1 = [["현장 조사", TINT, TLINE, INK, 1.7], ["수기 입력 (수주~수개월)", RED_BG, "F5C6CB", RED, 3.3], ["검증", TINT, TLINE, INK, 1.3], ["공개·개방", TINT, TLINE, INK, 1.7]];
  let x1 = ML + 1.35;
  steps1.forEach((st, i) => {
    rrect(s, { x: x1, y: 2.75, w: st[4], h: 0.6, rectRadius: 0.08, fill: { color: st[1] }, line: { color: st[2], width: 1 } });
    txt(s, st[0], { x: x1, y: 2.75, w: st[4], h: 0.6, fontSize: 11, bold: true, color: st[3], align: "center", valign: "middle" });
    x1 += st[4];
    if (i < 3) { arrow(s, x1 + 0.01, 2.85); x1 += 0.38; }
  });
  // 이후
  card(s, ML, 3.95, CW, 1.5, { fill: { color: BLUE_BG2 }, line: { color: "BCD7FF", width: 1.25 } });
  txt(s, "오토다타 도입 후", { x: ML + 0.25, y: 4.13, w: 3, h: 0.3, fontSize: 12.5, bold: true, color: BLUE_D });
  const steps2 = [["현장 조사", "FFFFFF", LINE, INK, 1.7], ["즉시 DB화 + 자동 검증", "FFFFFF", "BCD7FF", BLUE_D, 3.3], ["신속 공개·개방", GREEN_BG2, "B6EBD2", GREEN, 2.6]];
  let x2 = ML + 1.35;
  steps2.forEach((st, i) => {
    rrect(s, { x: x2, y: 4.5, w: st[4], h: 0.6, rectRadius: 0.08, fill: { color: st[1] }, line: { color: st[2], width: 1 } });
    txt(s, st[0], { x: x2, y: 4.5, w: st[4], h: 0.6, fontSize: 11, bold: true, color: st[3], align: "center", valign: "middle" });
    x2 += st[4];
    if (i < 2) { arrow(s, x2 + 0.01, 4.6); x2 += 0.38; }
  });
  note(s, "국민·연구자·지자체가 더 최신의 데이터로 환경영향 검토, 정책 수립, 연구에 활용 — 데이터 개방 품질과 속도가 함께 올라갑니다.", 5.85);
  foot(s, 16);
  s.addNotes("가점 1: 입력 자동화 → 공공데이터 개방 주기 단축 → 국민·연구자·지자체 편익.");
}

// ───────────────────────── 17 국민 서비스 2 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "국민 서비스 개선", ["가점"]);
  h1(s, [["국민이 내는 서류, ", INK], ["국민이 모으는 데이터", BLUE], ["까지", INK]]);
  const cy = 1.9, chh = 3.55, cw2 = (CW - 0.4) / 2;
  infoCard(s, ML, cy, cw2, chh, "▤", "① 대국민 서식 자동화",
    "국민이 제출하는 신청서·참가 신청·설문(수기·스캔 포함)을 자동 DB화 → 민원 처리 대기시간 단축.\n\n접수 창구의 반복 입력이 사라지면, 그 시간은 국민 응대의 질로 돌아갑니다.", {});
  infoCard(s, ML + cw2 + 0.4, cy, cw2, chh, "◫", "② 시민 참여형 조사 확대",
    "시민 모니터링단의 종이 야장·사진 기록을 표준 데이터로 자동 수집 → 국민 참여형 조사(시민과학)의 진입 장벽을 낮춤.\n\n“기록만 해 주세요, 정리는 AI가” — 참여가 늘수록 국가 생태 데이터가 풍부해집니다.", {});
  note(s, "접근성·신속성·편의성 — 공공서비스 만족도를 끌어올리는 구체적이고 즉시 실행 가능한 개선 시나리오입니다.", 5.75);
  foot(s, 17);
  s.addNotes("가점 2: 대국민 서식 자동화(민원 단축), 시민과학 확대(참여 장벽 완화) — 구체 시나리오 2건.");
}

// ───────────────────────── 18 직원 개발 서사 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "개발 이야기", ["창의성"]);
  h1(s, [["이 도구는 ", INK], ["직원이 AI와 함께 직접", BLUE], [" 만들었습니다", INK]]);
  lead(s, "개발자가 아닌 현업 담당자가, AI와 대화하며 기획부터 배포까지 — 예산 0원, 외주 0건.");
  const cy = 2.15, chh = 2.15, cw4 = (CW - 1.5) / 4;
  const steps = [
    ["STEP 1", "업무 불편 정의", "“조사표 수기 입력이\n너무 오래 걸린다”", TINT, TLINE, MUTED],
    ["STEP 2", "AI와 페어 개발", "2주 만에 첫 동작 버전 —\n대화로 기능을 쌓아 감", TINT, TLINE, MUTED],
    ["STEP 3", "현장 검증·개선", "실제 조사표로 시험,\n자동 테스트 100여 건 구축", TINT, TLINE, MUTED],
    ["STEP 4", "포터블 배포", "설치 없이 전 부서가\n쓸 수 있는 완성품", BLUE_BG2, "BCD7FF", BLUE_D],
  ];
  steps.forEach((st, i) => {
    const x = ML + i * (cw4 + 0.5);
    card(s, x, cy, cw4, chh, { fill: { color: st[3] }, line: { color: st[4], width: 1 } });
    txt(s, st[0], { x, y: cy + 0.22, w: cw4, h: 0.26, fontSize: 10, bold: true, color: st[5], align: "center" });
    txt(s, st[1], { x, y: cy + 0.55, w: cw4, h: 0.32, fontSize: 13, bold: true, align: "center", color: i === 3 ? BLUE_D : INK });
    txt(s, st[2], { x: x + 0.12, y: cy + 0.98, w: cw4 - 0.24, h: 1.0, fontSize: 9.5, color: SUB, align: "center", lineSpacing: 13 });
    if (i < 3) arrow(s, x + cw4 + 0.08, cy + 0.85);
  });
  // 다크 인용 카드
  card(s, ML, 4.75, CW, 1.35, { fill: { color: INK }, line: { color: INK, width: 1 } });
  s.addText([
    { text: "“AI를 ", options: { color: "FFFFFF", breakLine: false } },
    { text: "업무에 쓰는 것", options: { color: "9DB8FF", breakLine: false } },
    { text: "을 넘어, AI로 ", options: { color: "FFFFFF", breakLine: false } },
    { text: "업무 도구를 만드는", options: { color: "9DB8FF", breakLine: false } },
    { text: " 조직으로”", options: { color: "FFFFFF", breakLine: false } },
  ], { x: ML + 0.3, y: 4.95, w: CW - 0.6, h: 0.4, fontFace: F, fontSize: 14.5, bold: true, isTextBox: true, margin: 0 });
  txt(s, "이 개발 경험 자체가 복제 가능한 모델입니다 — 각 부서의 불편을, 각 부서가 AI와 함께 해결합니다.",
    { x: ML + 0.3, y: 5.42, w: CW - 0.6, h: 0.35, fontSize: 10.5, color: "C4CAD2" });
  foot(s, 18);
  s.addNotes("차별화 서사: 비개발자 직원이 AI 페어프로그래밍으로 직접 개발 — 대회 취지(AI 조직문화) 정면 부합.");
}

// ───────────────────────── 19 로드맵 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  topbar(s, "확산 계획", ["범용성", "실용성"]);
  h1(s, [["일회성 출품작이 아닌, ", INK], ["확산 로드맵", BLUE]]);
  const cy = 2.0, chh = 3.2, cw3 = (CW - 1.0) / 3;
  const phases = [
    ["1단계 · 완료", "현업 부서 실적용", "실제 조사표로 운영 중 — 템플릿·AI추출·보고서까지 전체 흐름 검증 완료. 자동 테스트 100여 건으로 품질 관리.", GREEN_BG2, "B6EBD2", GREEN],
    ["2단계 · 확산", "유사 서식으로 확대", "인접 부서의 조사·점검 서식에 적용, 표준 항목 사전(항목명·단위·형식) 정리로 데이터 일관성 확보.", "FFFFFF", LINE, MUTED],
    ["3단계 · 정착", "전 기관 배포·연계", "포터블 배포(USB·공유폴더)로 전 부서 보급, 기관 데이터 시스템과 표준 스키마로 연계.", "FFFFFF", LINE, MUTED],
  ];
  phases.forEach((p, i) => {
    const x = ML + i * (cw3 + 0.5);
    card(s, x, cy, cw3, chh, { fill: { color: p[3] }, line: { color: p[4], width: 1.25 } });
    txt(s, p[0], { x: x + 0.25, y: cy + 0.25, w: cw3 - 0.5, h: 0.28, fontSize: 10.5, bold: true, color: p[5] });
    txt(s, p[1], { x: x + 0.25, y: cy + 0.6, w: cw3 - 0.5, h: 0.36, fontSize: 15, bold: true });
    txt(s, p[2], { x: x + 0.25, y: cy + 1.1, w: cw3 - 0.5, h: 1.9, fontSize: 11, color: SUB, lineSpacing: 16 });
    if (i < 2) arrow(s, x + cw3 + 0.08, cy + 1.4);
  });
  note(s, "확산 비용: 프로그램 복사 + 사용법 1장 + 30분 시연. 서버 구축·라이선스 구매가 없어 확산의 장벽 자체가 없습니다.", 5.65);
  foot(s, 19);
  s.addNotes("로드맵 3단계: 완료된 실적용 → 확산 → 전 기관 정착. 확산 비용이 사실상 0임을 강조.");
}

// ───────────────────────── 20 마무리 ─────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  s.addShape("ellipse", { x: W / 2 - 0.75, y: 0.72, w: 0.1, h: 0.1, fill: { color: BLUE }, line: { type: "none" } });
  txt(s, "AutoData", { x: W / 2 - 0.58, y: 0.62, w: 1.4, h: 0.3, fontSize: 12, bold: true, color: BLUE, charSpacing: 1 });
  s.addText([
    { text: "조사는 현장에서,", options: { color: INK, breakLine: true } },
    { text: "입력은 AI가.", options: { color: BLUE, breakLine: false } },
  ], { x: 0, y: 1.15, w: W, h: 1.7, fontFace: F, fontSize: 38, bold: true, align: "center", isTextBox: true, margin: 0, lineSpacing: 46 });
  const cy = 3.35, cw4 = (CW - 0.9) / 4, chh = 1.55;
  const sums = [
    ["실용성", "무설치 완성품,\n오늘 바로 사용", BLUE_D],
    ["효과성", "입력 시간 절감 실측,\n오타 원천 제거", GREEN],
    ["범용성", "표 있는 모든 서식,\n모든 부서로", PURPLE],
    ["국민 서비스", "더 빠른 데이터 개방,\n민원·참여 확대", RED],
  ];
  sums.forEach((m, i) => {
    const x = ML + i * (cw4 + 0.3);
    card(s, x, cy, cw4, chh, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, m[0], { x: x + 0.2, y: cy + 0.2, w: cw4 - 0.4, h: 0.28, fontSize: 11.5, bold: true, color: m[2] });
    txt(s, m[1], { x: x + 0.2, y: cy + 0.55, w: cw4 - 0.4, h: 0.85, fontSize: 10.5, color: SUB, lineSpacing: 15 });
  });
  rrect(s, { x: W / 2 - 2.3, y: 5.45, w: 4.6, h: 0.68, rectRadius: 0.34, fill: { color: INK }, line: { type: "none" } });
  txt(s, "지금 이 자리에서 시연 가능합니다", { x: W / 2 - 2.3, y: 5.45, w: 4.6, h: 0.68, fontSize: 14.5, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
  foot(s, 20);
  s.addNotes("클로징: 4개 심사축 요약 + 라이브 시연 제안으로 마무리.");
}

pres.writeFile({ fileName: "autodata-slides.pptx" }).then(() => console.log("OK autodata-slides.pptx"));
