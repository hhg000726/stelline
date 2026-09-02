/* 노래방 화면이 쓰는 고정값. 예전 karaoke.js 맨 위에 있던 것과 같다. */

export const STORAGE_KEYS = {
  favorites: "stelline.karaoke.favorites",
  setlist: "stelline.karaoke.setlist",
  machine: "stelline.karaoke.machine",
  cache: "stelline.karaoke.cache",
};

export const SECTION_LABELS = { group: "단체", unit: "유닛", collab: "콜라보", gift: "기프트", solo: "개인" };
export const CATEGORY_LABELS = { original: "오리지널", cover: "커버" };
export const MACHINE_LABELS = { tj: "TJ", ky: "금영" };
export const SECTION_ORDER = ["group", "unit", "collab", "gift", "solo"];

export const CHOSEONG = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];
export const CHOSEONG_ONLY = /^[ㄱ-ㅎ]+$/;
export const KEY_SEPARATOR = "␟";

/* 가나다순 정렬에 쓰는 한국어 정렬기. 한 번 만들어 두고 계속 쓴다.
 * (localeCompare 는 부를 때마다 정렬기를 새로 만든다. 곡이 수백 개면 그 비용이
 *  정렬 자체보다 크다.) */
export const KO_COLLATOR = new Intl.Collator("ko");

/* 곡이 수백 개라 한 번에 다 그리면 스크롤 막대가 실낱같이 얇아진다.
 * 처음에는 이만큼만 그리고, 더 보고 싶을 때 같은 만큼씩 이어 붙인다.
 * 좁은 화면은 한 곡이 세로로 두 배를 쓰므로 절반만 그린다. */
export const NARROW = Boolean(window.matchMedia && window.matchMedia("(max-width: 640px)").matches);
export const PAGE_SIZE = NARROW ? 20 : 40;
