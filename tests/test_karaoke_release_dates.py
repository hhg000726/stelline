"""커버 곡 발매일 채우기의 순수 로직 테스트. DB·네트워크 불필요."""

import pytest

from stelline.database import karaoke_release_dates as release_dates


@pytest.mark.parametrize(
    "value,expected",
    [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("  dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ&t=30", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=12", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("", None),
        (None, None),
        ("https://www.youtube.com/", None),
        ("그냥 메모", None),
    ],
)
def test_extract_video_id(value, expected):
    assert release_dates.extract_video_id(value) == expected


def test_upload_date_is_converted_to_korean_date():
    # UTC 15:30은 한국 시간으로 다음 날 00:30이라 발매일도 하루 뒤가 된다.
    assert release_dates._upload_date("2024-08-01T15:30:00Z") == "2024-08-02"
    assert release_dates._upload_date("2024-08-01T05:00:00Z") == "2024-08-01"


def test_upload_date_ignores_unparsable_value():
    assert release_dates._upload_date("어제") is None
    assert release_dates._upload_date("") is None


class _FakeResponse:
    def __init__(self, payload, error=None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._payload


def _snippet(video_id, published_at):
    return {"id": video_id, "snippet": {"publishedAt": published_at}}


def test_fetch_upload_dates_requests_fifty_ids_at_a_time(monkeypatch):
    """쿼터는 호출 수로 매겨지니 51개는 두 번에 나눠 보내야 한다."""
    ids = [f"video{index:06d}" for index in range(51)]
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["id"].split(","))
        return _FakeResponse({"items": [_snippet(value, "2024-01-02T03:00:00Z") for value in params["id"].split(",")]})

    monkeypatch.setattr(release_dates.requests, "get", fake_get)
    dates = release_dates.fetch_upload_dates(ids, api_key="test-key")

    assert [len(call) for call in calls] == [50, 1]
    assert len(dates) == 51
    assert dates["video000000"] == "2024-01-02"


def test_fetch_upload_dates_skips_videos_missing_from_the_response(monkeypatch):
    """삭제·비공개 영상은 응답에 없다. 나머지는 그대로 채워져야 한다."""
    monkeypatch.setattr(
        release_dates.requests,
        "get",
        lambda url, params, timeout: _FakeResponse({"items": [_snippet("aaaaaaaaaaa", "2023-05-05T00:00:00Z")]}),
    )
    dates = release_dates.fetch_upload_dates(["aaaaaaaaaaa", "bbbbbbbbbbb"], api_key="test-key")

    assert dates == {"aaaaaaaaaaa": "2023-05-05"}


def test_fetch_upload_dates_continues_after_a_failed_batch(monkeypatch):
    responses = [
        _FakeResponse(None, error=RuntimeError("429 Too Many Requests")),
        _FakeResponse({"items": [_snippet("bbbbbbbbbbb", "2022-03-03T00:00:00Z")]}),
    ]
    monkeypatch.setattr(release_dates.requests, "get", lambda url, params, timeout: responses.pop(0))

    dates = release_dates.fetch_upload_dates([f"video{index:06d}" for index in range(51)], api_key="test-key")

    assert dates == {"bbbbbbbbbbb": "2022-03-03"}


def test_fetch_upload_dates_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(release_dates, "API_KEY", None)
    with pytest.raises(RuntimeError):
        release_dates.fetch_upload_dates(["dQw4w9WgXcQ"])
