/* 클립보드 복사.
 *
 * navigator.clipboard 는 https 가 아니거나 권한이 막히면 조용히 실패한다.
 * 그때 아무 일도 일어나지 않으면 눌러도 안 된다고만 느끼므로,
 * 예전 방식으로 한 번 더 시도하고 성공 여부를 돌려준다. (assets/site.js 와 같은 동작)
 */
export async function copyText(text) {
  const value = String(text == null ? "" : text);
  if (!value) return false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch (error) {
    /* 아래 대체 방법으로 넘어간다. */
  }
  try {
    const helper = document.createElement("textarea");
    helper.value = value;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(helper);
    return copied;
  } catch (error) {
    return false;
  }
}
