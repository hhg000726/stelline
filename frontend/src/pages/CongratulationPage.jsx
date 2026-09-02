/* 조회수 축하 화면.
 *
 * 최근 24시간 안에 달성한 기록을 카드로 보여 주고, 브라우저 알림을 켜고 끈다.
 * 목록 정렬(달성 시각 내림차순)과 배지 규칙은 예전 congratulation.js 그대로다.
 */
import { useEffect, useState } from "react";

import { ContentText } from "../components/ContentText";
import { EmptyState } from "../components/EmptyState";
import { Icon } from "../components/Icon";
import { SkeletonCards } from "../components/Loading";
import { ReportPanel } from "../components/ReportPanel";
import { useContentItem } from "../context/ContentContext";
import { api } from "../lib/api";
import { usePageMeta } from "../lib/usePageMeta";
import { useNotifications } from "./congratulation/useNotifications";

/* 배지 색을 정하는 기준.
 *
 * 100만·1000만 "단위"로 딱 떨어지는 기록만 눈에 띄게 한다. 1000만 단위가 가장 위다.
 * 120만이나 2500만처럼 중간에 걸친 기록은 기본 배지를 그대로 쓴다.
 * (인자는 만 단위 값이다. 100 = 100만, 1000 = 1000만)
 */
export function milestoneTier(tenThousands) {
  if (tenThousands <= 0) return "";
  if (tenThousands % 1000 === 0) return "is-ten-million";
  if (tenThousands % 100 === 0) return "is-million";
  return "";
}

/* 24시간 안에 나온 가장 큰 기록. 이 화면의 머리기사에 해당하는 값이라 제목 옆에 세운다.
 * (배지와 같은 기준으로 만 단위를 센다.) */
function topMilestone(items) {
  const best = items.reduce((max, song) => Math.max(max, Number(song.count) || 0), 0);
  return Math.floor(best / 100000) * 10;
}

function elapsedText(countedTime) {
  const diff = Date.now() - new Date(countedTime).getTime();
  const hours = Math.floor(diff / 3600000);
  return hours > 0 ? `${hours}시간 전` : "방금 전";
}

