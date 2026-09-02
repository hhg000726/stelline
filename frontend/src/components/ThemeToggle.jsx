/* 다크 모드 토글. 예전에는 theme.js 가 모든 화면 본문 끝에 직접 심었다.
 * 다크 모드일 때는 "밝게 되돌리기"를 뜻하는 해 아이콘을 보여준다. */
import { useTheme } from "../context/ThemeContext";
import { Icon } from "./Icon";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const toDark = theme !== "dark";
  const label = toDark ? "다크 모드 켜기" : "다크 모드 끄기";

  return (
    <button
      id="theme-toggle"
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-pressed={theme === "dark"}
      aria-label={label}
      title={label}
    >
      <Icon name={theme === "dark" ? "sun" : "moon"} size={20} />
    </button>
  );
}
