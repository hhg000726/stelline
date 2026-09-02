/* 검색·필터·정렬 상태 하나. 값이 아홉 개나 되고 서로 얽혀 있어 useReducer 로 묶는다.
 *
 * 주소 표시줄과도 짝을 이룬다. 지금 보고 있는 목록을 그대로 공유하거나 새로 고쳐도
 * 같은 목록이 나와야 하기 때문이다(예전 syncUrl / readUrlState 와 같은 규칙이다).
 */
export const INITIAL_FILTERS = {
  query: "",
  machine: "both",
  sort: "random",
  // "or"는 고른 것 중 하나라도, "and"는 고른 것을 모두 만족하는 곡만 남긴다.
  filterMode: "or",
  members: new Set(),
  sections: new Set(),
  categories: new Set(),
  onlyNumbered: false,
  onlyFavorites: false,
};

export function filtersReducer(state, action) {
  switch (action.type) {
    case "set":
      return { ...state, [action.key]: action.value };
    case "toggle": {
      const next = new Set(state[action.group]);
      if (next.has(action.value)) next.delete(action.value);
      else next.add(action.value);
      return { ...state, [action.group]: next };
    }
    case "reset":
      return {
        ...state,
        members: new Set(),
        sections: new Set(),
        categories: new Set(),
        filterMode: "or",
        onlyNumbered: false,
        onlyFavorites: false,
      };
    default:
      return state;
  }
}

/* 주소에 적힌 값으로 시작 상태를 만든다. 저장해 둔 기기 선택은 주소에 없을 때만 쓴다. */
export function initFilters({ search, savedMachine }) {
  const params = new URLSearchParams(search);
  const state = {
    ...INITIAL_FILTERS,
    members: new Set(),
    sections: new Set(),
    categories: new Set(),
  };

  if (["tj", "ky", "both"].includes(savedMachine)) state.machine = savedMachine;
  if (params.get("q")) state.query = params.get("q");
  if (["tj", "ky", "both"].includes(params.get("machine"))) state.machine = params.get("machine");
  if (["random", "title"].includes(params.get("sort"))) state.sort = params.get("sort");
  if (["or", "and"].includes(params.get("match"))) state.filterMode = params.get("match");
  (params.get("member") || "").split("|").filter(Boolean).forEach((value) => state.members.add(value));
  (params.get("section") || "").split("|").filter(Boolean).forEach((value) => state.sections.add(value));
  (params.get("category") || "").split("|").filter(Boolean).forEach((value) => state.categories.add(value));
  state.onlyNumbered = params.get("numbered") === "1";
  state.onlyFavorites = params.get("fav") === "1";
  return state;
}

/* 기본값과 다른 것만 주소에 적는다. 기본 상태에서는 주소가 깨끗하게 남는다. */
export function filtersToParams(filters) {
  const params = new URLSearchParams();
  if (filters.query) params.set("q", filters.query);
  if (filters.machine !== "both") params.set("machine", filters.machine);
  if (filters.sort !== "random") params.set("sort", filters.sort);
  if (filters.filterMode !== "or") params.set("match", filters.filterMode);
  if (filters.members.size) params.set("member", Array.from(filters.members).join("|"));
  if (filters.sections.size) params.set("section", Array.from(filters.sections).join("|"));
  if (filters.categories.size) params.set("category", Array.from(filters.categories).join("|"));
  if (filters.onlyNumbered) params.set("numbered", "1");
  if (filters.onlyFavorites) params.set("fav", "1");
  return params;
}

export function activeFilterCount(filters) {
  return (
    filters.members.size +
    filters.sections.size +
    filters.categories.size +
    (filters.onlyNumbered ? 1 : 0) +
    (filters.onlyFavorites ? 1 : 0)
  );
}
