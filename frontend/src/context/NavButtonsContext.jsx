/* 화면 이동 메뉴의 표시 여부·순서.
 *
 * 관리자 화면의 `메인 화면 버튼`(main_buttons) 설정 하나로 메인 화면의 기능 카드와
 * 모든 화면 위쪽 머리말 메뉴가 함께 움직인다. 한쪽에서 숨긴 기능이 다른 쪽에 남아
 * 있으면 안 되기 때문이다. (예전 assets/nav.js 와 같은 규칙이다.)
 *
 * 버튼 이름은 메인 화면 카드에만 반영한다. 머리말은 자리가 좁아 짧은 이름을 그대로
 * 쓰고, 표시 여부와 순서만 따라간다.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { readStore, writeStore } from "../lib/storage";

const CACHE_KEY = "stelline.main.buttons";

const NavButtonsContext = createContext(null);

export function NavButtonsProvider({ children }) {
  // 지난번 설정을 먼저 반영해, 숨긴 항목이 잠깐 보였다 사라지지 않게 한다.
  const [buttons, setButtons] = useState(() => readStore(CACHE_KEY, null));

  useEffect(() => {
    let alive = true;
    api("main/buttons")
      .then((response) => response.json())
      .then((loaded) => {
        if (!alive) return;
        const list = Array.isArray(loaded) ? loaded : [];
        setButtons(list);
        // 조회 실패 시 빈 목록이 오는데, 이걸 저장하면 다음 방문에서 숨긴 항목이 잠깐 보인다.
        if (list.length) writeStore(CACHE_KEY, list);
      })
      .catch((error) => {
        // 설정을 못 받아오면 기본 상태(전부 표시)를 그대로 둔다.
        console.error("메뉴 설정 로드 실패:", error);
      });
    return () => {
      alive = false;
    };
  }, []);

  return <NavButtonsContext.Provider value={buttons}>{children}</NavButtonsContext.Provider>;
}

/* 기본 항목 목록에 관리자 설정을 얹는다.
 *
 * DB 에 없는 키는 손대지 않고 원래 자리(앞쪽)에 남긴다. 화면에 새 항목을 먼저 넣어도
 * 사라지지 않게 하려는 것으로, 예전 nav.js 가 조각(fragment)으로 다시 붙이던 결과와 같다.
 */
export function useNavItems(defaultItems) {
  const buttons = useContext(NavButtonsContext);
  return useMemo(() => {
    if (!Array.isArray(buttons) || !buttons.length) return defaultItems;

    const config = new Map(buttons.map((button) => [button.key, button]));
    const ordered = buttons.slice().sort((a, b) => (a.order || 0) - (b.order || 0));

    const untouched = defaultItems.filter((item) => !config.has(item.key));
    const managed = ordered
      .map((button) => {
        const item = defaultItems.find((candidate) => candidate.key === button.key);
        if (!item) return null;
        return { ...item, hidden: !button.visible, label: button.label || item.label };
      })
      .filter(Boolean);

    return [...untouched, ...managed];
  }, [buttons, defaultItems]);
}
