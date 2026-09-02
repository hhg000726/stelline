/* 검색 안되는 노래 화면.
 *
 * 부르는 API 와 그 결과를 다루는 규칙은 예전 search.js 그대로다.
 *   - search/not_searched → 지금 막힌 곡·최근 7일 곡(둘 다 받아온 뒤 섞는다)
 *   - search/songs        → 검색어 목록
 *   - search/record       → 카드를 누를 때 기록(실패해도 화면은 그대로 진행)
 * 달라진 것은 화면 안에서 상태로 다룬다는 점과, 값을 기다리는 동안 빈칸을 보여 준다는 점이다.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ContentText } from "../components/ContentText";
import { EmptyState } from "../components/EmptyState";
import { Icon } from "../components/Icon";
import { ImageViewer } from "../components/ImageViewer";
import { SkeletonCards } from "../components/Loading";
import { ReportPanel } from "../components/ReportPanel";
import { SectionPanel } from "../components/SectionPanel";
import { Segmented, tabPanelProps } from "../components/Segmented";
import { SiteNotice } from "../components/SiteNotice";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";
import { copyText } from "../lib/clipboard";
import { usePageMeta } from "../lib/usePageMeta";
import { StepGrid } from "./search/StepGrid";
import "../styles/search.css";

const PC_STEPS = [
  { imageKey: "search_step_pc_1_image", labelKey: "search_step_pc_1_label", alt: "유튜브 검색 결과에서 필터 버튼 위치" },
  { imageKey: "search_step_pc_2_image", labelKey: "search_step_pc_2_label", alt: "필터 창에서 우선순위 인기도 순 위치" },
  { imageKey: "search_step_pc_3_image", labelKey: "search_step_pc_3_label", alt: "정렬된 검색 결과에서 영상 재생" },
];

const MOBILE_STEPS = [
  { imageKey: "search_step_mobile_1_image", labelKey: "search_step_mobile_1_label", alt: "모바일 검색 화면 오른쪽 위 점 세 개 위치" },
  { imageKey: "search_step_mobile_2_image", labelKey: "search_step_mobile_2_label", alt: "메뉴에서 검색필터 위치" },
  { imageKey: "search_step_mobile_3_image", labelKey: "search_step_mobile_3_label", alt: "검색 필터에서 우선순위 인기도 순 위치" },
  { imageKey: "search_step_mobile_4_image", labelKey: "search_step_mobile_4_label", alt: "정렬된 모바일 검색 결과" },
];

/* 안내 그림은 PC와 모바일 두 벌이 있다. 휴대폰으로 들어온 사람에게 PC 화면부터
 * 보여 주면, 자기 화면과 다른 그림을 보고 한 번 더 눌러야 한다. */
function defaultMethodTab() {
  const coarsePointer = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  const narrow = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  return coarsePointer || narrow ? "mobile" : "pc";
}

