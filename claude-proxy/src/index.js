/**
 * 현장 조사표 DB화 — Claude API 프록시 (Cloudflare Worker)
 *
 * 목적: 사용자 exe 는 이 Worker 로만 요청한다. 진짜 Claude 키(ANTHROPIC_API_KEY)는
 *       Worker secret 으로만 존재하며 사용자 PC 로 절대 내려가지 않는다.
 *
 * 흐름:  exe (anthropic SDK, base_url=이 Worker, api_key=APP_TOKEN)
 *          → Worker: APP_TOKEN 검증 → 모델/토큰 상한 → 실제 키로 Anthropic 전달
 *
 * 보안 메모:
 *  - 요청 본문(실데이터)은 절대 로깅하지 않는다.
 *  - APP_TOKEN 은 유출되어도 쿼터·레이트리밋으로 피해가 제한되고, 언제든 교체 가능하다.
 *  - 진짜 키는 이 파일/깃/응답 어디에도 노출되지 않는다.
 */

const ANTHROPIC_BASE = "https://api.anthropic.com";

// 허용 모델 화이트리스트 (비용/모델 고정). 필요 시 여기만 수정.
const ALLOWED_MODELS = new Set([
  "claude-opus-4-8",
  "claude-sonnet-4-5",
  "claude-haiku-4-5-20251001",
]);

// 요청당 max_tokens 상한 (비용 방어). 초과 요청은 이 값으로 깎는다.
const MAX_TOKENS_CAP = 8000;

// 지원 버전 헤더 기본값
const DEFAULT_ANTHROPIC_VERSION = "2023-06-01";

export default {
  async fetch(request, env) {
    // 1) POST 만 허용
    if (request.method !== "POST") {
      return json({ error: "Only POST is allowed" }, 405);
    }

    // 2) messages 엔드포인트만 허용 (SDK 는 {base_url}/v1/messages 로 보냄)
    const url = new URL(request.url);
    if (!url.pathname.endsWith("/v1/messages")) {
      return json({ error: "Not found" }, 404);
    }

    // 3) 앱 토큰 인증 (SDK 가 api_key 를 x-api-key 헤더로 전송)
    const presented = request.headers.get("x-api-key") || "";
    if (!env.APP_TOKEN || !timingSafeEqual(presented, env.APP_TOKEN)) {
      return json({ error: "Unauthorized" }, 401);
    }
    if (!env.ANTHROPIC_API_KEY) {
      return json({ error: "Proxy misconfigured: missing upstream key" }, 500);
    }

    // 4) 레이트리밋 (비용 폭주 방어)
    if (env.RATE_LIMITER) {
      const { success } = await env.RATE_LIMITER.limit({ key: "global" });
      if (!success) return json({ error: "Rate limit exceeded" }, 429);
    }

    // 5) 본문 파싱 + 모델/토큰 검증
    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON body" }, 400);
    }
    if (!ALLOWED_MODELS.has(body.model)) {
      return json({ error: `Model not allowed: ${body.model ?? "(none)"}` }, 403);
    }
    if (typeof body.max_tokens === "number" && body.max_tokens > MAX_TOKENS_CAP) {
      body.max_tokens = MAX_TOKENS_CAP;
    }

    // 6) 실제 키로 업스트림 전달 (본문 로깅 없음)
    const fwdHeaders = {
      "content-type": "application/json",
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version":
        request.headers.get("anthropic-version") || DEFAULT_ANTHROPIC_VERSION,
    };
    const beta = request.headers.get("anthropic-beta");
    if (beta) fwdHeaders["anthropic-beta"] = beta;

    let upstream;
    try {
      upstream = await fetch(ANTHROPIC_BASE + "/v1/messages", {
        method: "POST",
        headers: fwdHeaders,
        body: JSON.stringify(body),
      });
    } catch (e) {
      return json({ error: "Upstream request failed" }, 502);
    }

    // 7) 응답 그대로 전달 (스트리밍/SSE 포함)
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") || "application/json",
      },
    });
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// 상수시간 문자열 비교 (토큰 타이밍 공격 방어)
function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}
