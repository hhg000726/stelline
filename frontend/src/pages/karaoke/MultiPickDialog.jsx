/* 랜덤 여러 곡.
 *
 * 지금 목록에 걸린 필터를 그대로 써서 여러 곡을 한 번에 뽑는다. 어떤 조건으로
 * 뽑았는지 위쪽에 드러내(필터를 걸었는지 한눈에 알게 한다), 각 곡은 낱개로 빼거나
 * 즐겨찾기·부를 곡에 담을 수 있다. 목록 전체를 한 번에 담는 단추도 둔다.
 * 여닫기·뒤 화면 잠금·초점 되돌리기는 랜덤 한 곡과 같은 useModal 이 맡는다.
 */
import { useEffect, useRef } from "react";

import { useModal } from "../../lib/useModal";
import { MACHINE_LABELS, MULTI_PICK_MAX } from "./constants";

const QUICK_COUNTS = [3, 5, 10];

export function MultiPickDialog({
  open,
  songs,
  count,
  onCountChange,
  poolSize,
  totalSize,
  tags,
  favorites,
  setlistKeys,
  onCopy,
  onToggleFavorite,
  onToggleSetlist,
  onRemove,
  onReroll,
  onFavoriteAll,
  onSetlistAll,
  onClose,
}) {
  const card = useRef(null);

  useModal(open, onClose);

  /* 창을 열거나 다시 뽑아 목록이 바뀌면 창 자체에 초점을 준다. 낭독기가 새 목록의
     첫머리를 읽어 주고, 키보드만 쓰는 사람도 창 안에서 계속 움직일 수 있다. */
  useEffect(() => {
    if (open) card.current?.focus();
  }, [open, songs.length]);

  if (!open) return null;

  const max = Math.max(1, Math.min(MULTI_PICK_MAX, poolSize));
  const filtered = tags.length > 0;
  const allFavorite = songs.length > 0 && songs.every((song) => favorites.has(song.key));
  const allSetlist = songs.length > 0 && songs.every((song) => setlistKeys.has(song.key));

  return (
    <div
      id="multi-pick-dialog"
      className="pick-dialog multi-pick"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="pick-card multi-pick-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="multi-pick-title"
        ref={card}
        tabIndex={-1}
      >
        <p className="pick-kicker">랜덤 여러 곡</p>
        <h2 id="multi-pick-title">
          {filtered ? `조건에 맞는 ${poolSize}곡에서` : `전체 ${totalSize}곡에서`}
        </h2>

        {/* 뽑기 전에도 뽑은 뒤에도, 어떤 조건으로 뽑는(뽑은) 곡인지 늘 보인다. */}
        <div className="multi-pick-filters" aria-label="적용된 필터">
          {filtered ? (
            tags.map((tag) => (
              <span className="multi-pick-tag" key={tag}>
                {tag}
              </span>
            ))
          ) : (
            <span className="multi-pick-tag is-muted">필터 없음 · 전체에서</span>
          )}
        </div>

        <div className="multi-pick-count">
          <span id="multi-pick-count-label">뽑을 곡 수</span>
          <div className="multi-pick-stepper" role="group" aria-labelledby="multi-pick-count-label">
            <button
              type="button"
              className="icon-btn"
              aria-label="한 곡 줄이기"
              disabled={count <= 1}
              onClick={() => onCountChange(count - 1)}
            >
              −
            </button>
            <input
              id="multi-pick-count"
              type="number"
              min={1}
              max={max}
              value={count}
              aria-label="뽑을 곡 수"
              onChange={(event) => onCountChange(Number(event.target.value))}
            />
            <button
              type="button"
              className="icon-btn"
              aria-label="한 곡 늘리기"
              disabled={count >= max}
              onClick={() => onCountChange(count + 1)}
            >
              +
            </button>
          </div>
          <div className="multi-pick-quick">
            {QUICK_COUNTS.filter((value) => value <= max).map((value) => (
              <button
                type="button"
                key={value}
                className={`kara-chip${count === value ? " is-on" : ""}`}
                aria-pressed={count === value}
                onClick={() => onCountChange(value)}
              >
                {value}곡
              </button>
            ))}
          </div>
        </div>

        <button
          id="multi-pick-reroll"
          className="btn-primary multi-pick-reroll"
          type="button"
          onClick={onReroll}
        >
          {songs.length ? "다시 뽑기" : "뽑기"}
        </button>

        {songs.length > 0 && (
          <>
            <ol id="multi-pick-list" className="multi-pick-list">
              {songs.map((song) => {
                const numbers = [];
                if (song.tj) numbers.push({ machine: "tj", value: song.tj });
                if (song.ky) numbers.push({ machine: "ky", value: song.ky });
                const fav = favorites.has(song.key);
                const inList = setlistKeys.has(song.key);
                return (
                  <li className="multi-pick-item" key={song.key}>
                    <div className="multi-pick-song">
                      <strong>{song.title}</strong>
                      <span>{song.artist}</span>
                    </div>
                    <div className="multi-pick-numbers">
                      {numbers.length ? (
                        numbers.map((item) => (
                          <button
                            type="button"
                            key={item.machine}
                            className="num-btn is-primary"
                            onClick={() => onCopy(item.value, item.machine)}
                          >
                            <span className="num-label">{MACHINE_LABELS[item.machine]}</span>
                            <span className="num-value">{item.value}</span>
                          </button>
                        ))
                      ) : (
                        <span className="multi-pick-nonum">번호 없음</span>
                      )}
                    </div>
                    <div className="multi-pick-actions">
                      <button
                        type="button"
                        className={`icon-btn${fav ? " is-on" : ""}`}
                        aria-pressed={fav}
                        title="즐겨찾기"
                        onClick={() => onToggleFavorite(song)}
                      >
                        {fav ? "★" : "☆"}
                      </button>
                      <button
                        type="button"
                        className={`icon-btn${inList ? " is-on" : ""}`}
                        aria-pressed={inList}
                        title="부를 곡 목록에 담기"
                        onClick={() => onToggleSetlist(song)}
                      >
                        {inList ? "−" : "+"}
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        title="이 곡 빼기"
                        aria-label={`${song.title} 빼기`}
                        onClick={() => onRemove(song.key)}
                      >
                        ×
                      </button>
                    </div>
                  </li>
                );
              })}
            </ol>

            <div className="multi-pick-bulk">
              <button
                id="multi-pick-favorite-all"
                type="button"
                className="btn-secondary"
                disabled={allFavorite}
                onClick={onFavoriteAll}
              >
                {allFavorite ? "★ 모두 즐겨찾기에 있음" : "☆ 전체 즐겨찾기 추가"}
              </button>
              <button
                id="multi-pick-setlist-all"
                type="button"
                className="btn-secondary"
                disabled={allSetlist}
                onClick={onSetlistAll}
              >
                {allSetlist ? "✓ 전체 부를 곡에 담김" : "+ 전체 부를 곡 추가"}
              </button>
            </div>
          </>
        )}

        <div className="pick-actions">
          <button id="multi-pick-close" className="btn-secondary" type="button" onClick={onClose}>
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
