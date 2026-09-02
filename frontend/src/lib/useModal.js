/* 화면 위에 겹쳐 뜨는 창(랜덤 한 곡·그림 크게 보기)이 공통으로 지켜야 하는 것들.
 *
 * 예전에는 창마다 Esc 처리만 따로 적어 두었다. 그래서 창이 떠 있는 동안에도 뒤 화면이
 * 같이 굴러가고(휴대폰에서는 특히 티가 난다), 닫은 뒤에는 초점이 문서 맨 앞으로
 * 돌아가 키보드만 쓰는 사람이 보던 자리를 잃었다.
 *
 *   - Esc 로 닫는다.
 *   - 떠 있는 동안 뒤 화면은 굴러가지 않는다. 스크롤 막대가 사라지며 생기는 폭만큼
 *     여백으로 메워, 내용이 옆으로 튀지 않게 한다.
 *   - 닫으면 창을 열었던 자리로 초점을 돌려준다.
 */
import { useEffect, useRef } from "react";

export function useModal(open, onClose) {
  const opener = useRef(null);

  /* 닫는 함수는 부를 때마다 최신 것을 쓰되, 아래 효과가 그것 때문에 다시 돌지는 않게 한다.
   *
   * 부르는 쪽은 보통 onClose={() => setPick(null)} 처럼 그 자리에서 함수를 만든다. 그 값을
   * 효과의 조건으로 두면 화면이 다시 그려질 때마다(다시 뽑기·복사 알림 등) 효과가 한 번씩
   * 접혔다 펴진다. 그러면 "원래 넘침값"을 이미 잠근 상태에서 다시 적어 두게 되어, 창을 닫아도
   * 뒤 화면이 영영 굳어 버린다. 초점을 돌려줄 자리도 창 자신으로 덮어써진다. */
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    if (!open) return undefined;

    opener.current = document.activeElement;

    const onKeyDown = (event) => {
      if (event.key === "Escape") close.current();
    };
    document.addEventListener("keydown", onKeyDown);

    const { body } = document;
    const previousOverflow = body.style.overflow;
    const previousPadding = body.style.paddingRight;
    const scrollbar = window.innerWidth - document.documentElement.clientWidth;
    body.style.overflow = "hidden";
    if (scrollbar > 0) body.style.paddingRight = `${scrollbar}px`;

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      body.style.overflow = previousOverflow;
      body.style.paddingRight = previousPadding;

      const node = opener.current;
      if (node && typeof node.focus === "function" && document.contains(node)) node.focus();
    };
  }, [open]);
}
