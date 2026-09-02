/* React 는 그리는 값을 알아서 글자로만 남긴다. 이 함수가 필요한 곳은 딱 하나,
 * 네이버 지도 말풍선처럼 HTML 문자열을 그대로 넘겨야 하는 자리다.
 * (예전 assets/site.js 의 escapeHtml 과 같은 표를 쓴다. 따옴표 두 종류까지 막아
 *  속성값에 그대로 넣어도 안전하다. 마지막은 줄바꿈 없는 공백 U+00A0 이다.) */
const ENTITIES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
  " ": "&nbsp;",
};

const ESCAPE_RE = /[&<>"' ]/g;

export function escapeHtml(value) {
  return String(value ?? "").replace(ESCAPE_RE, (character) => ENTITIES[character]);
}
