/* 서버 API 호출.
 *
 * 예전 assets/site.js 의 Stelline.api 와 같은 규칙을 그대로 쓴다.
 * 엔드포인트와 요청·응답 형식은 하나도 바꾸지 않는다.
 */
export function api(path, options = {}) {
  return fetch(`/api/${String(path).replace(/^\//, "")}`, options);
}

/* 문서 머리(index.html)가 미리 부른 응답을 이만큼 지나면 버리고 새로 부른다.
 * 그 응답은 문서를 열 때 받은 것이라, 화면을 한참 오간 뒤에 꺼내 쓰면 옛 값이다. */
const EARLY_MAX_AGE_MS = 10000;

/* 문서 머리의 스크립트가 번들을 받는 동안 먼저 불러 둔 응답을 한 번만 꺼낸다. 없으면 null. */
function takeEarlyResponse(key) {
  const store = window.__stellineEarly;
  const entry = store && store[key];
  if (!entry) return null;
  delete store[key];
  return Date.now() - entry.at <= EARLY_MAX_AGE_MS ? entry.response : null;
}

/* 읽기 전용 GET 하나를 JSON 으로 받는다. 화면이 데이터를 받는 길은 모두 이것 하나다.
 *
 * - 들어온 화면의 데이터는 문서 머리가 이미 부르고 있다. 그 응답이 있으면 기다렸다 쓰고,
 *   그 요청이 실패했으면 여기서 다시 부른다. 그래서 번들·화면 조각·데이터가 한꺼번에 내려온다.
 * - 실패 응답({"error": …})을 데이터로 받지 않는다. 받으면 오류 문구가 카드 한 장으로 그려지거나,
 *   "목록이 비었다"처럼 틀린 말을 하게 된다. 부르는 쪽은 실패를 실패로 보여 준다.
 */
export async function getJson(path) {
  const key = String(path).replace(/^\//, "");
  const early = takeEarlyResponse(key);
  const response = (early && (await early.catch(() => null))) || (await api(key));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

/* 제보 보내기. 세 화면(검색·노래방·조회수 축하)이 같은 형식을 쓴다.
 * 성공하면 서버가 준 message 를, 실패하면 error 를 그대로 보여 준다.
 *
 * 앱까지 닿지 못한 실패(배포 중 502, 프록시의 시간 초과 등)는 JSON 이 아니라 HTML 이 온다.
 * 그대로 읽으면 "Unexpected token '<'" 같은 브라우저 문구가 사용자에게 보였다. */
export async function submitReport(path, content, captchaToken) {
  const response = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, captcha_token: captchaToken }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "제보를 보내지 못했습니다. 잠시 후 다시 시도하세요.");
  return result.message || "제보가 접수되었습니다.";
}
