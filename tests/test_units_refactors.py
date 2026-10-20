"""외부 자원 없이 도는 데이터 접근 로직 테스트.

DB 왕복을 줄이려고 손댄 자리들이 예전과 같은 결과를 내는지 가짜 커서로 확인한다.
(실제 MySQL을 쓰는 검증은 tests/test_background_tasks.py 와 통합 테스트가 맡는다.)
"""

from unittest.mock import MagicMock, patch

from pathlib import Path

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
    assert len(targets) == 15 == SEARCH_TARGET_LIMIT


def test_select_search_targets_prioritizes_unchecked_and_stale_songs():
    from datetime import datetime

    songs = [
        {**_song("recent-risk-28", 28), "last_checked_at": datetime(2026, 1, 3)},
        {**_song("old-risk-1", 1), "last_checked_at": datetime(2026, 1, 1)},
        {**_song("unchecked-risk-5", 5), "last_checked_at": None},
        {**_song("unchecked-risk-28", 28), "last_checked_at": None},
    ]
    _, targets = select_search_targets(songs)
    assert [song["query"] for song in targets] == [
        "unchecked-risk-28",
        "unchecked-risk-5",
        "old-risk-1",
        "recent-risk-28",
    ]


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
    cursor = FakeCursor([[{"video_id": "old", "title": "곡", "count": 100_000}]])
    songs = [{"video_id": "old", "title": "곡", "count": 100_001}, {"video_id": "new", "title": "새 곡", "count": 3}]

    monitoring.update_song_counts(cursor, songs, access_token="unused")

    selects = [sql for sql in cursor.statements() if sql.startswith("SELECT")]
    assert selects == ["SELECT video_id, title, count FROM song_counts"]


def test_update_song_counts_inserts_unknown_song():
    cursor = FakeCursor([[]])
    monitoring.update_song_counts(cursor, [{"video_id": "new", "title": "새 곡", "count": 7}], "unused")

    inserts = [sql for sql in cursor.statements() if sql.startswith("INSERT")]
    assert len(inserts) == 1
    assert cursor.calls[-1][2][:3] == ("새 곡", "new", 7)


def test_update_song_counts_notifies_only_when_crossing_a_milestone():
    cursor = FakeCursor([[{"video_id": "v", "title": "곡", "count": 120_000}]])
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        monitoring.update_song_counts(cursor, [{"video_id": "v", "title": "곡", "count": 150_000}], "tok")
    notify.assert_not_called()
    assert not [sql for sql in cursor.statements() if sql.startswith("UPDATE")]

    cursor = FakeCursor([[{"video_id": "v", "title": "곡", "count": 120_000}]])
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        monitoring.update_song_counts(cursor, [{"video_id": "v", "title": "곡", "count": 250_000}], "tok")
    notify.assert_called_once()
    assert [sql for sql in cursor.statements() if sql.startswith("UPDATE")]


def test_update_song_counts_refreshes_changed_title_without_milestone():
    cursor = FakeCursor([[{"video_id": "v", "title": "이전 제목", "count": 120_000}]])
    song = {"video_id": "v", "title": "새 제목", "count": 150_000}

    with patch.object(monitoring, "send_milestone_notifications") as notify:
        monitoring.update_song_counts(cursor, [song], "unused")

    notify.assert_not_called()
    updates = [call for call in cursor.calls if call[0] == "execute" and call[1].startswith("UPDATE")]
    assert updates == [
        ("execute", "UPDATE song_counts SET title = %s WHERE video_id = %s", ("새 제목", "v"))
    ]


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



def test_send_milestone_notifications_keeps_going_when_one_request_fails():
    """한 토큰의 시간 초과가 예외로 새면 조회수 갱신이 롤백되어 모두에게 알림이 다시 나간다."""
    import requests

    cursor = FakeCursor([[{"token": "slow"}, {"token": "ok"}]])
    responses = [requests.Timeout("timed out"), _fcm_response(200)]

    with patch.object(monitoring.SESSION, "post", side_effect=responses) as post:
        monitoring.send_milestone_notifications(cursor, "access", {"title": "곡", "video_id": "v", "count": 100_000})

    assert post.call_count == 2


