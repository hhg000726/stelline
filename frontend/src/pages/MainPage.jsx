/* 메인 화면.
 *
 * 트윗 안내 · 이벤트 · 벅스 순위 세 칸을 각각 따로 불러온다(예전 index.js 와 같다).
 * 한 칸이 실패해도 나머지는 그대로 보이고, 값이 하나도 없는 칸은 통째로 사라진다.
 */
import { Link } from "react-router-dom";

import { ContentText } from "../components/ContentText";
import { Icon } from "../components/Icon";
import { SiteNotice } from "../components/SiteNotice";
import { NAV_ITEMS } from "../components/navItems";
import { BugsPanel } from "./main/BugsPanel";
import { EventsPanel } from "./main/EventsPanel";
import { TwitsPanel } from "./main/TwitsPanel";
import { useNavItems } from "../context/NavButtonsContext";
import { usePageMeta } from "../lib/usePageMeta";

export default function MainPage() {
  usePageMeta();
  const items = useNavItems(NAV_ITEMS);

  return (
    <>
      <section className="hero">
        <div className="page-header">
          <h1 className="site-brand">
            <img src="/favicon.svg" alt="" width="36" height="36" />
            <span>Stelline</span>
          </h1>
          <ContentText contentKey="main_hero_subtitle" className="page-subtitle" />
        </div>

        <SiteNotice
          titleKey="main_notice_title"
          textKey="main_notice"
          imageKey="main_notice_image"
        />

        {/* 버튼만 늘어놓으면 무엇을 하는 곳인지 안 보여서, 한 줄 설명을 함께 둔다.
            data-button-key 는 관리자 화면의 `메인 화면 버튼` 설정과 짝을 이룬다. 바꾸지 마세요. */}
        <div className="nav-card-grid" id="main-nav" data-button-nav>
          {items.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              className="nav-card"
              data-button-key={item.key}
              hidden={item.hidden}
            >
              <span className="nav-card-icon">
                <Icon name={item.icon} size={18} />
              </span>
              <span className="nav-card-body">
                <strong data-button-label>{item.label}</strong>
                <span>{item.description}</span>
              </span>
              {/* 눌러서 옮겨 가는 자리임을 알리는 표시. 글로 읽을 것은 없으므로 낭독기에서는 뺀다. */}
              <span className="nav-card-go" aria-hidden="true">
                →
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* 세 칸 모두 같은 머리말 짜임을 쓴다. 한 칸에만 설명이 붙어 있으면
          그 줄이 어디에 딸린 말인지 헷갈린다. */}
      <section className="info-stack is-split">
        <TwitsPanel />
        <EventsPanel />
        <BugsPanel />
      </section>
    </>
  );
}
