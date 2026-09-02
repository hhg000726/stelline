/* 모든 공개 화면이 함께 쓰는 껍데기.
 *
 * 머리말·꼬리말·다크 모드 버튼은 여기 한 번만 있으면 되고, 화면을 옮겨도 다시 그리지
 * 않는다. 바뀌는 것은 <Outlet /> 자리뿐이다.
 */
import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { ErrorBoundary } from "./ErrorBoundary";
import { RouteFallback } from "./Loading";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader } from "./SiteHeader";
import { ThemeToggle } from "./ThemeToggle";

export function Layout() {
  const location = useLocation();
  // 메인 화면에는 큰 제목과 기능 카드가 따로 있어 머리말 줄을 두지 않는다(예전과 같다).
  const showHeader = location.pathname !== "/";

  return (
    <>
      <main className="site-container">
        {showHeader && <SiteHeader />}
        {/* key 를 주소로 두면 화면을 옮길 때마다 짧은 페이드가 다시 시작된다. */}
        <div className="route-view" key={location.pathname}>
          <ErrorBoundary resetKey={location.pathname}>
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </div>
        <SiteFooter />
      </main>
      <ThemeToggle />
    </>
  );
}