def test_monitoring_cleans_expired_rows_even_when_youtube_fails():
    from contextlib import contextmanager

    cursor = FakeCursor([])

    @contextmanager
    def fake_cursor():
        yield cursor

    with patch.object(monitoring, "database_cursor", fake_cursor),          patch.object(monitoring, "remove_expired_data") as remove,          patch.object(monitoring, "get_playlist_videos", side_effect=RuntimeError("quota")),          patch.object(monitoring.time, "sleep", side_effect=StopIteration):
        with pytest.raises(StopIteration):
            monitoring.monitoring_process()

    remove.assert_called_once_with(cursor)


def test_background_tasks_start_in_only_one_process(tmp_path):
    """워커가 여럿이어도 작업은 한 벌만 돌아야 알림이 겹쳐 나가지 않는다."""
    import stelline.background_tasks as background_tasks

    if background_tasks.fcntl is None:
        pytest.skip("파일 잠금은 POSIX 에서만 쓴다")

    lock_path = tmp_path / "runner.lock"
    previous = background_tasks._lock_handle
    try:
        assert background_tasks.acquire_runner_lock(lock_path) is True
        first = background_tasks._lock_handle
        # 다른 프로세스와 같은 처지: 같은 파일을 새로 열어 잠그려 한다.
        assert background_tasks.acquire_runner_lock(lock_path) is False
        first.close()
        assert background_tasks.acquire_runner_lock(lock_path) is True
        background_tasks._lock_handle.close()
    finally:
        background_tasks._lock_handle = previous


def test_start_background_tasks_skips_when_another_process_runs_them():
    import stelline.background_tasks as background_tasks

    with patch.object(background_tasks, "acquire_runner_lock", return_value=False),          patch.object(background_tasks, "start_monitoring") as monitoring_start,          patch.object(background_tasks, "start_search_scheduler") as search_start,          patch.object(background_tasks, "start_rank_refresh") as rank_start:
        background_tasks.start_background_tasks()

    monitoring_start.assert_not_called()
    search_start.assert_not_called()
    rank_start.assert_not_called()


def test_importing_the_app_never_starts_background_tasks():
    """마이그레이션·시드 명령은 앱 패키지를 불러온다. 그것만으로 작업이 돌면 안 된다.

    그 짧은 프로세스가 작업과 잠금을 먼저 잡으면, 그동안 뜬 서버 워커는 작업을 건너뛴다.
    운영처럼 START_BACKGROUND_TASKS=true 로 두고 별도 프로세스에서 실제로 불러와 본다.
    """
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "APP_ENV": "development",
        "START_BACKGROUND_TASKS": "true",
        "AUTO_CREATE_SCHEMA": "false",
        "SECRET_KEY": "test-secret-key",
    }
    code = (
        "import threading\n"
        "import stelline, stelline.database.migrate, stelline.database.karaoke_seed\n"
        "print(threading.active_count())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "1", "앱을 불러오기만 했는데 스레드가 떴습니다"


def test_gunicorn_worker_starts_background_tasks_after_loading_the_app():
    import importlib.util

    conf_path = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("stelline_gunicorn_conf", conf_path)
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)

    with patch("stelline.background_tasks.start_background_tasks_if_enabled") as start:
        conf.post_worker_init(worker=None)
    start.assert_called_once_with()



def test_gunicorn_picks_up_the_conf_file_from_the_repo_root():
    """systemd 는 --config 없이 저장소 맨 위에서 gunicorn 을 띄운다. 그래도 이 훅이 쓰여야 한다."""
    import subprocess
    import sys

    pytest.importorskip("fcntl", reason="gunicorn 은 POSIX 에서만 돈다")
    result = subprocess.run(
        [sys.executable, "-m", "gunicorn", "--print-config", "stelline:app"],
        capture_output=True, text=True, timeout=30, cwd=Path(__file__).resolve().parent.parent,
    )
    assert result.returncode == 0, result.stderr
    hook = next(line for line in result.stdout.splitlines() if line.startswith("post_worker_init "))
    # 기본값이면 '<PostWorkerInit.post_worker_init()>' 로 나온다.
    assert "PostWorkerInit" not in hook, hook

