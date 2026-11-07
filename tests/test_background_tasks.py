"""백그라운드 작업의 DB 로직 검증 (실제 MySQL). 네트워크 호출은 하지 않는다."""

from datetime import datetime, timedelta
from unittest.mock import patch

from stelline.background_tasks import monitoring
from stelline.apis.bugs import tasks as bugs_tasks
from tests.conftest import requires_db

pytestmark = requires_db


def _rows(db, sql, params=()):
    with db.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def test_remove_expired_data_deletes_only_stale_rows(db, clean_db):
    past = datetime.now() - timedelta(days=1)
    future = datetime.now() + timedelta(days=1)
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO events (title, link, expires_at) VALUES (%s, %s, %s)", ("만료", "l", past)
        )
        cursor.execute(
            "INSERT INTO events (title, link, expires_at) VALUES (%s, %s, %s)", ("유효", "l", future)
        )
        monitoring.remove_expired_data(cursor)
    db.commit()

    assert {r["title"] for r in _rows(db, "SELECT title FROM events")} == {"유효"}


def test_search_checks_older_than_the_retention_are_pruned(db, clean_db):
    """검색 검사 기록은 검색 점검 회차가 끝날 때 보관 기간(90일)이 지난 것만 지운다."""
    from stelline.apis.search import tasks as search_tasks
    from stelline.apis.search.history import CHECK_RETENTION

    now = datetime(2026, 11, 7, 3, 0)
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO search_checks (query, video_id, result, checked_at) VALUES (%s, %s, %s, %s)",
            [
                ("곡", "v", "blocked", now - CHECK_RETENTION - timedelta(minutes=1)),
                ("곡", "v", "visible", now - CHECK_RETENTION + timedelta(minutes=1)),
            ],
        )
    db.commit()
    search_tasks.prune_old_checks(now)
    assert [r["result"] for r in _rows(db, "SELECT result FROM search_checks")] == ["visible"]


def test_update_song_counts_inserts_new_song(db, clean_db):
    songs = [{"video_id": "vidNew", "title": "새 곡", "count": 12345}]
    with db.cursor() as cursor:
        monitoring.update_song_counts(cursor, songs, access_token="unused")
    db.commit()

    row = _rows(db, "SELECT * FROM song_counts WHERE video_id = 'vidNew'")[0]
    assert row["count"] == 12345
    assert row["counted_time"].year == 2000  # 신규는 과거 시각으로 저장


def test_update_song_counts_notifies_on_milestone_cross(db, clean_db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, %s)",
            ("vidM", "마일스톤 곡", 90_000, datetime(2000, 1, 1)),
        )
    db.commit()

    songs = [{"video_id": "vidM", "title": "마일스톤 곡", "count": 190_000}]
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        with db.cursor() as cursor:
            monitoring.update_song_counts(cursor, songs, access_token="unused")
        db.commit()

    notify.assert_called_once()
    updated = _rows(db, "SELECT count FROM song_counts WHERE video_id = 'vidM'")[0]
    assert updated["count"] == 190_000


def test_update_song_counts_no_notify_within_same_bucket(db, clean_db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, %s)",
            ("vidS", "곡", 120_000, datetime(2000, 1, 1)),
        )
    db.commit()

    songs = [{"video_id": "vidS", "title": "곡", "count": 150_000}]
    with patch.object(monitoring, "send_milestone_notifications") as notify:
        with db.cursor() as cursor:
            monitoring.update_song_counts(cursor, songs, access_token="unused")
        db.commit()
    notify.assert_not_called()


def test_update_song_counts_syncs_changed_title_without_milestone(db, clean_db):
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, %s)",
                ("vidTitle", "이전 제목", 120_000, datetime(2000, 1, 1)),
            )
        db.commit()

        with patch.object(monitoring, "send_milestone_notifications") as notify:
            with db.cursor() as cursor:
                monitoring.update_song_counts(
                    cursor,
                    [{"video_id": "vidTitle", "title": "바뀐 YouTube 제목", "count": 150_000}],
                    access_token="unused",
                )
            db.commit()

        notify.assert_not_called()
        row = _rows(db, "SELECT title, count, counted_time FROM song_counts WHERE video_id = 'vidTitle'")[0]
        assert row["title"] == "바뀐 YouTube 제목"
        assert row["count"] == 120_000
        assert row["counted_time"] == datetime(2000, 1, 1)


def test_bugs_load_targets_reads_rows(db, clean_db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO targets (name, title, url_number) VALUES (%s, %s, %s)",
            ("스텔라이브", "응원곡", 12345),
        )
    db.commit()
    targets = bugs_tasks.load_targets()
    assert [t["name"] for t in targets] == ["스텔라이브"]
