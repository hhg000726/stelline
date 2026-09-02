/* 화면마다 달랐던 <title> 과 설명·og 값.
 *
 * 예전에는 화면마다 HTML 이 따로 있어 <head> 에 적어 두었다. 한 문서 안에서 화면을
 * 바꾸는 지금은 옮겨 갈 때마다 여기서 고쳐 준다. 값은 예전 HTML 과 글자까지 같다.
 */
import { useEffect } from "react";

const SITE_TITLE = "Stelline · 스텔라이브 비공식 팬 사이트";
const SITE_DESCRIPTION = "스텔라이브를 좋아해서 만든 비공식 팬 사이트입니다.";

function setMeta(selector, value) {
  const node = document.head.querySelector(selector);
  if (node) node.setAttribute("content", value);
}

export function usePageMeta({ title, description } = {}) {
  useEffect(() => {
    const nextTitle = title || SITE_TITLE;
    const nextDescription = description || SITE_DESCRIPTION;
    document.title = nextTitle;
    setMeta('meta[name="description"]', nextDescription);
    setMeta('meta[property="og:title"]', nextTitle);
    setMeta('meta[property="og:description"]', nextDescription);
  }, [title, description]);
}
