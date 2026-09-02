/* 랜덤 한 곡.
 *
 * 뽑은 곡이 이미 담겨 있으면 버튼을 눌린 상태로 두어 두 번 담기지 않게 한다.
 * 바깥을 누르거나 Esc 로 닫는다.
 */
import { useEffect } from "react";

import { MACHINE_LABELS } from "./constants";

export function PickDialog({ song, isFavorite, inSetlist, onCopy, onFavorite, onSetlist, onAgain, onClose }) {
  useEffect(() => {
    if (!song) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [song, onClose]);

  if (!song) return null;

  const numbers = [];
  if (song.tj) numbers.push({ machine: "tj", value: song.tj });
  if (song.ky) numbers.push({ machine: "ky", value: song.ky });

  return (
    <div
      id="pick-dialog"
      className="pick-dialog"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="pick-card" role="dialog" aria-modal="true" aria-labelledby="pick-title">
        <p className="pick-kicker">오늘의 한 곡</p>
        <h2 id="pick-title">{song.title}</h2>
        <p id="pick-artist" className="pick-artist">
          {song.artist}
        </p>
        <div id="pick-numbers" className="pick-numbers">
          {numbers.length ? (
            numbers.map((item) => (
              <button
                key={item.machine}
                type="button"
                className="num-btn is-primary"
                onClick={() => onCopy(item.value, item.machine)}
              >
                <span className="num-label">{MACHINE_LABELS[item.machine]}</span>
                <span className="num-value">{item.value}</span>
              </button>
            ))
          ) : (
            <p className="empty-state">
              아직 노래방 번호가 없는 곡이에요.
              <br />
              필터의 “번호 있는 곡만”을 켜면 부를 수 있는 곡만 뽑습니다.
            </p>
          )}
        </div>
        <div className="pick-collect">
          <button
            id="pick-favorite"
            className={`btn-secondary${isFavorite ? " is-on" : ""}`}
            type="button"
            disabled={isFavorite}
            aria-pressed={isFavorite}
            onClick={onFavorite}
          >
            {isFavorite ? "★ 즐겨찾기에 있음" : "☆ 즐겨찾기 추가"}
          </button>
          <button
            id="pick-setlist"
            className={`btn-secondary${inSetlist ? " is-on" : ""}`}
            type="button"
            disabled={inSetlist}
            aria-pressed={inSetlist}
            onClick={onSetlist}
          >
            {inSetlist ? "✓ 부를 곡에 담김" : "+ 부를 곡 추가"}
          </button>
        </div>
        <div className="pick-actions">
          <button id="pick-again" className="btn-secondary" type="button" onClick={onAgain}>
            다시 뽑기
          </button>
          <button id="pick-close" className="btn-primary" type="button" onClick={onClose}>
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