function shuffled(list) {
  const array = Array.isArray(list) ? list.slice() : [];
  for (let i = array.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

function lastUpdatedText(searchedTime) {
  if (searchedTime === 0) return "마지막 검색 시도: 없음";
  if (typeof searchedTime === "string") return searchedTime;
  return `마지막 검색 시도: ${new Date(searchedTime * 1000).toLocaleString()}`;
}

export default function SearchPage() {
  usePageMeta({
    title: "검색 안되는 노래 · Stelline",
    description: "유튜브 검색에서 잘 노출되지 않는 스텔라이브 곡 목록과 검색 정상화 방법을 안내합니다.",
  });

  const toast = useToast();
  const [songs, setSongs] = useState({ status: "loading", current: [], recent: [], updated: "" });
  const [queries, setQueries] = useState({ status: "loading", items: [] });
  const [filter, setFilter] = useState("");
  const [songTab, setSongTab] = useState("current");
  const [methodTab, setMethodTab] = useState(defaultMethodTab);
  const [viewerImage, setViewerImage] = useState(null);

  useEffect(() => {
    let alive = true;
    api("search/not_searched")
      .then((response) => response.json())
      .then((data) => {
        if (!alive) return;
        setSongs({
          status: "ready",
          current: shuffled(data.all_songs),
          recent: shuffled(data.recent),
          updated: lastUpdatedText(data.searched_time),
        });
      })
      .catch((error) => {
        console.error("Error fetching songs:", error);
        if (alive) setSongs({ status: "error", current: [], recent: [], updated: "" });
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    api("search/songs")
      .then((response) => response.json())
      .then((data) => {
        if (alive) setQueries({ status: "ready", items: Array.isArray(data) ? data : [] });
      })
      .catch((error) => {
        console.error("JSON을 불러오는 중 오류 발생:", error);
        if (alive) setQueries({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  /* 검색어를 눌렀을 때. 기록은 결과를 기다리지 않고, 복사가 막히면 유튜브로 보내지 않는다.
   * (붙여 넣을 것이 없는 채로 보내 봐야 소용없다.) */
  const openYoutube = useCallback(
    async (query) => {
      api("search/record", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      }).catch((error) => console.error("API 요청 중 오류 발생:", error));

      if (!(await copyText(query))) {
        toast("복사하지 못했어요. 검색어를 직접 선택해 복사해 주세요.");
        return;
      }
      // 복사에 성공하면 곧바로 유튜브로 넘어간다. 넘어가는 것 자체가 알림 역할을 한다.
      window.location.href = "https://www.youtube.com/";
    },
    [toast],
  );

  const filteredQueries = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    return queries.items.filter((item) => String(item.query || "").toLowerCase().includes(normalized));
  }, [queries.items, filter]);

  return (
    <>
      <section className="page-shell">
        <div className="hero-heading">
          <div className="page-heading">
            <h1 className="page-title">검색 안되는 노래</h1>
            <p className="page-subtitle">
              <ContentText contentKey="search_hero_subtitle" as="span" />{" "}
              <span id="last-updated" className="meta-text">
                {songs.updated}
              </span>
            </p>
          </div>
          <ReportPanel
            endpoint="search/reports"
            openLabel="검색어 추가 제안"
            closeLabel="제안 입력 닫기"
            title="목록에 없는 검색어 추가를 제안해주세요"
            description="페이지 아래 검색어 목록에 없는 검색어를 제안하거나, 추가했으면 하는 내용을 남겨주세요."
            fieldLabel="제안 내용"
            placeholder="노래 제목, 검색어 또는 추가 의견을 입력하세요"
            submitLabel="제안 보내기"
          />
        </div>

        <SiteNotice titleKey="search_notice_title" textKey="search_notice" imageKey="search_notice_image" />
      </section>

      {/* 지금 막힌 곡과 최근에 막혔던 곡은 같은 종류의 목록이라, 두 칸을 따로 두는 대신
          한 칸에서 탭으로 바꿔 본다. 화면이 절반으로 짧아지고 둘의 관계도 분명해진다. */}
      <SectionPanel
        title="막힌 곡 목록"
        noteKey="search_songs_note"
        actions={
          <Segmented
            groupId="song-tabs"
            label="곡 목록 종류"
            value={songTab}
            onChange={setSongTab}
            tabs={[
              {
                name: "current",
                label: "지금 막힘 ",
                suffix: <span data-count="current">{songs.status === "ready" ? songs.current.length : ""}</span>,
              },
              {
                name: "recent",
                label: "최근 7일 ",
                suffix: <span data-count="recent">{songs.status === "ready" ? songs.recent.length : ""}</span>,
              },
            ]}
          />
        }
      >
        {songs.status === "loading" && <SkeletonCards count={8} />}
        {songs.status === "error" && <EmptyState isError>목록을 불러오지 못했습니다.</EmptyState>}
        {songs.status === "ready" && (
          <>
            <SongCards
              songs={songs.current}
              emptyText="검색 안되는 노래가 없습니다."
              onSelect={openYoutube}
              {...tabPanelProps("song-tabs", "current", songTab === "current")}
            />
            <SongCards
              songs={songs.recent}
              emptyText="최근 7일 이내에 막혔던 곡이 없습니다."
              onSelect={openYoutube}
              {...tabPanelProps("song-tabs", "recent", songTab === "recent")}
            />
          </>
        )}
      </SectionPanel>

      {/* 참고 메시지와 정상화 방법은 둘 다 "어떻게 도우면 되는지"를 말한다. 한 칸으로 합친다. */}
      <SectionPanel
        titleKey="search_help_title"
        noteKey="search_help_note"
        actions={
          <Segmented
            groupId="method-tabs"
            label="기기 종류"
            value={methodTab}
            onChange={setMethodTab}
            tabs={[
              { name: "pc", label: "PC" },
              { name: "mobile", label: "모바일" },
            ]}
          />
        }
      >
        <ContentText contentKey="search_help_list" as="ul" className="checklist" list />

        <StepGrid
          steps={PC_STEPS}
          onOpenImage={setViewerImage}
          {...tabPanelProps("method-tabs", "pc", methodTab === "pc")}
        />
        <StepGrid
          steps={MOBILE_STEPS}
          onOpenImage={setViewerImage}
          {...tabPanelProps("method-tabs", "mobile", methodTab === "mobile")}
        />
        <ContentText contentKey="search_steps_hint" className="list-note step-hint" />
      </SectionPanel>

      <SectionPanel
        title="검색어 리스트"
        noteKey="search_query_note"
        actions={
          <>
            <span id="query-count" className="results-count">
              {queries.status === "error" ? "불가" : `${filteredQueries.length}개`}
            </span>
            <label className="query-search" htmlFor="query-search">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M10.5 3a7.5 7.5 0 0 1 5.88 12.8l4.42 4.42 1.41-1.41-4.42-4.42A7.5 7.5 0 1 1 10.5 3Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z" />
              </svg>
              <input
                id="query-search"
                type="search"
                placeholder="검색어 찾기"
                aria-label="검색어 목록 필터"
                autoComplete="off"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
            </label>
          </>
        }
      >
        <ul id="query-list" className="info-list">
          {filteredQueries.length === 0 ? (
            <li className="query-empty">
              {filter.trim() ? "검색어를 찾을 수 없습니다." : "표시할 검색어가 없습니다."}
            </li>
          ) : (
            filteredQueries.map((item) => (
              <li className="query-item" key={`${item.video_id}-${item.query}`}>
                <button
                  type="button"
                  className="query-chip"
                  title={item.query}
                  onClick={() => openYoutube(item.query)}
                >
                  {item.query}
                </button>
              </li>
            ))
          )}
        </ul>
      </SectionPanel>

      <ImageViewer image={viewerImage} onClose={() => setViewerImage(null)} />
    </>
  );
}

/* 카드 전체가 "복사 & 이동" 버튼이라 별도의 버튼 줄이 필요 없다. */
function SongCards({ songs, emptyText, onSelect, ...panelProps }) {
  return (
    <div className="card-grid is-compact" {...panelProps}>
      {songs.map((song) => (
        <button
          key={`${song.video_id}-${song.query}`}
          type="button"
          className="card is-link"
          title={`${song.query} 복사하고 유튜브로 이동`}
          onClick={() => onSelect(song.query)}
        >
          <div className="thumb-wrap">
            <img src={`https://img.youtube.com/vi/${song.video_id}/0.jpg`} alt="" loading="lazy" />
            <span className="thumb-play">
              <Icon name="play" />
            </span>
          </div>
          <div className="info">
            <h3>{song.query}</h3>
            <span className="card-action">복사 &amp; 이동</span>
          </div>
        </button>
      ))}
      {songs.length === 0 && <EmptyState>{emptyText}</EmptyState>}
    </div>
  );
}
