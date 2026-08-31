// 오토다타 — 시나리오형 피칭 덱 (자문 반영: 빙의 오프닝·정량 핵심·데모 중심·4분 종료)
// 11장. 장면 슬라이드=다크(시네마틱), 도구 슬라이드=화이트(제품 톤). 커버·아젠다 없음.
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
const W = 13.333, H = 7.5;

const INK = "191F28", MUTED = "8B95A1", SUB = "6B7684", LINE = "E5E8EB",
  BLUE = "3182F6", BLUE_D = "1B64DA", BLUE_BG = "EAF3FF", BLUE_BG2 = "F0F6FF",
  GREEN = "04915A", GREEN_BG2 = "F4FCF8", RED = "F04452", RED_D = "D6303F",
  AMBER = "F59F00", TINT = "F7F8FA", TLINE = "EEF1F4", GRIDL = "D5DAE0", CELL = "F2F4F6";
const F = "Malgun Gothic";
const ML = 0.75, CW = W - ML * 2;

function txt(s, str, o) {
  s.addText(str, Object.assign({ fontFace: F, color: INK, isTextBox: true, margin: 0, align: "left", valign: "top" }, o));
}
function rect(s, o) { s.addShape("rect", o); }
function rrect(s, o) { s.addShape("roundRect", Object.assign({ rectRadius: 0.08 }, o)); }
function card(s, x, y, w, h, opts) {
  rrect(s, Object.assign({ x, y, w, h, fill: { color: "FFFFFF" }, line: { color: LINE, width: 1 } }, opts || {}));
}
function arrow(s, x, y, color) {
  txt(s, "→", { x, y, w: 0.4, h: 0.45, fontSize: 22, bold: true, color: color || "C4CAD2", align: "center", valign: "middle" });
}

// ── 1. 오프닝 장면 (다크·후킹) ─────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "14181F" };
  txt(s, "금요일 오후 5시 50분.", { x: 0, y: 2.0, w: W, h: 1.0, fontSize: 44, bold: true, color: "FFFFFF", align: "center", charSpacing: -1 });
  txt(s, "출장 조사에서 돌아온 책상 위, 조사표 서른 장.", { x: 0, y: 3.2, w: W, h: 0.5, fontSize: 17, color: "9DA5B4", align: "center" });
  txt(s, "“…이걸 오늘 다 입력해야 하는데.”", { x: 0, y: 4.3, w: W, h: 0.7, fontSize: 24, italic: true, color: "E8B4B8", align: "center" });
  s.addNotes("[연기 톤으로 시작 — 화면만 띄우고 3초 침묵 후]\n\"금요일 오후 5시 50분이었습니다. 출장에서 막 돌아왔는데, 책상 위에 조사표가 서른 장 쌓여 있었어요.\"\n(오토다타·도구 이름 언급 금지. 청중을 '그 날'로 데려가는 것이 목적)");
}

// ── 2. 사고 장면 (다크) ───────────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "14181F" };
  txt(s, "밤 8시, 두 시간째.", { x: 0, y: 1.7, w: W, h: 0.9, fontSize: 40, bold: true, color: "FFFFFF", align: "center", charSpacing: -1 });
  txt(s, "“어… 이 줄, 잘못 옮겨 적었다.”", { x: 0, y: 2.9, w: W, h: 0.7, fontSize: 26, italic: true, color: "E8B4B8", align: "center" });
  txt(s, "“어디서부터 틀렸지?”", { x: 0, y: 3.7, w: W, h: 0.7, fontSize: 26, italic: true, color: "E8B4B8", align: "center" });
  txt(s, "오타 하나 → 처음부터 전부 다시 대조.", { x: 0, y: 5.0, w: W, h: 0.5, fontSize: 16, color: "9DA5B4", align: "center" });
  s.addNotes("\"두 시간을 쳤는데, 한 줄이 밀려 있었습니다. 어디서부터 틀렸는지 몰라서 — 처음부터 다시 대조했습니다.\"\n(수작업의 진짜 고통 = 시간이 아니라 '오류 후 되감기'라는 점을 체감시킴)");
}

