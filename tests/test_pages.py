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


def test_karaoke_page_sorts_randomly_or_by_name(client):
    """정렬 기준으로 삼을 만한 날짜·순서 값을 두지 않아, 랜덤순과 가나다순만 남겼다."""
    html = client.get("/karaoke/").get_data(as_text=True)
    assert '<option value="random">랜덤순</option>' in html
    assert '<option value="title">가나다순</option>' in html
    for gone in ("최신순", "오래된순", "번호순", "기본순"):
        assert gone not in html
