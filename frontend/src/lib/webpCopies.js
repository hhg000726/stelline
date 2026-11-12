/* WebP 사본이 있는 기본 그림.
 *
 * 사본은 원본과 같은 폴더에 원본 이름 뒤에 ".webp" 를 붙여 둔다(예: /search/1.PNG → /search/1.PNG.webp).
 * PNG 는 무손실, JPG 는 품질 85 로 옮겨 검색 안내 그림 7장이 790KB 에서 400KB 남짓으로 준다.
 *
 * 화면은 <picture> 로 WebP 를 먼저 권하고, WebP 를 못 읽는 브라우저는 원본을 그대로 받는다.
 * 여기 적힌 주소에만 권한다. 사본이 없는 주소에 WebP 를 권하면 브라우저가 그 404 를 받고도
 * 원본으로 돌아가지 않아 그림이 깨진다. 관리자가 다른 그림으로 바꾸면(여기 없는 주소) 원본만 쓴다.
 *
 * 그림을 바꾸거나 늘리면 `python dev/make_web_images.py` 로 사본을 다시 만들고 이 목록도 고친다.
 * tests/test_static_images.py 가 목록과 파일이 맞는지, 사본이 지금 원본과 같은 그림인지 본다.
 */
const WEBP_COPIES = new Set([
  "/search/1.PNG",
  "/search/2.PNG",
  "/search/3.PNG",
  "/search/1.jpg",
  "/search/2.jpg",
  "/search/3.jpg",
  "/search/4.jpg",
]);

export function webpCopyOf(src) {
  return WEBP_COPIES.has(src) ? `${src}.webp` : null;
}
