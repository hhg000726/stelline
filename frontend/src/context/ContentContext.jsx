/* 관리자 화면에서 고치는 고정 문구·그림.
 *
 * 예전 assets/content.js 와 같은 원칙을 지킨다.
 *   - 값을 못 받아오면 화면에 박아 둔 기본 문구를 그대로 쓴다(빈 화면이 되지 않는다).
 *   - 지난번 값을 먼저 반영해, 관리자가 지운 문구가 잠깐 보였다 사라지지 않게 한다.
 *   - 모르는 키는 손대지 않는다.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { CONTENT_DEFAULTS } from "../lib/contentDefaults";
import { readStore, writeStore } from "../lib/storage";

const CACHE_KEY = "stelline.site.contents";

const ContentContext = createContext({ items: null });

export function ContentProvider({ children }) {
  const [items, setItems] = useState(() => readStore(CACHE_KEY, null));

  useEffect(() => {
    let alive = true;
    api("content")
      .then((response) => response.json())
      .then((loaded) => {
        if (!alive || !loaded || typeof loaded !== "object") return;
        setItems(loaded);
        if (Object.keys(loaded).length) writeStore(CACHE_KEY, loaded);
      })
      .catch((error) => {
        // 값을 못 받아오면 기본 문구를 그대로 둔다.
        console.error("사이트 콘텐츠 로드 실패:", error);
      });
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo(() => ({ items }), [items]);
  return <ContentContext.Provider value={value}>{children}</ContentContext.Provider>;
}

/* 항목 하나의 표시값. { value, hidden, type } 을 돌려준다.
 *
 * 아직 받아오지 못했거나 모르는 키면 기본값을 쓴다. 기본값이 비어 있는 항목(공지 등)은
 * hidden 이 되어 자리째 사라진다. 예전 HTML 의 hidden 속성과 같은 뜻이다. */
export function useContentItem(key) {
  const { items } = useContext(ContentContext);
  return useMemo(() => resolveItem(items, key), [items, key]);
}

function resolveItem(items, key) {
  const item = items && items[key];
  if (item) {
    const value = item.value || "";
    return { value, hidden: Boolean(item.hidden) || !value, type: item.type || "text" };
  }
  const fallback = CONTENT_DEFAULTS[key] || "";
  return { value: fallback, hidden: !fallback, type: key.endsWith("_image") ? "image" : "text" };
}

/* 여러 항목을 한 번에. 목록 안에서 항목마다 훅을 부르면 개수가 달라질 때 규칙이 깨진다. */
export function useContentItems(keys) {
  const { items } = useContext(ContentContext);
  return useMemo(() => keys.map((key) => resolveItem(items, key)), [items, keys]);
}
