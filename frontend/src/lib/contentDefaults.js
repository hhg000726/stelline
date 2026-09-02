/* 화면 HTML 에 적혀 있던 기본 문구·그림.
 *
 * 예전에는 같은 값이 HTML 에 직접 적혀 있고, assets/content.js 가 관리자가 바꾼 값만
 * 그 자리를 덮어썼다. 그래서 API 가 실패하거나 DB 가 비어 있어도 화면이 비지 않았다.
 * React 에서도 같은 성질을 지키려고, 서버 registry 의 기본값을 여기에 그대로 옮겨 둔다.
 * (stelline/content/registry.py 의 default 와 짝을 이룬다. 한쪽만 고치지 마세요.)
 */
export const CONTENT_DEFAULTS = {
  "main_hero_subtitle": "스텔라이브를 좋아해서 만든 비공식 팬 사이트입니다.",
  "main_notice_title": "",
  "main_notice": "",
  "main_notice_image": "",
  "main_twits_note": "총공 시간에 맞춰 태그와 키워드를 복사해 트윗합니다.",
  "main_events_note": "진행 중인 외부 이벤트로 이동합니다.",
  "main_bugs_note": "즐겨찾기 투표 현황입니다.",
  "search_hero_subtitle": "시크릿 모드에서 검색했을 때 3개 이내로만 뜨는 곡입니다.",
  "search_notice_title": "",
  "search_notice": "",
  "search_notice_image": "",
  "search_songs_note": "카드를 누르면 검색어가 복사되고 유튜브로 이동합니다.",
  "search_help_title": "도와주는 방법",
  "search_help_note": "인기도 순으로 정렬해서 들으면 검색 노출에 도움이 됩니다.",
  "search_help_list": "오리지널 곡은 본 채널 뮤비로 봐주세요.\n기억날 때마다 한 번씩 검색하고, 인기도 순으로 정렬 후 들어주세요.\n댓글과 공유까지 한다면 효과가 더 좋다는 말도 있습니다.\n한 번 막힌 영상이 계속 막히는 현상이 반복되고 있습니다.\n한 번 막혔던 영상도 생각날 때 한 번만 부탁드립니다.",
  "search_steps_hint": "그림을 누르면 크게 볼 수 있습니다.",
  "search_query_note": "최근에 막혔던 곡 + 랜덤 25곡을 6시간마다 검색하고 있습니다.",
  "search_step_pc_1_label": "필터 클릭",
  "search_step_pc_1_image": "/search/1.PNG",
  "search_step_pc_2_label": "우선순위 · 인기도 순 클릭",
  "search_step_pc_2_image": "/search/2.PNG",
  "search_step_pc_3_label": "노래 듣기",
  "search_step_pc_3_image": "/search/3.PNG",
  "search_step_mobile_1_label": "점 세 개 클릭",
  "search_step_mobile_1_image": "/search/1.jpg",
  "search_step_mobile_2_label": "검색필터 클릭",
  "search_step_mobile_2_image": "/search/2.jpg",
  "search_step_mobile_3_label": "우선순위 · 인기도 순 클릭",
  "search_step_mobile_3_image": "/search/3.jpg",
  "search_step_mobile_4_label": "노래 듣기",
  "search_step_mobile_4_image": "/search/4.jpg",
  "karaoke_hero_subtitle": "번호를 누르면 바로 복사됩니다.",
  "congratulation_notify_prompt": "앱 설치 없이 알림을 받으려면 버튼을 클릭하세요.",
  "congratulation_list_note": "카드를 누르면 유튜브에서 영상을 볼 수 있습니다.",
  "offline_hero_subtitle": "목록에서 고르면 지도에서 그 장소로 이동합니다.",
  "site_footer_note": "이 사이트는 개인이 운영하는 비영리 사이트입니다. 스텔라이브 공식과는 무관합니다.\n문제가 되는 콘텐츠가 있다면 연락 주시면 조치하겠습니다.",
  "site_footer_contact": "문의: pastel525600@gmail.com"
};
