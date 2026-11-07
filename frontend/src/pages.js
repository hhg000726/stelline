/* 화면 묶음(조각)을 받아 오는 길. 주소마다 하나씩이고, 화면을 그릴 때와 미리 받을 때가 같은 것을 쓴다.
 *
 * - 화면을 옮길 때 조각을 기다리지 않도록, 첫 화면이 뜨고 한가해지면 나머지 화면 조각을 미리 받아 둔다.
 *   메뉴에 손을 올리면(마우스·초점·터치) 그 화면 것은 그 자리에서 바로 받는다.
 * - 미리 받아 둔 화면은 기다리지 않고 바로 그린다. React.lazy 는 이미 받은 조각이라도 처음 그릴 때
 *   한 번은 기다려서, 옮길 때마다 '받는 중' 뼈대가 한 프레임 번쩍였다.
 * - 배포로 조각 이름이 바뀌면, 열어 둔 화면은 이미 지워진 옛 조각을 찾다 실패한다. 그때는 한 번만
 *   새로 고쳐 새 문서를 받는다. 곧바로 또 실패하면(정말 연결이 끊긴 경우) 오류 화면을 보여 준다.
 *
 * JSX 를 쓰지 않는 것은 이 파일이 .js 라서다(화면 조각 표와 함께 두려고 .jsx 로 옮기지 않았다).
 */
import { createElement, lazy, useState } from "react";

const RELOAD_KEY = "stelline.reloadedForUpdate";
// 이 안에 다시 실패하면 새로 고쳐도 소용없는 실패로 본다. 끝없이 새로 고치지 않게 하는 장치다.
const RELOAD_GUARD_MS = 30000;
// 첫 화면이 쓰는 그림·데이터와 다투지 않도록, 문서를 받고 이만큼 지난 뒤 한가할 때 받는다.
const PREFETCH_DELAY_MS = 1500;

/* 새 배포 때문에 조각을 못 받았으면 한 번 새로 고친다. 새로 고치기로 했으면 true. */
export function reloadForNewVersion() {
  try {
    const last = Number(window.sessionStorage.getItem(RELOAD_KEY) || 0);
    if (Date.now() - last < RELOAD_GUARD_MS) return false;
    window.sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch (error) {
    // 저장소가 막혀 있으면 방금 새로 고쳤는지 알 수 없다. 끝없이 새로 고칠 수 있어 하지 않는다.
    return false;
  }
  window.location.reload();
  return true;
}

/* 화면 하나. 조각을 이미 받았으면 바로 그리고, 아니면 받는 동안 Suspense 의 뼈대를 보여 준다. */
function lazyPage(load) {
  let loaded = null;
  const remember = () =>
    load().then((module) => {
      loaded = module.default;
      return module;
    });
  const Waiting = lazy(() =>
    remember().catch((error) => {
      // 새로 고치는 동안에는 받는 중 화면을 그대로 둔다(오류 화면이 한 번 번쩍이지 않게).
      if (reloadForNewVersion()) return new Promise(() => {});
      throw error;
    }),
  );

  function Page(props) {
    // 화면을 연 동안에는 처음 고른 것을 끝까지 쓴다. 도중에 바꾸면 React 가 화면을 통째로 새로 만들어
    // 치던 검색어·고른 필터가 사라진다(같은 주소로 다시 들어올 때는 받아 둔 것을 바로 쓴다).
    const [Component] = useState(() => loaded || Waiting);
    return createElement(Component, props);
  }
  // 미리 받기는 덤이다. 실패해도 옮겨 갈 때 다시 받는다.
  Page.preload = () => remember().catch(() => {});
  return Page;
}

export const PAGES = {
  "/": lazyPage(() => import("./pages/MainPage")),
  "/search": lazyPage(() => import("./pages/SearchPage")),
  "/karaoke": lazyPage(() => import("./pages/KaraokePage")),
  "/congratulation": lazyPage(() => import("./pages/CongratulationPage")),
  "/offline": lazyPage(() => import("./pages/OfflinePage")),
};

export const NotFoundPage = lazyPage(() => import("./pages/NotFoundPage"));

export function prefetchPage(path) {
  PAGES[path]?.preload();
}

/* 첫 화면이 다 뜬 뒤 한가할 때 나머지 화면 조각을 받아 둔다(다섯 화면을 다 합쳐도 25KB 남짓).
 * 데이터를 아끼는 설정이거나 느린 연결이면 받지 않는다. 돌려주는 함수로 취소한다. */
export function prefetchPagesWhenIdle() {
  const connection = navigator.connection;
  if (connection && (connection.saveData || /2g/.test(connection.effectiveType || ""))) return () => {};

  let idle = null;
  const run = () => Object.values(PAGES).forEach((page) => page.preload());
  const timer = window.setTimeout(() => {
    if ("requestIdleCallback" in window) idle = window.requestIdleCallback(run, { timeout: 3000 });
    else run();
  }, PREFETCH_DELAY_MS);
  return () => {
    window.clearTimeout(timer);
    if (idle !== null) window.cancelIdleCallback(idle);
  };
}

/* 메뉴·카드에 그대로 펼쳐 넣는 속성. 누르기 직전(손을 올린 순간)에 그 화면 조각을 받기 시작한다. */
export function prefetchProps(path) {
  const start = () => prefetchPage(path);
  return { onPointerEnter: start, onFocus: start, onTouchStart: start };
}