// ── 3. 우리 모두의 이야기 (라이트·정량) ────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "누구에게나 있는 밤입니다", { x: ML, y: 0.75, w: CW, h: 0.7, fontSize: 32, bold: true, charSpacing: -0.5 });
  txt(s, "우리 원의 하천·습지 정밀조사만 헤아려도 —", { x: ML, y: 1.55, w: CW, h: 0.4, fontSize: 15, color: SUB });
  const cy = 2.3, ch = 2.6, cw3 = (CW - 0.8) / 3;
  const facts = [
    ["49개", "하천 조사 대상지", "해마다 반복되는 정밀조사"],
    ["연간 __건", "수작업 입력 조사표", "발표 전 실제 건수 기입"],
    ["약 2시간", "조사표 1건 입력 시간", "옮겨 적기 + 검산 + 오류 되감기"],
  ];
  facts.forEach((f2, i) => {
    const x = ML + i * (cw3 + 0.4);
    card(s, x, cy, cw3, ch, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, f2[0], { x, y: cy + 0.5, w: cw3, h: 0.8, fontSize: 40, bold: true, color: BLUE_D, align: "center", charSpacing: -1 });
    txt(s, f2[1], { x, y: cy + 1.45, w: cw3, h: 0.4, fontSize: 14.5, bold: true, align: "center" });
    txt(s, f2[2], { x, y: cy + 1.9, w: cw3, h: 0.5, fontSize: 11, color: SUB, align: "center" });
  });
  txt(s, "조사는 하루, 입력은 며칠 — 그리고 이 시간은 어떤 성과로도 남지 않습니다.", { x: ML, y: 5.4, w: CW, h: 0.5, fontSize: 15, bold: true, align: "center", color: SUB });
  s.addNotes("\"저만의 이야기가 아닙니다. 우리 원 49개 하천 조사를 비롯해, 연간 __건의 조사표가 이렇게 손으로 입력됩니다. 1건에 약 2시간.\"\n(__건은 발표 전 실측·확인해 기입)");
}

// ── 4. 도구 정의 한 문장 (라이트·크게) ─────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "그래서, 만들었습니다.", { x: 0, y: 1.15, w: W, h: 0.6, fontSize: 20, color: SUB, align: "center" });
  s.addText([
    { text: "양식을 올리면, ", options: { color: INK, breakLine: true } },
    { text: "실제 문서 그대로 보여주고", options: { color: INK, breakLine: true } },
    { text: "추출 박스를 자동으로 만듭니다.", options: { color: BLUE, breakLine: false } },
  ], { x: 0, y: 2.0, w: W, h: 2.6, fontFace: F, fontSize: 40, bold: true, align: "center", isTextBox: true, margin: 0, lineSpacing: 56, charSpacing: -1 });
  txt(s, "박스를 확인만 하면 — 수백 장이 엑셀 데이터가 됩니다.", { x: 0, y: 4.9, w: W, h: 0.5, fontSize: 17, color: SUB, align: "center" });
  txt(s, "(도구 이름은 잠시 뒤에 소개하겠습니다)", { x: 0, y: 6.3, w: W, h: 0.4, fontSize: 12, color: MUTED, align: "center", italic: true });
  s.addNotes("자문 핵심: 이 문장이 도구의 정의. 천천히, 또박또박.\n\"양식을 올리면 — 실제 문서를 그대로 보여주고 — 추출 박스를 자동으로 만듭니다.\"");
}

