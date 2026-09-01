"""관리자가 고칠 수 있는 고정 문구·그림의 목록(코드 기준).

화면에 박아 둔 문구와 그림을 개발자 없이 바꾸려면, 무엇을 바꿀 수 있는지가 먼저
정해져 있어야 한다. 여기 적힌 항목만 관리자 화면에 나오고 저장도 된다.
DB에는 **바뀐 값만** 들어간다. 값이 없으면 여기 `default`가 그대로 쓰이므로
DB가 비어 있거나 조회에 실패해도 화면은 지금과 똑같이 보인다.

새 항목을 늘리는 방법
  1. 아래에 항목을 추가한다(글자 수 상한이나 그림 크기 범위를 함께 정한다).
  2. 화면 HTML의 해당 요소에 `data-content-key="<키>"`를 붙인다.
     비었을 때 함께 사라져야 할 바깥 상자가 있으면 `data-content-hide="<선택자>"`도 붙인다.
  3. 기본값이 비어 있는 항목은 HTML에 `hidden`을 함께 적어 둔다(값이 생기면 켜진다).
"""

TEXT = "text"
IMAGE = "image"

# 화면 묶음. 순서가 곧 관리자 화면의 차례다.
CONTENT_PAGES = (
    ("main", "메인 화면"),
    ("search", "검색 안되는 노래"),
    ("karaoke", "노래방 번호"),
    ("congratulation", "조회수 축하"),
    ("offline", "오프라인 이벤트"),
    ("common", "모든 화면 공통"),
)

# 화면 갈무리 안내 그림. 상자가 `object-fit: contain`이라 비율이 조금 달라도
# 레이아웃이 밀리지 않는다. 그래서 비율은 넉넉히 두고 용량과 최소 크기만 조인다.
_STEP_IMAGE = {
    "type": IMAGE,
    "max_bytes": 1_500_000,
    "min_width": 200,
    "min_height": 100,
    "max_width": 3000,
    "max_height": 3000,
    "min_aspect": 0.3,
    "max_aspect": 8.0,
    "aspect_hint": "가로로 긴 화면 갈무리를 권합니다(16:9 안팎).",
    "box": "step",
}

# 공지 그림. 16:9 상자를 잘라 채우므로(cover) 비율이 크게 어긋나면 잘려 나간다.
_NOTICE_IMAGE = {
    "type": IMAGE,
    "max_bytes": 2_000_000,
    "min_width": 480,
    "min_height": 240,
    "max_width": 3000,
    "max_height": 2000,
    "min_aspect": 1.2,
    "max_aspect": 2.6,
    "aspect_hint": "가로:세로 16:9(1.78) 안팎을 권합니다. 많이 벗어나면 위아래가 잘립니다.",
    "box": "notice",
}


def _text(page, title, description, default, max_length, multiline=False):
    return {
        "type": TEXT,
        "page": page,
        "title": title,
        "description": description,
        "default": default,
        "max_length": max_length,
        "multiline": multiline,
    }


def _image(page, title, description, default, shape):
    return {**shape, "page": page, "title": title, "description": description, "default": default}


