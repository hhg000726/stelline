/* 불러오는 중임을 알리는 조각들.
 *
 * 예전에는 어느 화면이든 "불러오는 중…" 한 줄이었다. 무엇이 들어올 자리인지 알 수 없어
 * 값이 도착하는 순간 화면이 한 번 튀었다. 들어올 모양과 같은 크기의 빈칸을 미리 깐다.
 */
export function RouteProgress() {
  return <div className="route-progress" role="progressbar" aria-label="화면을 불러오는 중" />;
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function SkeletonCards({ count = 6 }) {
  return (
    <div className="card-grid is-compact" aria-hidden="true">
      {Array.from({ length: count }, (unused, index) => (
        <div key={index} className="skeleton skeleton-card" />
      ))}
    </div>
  );
}

export function SkeletonRows({ count = 4 }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (unused, index) => (
        <div key={index} className="skeleton skeleton-row" />
      ))}
    </div>
  );
}

/* 화면 묶음을 아직 받아오는 중일 때. 상단 막대와 대략의 뼈대를 함께 보여 준다. */
export function RouteFallback() {
  return (
    <>
      <RouteProgress />
      <section className="section-panel skeleton-page" aria-busy="true">
        <div className="skeleton skeleton-line" style={{ width: "38%", height: 22 }} />
        <div className="skeleton skeleton-line" style={{ width: "62%" }} />
        <SkeletonRows count={3} />
      </section>
    </>
  );
}