// ── 5. 라이브 데모 배경판 ─────────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "지금, 직접 보여드리겠습니다", { x: ML, y: 0.85, w: CW, h: 0.7, fontSize: 32, bold: true, charSpacing: -0.5 });
  const cy = 2.1, ch = 3.3, cw3 = (CW - 0.9) / 3;
  const steps = [
    ["1", "양식 업로드", "실제 조사표가 화면에 뜨고\n추출 박스가 자동 생성", BLUE_BG2, "BCD7FF"],
    ["2", "100페이지도 그대로", "스크롤 한 번으로 확인 —\n분량이 늘어도 같은 방식", TINT, TLINE],
    ["3", "일괄 처리 → 엑셀", "조사표 여러 개 →\n요약 DB + 보고서 완성", GREEN_BG2, "B6EBD2"],
  ];
  steps.forEach((st, i) => {
    const x = ML + i * (cw3 + 0.45);
    card(s, x, cy, cw3, ch, { fill: { color: st[3] }, line: { color: st[4], width: 1.25 } });
    s.addShape("ellipse", { x: x + cw3 / 2 - 0.35, y: cy + 0.4, w: 0.7, h: 0.7, fill: { color: INK }, line: { type: "none" } });
    txt(s, st[0], { x: x + cw3 / 2 - 0.35, y: cy + 0.4, w: 0.7, h: 0.7, fontSize: 24, bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    txt(s, st[1], { x, y: cy + 1.35, w: cw3, h: 0.45, fontSize: 17, bold: true, align: "center" });
    txt(s, st[2], { x: x + 0.2, y: cy + 1.9, w: cw3 - 0.4, h: 1.1, fontSize: 12, color: SUB, align: "center", lineSpacing: 17 });
    if (i < 2) arrow(s, x + cw3 + 0.03, cy + 1.45);
  });
  txt(s, "※ 시연은 실제 프로그램 화면으로 진행합니다", { x: ML, y: 5.75, w: CW, h: 0.4, fontSize: 12, color: MUTED, align: "center" });
  s.addNotes("[이 슬라이드를 띄운 채 실제 프로그램으로 전환]\n데모 큐: ① 양식 업로드 → 박스 자동 생성(핵심 쇼트) ② 스크롤 쭉 내려 '100페이지 넘어도 됩니다' 퍼포먼스 ③ 미리 준비한 조사표 5건 일괄 처리 → 엑셀 열기(대기 시간 방지: 5건 이내로)\n[장비 사고 대비: 백업 시연 영상 준비]");
}

// ── 6. 2시간 → 5분 (정량 대비·보고서 쇼잉) ─────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  s.addText([
    { text: "2시간", options: { color: RED_D, breakLine: false } },
    { text: "  →  ", options: { color: MUTED, breakLine: false } },
    { text: "5분", options: { color: BLUE, breakLine: false } },
  ], { x: 0, y: 0.7, w: W, h: 1.1, fontFace: F, fontSize: 56, bold: true, align: "center", isTextBox: true, margin: 0, charSpacing: -1 });
  const cy = 2.15, ch = 3.35, cw2 = (CW - 0.6) / 2;
  // 좌: 기존
  card(s, ML, cy, cw2, ch, { line: { color: "F5C6CB", width: 1.25 } });
  txt(s, "기존 — 손으로 만든 보고서", { x: ML + 0.25, y: cy + 0.2, w: cw2 - 0.5, h: 0.35, fontSize: 13.5, bold: true, color: RED_D });
  const manual = ["조사표 보고 한 칸씩 입력", "계산기로 합계·평균 검산", "보고서 양식에 다시 옮겨 붙임", "오타 나면 처음부터 대조"];
  manual.forEach((m, i) => {
    txt(s, "· " + m, { x: ML + 0.3, y: cy + 0.75 + i * 0.5, w: cw2 - 0.6, h: 0.4, fontSize: 12.5, color: SUB });
  });
  txt(s, "약 2시간 / 1건", { x: ML + 0.25, y: cy + ch - 0.55, w: cw2 - 0.5, h: 0.35, fontSize: 14, bold: true, color: RED_D });
  // 우: 오토다타
  const rx = ML + cw2 + 0.6;
  card(s, rx, cy, cw2, ch, { fill: { color: BLUE_BG2 }, line: { color: "BCD7FF", width: 1.25 } });
  txt(s, "오토다타 — 같은 보고서, 자동으로", { x: rx + 0.25, y: cy + 0.2, w: cw2 - 0.5, h: 0.35, fontSize: 13.5, bold: true, color: BLUE_D });
  const autoL = ["파일 올리고 버튼 하나", "요약 DB + 보고서 시트 동시 생성", "합계·평균 수식 자동 계산", "우리가 실제 쓰는 보고서와 거의 동일한 형태"];
  autoL.forEach((m, i) => {
    txt(s, "· " + m, { x: rx + 0.3, y: cy + 0.75 + i * 0.5, w: cw2 - 0.6, h: 0.45, fontSize: 12.5, color: SUB });
  });
  txt(s, "약 5분 / 수십 건", { x: rx + 0.25, y: cy + ch - 0.55, w: cw2 - 0.5, h: 0.35, fontSize: 14, bold: true, color: BLUE_D });
  txt(s, "결과물이 '지금 쓰는 그 보고서'로 나온다는 것 — 도구를 믿게 되는 순간입니다.", { x: ML, y: 5.85, w: CW, h: 0.4, fontSize: 13, bold: true, align: "center", color: SUB });
  s.addNotes("[시연 직후] \"방금 보신 그대로입니다. 1건 2시간이 — 수십 건 5분이 됐습니다.\"\n가능하면 여기서 '실제 쓰는 보고서 양식으로 출력된 엑셀'을 화면에 잠깐 띄워 대비(쇼잉).\n(2시간/5분은 발표 전 실측으로 최종 확인)");
}

