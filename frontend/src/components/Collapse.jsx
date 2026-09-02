/* 눌러서 펼치는 칸 하나.
 *
 * 예전에는 `hidden` 을 붙였다 뗐다 했다. 내용이 한 프레임에 나타났다 사라져,
 * 어디가 열렸는지 눈으로 따라가지 못하고 그만큼 화면이 튀었다. 여기서는 칸의 높이를
 * 0fr ↔ 1fr 로 옮겨 짧게 밀어 올린다(내용 높이를 미리 재지 않아도 되는 방법이다).
 *
 * 접힌 칸은 화면에서 보이지 않을 뿐 문서에는 남는다. 그대로 두면 Tab 키가 보이지도
 * 않는 버튼에 들어가 갇히므로, 접힌 동안에는 `inert` 로 통째로 비활성화한다.
 * (React 18 은 참/거짓을 그대로 넘기면 경고하므로 빈 문자열로 붙인다.)
 */
export function Collapse({ id, open, className, children }) {
  const classNames = ["collapse", open ? "is-open" : "", className].filter(Boolean).join(" ");
  return (
    <div id={id} className={classNames} inert={open ? undefined : ""}>
      <div className="collapse-inner">{children}</div>
    </div>
  );
}