@pytest.mark.parametrize("enabled", [True, False])
def test_background_tasks_follow_the_switch(enabled):
    import stelline.background_tasks as background_tasks

    with patch.object(background_tasks, "START_BACKGROUND_TASKS", enabled), \
         patch.object(background_tasks, "start_background_tasks") as start:
        background_tasks.start_background_tasks_if_enabled()
    assert start.called is enabled


def test_search_runs_fit_the_youtube_quota_day_three_times():
    """할당량은 태평양 시간 자정에 다시 찬다. 8시간 간격이면 서머타임과 상관없이 하루에 정확히 세 회차다.

    네 회차였을 때는 마지막 회차(한국 15시)가 할당량을 넘겨 늘 429 로 끊겼다.
    """
    from collections import Counter
    from datetime import datetime, timedelta, timezone

    from stelline.apis.search.tasks import SEARCH_CALLS_PER_RUN
    from stelline.config import SEARCH_API_INTERVAL

    try:
        from zoneinfo import ZoneInfo
        pacific = ZoneInfo("America/Los_Angeles")
    except Exception:  # 윈도우에 tzdata 가 없으면
        pytest.skip("시간대 정보가 없다")

    start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2028, 1, 1, tzinfo=timezone.utc).timestamp())
    first = start - start % SEARCH_API_INTERVAL + SEARCH_API_INTERVAL
    # 첫 검색 호출은 회차 시작 20초 뒤에 나간다(tasks.search_unverified_songs 의 sleep).
    runs_per_quota_day = Counter(
        (datetime.fromtimestamp(t, timezone.utc) + timedelta(seconds=20)).astimezone(pacific).date()
        for t in range(first, end, SEARCH_API_INTERVAL)
    )
    full_days = list(runs_per_quota_day.items())[1:-1]  # 처음·마지막 날은 잘려 있다
    assert full_days and {count for _, count in full_days} == {3}

    daily_units = 3 * SEARCH_CALLS_PER_RUN * 100
    assert daily_units <= 9000, "같은 프로젝트의 다른 사용분 몫으로 1,000 은 남겨야 한다"


def test_one_search_run_never_exceeds_its_call_budget():
    from stelline.apis.search import tasks

    songs = [{"query": f"곡 {i}", "video_id": f"v{i}", "risk": 0} for i in range(200)]
    with patch.object(tasks, "fetch_song_infos_from_db", return_value=songs), \
         patch.object(tasks, "SEARCH_API_KEY", ["key"]), \
         patch.object(tasks, "update_song_risk"), \
         patch.object(tasks, "update_fallback_query", return_value=True), \
         patch.object(tasks, "crawl_search_results_for_missing_videos", side_effect=lambda found: found), \
         patch.object(tasks.time, "sleep"), \
         patch.object(tasks, "_youtube_video_ids_for_query", return_value=[]) as search:
        result = tasks.search_unverified_songs()

    assert search.call_count == tasks.SEARCH_CALLS_PER_RUN
    assert result["isQuotaExceeded"] is False


def test_search_uses_cover_fallback_and_records_match_for_public_display():
    from stelline.apis.search import tasks

    song = {"query": "토아 제육감", "video_id": "video", "risk": 28}
    with patch.object(tasks, "fetch_song_infos_from_db", return_value=[song]), \
         patch.object(tasks, "SEARCH_API_KEY", ["key"]), \
         patch.object(tasks, "update_song_risk"), \
         patch.object(tasks, "update_fallback_query", return_value=True) as save_fallback, \
         patch.object(tasks, "crawl_search_results_for_missing_videos", side_effect=lambda found: found), \
         patch.object(tasks.time, "sleep"), \
         patch.object(tasks, "_youtube_video_ids_for_query", side_effect=[[], ["video"]]) as search:
        result = tasks.search_unverified_songs()

    assert [call.args[0] for call in search.call_args_list] == ["토아 제육감", "토아 제육감 cover"]
    save_fallback.assert_called_once_with("토아 제육감", "토아 제육감 cover")
    assert result["all_songs"] == []


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
