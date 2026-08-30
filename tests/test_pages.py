"""화면(정적 페이지·템플릿) 제공을 검증한다. DB 불필요."""

import pytest


@pytest.mark.parametrize(
    "path",
    ["/", "/search", "/search/", "/congratulation", "/congratulation/", "/offline", "/offline/"],
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
