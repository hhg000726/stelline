/* 화면 아래 붙는 "부를 곡" 목록.
 *
 * 담은 곡이 없으면 바 자체가 사라진다. 바가 보이는 동안에는 그 높이를
 * --floating-offset 으로 알려 두어, 다크 모드 버튼과 말풍선이 그 위로 비켜선다.
 */
import { useEffect, useLayoutEffect, useRef } from "react";

export function SetlistBar({ songs, open, onToggle, onMove, onRemove, onCopy, onShare, onClear }) {
  const bar = useRef(null);

  /* 바의 높이가 달라지는 순간(담기·비우기·펼치기)마다 다시 알린다. */
  useLayoutEffect(() => {
    const height = songs.length ? bar.current?.offsetHeight || 0 : 0;
    document.documentElement.style.setProperty("--floating-offset", `${height}px`);
  }, [songs.length, open]);

  // 다른 화면으로 옮겨 가면 바가 사라지므로 비켜서 있을 이유도 없다.
  useEffect(
    () => () => {
      document.documentElement.style.removeProperty("--floating-offset");
    },
    [],
  );

  return (
    <div id="setlist-bar" className="setlist-bar" ref={bar} hidden={songs.length === 0}>
      <div className="setlist-bar-top">
        <button
          id="setlist-toggle"
          className={`setlist-summary${open ? " is-open" : ""}`}
          type="button"
          aria-expanded={open}
          onClick={onToggle}
        >
          <span>
            부를 곡 <strong id="setlist-count">{songs.length}</strong>곡
          </span>
          <span className="setlist-caret" aria-hidden="true">
            ▾
          </span>
        </button>
      </div>
      <div id="setlist-panel" className="setlist-panel" hidden={!open || songs.length === 0}>
        <ol id="setlist-items" className="setlist-items">
          {songs.map((song, index) => (
            <li className="setlist-item" data-key={song.key} key={song.key}>
              <span className="setlist-name">
                <strong>{song.title}</strong>
                <span>{song.artist}</span>
              </span>
              <span className="setlist-numbers">
                {song.tj ? `TJ ${song.tj}` : ""}
                {song.tj && song.ky ? " · " : ""}
                {song.ky ? `금영 ${song.ky}` : ""}
                {!song.tj && !song.ky ? "번호 없음" : ""}
              </span>
              <span className="setlist-buttons">
                <button
                  type="button"
                  className="icon-btn"
                  disabled={index === 0}
                  aria-label="위로"
                  onClick={() => onMove(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="icon-btn"
                  disabled={index === songs.length - 1}
                  aria-label="아래로"
                  onClick={() => onMove(index, 1)}
                >
                  ↓
                </button>
                <button type="button" className="icon-btn" aria-label="빼기" onClick={() => onRemove(index)}>
                  ×
                </button>
              </span>
            </li>
          ))}
        </ol>
        <div className="setlist-actions">
          <button id="setlist-copy" className="btn-primary" type="button" onClick={onCopy}>
            목록 복사
          </button>
          <button id="setlist-share" className="btn-secondary" type="button" onClick={onShare}>
            공유 링크 복사
          </button>
          <button id="setlist-clear" className="btn-secondary" type="button" onClick={onClear}>
            비우기
          </button>
        </div>
      </div>
    </div>
  );
}
