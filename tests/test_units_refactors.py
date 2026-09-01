"""외부 자원 없이 도는 데이터 접근 로직 테스트.

DB 왕복을 줄이려고 손댄 자리들이 예전과 같은 결과를 내는지 가짜 커서로 확인한다.
(실제 MySQL을 쓰는 검증은 tests/test_background_tasks.py 와 통합 테스트가 맡는다.)
"""

from unittest.mock import MagicMock, patch

import pytest

from stelline.apis.karaoke.service import _member_list
from stelline.apis.offline.service import _needs_geocoding
from stelline.apis.search.tasks import SEARCH_TARGET_LIMIT, select_search_targets
from stelline.background_tasks import monitoring
from stelline.database import import_admin_html


class FakeCursor:
    """execute/executemany 호출을 기록하고, 미리 정해 둔 결과를 돌려주는 커서."""

    def __init__(self, results=()):
        self.results = list(results)
        self.calls = []
        self._rows = []

    def execute(self, sql, params=None):
        self.calls.append(("execute", " ".join(sql.split()), params))
        if self.results:
            self._rows = self.results.pop(0)

    def executemany(self, sql, params):
        self.calls.append(("executemany", " ".join(sql.split()), list(params)))

    def fetchall(self):
        return self._rows

    def statements(self, kind=None):
        return [sql for call, sql, _ in self.calls if kind is None or call == kind]


# --- 검색 대상 고르기 --------------------------------------------------

def _song(query, risk):
    return {"query": query, "video_id": "v" + query, "risk": risk}


def test_select_search_targets_prefers_the_riskiest_songs():
    songs = [_song("a", 0), _song("b", 5), _song("c", 28), _song("d", 5), _song("e", 0)]
    risk_zero, targets = select_search_targets(songs)

    # 위험도가 큰 쪽부터, 같은 위험도 안에서는 원래 목록 순서 그대로.
    assert [song["query"] for song in targets] == ["c", "b", "d"]
    assert [song["query"] for song in risk_zero] == ["a", "e"]


def test_select_search_targets_stops_at_the_limit():
    songs = [_song(str(index), 10) for index in range(30)]
    _, targets = select_search_targets(songs)
    assert len(targets) == SEARCH_TARGET_LIMIT


def test_select_search_targets_ignores_songs_without_risk():
    risk_zero, targets = select_search_targets([{"query": "x", "video_id": "v"}])
    assert risk_zero == [] and targets == []


def test_select_search_targets_does_not_alias_the_bucket():
    """돌려준 목록을 호출부가 pop 해도 원본 곡 목록이 상하면 안 된다."""
    songs = [_song("a", 0), _song("b", 0)]
    risk_zero, _ = select_search_targets(songs)
    risk_zero.pop()
    assert len(songs) == 2


# --- 조회수 갱신 (곡마다 SELECT 하지 않는다) ---------------------------

def test_update_song_counts_reads_stored_counts_once():
    cursor = FakeCursor([[{"video_id": "old", "count": 100_000}]])
    songs = [{"video_id": "old", "title": "곡", "count": 100_001}, {"video_id": "new", "title": "새 곡", "count": 3}]

    monitoring.update_song_counts(cursor, songs, access_token="unused")

    selects = [sql for sql in cursor.statements() if sql.startswith("SELECT")]
    assert selects == ["SELECT video_id, count FROM song_counts"]


def test_update_song_counts_inserts_unknown_song():
    cursor = FakeCursor([[]])
    monitoring.update_song_counts(cursor, [{"video_id": "new", "title": "새 곡", "count": 7}], "unused")

    inserts = [sql for sql in cursor.statements() if sql.startswith("INSERT")]
    assert len(inserts) == 1
    assert cursor.calls[-1][2][:3] == ("새 곡", "new", 7)


def test_update_song_counts_notifies_only_when_crossing_a_milestone():
    cursor = FakeCursor([[{"video_id": "v", "count": 120_000}]])
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        monitoring.update_song_counts(cursor, [{"video_id": "v", "title": "곡", "count": 150_000}], "tok")
    notify.assert_not_called()
    assert not [sql for sql in cursor.statements() if sql.startswith("UPDATE")]

    cursor = FakeCursor([[{"video_id": "v", "count": 120_000}]])
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        monitoring.update_song_counts(cursor, [{"video_id": "v", "title": "곡", "count": 250_000}], "tok")
    notify.assert_called_once()
    assert [sql for sql in cursor.statements() if sql.startswith("UPDATE")]