CONTENT_ITEMS = {
    # ---------- 메인 화면 ----------
    "main_hero_subtitle": _text(
        "main", "메인 소개 문구", "제목 Stelline 바로 아래 한 줄입니다.",
        "스텔라이브를 좋아해서 만든 비공식 팬 사이트입니다.", 80,
    ),
    "main_notice_title": _text(
        "main", "메인 공지 제목", "메인 화면 위쪽 공지 칸의 제목입니다. 비우면 제목 줄이 사라집니다.",
        "", 40,
    ),
    "main_notice": _text(
        "main", "메인 공지 내용", "제목·내용·그림이 모두 비면 공지 칸 자체가 사라집니다.",
        "", 300, multiline=True,
    ),
    "main_notice_image": _image(
        "main", "메인 공지 그림", "공지 칸 안에 함께 보여 줄 그림입니다. 비우면 그림 자리가 사라집니다.",
        None, _NOTICE_IMAGE,
    ),
    "main_twits_note": _text(
        "main", "트윗 안내 설명", "트윗 안내 제목 옆 한 줄입니다.",
        "총공 시간에 맞춰 태그와 키워드를 복사해 트윗합니다.", 60,
    ),
    "main_events_note": _text(
        "main", "이벤트·펀딩 설명", "이벤트·펀딩 제목 옆 한 줄입니다.",
        "진행 중인 외부 이벤트로 이동합니다.", 60,
    ),
    "main_bugs_note": _text(
        "main", "벅스 순위 설명", "벅스 순위 제목 옆 한 줄입니다.",
        "즐겨찾기 투표 현황입니다.", 60,
    ),

    # ---------- 검색 안되는 노래 ----------
    "search_hero_subtitle": _text(
        "search", "검색 화면 소개 문구", "검색 안되는 노래 제목 아래 한 줄입니다.",
        "시크릿 모드에서 검색했을 때 3개 이내로만 뜨는 곡입니다.", 90,
    ),
    "search_notice_title": _text(
        "search", "검색 화면 공지 제목", "검색 화면 위쪽 공지 칸의 제목입니다.",
        "", 40,
    ),
    "search_notice": _text(
        "search", "검색 화면 공지 내용", "제목·내용·그림이 모두 비면 공지 칸 자체가 사라집니다.",
        "", 300, multiline=True,
    ),
    "search_notice_image": _image(
        "search", "검색 화면 공지 그림", "공지 칸 안에 함께 보여 줄 그림입니다.",
        None, _NOTICE_IMAGE,
    ),
    "search_songs_note": _text(
        "search", "막힌 곡 목록 설명", "막힌 곡 목록 제목 옆 한 줄입니다.",
        "카드를 누르면 검색어가 복사되고 유튜브로 이동합니다.", 60,
    ),
    "search_help_title": _text(
        "search", "도와주는 방법 제목", "단계 안내 칸의 제목입니다.", "도와주는 방법", 20,
    ),
    "search_help_note": _text(
        "search", "도와주는 방법 설명", "도와주는 방법 제목 옆 한 줄입니다.",
        "인기도 순으로 정렬해서 들으면 검색 노출에 도움이 됩니다.", 60,
    ),
    "search_help_list": _text(
        "search", "도와주는 방법 목록", "한 줄에 하나씩 적습니다. 빈 줄은 무시하고, 전부 비우면 목록이 사라집니다.",
        "오리지널 곡은 본 채널 뮤비로 봐주세요.\n"
        "기억날 때마다 한 번씩 검색하고, 인기도 순으로 정렬 후 들어주세요.\n"
        "댓글과 공유까지 한다면 효과가 더 좋다는 말도 있습니다.\n"
        "한 번 막힌 영상이 계속 막히는 현상이 반복되고 있습니다.\n"
        "한 번 막혔던 영상도 생각날 때 한 번만 부탁드립니다.",
        400, multiline=True,
    ),
    "search_steps_hint": _text(
        "search", "그림 안내 문구", "단계 그림 아래 작은 글씨입니다.",
        "그림을 누르면 크게 볼 수 있습니다.", 40,
    ),
    "search_query_note": _text(
        "search", "검색어 리스트 설명", "검색어 리스트 제목 옆 한 줄입니다.",
        "최근에 막혔던 곡 + 랜덤 25곡을 6시간마다 검색하고 있습니다.", 60,
    ),
    "search_step_pc_1_label": _text(
        "search", "PC 1단계 설명", "PC 안내 첫 번째 칸의 제목입니다.", "필터 클릭", 30,
    ),
    "search_step_pc_1_image": _image(
        "search", "PC 1단계 그림", "그림을 비우면 그 단계 칸이 통째로 사라지고 번호가 다시 매겨집니다.",
        "/search/1.PNG", _STEP_IMAGE,
    ),
    "search_step_pc_2_label": _text(
        "search", "PC 2단계 설명", "PC 안내 두 번째 칸의 제목입니다.", "우선순위 · 인기도 순 클릭", 30,
    ),
    "search_step_pc_2_image": _image(
        "search", "PC 2단계 그림", "PC 안내 두 번째 칸의 그림입니다.", "/search/2.PNG", _STEP_IMAGE,
    ),
    "search_step_pc_3_label": _text(
        "search", "PC 3단계 설명", "PC 안내 세 번째 칸의 제목입니다.", "노래 듣기", 30,
    ),
    "search_step_pc_3_image": _image(
        "search", "PC 3단계 그림", "PC 안내 세 번째 칸의 그림입니다.", "/search/3.PNG", _STEP_IMAGE,
    ),
    "search_step_mobile_1_label": _text(
        "search", "모바일 1단계 설명", "모바일 안내 첫 번째 칸의 제목입니다.", "점 세 개 클릭", 30,
    ),
    "search_step_mobile_1_image": _image(
        "search", "모바일 1단계 그림", "모바일 안내 첫 번째 칸의 그림입니다.", "/search/1.jpg", _STEP_IMAGE,
    ),
    "search_step_mobile_2_label": _text(
        "search", "모바일 2단계 설명", "모바일 안내 두 번째 칸의 제목입니다.", "검색필터 클릭", 30,
    ),
    "search_step_mobile_2_image": _image(
        "search", "모바일 2단계 그림", "모바일 안내 두 번째 칸의 그림입니다.", "/search/2.jpg", _STEP_IMAGE,
    ),
    "search_step_mobile_3_label": _text(
        "search", "모바일 3단계 설명", "모바일 안내 세 번째 칸의 제목입니다.", "우선순위 · 인기도 순 클릭", 30,
    ),
    "search_step_mobile_3_image": _image(
        "search", "모바일 3단계 그림", "모바일 안내 세 번째 칸의 그림입니다.", "/search/3.jpg", _STEP_IMAGE,
    ),
    "search_step_mobile_4_label": _text(
        "search", "모바일 4단계 설명", "모바일 안내 네 번째 칸의 제목입니다.", "노래 듣기", 30,
    ),
    "search_step_mobile_4_image": _image(
        "search", "모바일 4단계 그림", "모바일 안내 네 번째 칸의 그림입니다.", "/search/4.jpg", _STEP_IMAGE,
    ),

    # ---------- 노래방 번호 ----------
    "karaoke_hero_subtitle": _text(
        "karaoke", "노래방 화면 소개 문구", "노래방 번호 제목 아래 한 줄입니다.",
        "번호를 누르면 바로 복사됩니다.", 80,
    ),

    # ---------- 조회수 축하 ----------
    "congratulation_hero_subtitle": _text(
        "congratulation", "조회수 축하 소개 문구", "조회수 축하 제목 아래 한 줄입니다(알림 상태 줄 위).",
        "스텔라이브 영상이 조회수 고비를 넘으면 알려 드립니다.", 80,
    ),
    "congratulation_list_note": _text(
        "congratulation", "달성 목록 설명", "최근 24시간 이내 달성 제목 옆 한 줄입니다.",
        "카드를 누르면 유튜브에서 영상을 볼 수 있습니다.", 60,
    ),

    # ---------- 오프라인 이벤트 ----------
    "offline_hero_subtitle": _text(
        "offline", "오프라인 화면 소개 문구", "진행 중인 오프라인 이벤트 제목 아래 한 줄입니다.",
        "목록에서 고르면 지도에서 그 장소로 이동합니다.", 90,
    ),

    # ---------- 모든 화면 공통 ----------
    "site_footer_note": _text(
        "common", "꼬리말 안내", "모든 화면 맨 아래 문구입니다. 한 줄에 하나씩 적습니다.",
        "이 사이트는 개인이 운영하는 비영리 사이트입니다. 스텔라이브 공식과는 무관합니다.\n"
        "문제가 되는 콘텐츠가 있다면 연락 주시면 조치하겠습니다.",
        200, multiline=True,
    ),
    "site_footer_contact": _text(
        "common", "꼬리말 문의처", "모든 화면 맨 아래 문의 줄입니다.",
        "문의: pastel525600@gmail.com", 80,
    ),
}

