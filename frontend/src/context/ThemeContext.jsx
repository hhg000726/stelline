/* 사이트 전역 다크 모드.
 *
 * 첫 배색은 index.html 의 <head> 조각이 이미 정해 두었다(그리기 전에 정해야 번쩍이지 않는다).
 * 여기서는 그 값을 이어받아 토글 버튼과 운영체제 설정 따라가기를 맡는다.
 * 고른 값은 브라우저에 남기고, 고른 적이 없으면 운영체제 설정을 따라간다.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const STORAGE_KEY = "stelline.theme";
const THEMES = ["light", "dark"];

const ThemeContext = createContext({ theme: "light", toggle: () => {}, setTheme: () => {} });

function readStored() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return THEMES.includes(saved) ? saved : null;
  } catch (error) {
    return null;
  }
}

function systemTheme() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const chosen = useRef(readStored());
  const [theme, setThemeState] = useState(() => chosen.current || systemTheme());

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const setTheme = useCallback((next, remember = true) => {
    const value = THEMES.includes(next) ? next : "light";
    if (remember) {
      chosen.current = value;
      try {
        window.localStorage.setItem(STORAGE_KEY, value);
      } catch (error) {
        /* 저장이 막힌 환경에서도 이번 방문 동안은 그대로 쓴다. */
      }
    }
    setThemeState(value);
  }, []);

  // 직접 고른 적이 없으면 운영체제 설정을 그대로 따라간다.
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event) => {
      if (!chosen.current) setTheme(event.matches ? "dark" : "light", false);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [setTheme]);

  const value = useMemo(
    () => ({ theme, setTheme, toggle: () => setTheme(theme === "dark" ? "light" : "dark") }),
    [theme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
