"""화면(SPA 문서·정적 자원·서버 템플릿) 제공을 검증한다. DB 불필요.

공개 화면은 React 한 벌(SPA)이다. 서버는 어느 주소로 들어오든 같은 문서를 내려주고,
무엇을 그릴지는 브라우저가 정한다. 그래서 여기서 보는 것은 두 가지다.

  1. 서버가 제 몫을 하는가 - 주소마다 문서를 주는가, 없는 주소는 404인가,
     빌드 결과물이 실제로 저장소에 들어 있는가(배포 서버에는 Node가 없다).
  2. 화면 코드가 예전 규칙을 그대로 지키는가 - 예전에는 화면별 .js 파일을 읽어 확인했다.
     지금은 같은 규칙이 frontend/src 아래에 있으므로 그쪽을 읽는다.
"""

import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
STATIC_ROOT = PROJECT_ROOT / "stelline" / "static"

PAGE_PATHS = [
    "/",
    "/search",
    "/search/",
    "/congratulation",
    "/congratulation/",
    "/offline",
    "/offline/",
    "/karaoke",
    "/karaoke/",
]


def source(*parts):
    """frontend/src 아래 파일 하나를 글자로 읽는다."""
    return FRONTEND_SRC.joinpath(*parts).read_text(encoding="utf-8")


# --- 서버가 내려주는 것 -----------------------------------------------------

@pytest.mark.parametrize("path", PAGE_PATHS)
def test_public_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"<!DOCTYPE html>" in resp.data or b"<!doctype html>" in resp.data


@pytest.mark.parametrize("path", PAGE_PATHS)
def test_every_page_serves_the_same_app_shell(client, path):
    """주소를 직접 치고 들어와도(딥링크) 같은 문서가 와야 화면이 열린다."""
    assert client.get(path).data == client.get("/").data


def test_app_shell_loads_the_built_bundle(client):
    """빌드 결과물은 저장소에 커밋한다(배포 서버에 Node를 두지 않기 위해서다).

    문서가 가리키는 파일이 실제로 없으면 화면이 통째로 빈다. 빌드를 잊고 올린 경우가
    여기서 걸린다.
    """
    html = client.get("/").get_data(as_text=True)
    refs = re.findall(r'(?:src|href)="(/app/[^"]+)"', html)
    assert refs, "문서가 빌드된 번들을 가리키지 않습니다. `npm run build` 를 실행하세요."
    for ref in refs:
        assert client.get(ref).status_code == 200, ref


def test_theme_is_decided_before_the_page_is_painted(client):
    """본문 뒤에서 배색을 정하면 밝은 화면이 한 번 번쩍인다."""
    head = client.get("/").get_data(as_text=True).split("</head>")[0]
    assert "stelline.theme" in head
    assert "prefers-color-scheme" in head
    assert 'setAttribute("data-theme"' in head


@pytest.mark.parametrize(
    "path",
    [
        # 서버가 그리는 관리자·로그인 화면이 함께 쓰는 공용 배색과 다크 모드.
        "/assets/site.css",
        "/assets/theme.js",
        # 화면과 무관하게 그대로 남아야 하는 것들.
        "/firebase-messaging-sw.js",
        "/search/1.PNG",
        "/search/1.jpg",
        "/favicon.svg",
    ],
)
def test_static_assets_served(client, path):
    assert client.get(path).status_code == 200


def test_unknown_path_returns_404(client):
    resp = client.get("/definitely/not/here")
    assert resp.status_code == 404


def test_removed_frontend_files_are_gone(client):
    """예전 화면 파일이 남아 있으면 어느 쪽이 진짜인지 알 수 없다."""
    for path in ("/index.js", "/assets/site.js", "/assets/nav.js", "/assets/content.js",
                 "/search/search.js", "/karaoke/karaoke.js", "/offline/offline.js"):
        assert client.get(path).status_code == 404, path