// ── 6.5 가장 공들인 것 — 믿을 수 있는 자동화 (신뢰 후킹) ────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "가장 공을 들인 것 — “믿을 수 있는 자동화”", { x: ML, y: 0.75, w: CW, h: 0.65, fontSize: 30, bold: true, charSpacing: -0.5 });
  txt(s, "자동화의 적은 ‘못 미더움’입니다. 그래서 속도보다 정확에 공을 들였습니다.", { x: ML, y: 1.5, w: CW, h: 0.4, fontSize: 15, color: SUB });
  const cy = 2.15, ch = 1.5, cw2 = (CW - 0.5) / 2, gap = 0.5;
  const feats = [
    ["📌", "줄이 밀려도 정확", "칸 이름(라벨)을 따라가 값을 찾습니다 —\n서식에 줄이 늘어도 어긋나지 않습니다"],
    ["🚧", "남의 글자 차단", "칸 경계를 벗어난 글자는 값에 섞이지\n않게 잘라냅니다 — 혼입 원천 차단"],
    ["📑", "양식 자동 분류", "문서의 제목을 읽고 같은 양식끼리\n알아서 시트로 나눠 쌓습니다"],
    ["⚠️", "스스로 경고", "튀는 값은 엑셀에서 주황 표시 + 사유\n메모 — 오타·오추출을 스스로 잡습니다"],
  ];
  feats.forEach((f2, i) => {
    const x = ML + (i % 2) * (cw2 + gap);
    const y = cy + Math.floor(i / 2) * (ch + 0.3);
    card(s, x, y, cw2, ch, { fill: { color: TINT }, line: { color: TLINE, width: 1 } });
    txt(s, f2[0], { x: x + 0.25, y: y + 0.3, w: 0.55, h: 0.55, fontSize: 22 });
    txt(s, f2[1], { x: x + 0.9, y: y + 0.22, w: cw2 - 1.1, h: 0.4, fontSize: 15.5, bold: true });
    txt(s, f2[2], { x: x + 0.9, y: y + 0.66, w: cw2 - 1.1, h: 0.75, fontSize: 11.5, color: SUB, lineSpacing: 16 });
  });
  txt(s, "사람은 표시된 것만 확인하면 됩니다 — ‘처음부터 다시 대조하는 밤’이 사라집니다.", { x: ML, y: 5.85, w: CW, h: 0.45, fontSize: 14.5, bold: true, align: "center", color: SUB });
  s.addNotes("[시연 직후 신뢰 굳히기 — 25초]\n\"빠른 건 방금 보셨습니다. 저희가 정말 공들인 건 '믿을 수 있느냐'입니다. 서식이 밀려도 칸 이름을 따라가고, 칸 밖 글자는 잘라내고, 양식을 스스로 분류하고, 이상한 값은 스스로 경고합니다. 그래서 사람은 표시된 것만 확인하면 됩니다.\"\n(기술 용어 금지 — 효과로만 말하기)");
}

