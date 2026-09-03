"""외부 자원 없이 도는 순수 로직 테스트."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from stelline import app as flask_app
from stelline.apis import turnstile
from stelline.apis.bugs.tasks import scrape_bugs_favorite
from stelline.apis.offline.service import geocode_location
from stelline.apis.search import tasks as search_tasks
from stelline.admin import routes as admin_routes
from stelline.apis.karaoke import service as karaoke_service


# --- Cloudflare Turnstile -------------------------------------------------

def test_turnstile_rejects_without_secret(monkeypatch):
    monkeypatch.setattr(turnstile, "TURNSTILE_SECRET_KEY", "")
    assert turnstile.verify_turnstile("any-token") is False


def test_turnstile_rejects_without_token(monkeypatch):
    monkeypatch.setattr(turnstile, "TURNSTILE_SECRET_KEY", "secret")
    assert turnstile.verify_turnstile(None) is False


def test_turnstile_accepts_on_success(monkeypatch):
    monkeypatch.setattr(turnstile, "TURNSTILE_SECRET_KEY", "secret")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"success": true}'

    monkeypatch.setattr(turnstile.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with flask_app.test_request_context("/", environ_base={"REMOTE_ADDR": "1.2.3.4"}):
        assert turnstile.verify_turnstile("good-token") is True


def test_turnstile_returns_false_on_network_error(monkeypatch):
    monkeypatch.setattr(turnstile, "TURNSTILE_SECRET_KEY", "secret")

    def _boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(turnstile.urllib.request, "urlopen", _boom)
    with flask_app.test_request_context("/"):
        assert turnstile.verify_turnstile("good-token") is False


# --- Naver geocoding ----------------------------------------------------

def _geo_response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_geocode_parses_first_address():
    resp = _geo_response({"addresses": [{"y": "37.5665", "x": "126.9780"}]})
    with patch("stelline.apis.offline.service.requests.get", return_value=resp):
        assert geocode_location("서울시청", "id", "secret") == (37.5665, 126.9780)


def test_geocode_returns_none_when_no_result():
    resp = _geo_response({"addresses": []})
    with patch("stelline.apis.offline.service.requests.get", return_value=resp):
        assert geocode_location("존재하지 않는 주소", "id", "secret") == (None, None)


def test_geocode_swallows_request_error():
    import requests

    with patch(
        "stelline.apis.offline.service.requests.get",
        side_effect=requests.exceptions.RequestException("timeout"),
    ):
        assert geocode_location("서울", "id", "secret") == (None, None)


# --- Bugs 응원 순위 스크래핑 --------------------------------------------

BUGS_HTML = """
<html><body>
  <p class="title">첫번째 곡</p>
  <p class="title">스텔라이브 - 대상 곡</p>
  <p class="title">세번째 곡</p>
  <span class="count">1,200</span>
  <span class="count">1,000</span>
  <span class="count">900</span>
  <span class="streaming">60.0%</span>
  <span class="streaming">45.5%</span>
  <span class="streaming">30.0%</span>
  <div class="cheerupMessage"><span><em>오늘도 화이팅!</em></span></div>
</body></html>
"""


def _bugs_response(html, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    return resp


def test_scrape_bugs_favorite_computes_rank_and_diffs():
    with patch("stelline.apis.bugs.tasks.requests.get", return_value=_bugs_response(BUGS_HTML)):
        result = scrape_bugs_favorite("대상 곡", 42)

    assert result["rank"] == 2
    assert result["message"] == "오늘도 화이팅!"
    assert result["diffs"]["count_diff"] == 200  # 1200 - 1000
    assert result["diffs"]["count_to_first"] == 200
    assert result["diffs"]["streaming_diff"] == 14.5  # 60.0 - 45.5
    assert result["diffs"]["streaming_to_first"] == 14.5


def test_scrape_bugs_favorite_returns_none_when_target_missing():
    with patch("stelline.apis.bugs.tasks.requests.get", return_value=_bugs_response(BUGS_HTML)):
        assert scrape_bugs_favorite("목록에 없는 곡", 42) is None


def test_scrape_bugs_favorite_returns_none_on_http_error():
    with patch(
        "stelline.apis.bugs.tasks.requests.get", return_value=_bugs_response("", status=503)
    ):
        assert scrape_bugs_favorite("대상 곡", 42) is None


# --- 검색 위험도(risk) 판정 -------------------------------------------

def test_resolve_match_lowers_risk_when_video_present():
    with patch.object(search_tasks, "update_song_risk") as update:
        found = search_tasks._resolve_match("q", "vid1", ["vid1", "vid2"], song_risk=10)
    assert found is True
    update.assert_called_once_with("q", 9)


def test_resolve_match_raises_risk_when_video_missing():
    with patch.object(search_tasks, "update_song_risk") as update:
        found = search_tasks._resolve_match("q", "vidX", ["vid1"], song_risk=3)
    assert found is False
    update.assert_called_once_with("q", 28)


def test_resolve_match_risk_never_negative():
    with patch.object(search_tasks, "update_song_risk") as update:
        search_tasks._resolve_match("q", "vid1", ["vid1"], song_risk=0)
    update.assert_called_once_with("q", 0)


# --- 관리자 폼 헬퍼 ---------------------------------------------------

@pytest.mark.parametrize(
    "field,expected",
    [
        ("expires_at", "datetime-local"),
        ("start_date", "datetime-local"),
        ("url_number", "number"),
        ("risk", "number"),
        ("latitude", "number"),
        ("title", "text"),
        ("content", "text"),
    ],
)
def test_admin_input_type(field, expected):
    assert admin_routes.input_type(field) == expected


def test_admin_row_token_roundtrip():
    row = {"id": 7, "content": "제보 내용", "created_at": datetime(2026, 1, 2, 3, 4, 5)}
    token = admin_routes.serialize_row(row)
    restored = admin_routes.row_serializer().loads(token)
    assert restored == {"id": "7", "content": "제보 내용", "created_at": "2026-01-02 03:04:05"}


def test_admin_row_token_rejects_tampering():
    from itsdangerous import BadSignature

    token = admin_routes.serialize_row({"id": 1})
    with pytest.raises(BadSignature):
        admin_routes.row_serializer().loads(token + "x")


# --- 노래방 '마지막 갱신' 시각 ------------------------------------------

def test_karaoke_updated_at_is_shown_in_korean_time():
    """DB(UTC)에서 읽은 시각을 아홉 시간 앞으로 옮겨 내려준다."""
    rows = [{"updated_at": datetime(2026, 9, 1, 3, 0, 0)}]
    assert karaoke_service._updated_at_text(rows) == "2026-09-01 12:00:00"


def test_karaoke_updated_at_uses_the_latest_row():
    rows = [
        {"updated_at": datetime(2026, 9, 1, 3, 0, 0)},
        {"updated_at": datetime(2026, 9, 2, 15, 30, 0)},
        {"updated_at": None},
    ]
    assert karaoke_service._updated_at_text(rows) == "2026-09-03 00:30:00"


def test_karaoke_updated_at_is_empty_without_rows():
    assert karaoke_service._updated_at_text([]) == ""
    assert karaoke_service._updated_at_text([{"updated_at": None}]) == ""
