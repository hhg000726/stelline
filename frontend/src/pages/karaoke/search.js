/* 곡 검색·필터·정렬. 예전 karaoke.js 의 계산 부분을 그대로 옮겼다.
 *
 * 화면을 그리는 일과 떨어져 있어야 규칙을 눈으로 따라갈 수 있고, 값이 바뀌지 않았을 때
 * 다시 계산하지 않게 묶어 두기도 쉽다.
 */
import { CHOSEONG, CHOSEONG_ONLY, KEY_SEPARATOR, KO_COLLATOR } from "./constants";

export function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣぁ-んァ-ヺ一-龥]/g, "");
}

export function toChoseong(value) {
  let result = "";
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) {
      result += CHOSEONG[Math.floor((code - 0xac00) / 588)];
    } else {
      result += character;
    }
  }
  return result;
}

export function prepareQuery(raw) {
  const normalized = normalizeText(raw);
  return {
    raw: String(raw || "").trim(),
    normalized,
    isChoseong: normalized.length > 0 && CHOSEONG_ONLY.test(normalized),
  };
}

export function songKey(song) {
  return song.title + KEY_SEPARATOR + song.artist;
}

/* 검색에 쓸 값을 곡마다 미리 만들어 둔다. 한 글자 칠 때마다 다시 만들면
 * 곡 수만큼 문자열을 새로 만드는 셈이 된다. */
export function decorate(song) {
  const searchText = normalizeText(
    [song.title, song.titleAlt, song.artist, (song.members || []).join(" "), song.tj, song.ky].join(" "),
  );
  return {
    ...song,
    key: songKey(song),
    searchText,
    searchChoseong: toChoseong(searchText),
    shuffle: Math.random(),
  };
}

export function hasNumber(song, machine) {
  if (machine === "tj") return Boolean(song.tj);
  if (machine === "ky") return Boolean(song.ky);
  return Boolean(song.tj || song.ky);
}

function matchesQuery(song, query) {
  if (!query.normalized) return true;
  if (query.isChoseong) return song.searchChoseong.includes(query.normalized);
  return song.searchText.includes(query.normalized);
}

function matchesMembers(song, filters) {
  const names = song.members || [];
  // 구분·종류는 곡마다 하나뿐이라 '모두'로 찾을 수 없다. 여러 값을 가지는 멤버에만 적용한다.
  if (filters.filterMode === "and") return Array.from(filters.members).every((name) => names.includes(name));
  return names.some((name) => filters.members.has(name));
}

export function applyFilters(songs, filters, favorites) {
  const query = prepareQuery(filters.query);
  const list = songs.filter((song) => {
    if (filters.onlyFavorites && !favorites.has(song.key)) return false;
    if (filters.onlyNumbered && !hasNumber(song, filters.machine)) return false;
    if (filters.sections.size && !filters.sections.has(song.section)) return false;
    if (filters.categories.size && !filters.categories.has(song.category)) return false;
    if (filters.members.size && !matchesMembers(song, filters)) return false;
    return matchesQuery(song, query);
  });

  if (filters.sort === "title") {
    list.sort((a, b) => KO_COLLATOR.compare(a.title, b.title));
  } else {
    list.sort((a, b) => a.shuffle - b.shuffle);
  }
  return { list, query };
}

/* 검색어와 겹치는 부분을 <mark> 로 감싼다. React 가 그리므로 문자열이 아니라 조각을 돌려준다. */
export function highlightParts(text, query) {
  const value = String(text ?? "");
  if (!query.raw) return [{ text: value, mark: false }];
  const index = value.toLowerCase().indexOf(query.raw.toLowerCase());
  if (index < 0) return [{ text: value, mark: false }];
  return [
    { text: value.slice(0, index), mark: false },
    { text: value.slice(index, index + query.raw.length), mark: true },
    { text: value.slice(index + query.raw.length), mark: false },
  ];
}