// ── 7. AI 해석까지 (밸류 완성) ─────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "입력이 끝이 아닙니다 — AI가 해석까지", { x: ML, y: 0.85, w: CW, h: 0.7, fontSize: 30, bold: true, charSpacing: -0.5 });
  const cy = 2.05, ch = 3.4, cw2 = (CW - 0.6) / 2;
  card(s, ML, cy, cw2, ch, { fill: { color: "FFFBEF" }, line: { color: "F5DEA6", width: 1.25 } });
  txt(s, "⚠ 이상한 값을 스스로 찾아냅니다", { x: ML + 0.25, y: cy + 0.25, w: cw2 - 0.5, h: 0.4, fontSize: 15, bold: true, color: AMBER });
  rrect(s, { x: ML + 0.3, y: cy + 0.85, w: cw2 - 0.6, h: 0.85, rectRadius: 0.06, fill: { color: "FFFFFF" }, line: { color: "F5DEA6", width: 1 } });
  s.addText([
    { text: "⚠ 보 길이 349m", options: { bold: true, color: "A06F00", breakLine: true } },
    { text: "다른 조사표 평균 25m의 14배 — 확인 필요", options: { color: SUB, breakLine: false } },
  ], { x: ML + 0.5, y: cy + 1.0, w: cw2 - 1.0, h: 0.6, fontFace: F, fontSize: 11.5, isTextBox: true, margin: 0, lineSpacing: 16 });
  txt(s, "오타·오추출 의심 값을 자동 경고 —\n사람은 표시된 것만 확인하면 됩니다.", { x: ML + 0.25, y: cy + 2.0, w: cw2 - 0.5, h: 0.9, fontSize: 12.5, color: SUB, lineSpacing: 18 });
  card(s, ML + cw2 + 0.6, cy, cw2, ch, { fill: { color: GREEN_BG2 }, line: { color: "B6EBD2", width: 1.25 } });
  txt(s, "📈 쌓인 데이터로 인사이트", { x: ML + cw2 + 0.85, y: cy + 0.25, w: cw2 - 0.5, h: 0.4, fontSize: 15, bold: true, color: GREEN });
  txt(s, "회차가 쌓일수록 추세가 보입니다.\n\nAI가 조사 결과를 요약하고, 눈에 띄는 변화와 점검 포인트를 짚어 줍니다 — 데이터 입력이 곧 분석의 시작이 됩니다.", { x: ML + cw2 + 0.85, y: cy + 0.85, w: cw2 - 1.1, h: 2.2, fontSize: 12.5, color: SUB, lineSpacing: 18 });
  s.addNotes("\"입력 자동화로 끝나지 않습니다. 이상치를 스스로 찾아 경고하고, 쌓인 데이터는 AI가 해석해 줍니다.\" (밸류 체인 완성 — 짧게 30초)");
}

