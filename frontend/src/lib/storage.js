/* localStorage 는 사생활 보호 모드나 저장 공간이 꽉 찬 환경에서 읽기·쓰기 모두 예외를 던진다.
 * 화면은 저장소를 못 써도 그대로 동작해야 하므로 여기서 전부 삼킨다. */
export function readStore(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (error) {
    return fallback;
  }
}

export function writeStore(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    /* 저장이 막힌 환경에서도 이번 방문 동안은 그대로 쓴다. */
  }
}
