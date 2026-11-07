/* 제목 아래 '마지막 검색'·'다음 검색' 칩과, 마우스를 올리거나 누르면 펼쳐지는 곡 목록.
 *
 * 목록은 서버가 정한 그대로 보여 준다(search/status 의 last_run·next_run). 다음 검색은 예상이 아니라
 * 실제 회차와 같은 계산이라, 앞 곡이 모두 막혀도 반드시 검색하는 '최소 목록'과 앞 곡이 정상이면
 * 이어서 검색하는 '최대 목록'을 나눠 보여 준다.
 *
 * 마우스가 있는 기기는 올리기만 해도 열리고, 터치 기기는 눌러서 연다. 바깥을 누르거나 Esc 로 닫는다.
 */
import { useEffect, useId, useMemo, useRef, useState } from "react";

const RESULT_LABELS = { blocked: "막힘", cover_only: "cover로만", visible: "정상", unchecked: "검색 전" };

/* "11월 7일 09:00". 초까지 적힌 긴 시각은 칩 안에서 읽히지 않는다. */
export function shortTime(epochSeconds) {
  if (!epochSeconds) return "";
  const date = new Date(epochSeconds * 1000);
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${hh}:${mm}`;
}

/* 마우스가 칩·목록을 벗어난 뒤 이만큼 기다렸다가 닫는다. 칩에서 목록으로 옮겨 가거나 대각선으로
 * 움직이다 잠깐 벗어나도 바로 닫히지 않게 한다. */
const HOVER_CLOSE_DELAY_MS = 200;

export function RunPill({ label, value, children }) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef(null);
  const closeTimer = useRef(null);
  const panelId = useId();
  const canHover = useMemo(() => Boolean(window.matchMedia?.("(hover: hover)").matches), []);

  const openNow = () => {
    clearTimeout(closeTimer.current);
    setOpen(true);
  };
  const closeSoon = () => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(false), HOVER_CLOSE_DELAY_MS);
  };
  useEffect(() => () => clearTimeout(closeTimer.current), []);

  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = (event) => {
      if (!wrapper.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <span
      className="run-pill"
      ref={wrapper}
      onMouseEnter={canHover ? openNow : undefined}
      onMouseLeave={canHover ? closeSoon : undefined}
    >
      <button
        type="button"
        className="meta-pill run-pill-button"
        aria-expanded={open}
        aria-controls={panelId}
        // 마우스로 이미 열린 상태에서 누르면 닫히지 않게 한다(올려 둔 채 누르는 일이 잦다).
        onClick={() => setOpen((value) => (canHover ? true : !value))}
      >
        <span>{label}</span>
        <strong>{value}</strong>
      </button>
      {open && (
        <div className="run-popover" id={panelId} role="region" aria-label={`${label} 곡 목록`}>
          {children}
        </div>
      )}
    </span>
  );
}

function SongNames({ songs, dotOf }) {
  return (
    <ul className="run-names">
      {songs.map((song) => (
        <li key={song.query}>
          <span className={`week-mark is-${dotOf(song)}`} aria-hidden="true" />
          {song.query}
        </li>
      ))}
    </ul>
  );
}

export function LastRunDetails({ lastRun }) {
  if (!lastRun || !lastRun.songs?.length) return <p className="run-note">아직 검색 기록이 없어요.</p>;
  const groups = ["blocked", "cover_only", "visible"]
    .map((result) => ({ result, songs: lastRun.songs.filter((song) => song.result === result) }))
    .filter((group) => group.songs.length);
  return (
    <>
      <p className="run-head">
        {shortTime(lastRun.started_at)} 회차 · {lastRun.songs.length}곡
      </p>
      {groups.map((group) => (
        <section key={group.result}>
          <h4 className="run-subhead">
            {RESULT_LABELS[group.result]} {group.songs.length}
          </h4>
          <SongNames songs={group.songs} dotOf={(song) => song.result} />
        </section>
      ))}
    </>
  );
}

export function NextRunDetails({ nextRun, scheduleText }) {
  if (!nextRun || !nextRun.songs?.length) return <p className="run-note">검색할 곡이 없어요.</p>;
  const sure = nextRun.songs.slice(0, nextRun.sure);
  const more = nextRun.songs.slice(nextRun.sure);
  return (
    <>
      <p className="run-head">
        {shortTime(nextRun.at)}
        {scheduleText ? ` · ${scheduleText}` : ""}
      </p>
      <h4 className="run-subhead">최소 목록 · 반드시 검색 {sure.length}곡</h4>
      <SongNames songs={sure} dotOf={(song) => song.state} />
      {more.length > 0 && (
        <>
          <h4 className="run-subhead">최대 목록 · 앞 곡이 정상이면 이어서 {more.length}곡</h4>
          <SongNames songs={more} dotOf={(song) => song.state} />
        </>
      )}
      <p className="run-note">점 색은 지금 상태예요. 막혔던 곡을 먼저, 나머지는 돌아가며 검색해요.</p>
    </>
  );
}
