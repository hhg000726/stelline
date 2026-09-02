/* 바깥에서 불러오는 스크립트(Turnstile · Firebase · 네이버 지도).
 *
 * 예전에는 화면마다 <script> 로 박아 두어, 그 화면에 들어가지 않아도 늘 받아 왔다.
 * SPA 에서는 해당 화면을 열 때 한 번만 받고, 같은 주소는 약속을 재사용한다.
 */
const loading = new Map();

export function loadScript(src, { attributes } = {}) {
  if (loading.has(src)) return loading.get(src);

  const promise = new Promise((resolve, reject) => {
    // 이미 붙어 있는 태그(예: 서버가 심어 둔 것)가 있으면 그것을 기다린다.
    const existing = document.querySelector(`script[src="${src}"]`);
    const script = existing || document.createElement("script");
    if (!existing) {
      script.src = src;
      script.async = true;
      Object.entries(attributes || {}).forEach(([name, value]) => {
        script.setAttribute(name, value);
      });
    }
    script.addEventListener("load", () => resolve(script));
    script.addEventListener("error", () => {
      // 실패한 약속을 남겨 두면 다시 들어와도 영영 못 받는다. 지워서 재시도를 연다.
      loading.delete(src);
      reject(new Error(`스크립트를 불러오지 못했습니다: ${src}`));
    });
    if (!existing) document.head.appendChild(script);
  });

  loading.set(src, promise);
  return promise;
}
