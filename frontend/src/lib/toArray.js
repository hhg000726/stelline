/* API 가 배열·객체·단일 값 어느 쪽으로 답해도 목록으로 다룬다.
 * (예전 index.js 의 toArray 와 같다. 벅스 순위는 지금도 객체로 온다.) */
export function toArray(value) {
  if (value == null) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "object") return Object.values(value);
  return [value];
}
