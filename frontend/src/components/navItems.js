/* 기능 화면 네 개. 머리말 메뉴와 메인 화면 카드가 같은 목록을 쓴다.
 *
 * key 는 관리자 화면의 `메인 화면 버튼`(main_buttons) 설정과 짝을 이룬다. 바꾸지 마세요.
 * label 은 메인 화면 카드 이름이라 관리자가 고칠 수 있고, navLabel 은 머리말 자리가
 * 좁아 짧은 이름을 그대로 쓴다(표시 여부와 순서만 설정을 따라간다).
 */
export const NAV_ITEMS = [
  {
    key: "search",
    to: "/search",
    navLabel: "검색 안되는 노래",
    label: "검색 안되는 노래 보기",
    description: "유튜브 검색에 잘 안 뜨는 곡 목록",
    icon: "search",
  },
  {
    key: "karaoke",
    to: "/karaoke",
    navLabel: "노래방 번호",
    label: "노래방 번호 찾기",
    description: "TJ·금영 번호 검색과 부를 곡 목록",
    icon: "mic",
  },
  {
    key: "congratulation",
    to: "/congratulation",
    navLabel: "조회수 축하",
    label: "조회수 축하 알림",
    description: "조회수 달성 기록과 알림 설정",
    icon: "bell",
  },
  {
    key: "offline",
    to: "/offline",
    navLabel: "오프라인 이벤트",
    label: "오프라인 이벤트",
    description: "지도에서 보는 진행 중인 행사",
    icon: "pin",
  },
];
