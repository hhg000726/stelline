/* 검색 안되는 노래 화면.
 *
 * 곡별 노출 상태는 search/status 하나로 받는다. 판정은 서버 한 곳(stelline/apis/search/history.py)에서만
 * 하고, 화면은 서버가 정한 값으로 거르기만 한다.
 *   - 지금 막힘: 마지막 검사에서 막힌 곡(state). 예전처럼 '마지막 회차에서 검사한 곡'만 보지 않는다.
 *   - 최근 7일: 7일 안에 검색이 안 된(막힘·cover로만) 적이 있는 곡(recent). 지금 상태는 카드에 적는다.
 *     막힌 곡은 '지금 막힘'과 여기 둘 다 나온다. 두 탭은 '지금'과 '지난 7일'이라는 다른 질문에 답한다.
 *   - cover 검색으로 발견: 마지막 검사에서 cover 를 붙여야만 찾은 곡(state).
 *   - 카드마다 최근 7일 검사 결과(점)와 마지막 검사 시각을 붙여, 왜 그 탭에 있는지 보이게 한다.
 *   - 제목 아래 '마지막 검색'·'다음 검색' 칩을 펼치면 그 회차의 곡 목록이 나온다(search/RunPill.jsx).
 *   - 아래 검색어 리스트도 같은 응답을 쓴다.
 *   - search/record → 카드를 누를 때 기록(실패해도 화면은 그대로 진행)
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
import { openExternal } from "../lib/openExternal";
import { usePageMeta } from "../lib/usePageMeta";
import { LastRunDetails, NextRunDetails, RunPill, shortTime } from "./search/RunPill";
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

/* 곡 목록 탭. 이름·순서는 예전 화면 그대로이고, 어느 곡이 들어가는지는 서버 판정(state·recent)으로 정한다. */
const SONG_TABS = [
  { name: "current", label: "지금 막힘", pick: (song) => song.state === "blocked" },
  { name: "recent", label: "최근 7일", pick: (song) => song.recent === true },
  { name: "cover", label: "cover 검색으로 발견", pick: (song) => song.state === "cover_only" },
];

const RESULT_LABELS = { blocked: "막힘", cover_only: "cover로만", visible: "정상" };

/* '최근 7일' 탭 카드의 썸네일 위에 붙이는 지금 상태. 본문에 문장으로 적으면 카드가 길어진다. */
const STATE_BADGES = { blocked: "지금 막힘", cover_only: "cover로만", visible: "지금 정상" };

/* 카드에 늘어놓는 검사 결과 점의 최대 개수. 더 있으면 최근 것만 보이고 개수는 글로 센다. */
const MAX_MARKS = 12;

/* 안내 그림은 PC와 모바일 두 벌이 있다. 휴대폰으로 들어온 사람에게 PC 화면부터
 * 보여 주면, 자기 화면과 다른 그림을 보고 한 번 더 눌러야 한다. */
function defaultMethodTab() {
  const coarsePointer = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  const narrow = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  return coarsePointer || narrow ? "mobile" : "pc";
}

