"""화면(정적 페이지·템플릿) 제공을 검증한다. DB 불필요."""

import pytest


@pytest.mark.parametrize(
    "path",
    ["/", "/search", "/search/", "/congratulation", "/congratulation/", "/offline", "/offline/", "/karaoke", "/karaoke/"],
)
def test_public_pages_render(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"<!DOCTYPE html>" in resp.data or b"<!doctype html>" in resp.data


@pytest.mark.parametrize(
    "path,mimetype",
    [
        ("/assets/site.css", "text/css"),
        ("/assets/site.js", "text/javascript"),
        ("/assets/theme.js", "text/javascript"),
        ("/assets/nav.js", "text/javascript"),
        ("/assets/content.js", "text/javascript"),
        ("/firebase-messaging-sw.js", "text/javascript"),
        ("/search/style.css", "text/css"),
        ("/search/search.js", "text/javascript"),
        ("/congratulation/congratulation.js", "text/javascript"),
        ("/offline/offline.js", "text/javascript"),
    ],
)
def test_static_assets_served(client, path, mimetype):
    resp = client.get(path)
    assert resp.status_code == 200
    # 일부 환경에서 js mimetype이 application/javascript 로 잡히므로 느슨하게 확인
    assert "javascript" in resp.mimetype or resp.mimetype == mimetype


def test_unknown_path_returns_404(client):
    resp = client.get("/definitely/not/here")
    assert resp.status_code == 404


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


# --- 다크 모드 / 노래방 화면 컨트롤 -----------------------------------------

@pytest.mark.parametrize("path", ["/", "/search/", "/congratulation/", "/offline/", "/karaoke/"])
def test_every_public_page_loads_the_theme_script(client, path):
    """테마는 화면이 그려지기 전에 정해져야 하므로 <head>에서 불러온다."""
    html = client.get(path).get_data(as_text=True)
    head = html.split("</head>")[0]
    assert "/assets/theme.js" in head


def test_dark_theme_is_defined_for_the_whole_site(client):
    css = client.get("/assets/site.css").get_data(as_text=True)
    assert ':root[data-theme="dark"]' in css
    assert ".theme-toggle" in css


def test_karaoke_mode_is_gone(client):
    """어두운 배색은 전역 다크 모드가 맡으므로 노래방 모드는 없앴다."""
    css = client.get("/karaoke/style.css").get_data(as_text=True)
    html = client.get("/karaoke/").get_data(as_text=True)
    assert "karaoke-mode" not in css
    assert "노래방 모드" not in html


def test_karaoke_page_offers_the_new_controls(client):
    html = client.get("/karaoke/").get_data(as_text=True)
    assert 'data-match="and"' in html             # 필터 AND 옵션
    assert 'id="pick-favorite"' in html           # 랜덤 뽑기에서 바로 담기
    assert 'id="pick-setlist"' in html


@pytest.mark.parametrize("path", ["/", "/search/", "/congratulation/", "/offline/", "/karaoke/"])
def test_every_page_menu_follows_the_admin_button_settings(client, path):
    """숨긴 기능이 어느 화면에는 남아 있으면 안 된다. 메뉴는 모두 같은 설정을 따른다."""
    html = client.get(path).get_data(as_text=True)
    assert "data-button-nav" in html
    assert "/assets/nav.js" in html
    for key in ("search", "karaoke", "congratulation", "offline"):
        assert f'data-button-key="{key}"' in html


@pytest.mark.parametrize("path", ["/search/", "/congratulation/", "/offline/", "/karaoke/"])
def test_sub_pages_link_to_every_other_screen(client, path):
    """화면마다 '메인으로'만 있으면 기능 사이를 오가려면 메인을 거쳐야 한다."""
    html = client.get(path).get_data(as_text=True)
    assert 'class="site-nav"' in html
    assert 'aria-current="page"' in html


def test_karaoke_list_is_shown_in_pages(client):
    """곡이 수백 개라 한 번에 다 그리면 스크롤 막대가 실낱같이 얇아진다."""
    html = client.get("/karaoke/").get_data(as_text=True)
    assert 'id="load-more"' in html
    js = client.get("/karaoke/karaoke.js").get_data(as_text=True)
    assert "PAGE_SIZE" in js
    assert "resetPaging" in js


def test_karaoke_page_sorts_randomly_or_by_name(client):
    """정렬 기준으로 삼을 만한 날짜·순서 값을 두지 않아, 랜덤순과 가나다순만 남겼다."""
    html = client.get("/karaoke/").get_data(as_text=True)
    assert '<option value="random">랜덤순</option>' in html
    assert '<option value="title">가나다순</option>' in html
    for gone in ("최신순", "오래된순", "번호순", "기본순"):
        assert gone not in html


def test_congratulation_badge_marks_exact_milestones_only(client):
    """배지 색은 100만·1000만 '단위'로 딱 떨어질 때만 바뀐다.

    예전에는 100만을 넘기기만 하면 계속 파란 배지가 붙어, 120만과 100만이 같아 보였다.
    """
    js = client.get("/congratulation/congratulation.js").get_data(as_text=True)
    assert "function milestoneTier" in js
    # 나머지 연산으로 '단위'를 판정한다(이상/초과가 아니다).
    assert "tenThousands % 1000 === 0" in js
    assert "tenThousands % 100 === 0" in js
    assert "tenThousands >= 1000" not in js
    assert "tenThousands >= 100" not in js


# --- 복사·알림 말풍선 -------------------------------------------------------

def test_copy_and_toast_helpers_live_in_the_shared_asset(client):
    """복사 실패 처리와 말풍선은 화면마다 따로 두면 조금씩 어긋난다."""
    js = client.get("/assets/site.js").get_data(as_text=True)
    assert "copyText" in js
    assert "toast" in js
    # https 가 아니거나 권한이 막힌 곳을 위한 대체 복사 경로.
    assert "execCommand" in js


def test_karaoke_uses_the_shared_copy_helper(client):
    """예전에는 노래방 화면에만 있던 것을 공용으로 옮겼다. 사본이 남아 있으면 안 된다."""
    js = client.get("/karaoke/karaoke.js").get_data(as_text=True)
    assert "window.Stelline.copyText" in js
    assert "window.Stelline.toast" in js
    assert "execCommand" not in js


@pytest.mark.parametrize(
    "path",
    ["/index.js", "/search/search.js"],
)
def test_copy_failures_are_reported_instead_of_doing_nothing(client, path):
    """복사가 막히면 예전에는 .then 이 실행되지 않아 눌러도 아무 일이 없었다."""
    js = client.get(path).get_data(as_text=True)
    assert "Stelline.copyText" in js
    assert "복사하지 못했어요" in js
    # 복사를 못 했으면 붙여 넣을 것이 없으므로 바깥 사이트로 보내지 않는다.
    assert "navigator.clipboard.writeText" not in js


# --- 바깥 사이트로 나가는 자리는 링크로 -------------------------------------

def test_outbound_targets_are_links_not_buttons(client):
    """버튼으로 두면 새 탭으로 열기·주소 미리보기 같은 것이 전부 막힌다."""
    congrats = client.get("/congratulation/congratulation.js").get_data(as_text=True)
    assert 'createElement("a")' in congrats
    assert 'card.target = "_blank"' in congrats
    assert "window.location.href" not in congrats

    index = client.get("/index.js").get_data(as_text=True)
    assert 'createElement("a")' in index
    # 인라인 onclick 으로 주소를 끼워 넣던 자리도 링크로 바꿨다.
    assert "onclick=" not in index


# --- 검색 화면의 탭 ---------------------------------------------------------

def test_search_tabs_are_wired_for_keyboard_and_screen_readers(client):
    """role=tab 을 붙여 둔 이상 화살표로 옮겨 다닐 수 있어야 한다."""
    js = client.get("/search/search.js").get_data(as_text=True)
    assert "aria-controls" in js
    assert "tabpanel" in js
    assert "ArrowRight" in js and "ArrowLeft" in js


def test_search_steps_open_on_the_tab_matching_the_device(client):
    """휴대폰으로 들어온 사람에게 PC 화면 그림부터 보여 주지 않는다."""
    js = client.get("/search/search.js").get_data(as_text=True)
    assert "defaultMethodTab" in js
    assert "pointer: coarse" in js


# --- 오프라인 이벤트 화면 ---------------------------------------------------

def test_offline_cards_do_not_nest_links_inside_a_button(client):
    """버튼 안의 링크는 표준에서 허용하지 않고 낭독기도 제대로 읽지 못한다."""
    js = client.get("/offline/offline.js").get_data(as_text=True)
    assert "event-card-main" in js
    assert "stopPropagation" not in js


def test_offline_card_text_starts_at_the_left_edge(client):
    """<button>은 안쪽 내용을 통째로 가운데로 모은다. text-align 만으로는 안 된다."""
    css = client.get("/offline/style.css").get_data(as_text=True)
    main = css.split(".event-card-main {")[1].split("}")[0]
    assert "text-align: left" in main
    assert "justify-content: stretch" in main


def test_offline_explains_itself_when_the_map_is_missing(client):
    """빈 상자만 남으면 고장인지 아직 불러오는 중인지 알 수 없다."""
    js = client.get("/offline/offline.js").get_data(as_text=True)
    css = client.get("/offline/style.css").get_data(as_text=True)
    assert "showMapUnavailable" in js
    # 지도 인증이 막히면 스크립트는 멀쩡히 올라오고 화면만 빈다.
    assert "navermap_authFailure" in js
    assert ".map-fallback" in css


def test_offline_list_scrolls_on_its_own_only_beside_the_map(client):
    """좁은 화면에서 안쪽 스크롤을 두면 페이지를 내리려다 목록 안에 갇힌다."""
    css = client.get("/offline/style.css").get_data(as_text=True)
    wide = css.split("@media (min-width: 900px)")[1]
    assert "overflow-y: auto" in wide
    assert css.split("@media (min-width: 900px)")[0].count("overflow-y: auto") == 0


# --- 좁은 화면의 머리말 -----------------------------------------------------

def test_header_stacks_the_brand_above_the_menu_on_narrow_screens(client):
    """한 줄에 같이 두면 이름이 폭의 절반을 먹고 메뉴가 세 줄까지 접혔다."""
    css = client.get("/assets/site.css").get_data(as_text=True)
    narrow = css.split("@media (max-width: 720px)")[-1]
    header = narrow.split(".site-header {")[1].split("}")[0]
    assert "flex-direction: column" in header
