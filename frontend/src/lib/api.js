/* 서버 API 호출.
 *
 * 예전 assets/site.js 의 Stelline.api 와 같은 규칙을 그대로 쓴다.
 * 엔드포인트와 요청·응답 형식은 하나도 바꾸지 않는다.
 */
export function api(path, options = {}) {
  return fetch(`/api/${String(path).replace(/^\//, "")}`, options);
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