// ── 8. 연간 절감 (정량 핵심) ───────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "연간으로 계산하면", { x: ML, y: 0.85, w: CW, h: 0.7, fontSize: 32, bold: true, charSpacing: -0.5 });
  card(s, ML, 2.1, CW, 2.6, { fill: { color: BLUE_BG2 }, line: { color: "BCD7FF", width: 1.25 } });
  s.addText([
    { text: "연간 __건", options: { color: INK, breakLine: false } },
    { text: "  ×  ", options: { color: MUTED, breakLine: false } },
    { text: "건당 약 1시간 55분 절감", options: { color: INK, breakLine: false } },
  ], { x: 0, y: 2.55, w: W, h: 0.6, fontFace: F, fontSize: 24, bold: true, align: "center", isTextBox: true, margin: 0 });
  s.addText([
    { text: "= 약 __시간", options: { color: BLUE_D, breakLine: false } },
    { text: "  (≈ 근무일 __일)", options: { color: SUB, breakLine: false } },
  ], { x: 0, y: 3.4, w: W, h: 0.9, fontFace: F, fontSize: 40, bold: true, align: "center", isTextBox: true, margin: 0, charSpacing: -1 });
  txt(s, "그 시간은 입력이 아니라 — 조사와 분석으로 돌아갑니다.", { x: 0, y: 5.1, w: W, h: 0.5, fontSize: 16, bold: true, align: "center", color: SUB });
  txt(s, "※ 수치는 표본 10건 실측 기준(발표 전 확정 기입) — 추정 배수가 아닌 실측 절대값만 제시", { x: 0, y: 6.15, w: W, h: 0.4, fontSize: 10.5, color: MUTED, align: "center" });
  s.addNotes("빈칸(__건, __시간, __일)은 발표 전 실측·기관 실적으로 확정 기입.\n\"이 시간이 전부 조사와 분석으로 돌아갑니다\" — 절감의 '용도'까지 말해야 설득 완성.");
}

// ── 9. 국민에게 확산되면 (국민 서비스 개선 — 가점 후킹) ─────
{
  const s = pres.addSlide(); s.background = { color: "FFFFFF" };
  txt(s, "국민에게 확산되면", { x: ML, y: 0.7, w: CW, h: 0.65, fontSize: 32, bold: true, charSpacing: -0.5 });
  txt(s, "표가 있는 서식이면 어디든 — 개발 없이 템플릿만 만들면 됩니다. 원내 점검표·설문·관리대장은 즉시, 그리고 —", { x: ML, y: 1.45, w: CW, h: 0.4, fontSize: 14, color: SUB });
  const cy = 2.05, ch = 2.5, cw3 = (CW - 0.8) / 3;
  const cases = [
    ["🏥", "보건소·병원", "수기 문진표·검사 기록지를\n자동 전산화", "접수 대기가 짧아지고,\n기록 오류가 줄어듭니다", BLUE_BG2, "BCD7FF", BLUE_D],
    ["🏛", "지자체 현장 민원", "현장 점검 서식을 그 자리에서\n데이터로", "민원 처리·회신이\n빨라집니다", GREEN_BG2, "B6EBD2", GREEN],
    ["🏫", "학교·복지시설", "안전점검 기록을 쌓아\n이상 신호를 조기에", "사고를 데이터로\n예방합니다", "FFFBEF", "F5DEA6", "A06F00"],
  ];
  cases.forEach((c2, i) => {
    const x = ML + i * (cw3 + 0.4);
    card(s, x, cy, cw3, ch, { fill: { color: c2[4] }, line: { color: c2[5], width: 1.25 } });
    txt(s, c2[0], { x, y: cy + 0.25, w: cw3, h: 0.5, fontSize: 24, align: "center" });
    txt(s, c2[1], { x, y: cy + 0.8, w: cw3, h: 0.4, fontSize: 15.5, bold: true, align: "center" });
    txt(s, c2[2], { x: x + 0.2, y: cy + 1.22, w: cw3 - 0.4, h: 0.6, fontSize: 11.5, color: SUB, align: "center", lineSpacing: 16 });
    txt(s, c2[3], { x: x + 0.2, y: cy + 1.85, w: cw3 - 0.4, h: 0.55, fontSize: 12, bold: true, color: c2[6], align: "center", lineSpacing: 16 });
  });
  rrect(s, { x: ML, y: 4.85, w: CW, h: 0.62, rectRadius: 0.08, fill: { color: TINT }, line: { color: TLINE, width: 1 } });
  txt(s, "🔒 완전 로컬 + 무료 — 자료가 컴퓨터 밖으로 나가지 않아, 민감정보를 다루는 공공·의료 현장에도 안심하고 확산할 수 있습니다.", { x: ML + 0.25, y: 4.98, w: CW - 0.5, h: 0.4, fontSize: 12.5, color: SUB });
  txt(s, "공공의 종이가 데이터가 되는 속도만큼 — 국민이 기다리는 시간이 줄어듭니다.", { x: ML, y: 5.8, w: CW, h: 0.45, fontSize: 15, bold: true, align: "center" });
  s.addNotes("[국민 서비스 개선 — 30초]\n\"이건 조사표만의 이야기가 아닙니다. 보건소 문진표, 지자체 현장 민원 서식, 학교 안전점검 — 종이와 엑셀 사이에서 시간을 잃는 모든 공공 현장이 대상입니다. 자료가 컴퓨터 밖으로 안 나가는 로컬 방식이라 민감한 현장에도 그대로 확산할 수 있습니다. 공공의 종이가 데이터가 되는 속도만큼, 국민이 기다리는 시간이 줄어듭니다.\"\n(마지막 문장은 또박또박 — 이 슬라이드의 후킹 라인)");
}