def test_update_song_counts_inserts_a_repeated_video_only_once():
    """예전에는 곡마다 다시 SELECT 해서 방금 넣은 행을 봤다. 그 동작을 유지한다."""
    cursor = FakeCursor([[]])
    song = {"video_id": "dup", "title": "곡", "count": 5}
    monitoring.update_song_counts(cursor, [song, song], "unused")
    assert len([sql for sql in cursor.statements() if sql.startswith("INSERT")]) == 1


# --- FCM 발송 (연결 재사용 + 삭제 일괄 처리) ---------------------------

def _fcm_response(status_code, text="", ok=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.ok = (status_code < 400) if ok is None else ok
    return response


def test_send_milestone_notifications_posts_once_per_token():
    cursor = FakeCursor([[{"token": "t1"}, {"token": "t2"}]])
    song = {"title": "곡", "video_id": "vid", "count": 1_000_000}

    with patch.object(monitoring.SESSION, "post", return_value=_fcm_response(200)) as post:
        monitoring.send_milestone_notifications(cursor, "access", song)

    assert post.call_count == 2
    assert post.call_args.kwargs["json"]["message"]["data"]["body"] == "100만회 달성!"
    assert not cursor.statements("executemany")


def test_send_milestone_notifications_deletes_dead_tokens_in_one_batch():
    cursor = FakeCursor([[{"token": "gone1"}, {"token": "alive"}, {"token": "gone2"}]])
    responses = [
        _fcm_response(404, "UNREGISTERED"),
        _fcm_response(200),
        _fcm_response(404, "UNREGISTERED"),
    ]

    with patch.object(monitoring.SESSION, "post", side_effect=responses):
        monitoring.send_milestone_notifications(cursor, "access", {"title": "곡", "video_id": "v", "count": 100_000})

    deletes = [call for call in cursor.calls if call[0] == "executemany"]
    assert len(deletes) == 1
    assert deletes[0][2] == [("gone1",), ("gone2",)]


# --- 오프라인 좌표 보완 ------------------------------------------------

@pytest.mark.parametrize(
    "event,expected",
    [
        ({"latitude": None, "longitude": None, "address": "서울"}, True),
        ({"latitude": 0, "longitude": 0, "address": "서울"}, True),
        ({"latitude": 37.5, "longitude": 127.0, "address": "서울"}, False),
        ({"latitude": 0, "longitude": 0, "address": ""}, False),
        ({"latitude": 0, "longitude": 0}, False),
        ({"latitude": 37.5, "longitude": 0, "address": "서울"}, True),
    ],
)
def test_needs_geocoding(event, expected):
    assert _needs_geocoding(event) is expected


# --- 노래방 멤버 폴백 --------------------------------------------------

def test_member_list_falls_back_to_names_written_on_songs():
    songs = [
        {"members": "유즈하 리코, 아오쿠모 린"},
        {"members": "아오쿠모 린"},
        {"members": None},
    ]
    assert _member_list([], songs) == [
        {"name": "아오쿠모 린", "unit": "", "formerUnits": []},
        {"name": "유즈하 리코", "unit": "", "formerUnits": []},
    ]


def test_member_list_prefers_the_member_master():
    members = [{"name": "네네코 마시로", "unit": "UNIVERSE", "former_units": "MYSTIC, X"}]
    assert _member_list(members, [{"members": "다른 사람"}]) == [
        {"name": "네네코 마시로", "unit": "UNIVERSE", "formerUnits": ["MYSTIC", "X"]}
    ]


# --- 스냅샷 적재 (행마다 왕복하지 않는다) ------------------------------

def test_import_snapshot_inserts_rows_in_one_batch():
    cursor = FakeCursor()
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    snapshot = {"events": [{"title": "a", "link": "l"}, {"title": "b", "link": "l2"}]}
    with patch.object(import_admin_html, "get_connection", return_value=connection):
        import_admin_html.import_snapshot(snapshot, replace=True)

    assert cursor.statements("execute") == ["DELETE FROM `events`"]
    batched = [call for call in cursor.calls if call[0] == "executemany"]
    assert len(batched) == 1
    assert batched[0][1] == "INSERT INTO `events` (`title`, `link`) VALUES (%s, %s)"
    assert batched[0][2] == [["a", "l"], ["b", "l2"]]
    connection.commit.assert_called_once()