/* 같은 곡에만 응원이 몰리지 않게 탭 안의 순서는 열 때마다 섞는다(예전 화면과 같다). */
function shuffled(list) {
  const array = list.slice();
  for (let i = array.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

function absoluteTime(epochSeconds) {
  return epochSeconds ? new Date(epochSeconds * 1000).toLocaleString() : "";
}

/* 화면 낭독기에만 읽히는 글. 눈에는 점·색으로 보이는 것을 말로 옮긴다. */
function ScreenReaderText({ children }) {
  return <span className="search-sr-only">{children}</span>;
}

/* "3시간 전"처럼 지금부터 얼마나 지났는지. 판정이 언제 것인지 한눈에 보이게 한다. */
function timeAgo(epochSeconds) {
  if (!epochSeconds) return "";
  const seconds = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}분 전`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}시간 전`;
  return `${Math.floor(seconds / 86400)}일 전`;
}

function emptyStatus(phase) {
  return { phase, songs: [], summary: null, lastCheckedAt: null, windowDays: 7, schedule: null, lastRun: null, nextRun: null };
}

/* "N시간마다(한국 시간 HH·HH·HH시)". 간격을 화면에 글자로 적지 않고 서버 설정에서 받는다. */
function scheduleText(schedule) {
  if (!schedule || !schedule.interval_hours) return "";
  const hours = (schedule.run_hours_kst || []).map((hour) => String(hour).padStart(2, "0")).join("·");
  return `${schedule.interval_hours}시간마다` + (hours ? `(한국 시간 ${hours}시)` : "");
}

export default function SearchPage() {
  usePageMeta({
    title: "검색 안되는 노래 · Stelline",
    description: "유튜브 검색에서 잘 노출되지 않는 스텔라이브 곡 목록과 검색 정상화 방법을 안내합니다.",
  });

  const toast = useToast();
  const [status, setStatus] = useState(() => emptyStatus("loading"));
  const [filter, setFilter] = useState("");
  const [songTab, setSongTab] = useState(SONG_TABS[0].name);
  const [methodTab, setMethodTab] = useState(defaultMethodTab);
  const [viewerImage, setViewerImage] = useState(null);

  useEffect(() => {
    let alive = true;
    api("search/status")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!alive) return;
        setStatus({
          phase: "ready",
          songs: Array.isArray(data.songs) ? data.songs : [],
          summary: data.summary || null,
          lastCheckedAt: data.last_checked_at || null,
          windowDays: data.window_days || 7,
          schedule: data.schedule || null,
          lastRun: data.last_run || null,
          nextRun: data.next_run || null,
        });
      })
      .catch((error) => {
        console.error("검색 노출 상태를 불러오지 못했습니다:", error);
        if (alive) setStatus(emptyStatus("error"));
      });
    return () => {
      alive = false;
    };
  }, []);

  /* 탭마다 한 번만 섞는다. 다시 그릴 때마다 섞으면 카드가 눈앞에서 자리를 바꾼다. */
  const tabSongs = useMemo(
    () => Object.fromEntries(SONG_TABS.map((tab) => [tab.name, shuffled(status.songs.filter(tab.pick))])),
    [status.songs],
  );

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
      // 보던 목록은 그대로 두고 새 탭만 연다. 여기서 넘어가 버리면 여러 검색어를
      // 이어서 눌러 볼 수 없다. 화면이 그대로이니 무슨 일이 있었는지는 말풍선으로 알린다.
      if (openExternal("https://www.youtube.com/")) {
        toast("복사했어요. 새 탭에서 유튜브를 열었습니다.");
      } else {
        toast("팝업 차단을 확인해 주세요. PC에서 애드가드를 쓰면 이 사이트의 보호를 끄거나 팝업을 허용해 주세요.");
      }
    },
    [toast],
  );

  const filteredQueries = useMemo(() => {
    const normalized = filter.trim().toLowerCase();
    return status.songs.filter((song) => String(song.query || "").toLowerCase().includes(normalized));
  }, [status.songs, filter]);

  const ready = status.phase === "ready";
  const summary = status.summary;
  /* 검사는 모든 곡을 매번 하지 않는다. 그 사실은 숫자 한 줄로만 적고, 일정과 방식은 '다음 검색'
   * 칩을 펼치면 보이게 한다(설명 문장이 길면 목록보다 먼저 읽히지 않는다). */
  const coverage = ready && summary
    ? `최근 ${status.windowDays}일 ${summary.checked_in_window}/${summary.songs}곡 검색`
      + (summary.unchecked ? ` · 검색 전 ${summary.unchecked}곡` : "")
    : undefined;
  const lastRunTime = status.lastRun?.started_at || status.lastCheckedAt;

  return (
    <>
      <section className="page-shell">
        <div className="hero-heading">
          <div className="page-heading">
            <h1 className="page-title">검색 안되는 노래</h1>
            <ContentText contentKey="search_hero_subtitle" className="page-subtitle" />
            {/* 설명 문장 뒤에 시각을 이어 붙이면 어디까지가 문장인지 알 수 없다.
                이름표를 붙여 따로 세운다. */}
            <div className="page-meta">
              {/* 칩에 마우스를 올리거나 누르면 그 회차에 검색한(할) 곡이 펼쳐진다. */}
              {ready && (
                <RunPill label="마지막 검색" value={lastRunTime ? shortTime(lastRunTime) : "없음"}>
                  <LastRunDetails lastRun={status.lastRun} />
                </RunPill>
              )}
              {ready && status.nextRun?.at && (
                <RunPill label="다음 검색" value={shortTime(status.nextRun.at)}>
                  <NextRunDetails nextRun={status.nextRun} scheduleText={scheduleText(status.schedule)} />
                </RunPill>
              )}
            </div>
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

      <SectionPanel
        title="검색 노출 현황"
        note={coverage}
        actions={
          <Segmented
            groupId="song-tabs"
            label="곡 목록 종류"
            value={songTab}
            onChange={setSongTab}
            tabs={SONG_TABS.map((tab) => ({
              name: tab.name,
              label: `${tab.label} `,
              suffix: <span data-count={tab.name}>{ready ? tabSongs[tab.name].length : ""}</span>,
            }))}
          />
        }
      >
        {status.phase === "loading" && <SkeletonCards count={8} />}
        {status.phase === "error" && <EmptyState isError>목록을 불러오지 못했습니다.</EmptyState>}
        {ready && (
          <>
            <p className="search-legend">
              <span className="week-mark is-blocked" aria-hidden="true" />막힘
              <span className="week-mark is-cover_only" aria-hidden="true" />cover로만
              <span className="week-mark is-visible" aria-hidden="true" />정상
              <span className="search-legend-note">· 점 1개 = 최근 7일 검색 1번</span>
            </p>
            <div {...tabPanelProps("song-tabs", "current", songTab === "current")}>
              <SongCards
                songs={tabSongs.current}
                emptyText="검색 안되는 노래가 없습니다."
                windowDays={status.windowDays}
                onSelect={openYoutube}
              />
            </div>
            <div {...tabPanelProps("song-tabs", "recent", songTab === "recent")}>
              <SongCards
                songs={tabSongs.recent}
                emptyText="최근 7일 이내에 검색이 안 됐던 곡이 없습니다."
                windowDays={status.windowDays}
                onSelect={openYoutube}
                showState
              />
            </div>
            <div
              className="cover-results-panel"
              {...tabPanelProps("song-tabs", "cover", songTab === "cover")}
            >
              <ContentText contentKey="search_songs_note" />
              <SongCards
                songs={tabSongs.cover}
                emptyText="기본 검색에서 찾지 못해 cover를 붙여 다시 찾은 곡이 없습니다."
                windowDays={status.windowDays}
                onSelect={openYoutube}
              />
            </div>
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
              {status.phase === "error" ? "불가" : `${filteredQueries.length}개`}
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
            filteredQueries.map((song) => <QueryChip key={`${song.video_id}-${song.query}`} song={song} onSelect={openYoutube} />)
          )}
        </ul>
      </SectionPanel>

      <ImageViewer image={viewerImage} onClose={() => setViewerImage(null)} />
    </>
  );
}