# 관리자 화면의 미리보기 상자가 실제 화면과 같은 크기·색으로 보이게 하는 짝짓기.
# 항목마다 따로 적으면 정의가 길어지고, 여기 한 곳에 모아 두면 "이 문구가 화면 어디에
# 어떤 크기로 나오는지"를 한눈에 볼 수 있다. 적지 않은 항목은 'note'로 본다.
_PREVIEW_STYLES = {
    "subtitle": (
        "main_hero_subtitle", "search_hero_subtitle", "karaoke_hero_subtitle",
        "congratulation_hero_subtitle", "offline_hero_subtitle",
    ),
    "heading": ("search_help_title",),
    "notice-title": ("main_notice_title", "search_notice_title"),
    "notice-body": ("main_notice", "search_notice"),
    "list": ("search_help_list",),
    "hint": ("search_steps_hint",),
    "step": (
        "search_step_pc_1_label", "search_step_pc_2_label", "search_step_pc_3_label",
        "search_step_mobile_1_label", "search_step_mobile_2_label",
        "search_step_mobile_3_label", "search_step_mobile_4_label",
    ),
    "footer": ("site_footer_note", "site_footer_contact"),
}

for _style, _keys in _PREVIEW_STYLES.items():
    for _key in _keys:
        # 없는 키를 적으면 여기서 바로 KeyError가 난다(이름을 잘못 적은 채 배포되지 않는다).
        CONTENT_ITEMS[_key]["preview"] = _style

for _item in CONTENT_ITEMS.values():
    _item.setdefault("preview", "note")

# 화면 묶음별로 나눈 항목. 관리자 화면이 이 순서로 그린다.
CONTENT_GROUPS = [
    group
    for group in (
        {
            "key": page_key,
            "label": label,
            "items": [
                {"key": key, **item}
                for key, item in CONTENT_ITEMS.items()
                if item["page"] == page_key
            ],
        }
        for page_key, label in CONTENT_PAGES
    )
    if group["items"]
]


def get_item(key):
    """등록되지 않은 키는 저장도 조회도 되지 않는다."""
    return CONTENT_ITEMS.get(key)
