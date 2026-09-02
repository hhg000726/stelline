/* 바깥 사이트로 나가기.
 *
 * 나가는 자리는 어디서나 새 탭이다. 보던 화면은 그 자리에 그대로 둔다.
 * 링크로 둘 수 있는 자리는 <a target="_blank" rel="noopener noreferrer"> 를 쓰고,
 * 복사처럼 먼저 해야 할 일이 있어 링크로 둘 수 없는 자리에서 이 함수를 쓴다.
 *
 * 창 옵션에 "noopener" 를 넘기면 새 탭이 잘 떠도 window.open 이 null 을 돌려준다.
 * 그러면 팝업이 막힌 것과 구분할 수 없어, 잘 열렸는데도 막힌 줄 알고 이 창까지
 * 옮겨 버린다. 옵션으로 넘기는 대신 열고 나서 opener 를 끊는다.
 *
 * 대신 "noreferrer" 도 함께 잃는다(둘은 같은 자리에 적는 값이고, noreferrer 역시
 * null 을 돌려준다). 나가는 곳이 x.com·youtube.com 첫 화면이고 넘어가는 값도
 * 공개된 이 사이트 주소뿐이라, 팝업이 막힌 것을 알아채는 쪽을 택했다.
 * 링크로 둘 수 있는 자리는 그대로 rel="noopener noreferrer" 를 쓴다.
 *
 * 돌아오는 값은 "열린 것이 확실한가"이지 "열리지 않았다"가 아니다. 창을 대신
 * 다루는 환경(앱 안에 들어 있는 웹뷰 같은)에서는 잘 열고도 null 을 주기 때문에,
 * false 를 받은 쪽은 못 열었다고 단정하지 말고 조건을 붙여 알려야 한다.
 */
export function openExternal(url) {
  const opened = window.open(url, "_blank");
  if (!opened) return false;
  try {
    opened.opener = null;
  } catch (error) {
    /* 끊지 못해도 탭은 이미 열렸다. 열린 것은 열린 것으로 알린다. */
  }
  return true;
}
