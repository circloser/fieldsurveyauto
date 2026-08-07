# Claude API 프록시 (Cloudflare Worker)

현장 조사표 DB화 프로그램이 쓰는 **Claude API 프록시**입니다.
진짜 API 키는 이 서버(Worker)에만 보관되고, 사용자 exe·팀원 PC로는 절대 내려가지 않습니다.

```
사용자 exe ──(APP_TOKEN)──▶ 이 Worker ──(진짜 키)──▶ Claude API
                            └ 키는 여기서만 존재
```

## 배포 방법 (GitHub 불필요, 로컬에서 바로)

터미널에서 이 폴더(`claude-proxy`)로 이동한 뒤:

```bash
# 1) 의존성 설치 (최초 1회)
npm install

# 2) Cloudflare 로그인 (브라우저 열림, 최초 1회)
npx wrangler login

# 3) 시크릿 2개 등록 (값은 프롬프트에 붙여넣기 — 화면/깃에 안 남음)
npx wrangler secret put ANTHROPIC_API_KEY   # 진짜 Claude 키
npx wrangler secret put APP_TOKEN           # 아무 긴 랜덤 문자열

# 4) 배포
npx wrangler deploy
```

배포가 끝나면 `https://field-survey-claude-proxy.<계정서브도메인>.workers.dev` 형태의 주소가 출력됩니다.
이 주소가 프로그램에서 쓸 **base_url** 입니다.

## 프로그램(exe) 연결 방법

Python 쪽 anthropic 클라이언트를 이렇게 바꾸면 됩니다:

```python
import anthropic
client = anthropic.Anthropic(
    base_url="https://field-survey-claude-proxy.<서브도메인>.workers.dev",
    api_key="<APP_TOKEN 값>",   # 진짜 키가 아니라 앱 토큰
)
```

> 실제 연동은 Phase 1에서 `core/llm_understand.py` 와 새 Vision 추출 코드에 반영합니다.

## 로컬 테스트

```bash
cp .dev.vars.example .dev.vars   # 값 채우기
npx wrangler dev                 # http://localhost:8787 에서 프록시 동작
```

## 안전장치 (index.js)
- **APP_TOKEN 인증** — 없거나 틀리면 401
- **모델 화이트리스트** — 허용 모델 외 403 (`ALLOWED_MODELS`)
- **max_tokens 상한** — 초과 시 자동으로 깎음 (`MAX_TOKENS_CAP`)
- **레이트리밋** — 60초당 60건 (`wrangler.jsonc` 의 `ratelimits`)
- **본문 로깅 없음** — 실데이터는 통과만, 저장 안 함

## 운영 팁
- 앱 토큰 유출 의심 시: `npx wrangler secret put APP_TOKEN` 으로 새 값 넣고 exe 재배포 → 옛 토큰 즉시 무효.
- 로그 보기: `npx wrangler tail`
- 삭제: `npx wrangler delete`
