/* 모든 공개 화면이 같은 줄을 쓴다. 어느 화면에서든 다른 기능으로 바로 갈 수 있어야
 * "메인으로 돌아갔다가 다시 들어가는" 왕복이 사라진다.
 *
 * 메인 화면에는 큰 제목과 기능 카드가 따로 있어 이 줄을 두지 않는다(예전과 같다).
 */
import { NavLink, Link } from "react-router-dom";

import { useNavItems } from "../context/NavButtonsContext";
import { NAV_ITEMS } from "./navItems";

export function SiteHeader() {
  const items = useNavItems(NAV_ITEMS);

  return (
    <header className="site-header">
      <Link className="site-header-brand" to="/">
        <img src="/favicon.svg" alt="" width="26" height="26" />
        <span>Stelline</span>
      </Link>
      {/* NavLink 는 지금 보고 있는 화면에 aria-current="page" 를 스스로 붙인다.
          예전에는 화면마다 HTML 에 직접 적어 두어, 새 화면을 만들 때 빠뜨리기 쉬웠다. */}
      <nav className="site-nav" aria-label="사이트 메뉴" data-button-nav>
        {items.map((item) => (
          <NavLink
            key={item.key}
            to={item.to}
            data-button-key={item.key}
            hidden={item.hidden}
          >
            {item.navLabel}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
