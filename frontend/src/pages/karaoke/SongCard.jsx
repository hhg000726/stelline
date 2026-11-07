/* 곡 한 줄. 번호 두 개와 즐겨찾기·부를 곡 담기 버튼이 함께 있다. */
import { memo } from "react";

import { CATEGORY_LABELS, MACHINE_LABELS, SECTION_LABELS } from "./constants";
import { highlightParts } from "./search";

function Highlight({ text, query }) {
  return highlightParts(text, query).map((part, index) =>
    part.mark ? <mark key={index}>{part.text}</mark> : <span key={index}>{part.text}</span>,
  );
}

/* 고른 기기의 번호를 굵게, 나머지를 흐리게 둔다. 번호가 없으면 누를 수 없는 자리로 남긴다. */
export function NumberButton({ song, machine, selectedMachine, onCopy }) {
  const value = machine === "tj" ? song.tj : song.ky;
  const label = MACHINE_LABELS[machine];
  const emphasis = selectedMachine !== "both" && selectedMachine !== machine ? "is-secondary" : "is-primary";

  if (!value) {
    return (
      <span className={`num-btn is-empty ${emphasis}`}>
        <span className="num-label">{label}</span>
        <span className="num-value">없음</span>
      </span>
    );
  }

  return (
    <button
      type="button"
      className={`num-btn ${emphasis}`}
      title={`${label} ${value} 복사`}
      onClick={() => onCopy(value, machine)}
    >
      <span className="num-label">{label}</span>
      <span className="num-value">{value}</span>
    </button>
  );
}

function SongCardBase({ song, query, machine, isFavorite, inSetlist, onCopy, onToggleFavorite, onToggleSetlist }) {
  const tags = [SECTION_LABELS[song.section] || song.section, CATEGORY_LABELS[song.category] || song.category];

  return (
    <article className="song-card" data-key={song.key}>
      <div className="song-main">
        <p className="song-title">
          <Highlight text={song.title} query={query} />
        </p>
        <p className="song-meta">
          <span className="song-artist">
            <Highlight text={song.artist} query={query} />
          </span>
          {tags.map((tag) => (
            <span className="song-tag" key={tag}>
              {tag}
            </span>
          ))}
        </p>
      </div>
      <div className="song-numbers">
        <NumberButton song={song} machine="tj" selectedMachine={machine} onCopy={onCopy} />
        <NumberButton song={song} machine="ky" selectedMachine={machine} onCopy={onCopy} />
      </div>
      {/* 단추 글자가 기호(☆·+)뿐이라, 낭독기가 "흰 별"처럼 기호 이름을 읽지 않게 이름을 붙인다.
          목록에서 단추만 옮겨 다녀도 어느 곡인지 알도록 곡명을 앞에 둔다.
          켜졌는지는 aria-pressed 가 알려 주므로 이름은 그대로 둔다. */}
      <div className="song-actions">
        <button
          type="button"
          className={`icon-btn${isFavorite ? " is-on" : ""}`}
          aria-pressed={isFavorite}
          aria-label={`${song.title} 즐겨찾기`}
          title="즐겨찾기"
          onClick={() => onToggleFavorite(song)}
        >
          {isFavorite ? "★" : "☆"}
        </button>
        <button
          type="button"
          className={`icon-btn${inSetlist ? " is-on" : ""}`}
          aria-pressed={inSetlist}
          aria-label={`${song.title} 부를 곡 목록에 담기`}
          title="부를 곡 목록에 담기"
          onClick={() => onToggleSetlist(song)}
        >
          {inSetlist ? "−" : "+"}
        </button>
      </div>
    </article>
  );
}

/* 목록이 수십 줄이라, 값이 그대로인 줄은 다시 그리지 않게 한다.
 * (예전에는 즐겨찾기 하나를 눌러도 목록 전체 HTML 을 새로 만들어 붙였다.) */
export const SongCard = memo(SongCardBase);
