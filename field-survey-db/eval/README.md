# 정확도 평가 (Phase 2)

Vision 추출이 "우연히 잘 된 1건"이 아니라 **N건에서 정확도 X%** 임을 숫자로 증명하는 폴더.

## 골드셋 형식 (`eval/gold/*.json`)

파일 하나 = 한 페이지의 정답.

```json
{
  "file": "tests/fixtures/sample.pdf",   // 프로젝트 루트 기준 상대경로
  "form": "artificial_structure",         // 서식 코드 (A=artificial_structure, C=fishway)
  "page": 0,                               // 0부터
  "verified": true,                        // 사람이 실제 양식과 대조해 확인했는가
  "numeric_tol": 0.0,                      // 숫자 필드 허용 오차(선택)
  "values": { "하천명": "해남천", "보길이": "30", ... }
}
```

## 정답(gold) 만드는 방법 — "AI 초안 → 사람 검증"

1. `scripts/try_vision.py` 로 한 페이지 뽑아 나온 JSON을 `values` 에 붙여넣어 **초안** 생성 (`verified: false`).
2. **사람(도메인 전문가)이 실제 양식과 대조**해 틀린 값 수정.
3. 다 맞으면 `verified: true` 로 변경.

> ⚠️ `verified: false` 인 골드로 낸 정확도는 **자기참조(잠정)** 라 신뢰할 수 없습니다.
> 대회에 쓸 수치는 반드시 `verified: true` 골드에서 나와야 합니다.

## 실행

```bash
# 프록시 환경변수 설정 후
.venv/Scripts/python.exe eval/run_eval.py
```

→ 콘솔에 파일별·서식별·전체 정확도 + 틀린 필드 목록, `eval/REPORT.md` 저장.

## 좋은 골드셋 구성 (대회용)
- 서식 A/C 각 여러 건, **텍스트 PDF + 스캔/손글씨** 혼합.
- **틀어진 변형본**(밀림·줄추가)과 **제목만 다른 변형본** 포함 → 강건성까지 정량화.
- 20~30건이면 설득력 충분.
