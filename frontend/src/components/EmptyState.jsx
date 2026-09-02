/* 목록이 비었거나 불러오지 못했을 때의 한 줄. 화면마다 모양이 어긋나지 않게 한 곳에 둔다. */
export function EmptyState({ children, isError = false }) {
  return <p className={isError ? "empty-state is-error" : "empty-state"}>{children}</p>;
}
