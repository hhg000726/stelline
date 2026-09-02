/* 노래방 번호 화면.
 *
 * 곡 목록은 한 번만 받아 두고 검색·필터·정렬은 모두 브라우저에서 처리한다.
 * 즐겨찾기와 부를 곡 목록은 로그인 없이 쓰도록 브라우저 저장소에만 남긴다.
 * (예전 karaoke.js 와 같은 규칙·같은 저장소 키·같은 문구를 쓴다.)
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ContentText } from "../components/ContentText";
import { EmptyState } from "../components/EmptyState";
import { SkeletonRows } from "../components/Loading";
import { ReportPanel } from "../components/ReportPanel";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";
import { copyText } from "../lib/clipboard";
import { readStore, writeStore } from "../lib/storage";
import { usePageMeta } from "../lib/usePageMeta";
import { FilterPanel } from "./karaoke/FilterPanel";
import { PickDialog } from "./karaoke/PickDialog";
import { SetlistBar } from "./karaoke/SetlistBar";
import { SongCard } from "./karaoke/SongCard";
import { MACHINE_LABELS, NARROW, PAGE_SIZE, STORAGE_KEYS } from "./karaoke/constants";
import { activeFilterCount, filtersReducer, filtersToParams, initFilters } from "./karaoke/filters";
import { applyFilters, decorate, hasNumber } from "./karaoke/search";
import "../styles/karaoke.css";

const MACHINES = [
  { value: "tj", label: "TJ" },
  { value: "ky", label: "금영" },
  { value: "both", label: "둘 다" },
];

export default function KaraokePage() {
  usePageMeta({
    title: "노래방 번호 · Stelline",
    description: "스텔라이브 곡의 TJ·금영 노래방 번호를 검색하고, 즐겨찾기와 부를 곡 목록으로 정리할 수 있습니다.",
  });

  const toast = useToast();
  const location = useLocation();
  const navigate = useNavigate();

  const [filters, dispatch] = useReducer(
    filtersReducer,
    { search: window.location.search, savedMachine: readStore(STORAGE_KEYS.machine, "both") },
    initFilters,
  );

  const [data, setData] = useState({ status: "loading", songs: [], members: [], updatedAt: "" });
  const [showOfflineNote, setShowOfflineNote] = useState(false);
  const [favorites, setFavorites] = useState(() => new Set(readStore(STORAGE_KEYS.favorites, [])));
  const [setlist, setSetlist] = useState(() =>
    readStore(STORAGE_KEYS.setlist, []).filter((key) => typeof key === "string"),
  );
  const [shownCount, setShownCount] = useState(PAGE_SIZE);
  const [searchInput, setSearchInput] = useState(filters.query);
  const [filterOpen, setFilterOpen] = useState(() => activeFilterCount(filters) > 0);
  const [setlistOpen, setSetlistOpen] = useState(false);
  const [pick, setPick] = useState(null);

  const searchField = useRef(null);
  const appliedHash = useRef("");

  /* ---------- 곡 목록 ----------
   * 저장해 둔 목록이 있으면 먼저 보여 주고, 받아온 뒤 갈아 끼운다.
   * 받아오지 못했더라도 저장해 둔 것이 있으면 그걸 계속 쓰고 안내만 띄운다. */
  useEffect(() => {
    let alive = true;
    const cached = readStore(STORAGE_KEYS.cache, null);
    let hadCache = false;
    if (cached && cached.songs) {
      hadCache = true;
      setData({ status: "ready", songs: cached.songs.map(decorate), members: cached.members || [], updatedAt: cached.updatedAt || "" });
    }

    api("karaoke/songs")
      .then((response) => {
        if (!response.ok) throw new Error("목록을 불러오지 못했습니다.");
        return response.json();
      })
      .then((payload) => {
        if (!alive) return;
        setShowOfflineNote(false);
        writeStore(STORAGE_KEYS.cache, payload);
        setData({
          status: "ready",
          songs: (payload.songs || []).map(decorate),
          members: payload.members || [],
          updatedAt: payload.updatedAt || "",
        });
      })
      .catch(() => {
        if (!alive) return;
        // 저장해 둔 목록이 있으면 그대로 두고 안내만 띄운다.
        if (hadCache) setShowOfflineNote(true);
        else setData({ status: "error", songs: [], members: [], updatedAt: "" });
      });

    return () => {
      alive = false;
    };
  }, []);

  const songs = data.songs;

  const songByKey = useMemo(() => new Map(songs.map((song) => [song.key, song])), [songs]);
  const songById = useMemo(() => new Map(songs.map((song) => [song.id, song])), [songs]);

  // 저장해 둔 목록에서 지금은 사라진 곡은 정리한다.
  useEffect(() => {
    if (data.status !== "ready" || !songs.length) return;
    setSetlist((prev) => {
      const kept = prev.filter((key) => songByKey.has(key));
      return kept.length === prev.length ? prev : kept;
    });
    // 저장소도 함께 맞춘다. 다음 방문에 없는 곡을 또 들고 오지 않게 한다.
  }, [data.status, songs.length, songByKey]);

  /* ---------- 주소 표시줄 ----------
   * 지금 보고 있는 목록을 그대로 공유하거나 새로 고쳐도 같은 목록이 나오게 한다.
   * 값이 그대로면 아무것도 하지 않는다(같은 주소로 계속 옮겨 다니지 않게 한다). */
  useEffect(() => {
    const next = filtersToParams(filters).toString();
    if (next === location.search.replace(/^\?/, "")) return;
    navigate({ pathname: location.pathname, search: next ? `?${next}` : "" }, { replace: true });
  }, [filters, location.pathname, location.search, navigate]);

  /* 검색어·필터·정렬이 바뀌면 목록의 내용 자체가 달라지므로 다시 처음부터 그린다.
   * 즐겨찾기처럼 목록이 그대로인 동작에서는 접지 않는다(보던 자리가 접히면 안 된다). */
  useEffect(() => {
    setShownCount(PAGE_SIZE);
  }, [filters]);

  /* 검색어는 한 글자마다 목록을 다시 고르지 않고 잠깐 모아서 처리한다. */
  useEffect(() => {
    const timer = window.setTimeout(() => {
      dispatch({ type: "set", key: "query", value: searchInput });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  /* ---------- 목록 계산 ---------- */
  const { list, query } = useMemo(
    () => applyFilters(songs, filters, favorites),
    [songs, filters, favorites],
  );

  const page = list.slice(0, shownCount);
  const remaining = list.length - page.length;
  const numbered = useMemo(() => list.filter((song) => hasNumber(song, filters.machine)).length, [list, filters.machine]);

  // 다 그리지 못했을 때는 지금 몇 곡을 보고 있는지도 함께 알려 준다.
  const resultCount = useMemo(() => {
    if (!songs.length) return "";
    const parts = [remaining > 0 ? `${page.length}/${list.length}곡` : `${list.length}곡`];
    parts.push(`번호 있는 곡 ${numbered}곡`);
    if (list.length !== songs.length) parts.push(`전체 ${songs.length}곡`);
    return parts.join(" · ");
  }, [songs.length, list.length, page.length, remaining, numbered]);

  const setlistKeys = useMemo(() => new Set(setlist), [setlist]);
  const setlistSongs = useMemo(
    () => setlist.map((key) => songByKey.get(key)).filter(Boolean),
    [setlist, songByKey],
  );

  /* 랜덤순은 화면을 여는 동안에는 고정이어야 한다. 검색어를 칠 때마다 순서가
   * 바뀌면 목록을 눈으로 따라갈 수 없다. 그래서 곡마다 섞기 값을 한 번 정해 둔다. */
  const reshuffle = useCallback(() => {
    setData((prev) => ({
      ...prev,
      songs: prev.songs.map((song) => ({ ...song, shuffle: Math.random() })),
    }));
  }, []);

  /* ---------- 담기·복사 ---------- */
  const recordCopy = useCallback(() => {
    // 통계 실패는 화면 동작에 영향을 주지 않는다.
    api("karaoke/record_copy", { method: "POST" }).catch(() => {});
  }, []);

  const copyNumber = useCallback(
    async (value, machine, failText) => {
      const copied = await copyText(value);
      toast(copied ? `${MACHINE_LABELS[machine]} ${value} 복사했어요` : failText);
      if (copied) recordCopy();
    },
    [recordCopy, toast],
  );

  const copyFromList = useCallback(
    (value, machine) => copyNumber(value, machine, "복사하지 못했어요. 번호를 길게 눌러 복사해주세요."),
    [copyNumber],
  );
  const copyFromPick = useCallback(
    (value, machine) => copyNumber(value, machine, "복사하지 못했어요."),
    [copyNumber],
  );

  /* 상태 갱신 함수 안에서 저장·말풍선 같은 바깥일을 하면, React 가 그 함수를 두 번
   * 부를 때 두 번 일어난다. 최신 값을 따로 들고 있다가 바깥에서 한 번만 처리한다. */
  const latest = useRef({ favorites, setlist });
  latest.current = { favorites, setlist };

  const saveFavorites = useCallback((next) => {
    setFavorites(next);
    writeStore(STORAGE_KEYS.favorites, Array.from(next));
  }, []);

  const saveSetlist = useCallback((next) => {
    setSetlist(next);
    writeStore(STORAGE_KEYS.setlist, next);
  }, []);

  const toggleFavorite = useCallback(
    (song) => {
      const next = new Set(latest.current.favorites);
      if (next.has(song.key)) next.delete(song.key);
      else next.add(song.key);
      saveFavorites(next);
    },
    [saveFavorites],
  );

  const toggleSetlist = useCallback(
    (song) => {
      const current = latest.current.setlist;
      const index = current.indexOf(song.key);
      saveSetlist(index >= 0 ? current.filter((key) => key !== song.key) : [...current, song.key]);
      toast(index >= 0 ? "목록에서 뺐어요" : "부를 곡 목록에 담았어요");
    },
    [saveSetlist, toast],
  );

  const moveInSetlist = useCallback(
    (index, step) => {
      const current = latest.current.setlist;
      const target = index + step;
      if (target < 0 || target >= current.length) return;
      const next = current.slice();
      next.splice(target, 0, next.splice(index, 1)[0]);
      saveSetlist(next);
    },
    [saveSetlist],
  );

  const removeFromSetlist = useCallback(
    (index) => {
      saveSetlist(latest.current.setlist.filter((unused, position) => position !== index));
    },
    [saveSetlist],
  );

  const setlistText = useCallback(
    () =>
      setlistSongs
        .map((song, index) => {
          const numbers = [];
          if (song.tj && filters.machine !== "ky") numbers.push(`TJ ${song.tj}`);
          if (song.ky && filters.machine !== "tj") numbers.push(`금영 ${song.ky}`);
          return `${index + 1}. ${song.title} - ${song.artist}${numbers.length ? ` (${numbers.join(", ")})` : " (번호 없음)"}`;
        })
        .join("\n"),
    [setlistSongs, filters.machine],
  );

  /* ---------- 공유받은 목록 ---------- */
  useEffect(() => {
    const match = location.hash.match(/list=([0-9,]+)/);
    if (!match || !songs.length) return;
    if (appliedHash.current === location.hash) return;
    appliedHash.current = location.hash;

    const shared = match[1]
      .split(",")
      .map((value) => songById.get(Number(value)))
      .filter(Boolean);

    // 주소에서 목록 부분을 먼저 걷어 낸다. 새로 고쳤을 때 다시 묻지 않게 하려는 것이다.
    navigate(`${location.pathname}${location.search}`, { replace: true });

    if (!shared.length) {
      toast("공유된 목록의 곡을 찾지 못했습니다.");
      return;
    }
    if (setlist.length && !window.confirm(`공유받은 ${shared.length}곡으로 부를 곡 목록을 바꿀까요? 지금 담아둔 목록은 사라집니다.`)) {
      return;
    }
    saveSetlist(shared.map((song) => song.key));
    toast(`공유받은 ${shared.length}곡을 불러왔습니다.`);
    // setlist 는 확인 창에서 한 번 읽을 뿐이라 아래 목록에 넣지 않는다. 넣으면 목록을
    // 바꿀 때마다 이 효과가 다시 돌아, 이미 지운 주소를 또 살펴보게 된다.
  }, [location.hash, songs.length, songById, navigate, saveSetlist, toast]);

  /* ---------- 랜덤 한 곡 ---------- */
  const showRandomPick = useCallback(() => {
    if (!list.length) return;
    setPick(list[Math.floor(Math.random() * list.length)]);
  }, [list]);

  const filterCount = activeFilterCount(filters);

  return (
    <>
      <section className="page-shell">
        <div className="hero-heading">
          <div className="page-heading">
            <h1 className="page-title">노래방 번호</h1>
            <p className="page-subtitle">
              <ContentText contentKey="karaoke_hero_subtitle" as="span" />{" "}
              <span id="last-updated" className="meta-text">
                {data.updatedAt ? `마지막 갱신: ${data.updatedAt}` : ""}
              </span>
            </p>
          </div>
          <ReportPanel
            endpoint="karaoke/reports"
            openLabel="번호 제보"
            closeLabel="제보 입력 닫기"
            title="빠진 번호나 잘못된 정보를 알려주세요"
            description="새로 나온 노래방 번호, 잘못 적힌 번호, 목록에 없는 곡을 남겨주시면 확인 후 반영하겠습니다."
            fieldLabel="제보 내용"
            placeholder="예) 유즈하 리코 - 용사 / TJ 68860 로 수정 부탁드립니다"
            submitLabel="제보 보내기"
          />
        </div>

        <div className="kara-controls">
          <div className="kara-search">
            <svg
              className="kara-search-icon"
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              id="search-input"
              ref={searchField}
              type="search"
              autoComplete="off"
              /* 좁은 화면에서는 긴 안내가 괄호 한가운데서 잘려 고장난 것처럼 보인다.
                 같은 내용을 짧게 줄여 끝까지 읽히게 한다(낭독기가 읽는 aria-label 은 그대로다). */
              placeholder={NARROW ? "곡명·가수·번호·초성 검색" : "곡명·가수·번호 검색 (ㄱㅅㅇㄲㄴㄹ 처럼 초성도 가능)"}
              aria-label="곡 검색"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <button
              id="search-clear"
              className="kara-clear"
              type="button"
              hidden={!searchInput}
              aria-label="검색어 지우기"
              onClick={() => {
                setSearchInput("");
                searchField.current?.focus();
              }}
            >
              ×
            </button>
          </div>

          <div className="kara-toolbar">
            <div className="machine-switch" role="group" aria-label="노래방 기기 선택">
              {MACHINES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={filters.machine === option.value ? "is-on" : undefined}
                  aria-pressed={filters.machine === option.value}
                  onClick={() => {
                    dispatch({ type: "set", key: "machine", value: option.value });
                    writeStore(STORAGE_KEYS.machine, option.value);
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <label className="kara-sort" htmlFor="sort-select">
              정렬
              <select
                id="sort-select"
                aria-label="정렬 기준"
                value={filters.sort}
                onChange={(event) => {
                  // 랜덤순을 다시 고르면 새로 섞어 준다.
                  if (event.target.value === "random") reshuffle();
                  dispatch({ type: "set", key: "sort", value: event.target.value });
                }}
              >
                <option value="random">랜덤순</option>
                <option value="title">가나다순</option>
              </select>
            </label>
            <button
              id="filter-toggle"
              className="kara-chip-button"
              type="button"
              aria-expanded={filterOpen}
              onClick={() => setFilterOpen((prev) => !prev)}
            >
              필터{" "}
              <span id="filter-count" className="kara-badge" hidden={filterCount === 0}>
                {filterCount}
              </span>
            </button>
            <div className="kara-toolbar-end">
              <p id="result-count" className="results-count">
                {data.status === "loading" ? "불러오는 중…" : resultCount}
              </p>
              <button
                id="random-pick"
                className="btn-secondary btn-small"
                type="button"
                disabled={list.length === 0}
                onClick={showRandomPick}
              >
                🎲 랜덤 한 곡
              </button>
            </div>
          </div>

          <FilterPanel
            hidden={!filterOpen}
            members={data.members}
            songs={songs}
            filters={filters}
            dispatch={dispatch}
          />
        </div>

        <p id="offline-note" className="kara-offline" hidden={!showOfflineNote}>
          지금은 저장해 둔 목록을 보여주고 있습니다. 연결되면 자동으로 새로 고쳐집니다.
        </p>

        <div id="song-list" className="kara-list" aria-live="polite">
          {data.status === "loading" && <SkeletonRows count={6} />}
          {data.status === "error" && (
            <EmptyState>목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</EmptyState>
          )}
          {data.status === "ready" && !songs.length && <EmptyState>등록된 곡이 없습니다.</EmptyState>}
          {data.status === "ready" && songs.length > 0 && !list.length && (
            <EmptyState>조건에 맞는 곡이 없습니다. 검색어나 필터를 바꿔보세요.</EmptyState>
          )}
          {data.status === "ready" &&
            page.map((song) => (
              <SongCard
                key={song.key}
                song={song}
                query={query}
                machine={filters.machine}
                isFavorite={favorites.has(song.key)}
                inSetlist={setlistKeys.has(song.key)}
                onCopy={copyFromList}
                onToggleFavorite={toggleFavorite}
                onToggleSetlist={toggleSetlist}
              />
            ))}
        </div>

        <button
          id="load-more"
          className="btn-secondary kara-more"
          type="button"
          hidden={remaining <= 0}
          onClick={() => setShownCount((prev) => prev + PAGE_SIZE)}
        >
          {remaining}곡 더 보기
        </button>
      </section>

      <SetlistBar
        songs={setlistSongs}
        open={setlistOpen}
        onToggle={() => setSetlistOpen((prev) => !prev)}
        onMove={moveInSetlist}
        onRemove={removeFromSetlist}
        onCopy={async () => {
          const copied = await copyText(setlistText());
          toast(copied ? "목록을 복사했어요" : "복사하지 못했어요");
        }}
        onShare={async () => {
          const ids = setlistSongs.map((song) => song.id).join(",");
          const link = `${window.location.origin}${window.location.pathname}#list=${ids}`;
          const copied = await copyText(link);
          toast(copied ? "공유 링크를 복사했어요" : "복사하지 못했어요");
        }}
        onClear={() => {
          if (!window.confirm("부를 곡 목록을 비울까요?")) return;
          saveSetlist([]);
        }}
      />

      <PickDialog
        song={pick}
        isFavorite={Boolean(pick) && favorites.has(pick.key)}
        inSetlist={Boolean(pick) && setlistKeys.has(pick.key)}
        onCopy={copyFromPick}
        onFavorite={() => {
          if (!pick || favorites.has(pick.key)) return;
          toggleFavorite(pick);
          toast("즐겨찾기에 담았어요");
        }}
        onSetlist={() => {
          if (!pick || setlistKeys.has(pick.key)) return;
          toggleSetlist(pick);
        }}
        onAgain={showRandomPick}
        onClose={() => setPick(null)}
      />
    </>
  );
}
