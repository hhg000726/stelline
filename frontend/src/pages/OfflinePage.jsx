/* 오프라인 이벤트 화면.
 *
 * 지도만 두면 표시된 행사가 몇 개인지 알 수 없고, 마커를 하나씩 눌러야만 내용을 볼 수 있다.
 * 같은 데이터를 목록으로도 보여 주고, 목록과 지도를 서로 연결한다(예전 offline.js 와 같다).
 *
 * 지도 스크립트는 이 화면에 들어올 때 받아 온다. 마커·말풍선은 React 가 다루는 자리가
 * 아니라 지도 쪽 객체라, 목록이 바뀔 때마다 만들고 지우는 일만 효과 안에서 한다.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ContentText } from "../components/ContentText";
import { EmptyState } from "../components/EmptyState";
import { SkeletonRows } from "../components/Loading";
import { api } from "../lib/api";
import { escapeHtml } from "../lib/escapeHtml";
import { loadScript } from "../lib/loadScript";
import { usePageMeta } from "../lib/usePageMeta";
import "../styles/offline.css";

const NAVER_MAPS = "https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=f7tppyljgr";

function formatDate(dateStr) {
  const date = new Date(dateStr);
  const year = date.getUTCFullYear();
  if (year >= 3000) return "(미정)";
  return `${year}.${date.getUTCMonth() + 1}.${date.getUTCDate()}`;
}

function formatDateRange(startStr, endStr) {
  const start = new Date(startStr);
  const end = new Date(endStr);
  if (start.getFullYear() >= 3000 && end.getFullYear() >= 3000) return "(미정)";

  const startFormatted = formatDate(startStr);
  const endFormatted = formatDate(endStr);
  return startFormatted === endFormatted ? startFormatted : `${startFormatted} ~ ${endFormatted}`;
}

function eventLinks(event) {
  return String(event.description || "")
    .split(",")
    .map((link) => link.trim())
    .filter(Boolean);
}

export default function OfflinePage() {
  usePageMeta({
    title: "진행 중인 오프라인 이벤트 · Stelline",
    description: "지도에서 진행 중인 스텔라이브 오프라인 이벤트와 일정을 한눈에 확인하세요.",
  });

  const [events, setEvents] = useState({ status: "loading", items: [] });
  const [showFuture, setShowFuture] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [selected, setSelected] = useState(-1);

  const mapShell = useRef(null);
  const map = useRef(null);
  const entries = useRef([]);
  const openInfoWindow = useRef(null);
  const cardNodes = useRef([]);
  // 지금 이 순간을 한 번만 정한다. 다시 그릴 때마다 새로 재면 기준이 흔들린다.
  const today = useMemo(() => new Date(), []);

  /* ---------- 지도 준비 ---------- */
  useEffect(() => {
    let alive = true;

    /* 지도 인증이 막히면(키 만료·사용량 초과 등) 스크립트는 멀쩡히 올라오고 화면만 비어
       있다. 이 이름의 함수를 지도 쪽에서 직접 불러 주므로, 그때도 같은 안내를 보여 준다. */
    window.navermap_authFailure = () => {
      map.current = null;
      if (alive) setMapReady(false);
    };

    loadScript(NAVER_MAPS)
      .then(() => {
        if (!alive || !mapShell.current) return;
        if (!window.naver || !window.naver.maps) {
          setMapReady(false);
          return;
        }
        try {
          map.current = new window.naver.maps.Map(mapShell.current, {
            center: new window.naver.maps.LatLng(36.5, 127.5),
            zoom: 7,
          });
        } catch (error) {
          // 인증이 막히면 스크립트는 올라와도 지도를 만들다 멈춘다. 목록만으로도 쓸 수 있다.
          map.current = null;
          setMapReady(false);
          return;
        }
        setMapReady(true);
      })
      .catch(() => {
        if (alive) setMapReady(false);
      });

    return () => {
      alive = false;
      delete window.navermap_authFailure;
    };
  }, []);

  /* ---------- 데이터 ---------- */
  useEffect(() => {
    let alive = true;
    api("offline/offline_api", { method: "GET", headers: { "Content-Type": "application/json" } })
      .then((response) => response.json())
      .then((data) => {
        if (alive) setEvents({ status: "ready", items: Array.isArray(data) ? data : [] });
      })
      .catch((error) => {
        console.error(error);
        if (alive) setEvents({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  const visible = useMemo(
    () =>
      events.items.filter((event) => {
        const start = new Date(event.start_date);
        const end = new Date(event.end_date);
        if (end < today) return false;
        if (event.always) return true;
        if (!showFuture && start > today) return false;
        return true;
      }),
    [events.items, showFuture, today],
  );

  /* 목록에서 고른 행사를 지도에서도 펼쳐 보여 준다. */
  const focusEvent = useCallback((index) => {
    const entry = entries.current[index];
    if (!entry || !map.current) return;

    setSelected(index);
    // 지도의 마커에서 들어온 경우, 짝이 되는 카드가 목록 밖으로 밀려 있을 수 있다.
    cardNodes.current[index]?.scrollIntoView({ block: "nearest", behavior: "smooth" });

    map.current.setCenter(entry.marker.getPosition());
    map.current.setZoom(Math.max(map.current.getZoom(), 13));
    openInfoWindow.current?.close();
    entry.infowindow.open(map.current, entry.marker);
    openInfoWindow.current = entry.infowindow;
  }, []);

  /* ---------- 마커 ----------
   * 지도 쪽 객체를 만드는 일이라, 인증이 막히거나 스크립트가 반만 올라온 상태에서는
   * 여기서 멈출 수 있다. 그때는 지도를 접고 목록만 남긴다. 목록만으로도 장소와
   * 기간은 다 볼 수 있으므로, 화면 전체가 멈추는 것보다 훨씬 낫다. */
  useEffect(() => {
    // 지도를 못 띄웠으면 붙일 곳이 없다.
    if (!mapReady || !map.current) return undefined;
    const maps = window.naver.maps;

    try {
      entries.current = visible.map((event, index) => {
        const marker = new maps.Marker({
          position: new maps.LatLng(event.latitude, event.longitude),
          map: map.current,
          title: event.name,
        });

        // 말풍선은 HTML 문자열로 넘겨야 한다. 값에 <, & 같은 글자가 있어도 그대로
        // 보이도록(그리고 표시가 깨지지 않도록) 모두 이스케이프해서 넣는다.
        const links = eventLinks(event)
          .map((link) => `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(link)}</a>`)
          .join("<br>");

        const content = `
      <div class="map-info">
        <strong>${escapeHtml(event.name)}</strong>
        장소: ${escapeHtml(event.location_name)}<br>
        기간: ${escapeHtml(formatDateRange(event.start_date, event.end_date))}
        ${links ? `<br>관련 링크<br>${links}` : ""}
      </div>
    `;

        const infowindow = new maps.InfoWindow({ content });

        maps.Event.addListener(marker, "click", () => {
          if (openInfoWindow.current === infowindow) {
            infowindow.close();
            openInfoWindow.current = null;
            setSelected(-1);
          } else {
            focusEvent(index);
          }
        });

        return { event, marker, infowindow };
      });
    } catch (error) {
      console.error("지도에 표시하지 못했습니다:", error);
      entries.current = [];
      map.current = null;
      setMapReady(false);
      return undefined;
    }

    return () => {
      /* 치우는 일도 지도 쪽 객체를 건드린다. 인증이 뒤늦게 막히면(navermap_authFailure)
       * 지도가 이미 망가진 채라 여기서 멈춰 버린다. 치우다 만 마커는 지도를 접으면
       * 어차피 보이지 않으므로, 실패는 삼키고 넘어간다. */
      try {
        entries.current.forEach((entry) => entry.marker.setMap(null));
        openInfoWindow.current?.close();
      } catch (error) {
        console.error("지도 표시를 치우지 못했습니다:", error);
      }
      entries.current = [];
      openInfoWindow.current = null;
    };
  }, [visible, mapReady, focusEvent]);

  // 목록이 바뀌면 골라 둔 자리도 뜻을 잃는다.
  useEffect(() => setSelected(-1), [visible]);

  return (
    <>
      {/* 지도만 두면 표시된 행사가 몇 개인지, 어디에 있는지 훑어볼 수 없다.
          목록과 지도를 나란히 두고 서로 연결한다. */}
      <section className="page-shell">
        <div className="hero-heading">
          <div className="page-heading">
            <h1 className="page-title">진행 중인 오프라인 이벤트</h1>
            <p className="page-subtitle">
              <ContentText contentKey="offline_hero_subtitle" as="span" />{" "}
              <span id="event-count" className="meta-text">
                {events.status === "ready" ? `${visible.length}건` : ""}
              </span>
            </p>
          </div>
          <label className="toggle-row">
            <input
              type="checkbox"
              id="showFutureEvents"
              checked={showFuture}
              onChange={(event) => setShowFuture(event.target.checked)}
            />
            아직 시작되지 않은 이벤트도 보기
          </label>
        </div>
      </section>

      <section className="section-panel offline-layout">
        <div className="offline-list" id="event-list" aria-live="polite">
          {events.status === "loading" && <SkeletonRows count={3} />}
          {events.status === "error" && <EmptyState isError>이벤트 목록을 불러오지 못했습니다.</EmptyState>}
          {events.status === "ready" && visible.length === 0 && (
            <EmptyState>진행 중인 오프라인 이벤트가 없습니다.</EmptyState>
          )}
          {events.status === "ready" &&
            visible.map((event, index) => (
              <EventCard
                key={`${event.name}-${event.start_date}-${index}`}
                event={event}
                clickable={mapReady}
                active={selected === index}
                onFocusEvent={() => focusEvent(index)}
                nodeRef={(node) => {
                  cardNodes.current[index] = node;
                }}
              />
            ))}
        </div>
        <div className={mapReady ? "map-shell" : "map-shell is-unavailable"}>
          {/* 지도에 넘기는 칸. 지도가 이 안을 통째로 다시 그리므로 여기에는 아무것도 두지 않는다. */}
          <div id="map" ref={mapShell} className="map-canvas" />
          {/* 지도 쪽에서 뒤늦게 제 오류 화면을 그려 넣기도 한다. 우리 안내만 남도록
              위 칸은 CSS(.map-shell.is-unavailable)에서 감춘다. */}
          {!mapReady && (
            <p className="map-fallback">지도를 불러오지 못했습니다. 아래 목록에서 장소와 기간을 확인해 주세요.</p>
          )}
        </div>
      </section>
    </>
  );
}

/* 예전에는 카드 자체가 <button>이고 관련 링크가 그 안에 들어 있었다. 버튼 안의
 * 링크는 표준에서 허용하지 않고 화면 낭독기도 제대로 읽지 못한다. 그래서 지도로
 * 옮기는 부분만 버튼으로 두고, 링크는 그 옆(버튼 바깥)에 나란히 둔다.
 *
 * 지도를 못 불러왔다면 눌러도 옮겨 갈 곳이 없다. 그때는 눌리지 않는 칸으로 둔다. */
function EventCard({ event, clickable, active, onFocusEvent, nodeRef }) {
  const links = eventLinks(event);
  const body = (
    <>
      <strong>{event.name || "오프라인 이벤트"}</strong>
      <span className="event-place">{event.location_name || event.address || ""}</span>
      <span className="event-date">{formatDateRange(event.start_date, event.end_date)}</span>
    </>
  );

  return (
    <div className={`event-card${active ? " is-on" : ""}`} ref={nodeRef}>
      {clickable ? (
        <button type="button" className="event-card-main" onClick={onFocusEvent}>
          {body}
        </button>
      ) : (
        <div className="event-card-main">{body}</div>
      )}
      {links.length > 0 && (
        <div className="event-links">
          {links.map((link, index) => (
            <a key={link} href={link} target="_blank" rel="noopener noreferrer">
              {links.length > 1 ? `관련 링크 ${index + 1}` : "관련 링크"}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