/* 검색어 하나. 지금 막혔거나 cover로만 찾히는 곡은 위 현황과 같은 색 점으로 표시한다.
 * (칩마다 두 번째 줄에 문장을 달면 332개 목록이 두 배로 길어진다. 말은 화면 낭독기와 title 에 둔다.) */
function QueryChip({ song, onSelect }) {
  const isCover = song.state === "cover_only" && song.fallback_query;
  const isBlocked = song.state === "blocked";
  const className = ["query-chip", isCover ? "has-cover-match" : "", isBlocked ? "is-blocked" : ""].filter(Boolean).join(" ");
  const note = isCover ? "cover를 붙여야 검색돼요" : isBlocked ? "지금 막힘" : "";
  return (
    <li className="query-item">
      <button
        type="button"
        className={className}
        title={isCover ? `${note} · ‘${song.fallback_query}’ 복사 후 유튜브 열기` : note || song.query}
        onClick={() => onSelect(isCover ? song.fallback_query : song.query)}
      >
        {note && <span className={`week-mark is-${song.state}`} aria-hidden="true" />}
        <span>{song.query}</span>
        {note && <ScreenReaderText>{note}</ScreenReaderText>}
      </button>
    </li>
  );
}

/* 카드 전체가 "복사 & 새 탭" 버튼이라 별도의 버튼 줄이 필요 없다.
 * showState: '최근 7일' 탭처럼 지금 상태가 섞여 있는 목록에서 카드마다 지금 상태를 적는다. */
