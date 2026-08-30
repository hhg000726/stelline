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


def test_force_search_spawns_worker_and_returns_ok(client):
    import threading

    called = threading.Event()
    captured = {}

    def fake_cycle(by_admin=False):
        captured["by_admin"] = by_admin
        called.set()

    with patch("stelline.apis.search.service.run_search_cycle", side_effect=fake_cycle):
        resp = client.get("/api/search/force_search")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}
        assert called.wait(timeout=5), "백그라운드 검색 워커가 기동되지 않았습니다"

    assert captured["by_admin"] is True
