/* 서버 API 호출.
 *
 * 예전 assets/site.js 의 Stelline.api 와 같은 규칙을 그대로 쓴다.
 * 엔드포인트와 요청·응답 형식은 하나도 바꾸지 않는다.
 */
export function api(path, options = {}) {
  return fetch(`/api/${String(path).replace(/^\//, "")}`, options);
}

/* 제보 보내기. 세 화면(검색·노래방·조회수 축하)이 같은 형식을 쓴다.
 * 성공하면 서버가 준 message 를, 실패하면 error 를 그대로 보여 준다. */
export async function submitReport(path, content, captchaToken) {
  const response = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, captcha_token: captchaToken }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "제보를 보내지 못했습니다.");
  return result.message;
}