export default function CongratulationPage() {
  usePageMeta({
    title: "조회수 축하 · Stelline",
    description: "스텔라이브 영상의 조회수 달성 기록을 확인하고, 앱 설치 없이 브라우저 알림을 받아보세요.",
  });

  const [records, setRecords] = useState({ status: "loading", items: [] });
  const notifications = useNotifications();
  const prompt = useContentItem("congratulation_notify_prompt");

  useEffect(() => {
    let alive = true;
    api("congratulation/congratulations")
      .then((response) => response.json())
      .then((data) => {
        if (!alive) return;
        const items = Array.isArray(data) ? data.slice() : [];
        items.sort((a, b) => new Date(b.counted_time) - new Date(a.counted_time));
        setRecords({ status: "ready", items });
      })
      .catch((error) => {
        console.error("Error fetching songs:", error);
        if (alive) setRecords({ status: "error", items: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  // 상태 줄이 나올 때는 안내 문구가 그 자리를 비켜 준다(예전 is-status-replaced 와 같다).
  const statusShown = Boolean(notifications.status.text || notifications.extraNote);

  return (
    <>
      {/* 알림 설정은 이 화면의 핵심 동작이라, 따로 칸을 두지 않고 제목 바로 아래에 붙인다. */}
      <section className="congrats-hero">
        <div className="hero-heading">
          <div className="page-heading">
            <h1>조회수 축하</h1>
            {/* 안내 문구는 관리자 화면에서 고친다. 아래 상태 줄은 알릴 것이 생겼을 때만 나온다. */}
            {!prompt.hidden && (
              <p className={`page-subtitle${statusShown ? " is-status-replaced" : ""}`}>{prompt.value}</p>
            )}
            {/* 오늘 나온 가장 큰 기록. 목록을 훑기 전에 "오늘 무슨 일이 있었는지"를 한 줄로 알려 준다. */}
            {records.status === "ready" && records.items.length > 0 && (
              <div className="page-meta">
                <span className="meta-pill is-key">
                  <span>오늘 최고 기록</span>
                  <strong>{topMilestone(records.items).toLocaleString("ko-KR")}만</strong>
                </span>
              </div>
            )}
            <p
              id="status"
              className={`status-text ${notifications.status.tone}`.trim()}
              role="status"
              hidden={!statusShown}
            >
              {notifications.status.text}
              {notifications.extraNote && (
                <>
                  <br />
                  <strong className="status-note">{notifications.extraNote}</strong>
                </>
              )}
            </p>
          </div>
          <ReportPanel
            endpoint="congratulation/reports"
            openLabel="누락된 노래 제보"
            closeLabel="제보 입력 닫기"
            title="조회수 알림에서 누락된 노래를 알려주세요"
            description="조회수 알림 목록에 없는 노래를 제보하거나, 추가했으면 하는 내용을 남겨주세요."
            fieldLabel="제보 내용"
            placeholder="노래 제목, 영상 링크 또는 추가 의견을 입력하세요"
            submitLabel="제보 보내기"
          />
        </div>
        <div className="notification-actions">
          <button
            id="enableNotificationsButton"
            className={`btn-primary ${notifications.enableButton.state || ""}`.trim()}
            type="button"
            disabled={notifications.enableButton.disabled}
            onClick={notifications.enable}
          >
            <Icon name="bell" /> {notifications.enableButton.label}
          </button>
          <button
            id="disableNotificationsButton"
            className="btn-secondary"
            type="button"
            disabled={notifications.disableButton.disabled}
            onClick={notifications.disable}
          >
            {notifications.disableButton.label}
          </button>
        </div>
      </section>

      <section className="congrats-section">
        <div className="section-header">
          <div className="section-title">
            <h2>최근 24시간 이내 달성</h2>
            <ContentText contentKey="congratulation_list_note" />
          </div>
          <span id="resultsCount" className="results-count">
            {records.status === "ready" ? `${records.items.length}개 기록` : "0개 기록"}
          </span>
        </div>
        <div id="congratulationTable" className="card-grid is-compact" aria-live="polite">
          {records.status === "loading" && <SkeletonCards count={8} />}
          {records.status === "error" && <EmptyState isError>기록을 불러오지 못했습니다.</EmptyState>}
          {records.status === "ready" && records.items.length === 0 && (
            <EmptyState>최근 24시간 이내 달성 기록이 아직 없습니다.</EmptyState>
          )}
          {records.status === "ready" && records.items.map((song) => <RecordCard key={`${song.video_id}-${song.counted_time}`} song={song} />)}
        </div>
      </section>
    </>
  );
}

/* 카드 전체가 "유튜브로 이동"이라 버튼 줄을 따로 두지 않는다. 나가는 자리이므로
 * 버튼이 아닌 링크로 둔다. 그래야 새 탭으로 열거나 주소를 미리 보는 것이 그대로 된다. */
function RecordCard({ song }) {
  // 배지에는 순번 대신 달성 기록을 넣는다. 목록에서 바로 읽히는 값이다.
  const tenThousands = Math.floor(song.count / 100000) * 10;
  const tier = milestoneTier(tenThousands);

  return (
    <a
      className="card is-link"
      href={`https://www.youtube.com/watch?v=${encodeURIComponent(song.video_id)}`}
      target="_blank"
      rel="noopener noreferrer"
    >
      <div className="thumb-wrap">
        <span className={`card-badge${tier ? ` ${tier}` : ""}`}>
          {tenThousands.toLocaleString("ko-KR")}만
        </span>
        <img src={`https://img.youtube.com/vi/${song.video_id}/0.jpg`} alt="" loading="lazy" />
        <span className="thumb-play">
          <Icon name="play" />
        </span>
      </div>
      <div className="info">
        <h3>{song.title || "조회수 달성"}</h3>
        <div className="meta">
          <span>{elapsedText(song.counted_time)}</span>
          <span className="card-action">유튜브로 이동</span>
        </div>
      </div>
    </a>
  );
}
