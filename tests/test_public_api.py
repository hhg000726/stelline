"""DB 없이 검증 가능한 API 동작(요청 검증·캡차·스레드 기동)."""

from unittest.mock import patch

import pytest

from stelline.apis import reports


def test_bugs_rank_returns_current_snapshot(client):
    with patch("stelline.apis.bugs.service.recent_rank_data", {"곡": {"rank": 1}}):
        resp = client.get("/api/bugs/rank")
    assert resp.status_code == 200
    assert resp.get_json() == {"곡": {"rank": 1}}


def test_bugs_rank_empty_by_default(client):
    resp = client.get("/api/bugs/rank")
    assert resp.status_code == 200
    assert resp.get_json() == {}


@pytest.mark.parametrize("endpoint", ["/api/search/reports", "/api/congratulation/reports"])
def test_report_rejects_failed_captcha(client, endpoint):
    resp = client.post(endpoint, json={"content": "누락된 노래입니다", "captcha_token": "bad"})
    assert resp.status_code == 400
    assert "캡차" in resp.get_json()["error"]


@pytest.mark.parametrize("endpoint", ["/api/search/reports", "/api/congratulation/reports"])
def test_report_rejects_empty_content(client, endpoint):
    with patch.object(reports, "verify_turnstile", return_value=True):
        resp = client.post(endpoint, json={"content": "   ", "captcha_token": "ok"})
    assert resp.status_code == 400
    assert "내용을 입력" in resp.get_json()["error"]


@pytest.mark.parametrize("endpoint", ["/api/search/reports", "/api/congratulation/reports"])
def test_report_rejects_overlong_content(client, endpoint):
    with patch.object(reports, "verify_turnstile", return_value=True):
        resp = client.post(endpoint, json={"content": "x" * 2001, "captcha_token": "ok"})
    assert resp.status_code == 400
    assert "2000" in resp.get_json()["error"]


def test_force_search_is_not_a_public_api(client):
    """즉시 검사는 관리자 키의 할당량을 쓴다. 로그인 없이 띄울 수 있으면 안 된다."""
    with patch("stelline.apis.search.tasks.start_admin_search") as start:
        assert client.get("/api/search/force_search").status_code == 404
        assert client.post("/api/search/force_search").status_code in (404, 405)
    start.assert_not_called()


def test_admin_force_search_requires_login(client):
    with patch("stelline.admin.routes.start_admin_search") as start:
        resp = client.post("/admin/search/force")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    start.assert_not_called()


def test_admin_force_search_requires_csrf(admin_client):
    with patch("stelline.admin.routes.start_admin_search") as start:
        resp = admin_client.post("/admin/search/force", data={"csrf_token": "wrong"})
    assert resp.status_code == 400
    start.assert_not_called()


def test_admin_force_search_starts_one_run(admin_client):
    with patch("stelline.admin.routes.start_admin_search", return_value=True) as start:
        resp = admin_client.post("/admin/search/force", data={"csrf_token": admin_client.csrf})
    assert resp.status_code == 302
    start.assert_called_once_with()


def test_start_admin_search_refuses_while_a_run_is_in_progress():
    import threading

    from stelline.apis.search import tasks

    started = threading.Event()
    release = threading.Event()

    def slow_run(by_admin=False):
        started.set()
        release.wait(timeout=5)

    with patch.object(tasks, "run_search_once", side_effect=slow_run) as run:
        assert tasks.start_admin_search() is True
        assert started.wait(timeout=5)
        # 첫 회차가 끝나기 전에는 두 번째를 띄우지 않는다.
        assert tasks.start_admin_search() is False
        release.set()
        for _ in range(50):
            if not tasks.SEARCH_LOCK.locked():
                break
            threading.Event().wait(0.05)
        assert not tasks.SEARCH_LOCK.locked(), "회차가 끝나면 잠금이 풀려야 합니다"
    run.assert_called_once_with(by_admin=True)


def test_admin_login_accepts_only_the_configured_account(client):
    resp = client.post("/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert not sess.get("logged_in")

    resp = client.post("/auth/login", data={"username": "admin", "password": "test-admin-password"})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


def test_admin_login_is_closed_when_no_password_is_configured(client):
    with patch("stelline.auth.routes.ADMIN_PASSWORD", ""), patch("stelline.auth.routes.ADMIN_USERNAME", ""):
        client.post("/auth/login", data={"username": "", "password": ""})
    with client.session_transaction() as sess:
        assert not sess.get("logged_in")


def test_cors_is_limited_to_public_api(client):
    origin = {"Origin": "https://example.com"}
    assert client.get("/api/bugs/rank", headers=origin).headers.get("Access-Control-Allow-Origin")
    assert "Access-Control-Allow-Origin" not in client.get("/auth/login", headers=origin).headers