function SongCards({ songs, emptyText, windowDays, onSelect, showState = false }) {
  return (
    <div className="card-grid is-compact">
      {songs.map((song) => (
        <SongCard
          key={`${song.video_id}-${song.query}`}
          song={song}
          windowDays={windowDays}
          onSelect={onSelect}
          showState={showState}
        />
      ))}
      {songs.length === 0 && <EmptyState>{emptyText}</EmptyState>}
    </div>
  );
}

function SongCard({ song, windowDays, onSelect, showState }) {
  const searchQuery = song.fallback_query || song.query;
  const badge = showState ? STATE_BADGES[song.state] : null;
  return (
    <button
      type="button"
      className="card is-link"
      title={`${searchQuery} 복사하고 유튜브를 새 탭에서 열기`}
      onClick={() => onSelect(searchQuery)}
    >
      <div className="thumb-wrap">
        <img src={`https://img.youtube.com/vi/${song.video_id}/0.jpg`} alt="" loading="lazy" />
        {badge && <span className={`card-badge state-badge is-${song.state}`}>{badge}</span>}
        <span className="thumb-play">
          <Icon name="play" />
        </span>
      </div>
      <div className="info">
        <h3>{song.query}</h3>
        {/* 복사되는 검색어가 제목과 달라지는 이유만 짧게 적는다. 복사할 검색어는 title 에 있다. */}
        {song.fallback_query && <span className="cover-match-note">cover를 붙여야 검색돼요</span>}
        <WeekRecord week={song.week} windowDays={windowDays} />
        <span className="meta">
          <span title={absoluteTime(song.checked_at)}>{song.checked_at ? timeAgo(song.checked_at) : "검색 전"}</span>
          <span className="card-action">복사 & 새 탭</span>
        </span>
      </div>
    </button>
  );
}

/* 최근 7일 검사 결과를 점으로(점 하나가 검색 한 번, 왼쪽이 먼저). 같은 내용의 글은 화면 낭독기와
 * 마우스를 올렸을 때(title)만 보인다. 카드마다 같은 문장을 적으면 점과 글이 같은 말을 두 번 한다. */
function WeekRecord({ week, windowDays }) {
  const checks = week?.checks || 0;
  if (!checks) return <span className="week-record is-empty">최근 {windowDays}일 기록 없음</span>;
  const results = Array.isArray(week.results) ? week.results.slice(-MAX_MARKS) : [];
  const parts = ["blocked", "cover_only", "visible"]
    .filter((result) => week[result])
    .map((result) => `${RESULT_LABELS[result]} ${week[result]}`);
  const summary = `최근 ${windowDays}일 ${checks}번 검색: ${parts.join(", ")}`;
  return (
    <span className="week-record" title={summary}>
      <span className="week-marks" aria-hidden="true">
        {results.map((entry) => (
          <span key={`${entry.at}-${entry.result}`} className={`week-mark is-${entry.result}`} />
        ))}
      </span>
      <ScreenReaderText>{summary}</ScreenReaderText>
    </span>
  );
}