// ── 10. 이름 공개 (다크) ───────────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "14181F" };
  txt(s, "이 도구의 이름은", { x: 0, y: 1.5, w: W, h: 0.5, fontSize: 18, color: "9DA5B4", align: "center" });
  s.addText([
    { text: "Auto", options: { color: "9DB8FF", breakLine: false } },
    { text: " + ", options: { color: "5A6270", breakLine: false } },
    { text: "Data", options: { color: "9DB8FF", breakLine: false } },
  ], { x: 0, y: 2.15, w: W, h: 0.9, fontFace: F, fontSize: 40, bold: true, align: "center", isTextBox: true, margin: 0 });
  txt(s, "오토다타", { x: 0, y: 3.15, w: W, h: 1.1, fontSize: 60, bold: true, color: "FFFFFF", align: "center", charSpacing: -1.5 });
  txt(s, "자동으로(Auto), 데이터를(Data) 뽑아내는 도구 —\n오늘 보신 모든 것이 이 이름 안에 있습니다.", { x: 0, y: 4.55, w: W, h: 0.9, fontSize: 15, color: "9DA5B4", align: "center", lineSpacing: 22 });
  s.addNotes("자문 반영: 이름은 마지막에. \"자동으로 데이터를 뽑는다 — 그래서 오토다타입니다.\" (10초)");
}

// ── 11. 클로징 (다크) ──────────────────────────────────────
{
  const s = pres.addSlide(); s.background = { color: "14181F" };
  s.addText([
    { text: "조사는 현장에서,", options: { color: "FFFFFF", breakLine: true } },
    { text: "입력은 AI가.", options: { color: "9DB8FF", breakLine: false } },
  ], { x: 0, y: 2.3, w: W, h: 2.0, fontFace: F, fontSize: 46, bold: true, align: "center", isTextBox: true, margin: 0, lineSpacing: 58, charSpacing: -1 });
  txt(s, "종이와 엑셀 사이에서 사라지던 시간을 — 현장과 국민에게 돌려드리겠습니다.", { x: 0, y: 4.75, w: W, h: 0.5, fontSize: 16, color: "C8CEDA", align: "center" });
  txt(s, "들어주셔서 감사합니다 — 질문 주시면 바로 시연으로 답하겠습니다.", { x: 0, y: 5.45, w: W, h: 0.5, fontSize: 14, color: "9DA5B4", align: "center" });
  s.addNotes("4분 30초 안에 여기 도착이 목표. 남는 시간은 전부 질의응답 — 질문이 나오면 말 대신 화면으로 시연하며 답변.\n기술 질문 대응: \"발표에선 사용성 위주로 보여드렸고, 내부 구조는 별도로 정리해 두었습니다\" 한 줄로 정리 후 비즈니스로 복귀.");
}

pres.writeFile({ fileName: "autodata-pitch.pptx" }).then(() => console.log("OK autodata-pitch.pptx"));