def test_login_page_renders(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "관리자" in resp.get_data(as_text=True)


def test_admin_requires_login(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_logout_redirects_to_login(client):
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_rejects_bad_credentials(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 200  # 리다이렉트 없이 로그인 화면 재표시
    assert "로그인 실패" in resp.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "logged_in" not in sess


def test_login_accepts_configured_credentials(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "test-admin-password"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


# --- 화면 사이 이동 ---------------------------------------------------------

def test_pages_move_without_reloading_the_document():
    """링크마다 문서를 다시 받으면 흰 화면이 한 번 번쩍이고 받아 둔 것도 다 버린다."""
    app = source("App.jsx")
    for path in ("/", "/search", "/karaoke", "/congratulation", "/offline"):
        assert f'path="{path}"' in app, path
    # 화면 묶음은 들어간 화면 것만 받아 온다.
    assert "lazy(" in app
    assert "Suspense" in source("components", "Layout.jsx")


def test_moving_between_pages_shows_that_something_is_loading():
    """아무 표시 없이 멈춰 있으면 눌린 건지 고장인지 알 수 없다."""
    loading = source("components", "Loading.jsx")
    assert "RouteProgress" in loading
    assert "Skeleton" in loading
    assert "RouteFallback" in source("components", "Layout.jsx")


def test_one_screen_falling_over_does_not_empty_the_site():
    """한 문서 안에서 화면을 바꾸므로, 막지 않으면 사고 하나가 사이트를 통째로 지운다."""
    assert "ErrorBoundary" in source("components", "Layout.jsx")
    assert "getDerivedStateFromError" in source("components", "ErrorBoundary.jsx")


def test_every_page_menu_follows_the_admin_button_settings():
    """숨긴 기능이 어느 화면에는 남아 있으면 안 된다. 메뉴는 모두 같은 설정을 따른다."""
    nav = source("context", "NavButtonsContext.jsx")
    assert "main/buttons" in nav
    items = source("components", "navItems.js")
    for key in ("search", "karaoke", "congratulation", "offline"):
        assert f'key: "{key}"' in items
    # 머리말 메뉴와 메인 화면 카드가 같은 목록·같은 설정을 쓴다.
    assert "useNavItems" in source("components", "SiteHeader.jsx")
    assert "useNavItems" in source("pages", "MainPage.jsx")


def test_sub_pages_link_to_every_other_screen():
    """화면마다 '메인으로'만 있으면 기능 사이를 오가려면 메인을 거쳐야 한다."""
    header = source("components", "SiteHeader.jsx")
    assert 'className="site-nav"' in header
    # NavLink 는 지금 보고 있는 화면에 aria-current="page" 를 스스로 붙인다.
    assert "NavLink" in header
    # 메인 화면에는 큰 제목과 기능 카드가 따로 있어 이 줄을 두지 않는다.
    assert 'location.pathname !== "/"' in source("components", "Layout.jsx")


# --- 노래방 화면 ------------------------------------------------------------

def test_karaoke_mode_is_gone():
    """어두운 배색은 전역 다크 모드가 맡으므로 노래방 모드는 없앴다."""
    assert "karaoke-mode" not in source("styles", "karaoke.css")
    assert "노래방 모드" not in source("pages", "KaraokePage.jsx")


def test_karaoke_page_offers_the_new_controls():
    page = source("pages", "KaraokePage.jsx")
    assert 'value: "and"' in source("pages", "karaoke", "FilterPanel.jsx")  # 필터 AND 옵션
    assert 'id="pick-favorite"' in source("pages", "karaoke", "PickDialog.jsx")
    assert 'id="pick-setlist"' in source("pages", "karaoke", "PickDialog.jsx")
    assert "PickDialog" in page


def test_karaoke_list_is_shown_in_pages():
    """곡이 수백 개라 한 번에 다 그리면 스크롤 막대가 실낱같이 얇아진다."""
    page = source("pages", "KaraokePage.jsx")
    assert 'id="load-more"' in page
    assert "PAGE_SIZE" in source("pages", "karaoke", "constants.js")
    assert "setShownCount(PAGE_SIZE)" in page


def test_karaoke_page_sorts_randomly_or_by_name():
    """정렬 기준으로 삼을 만한 날짜·순서 값을 두지 않아, 랜덤순과 가나다순만 남겼다."""
    page = source("pages", "KaraokePage.jsx")
    assert '<option value="random">랜덤순</option>' in page
    assert '<option value="title">가나다순</option>' in page
    for gone in ("최신순", "오래된순", "번호순", "기본순"):
        assert gone not in page


def test_karaoke_keeps_what_you_are_looking_at_in_the_address():
    """새로 고쳐도, 링크를 건네줘도 같은 목록이 나와야 한다."""
    filters = source("pages", "karaoke", "filters.js")
    for name in ("q", "machine", "sort", "match", "member", "section", "category", "numbered", "fav"):
        assert f'"{name}"' in filters, name
    assert "initFilters" in filters and "filtersToParams" in filters


# --- 조회수 축하 화면 -------------------------------------------------------

def test_congratulation_badge_marks_exact_milestones_only():
    """배지 색은 100만·1000만 '단위'로 딱 떨어질 때만 바뀐다.

    예전에는 100만을 넘기기만 하면 계속 파란 배지가 붙어, 120만과 100만이 같아 보였다.
    """
    page = source("pages", "CongratulationPage.jsx")
    assert "function milestoneTier" in page
    # 나머지 연산으로 '단위'를 판정한다(이상/초과가 아니다).
    assert "tenThousands % 1000 === 0" in page
    assert "tenThousands % 100 === 0" in page
    assert "tenThousands >= 1000" not in page
    assert "tenThousands >= 100" not in page


# --- 복사·알림 말풍선 -------------------------------------------------------

def test_copy_and_toast_helpers_live_in_one_place():
    """복사 실패 처리와 말풍선은 화면마다 따로 두면 조금씩 어긋난다."""
    clipboard = source("lib", "clipboard.js")
    assert "copyText" in clipboard
    # https 가 아니거나 권한이 막힌 곳을 위한 대체 복사 경로.
    assert "execCommand" in clipboard
    assert "site-toast" in source("context", "ToastContext.jsx")


@pytest.mark.parametrize(
    "parts",
    [("pages", "KaraokePage.jsx"), ("pages", "SearchPage.jsx"), ("pages", "main", "TwitsPanel.jsx")],
)
def test_screens_use_the_shared_copy_helper(parts):
    """사본이 남아 있으면 복사 실패 처리가 화면마다 어긋난다."""
    text = source(*parts)
    assert "copyText" in text
    assert "execCommand" not in text


@pytest.mark.parametrize(
    "parts",
    [("pages", "main", "TwitsPanel.jsx"), ("pages", "SearchPage.jsx")],
)
def test_copy_failures_are_reported_instead_of_doing_nothing(parts):
    """복사가 막히면 예전에는 아무 일도 일어나지 않아 눌러도 반응이 없었다."""
    text = source(*parts)
    assert "복사하지 못했어요" in text
    # 복사를 못 했으면 붙여 넣을 것이 없으므로 바깥 사이트로 보내지 않는다.
    assert "navigator.clipboard.writeText" not in text


# --- 바깥 사이트로 나가는 자리는 링크로 -------------------------------------

def test_outbound_targets_are_links_not_buttons():
    """버튼으로 두면 새 탭으로 열기·주소 미리보기 같은 것이 전부 막힌다."""
    congrats = source("pages", "CongratulationPage.jsx")
    assert '<a\n      className="card is-link"' in congrats
    assert 'target="_blank"' in congrats
    assert "window.location.href" not in congrats

    events = source("pages", "main", "EventsPanel.jsx")
    assert '<a className="btn-secondary"' in events
    assert 'target: "_blank"' in events


# --- 검색 화면의 탭 ---------------------------------------------------------

def test_search_tabs_are_wired_for_keyboard_and_screen_readers():
    """role=tab 을 붙여 둔 이상 화살표로 옮겨 다닐 수 있어야 한다."""
    tabs = source("components", "Segmented.jsx")
    assert "aria-controls" in tabs
    assert "tabpanel" in tabs
    assert "ArrowRight" in tabs and "ArrowLeft" in tabs


def test_search_steps_open_on_the_tab_matching_the_device():
    """휴대폰으로 들어온 사람에게 PC 화면 그림부터 보여 주지 않는다."""
    page = source("pages", "SearchPage.jsx")
    assert "defaultMethodTab" in page
    assert "pointer: coarse" in page


def test_search_steps_renumber_when_a_step_is_removed():
    """단계 하나를 지우면 STEP 1, STEP 3 처럼 번호가 비어 버린다."""
    grid = source("pages", "search", "StepGrid.jsx")
    assert "image.hidden" in grid
    assert "STEP {index + 1}" in grid


# --- 오프라인 이벤트 화면 ---------------------------------------------------

def test_offline_cards_do_not_nest_links_inside_a_button():
    """버튼 안의 링크는 표준에서 허용하지 않고 낭독기도 제대로 읽지 못한다."""
    page = source("pages", "OfflinePage.jsx")
    assert "event-card-main" in page
    assert "stopPropagation" not in page


def test_offline_card_text_starts_at_the_left_edge():
    """<button>은 안쪽 내용을 통째로 가운데로 모은다. text-align 만으로는 안 된다."""
    css = source("styles", "offline.css")
    main = css.split(".event-card-main {")[1].split("}")[0]
    assert "text-align: left" in main
    assert "justify-content: stretch" in main


def test_offline_explains_itself_when_the_map_is_missing():
    """빈 상자만 남으면 고장인지 아직 불러오는 중인지 알 수 없다."""
    page = source("pages", "OfflinePage.jsx")
    css = source("styles", "offline.css")
    assert "map-fallback" in page
    # 지도 인증이 막히면 스크립트는 멀쩡히 올라오고 화면만 빈다.
    assert "navermap_authFailure" in page
    assert ".map-fallback" in css


def test_offline_gives_the_map_a_box_of_its_own():
    """지도는 제 칸의 자식을 통째로 갈아치운다. 우리가 그린 것을 같이 두면 화면이 멈춘다."""
    page = source("pages", "OfflinePage.jsx")
    assert 'className="map-canvas"' in page
    assert ".map-canvas" in source("styles", "offline.css")


def test_offline_list_scrolls_on_its_own_only_beside_the_map():
    """좁은 화면에서 안쪽 스크롤을 두면 페이지를 내리려다 목록 안에 갇힌다."""
    css = source("styles", "offline.css")
    wide = css.split("@media (min-width: 900px)")[1]
    assert "overflow-y: auto" in wide
    assert css.split("@media (min-width: 900px)")[0].count("overflow-y: auto") == 0


# --- 배색과 좁은 화면 -------------------------------------------------------

def test_dark_theme_is_defined_for_the_whole_site(client):
    css = client.get("/assets/site.css").get_data(as_text=True)
    assert ':root[data-theme="dark"]' in css
    assert ".theme-toggle" in css


def test_the_app_reuses_the_shared_palette():
    """색은 한 곳에서만 정한다. 옮겨 적으면 관리자 화면과 공개 화면이 어긋난다."""
    assert "stelline/static/assets/site.css" in source("main.jsx")
    # React 전환에서 새로 넣은 CSS 는 움직임과 빈자리뿐이라, 색은 토큰으로만 쓴다.
    app_css = source("styles", "app.css")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", app_css)
    assert not re.search(r"\b(rgb|hsl)a?\(", app_css)


def test_header_stacks_the_brand_above_the_menu_on_narrow_screens(client):
    """한 줄에 같이 두면 이름이 폭의 절반을 먹고 메뉴가 세 줄까지 접혔다."""
    css = client.get("/assets/site.css").get_data(as_text=True)
    narrow = css.split("@media (max-width: 720px)")[-1]
    header = narrow.split(".site-header {")[1].split("}")[0]
    assert "flex-direction: column" in header
