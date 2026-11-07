"""스키마 마이그레이션 검증 (실제 MySQL)."""

from datetime import datetime, timedelta, timezone

from stelline.database.connection import get_connection
from stelline.database.migrate import apply_migrations
from stelline.database.schema import MIGRATIONS, backfill_search_checks, backfill_search_run_started_at
from tests.conftest import requires_db

pytestmark = requires_db

EXPECTED_TABLES = {
    "song_infos",
    "search_checks",
    "search_requests",
    "songs_data",
    "recent_data",
    "record_main",
    "record_search",
    "targets",
    "events",
    "twits",
    "song_counts",
    "fcm_tokens",
    "offline",
    "song_reports",
    "view_reports",
    "schema_migrations",
}


def _table_names(db):
    with db.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        return {next(iter(row.values())) for row in cursor.fetchall()}


def test_all_expected_tables_exist(db, _schema):
    assert EXPECTED_TABLES.issubset(_table_names(db))


def test_every_migration_is_recorded(db, _schema):
    with db.cursor() as cursor:
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in cursor.fetchall()}
    assert {version for version, _ in MIGRATIONS}.issubset(applied)


def test_apply_migrations_is_idempotent(_schema):
    # 이미 한 번 적용된 상태에서 다시 호출해도 예외 없이 통과해야 한다.
    apply_migrations()
    apply_migrations()

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM schema_migrations")
            count = cursor.fetchone()["n"]
    finally:
        conn.close()
    assert count == len(MIGRATIONS)


def test_song_infos_primary_key_is_query(db, _schema):
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'song_infos'
                 AND CONSTRAINT_NAME = 'PRIMARY'"""
        )
        pk_columns = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    assert pk_columns == {"query"}


def test_search_cover_fallback_columns_exist(db, _schema):
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT COLUMN_NAME FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'song_infos'"""
        )
        columns = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    assert {"fallback_query", "last_checked_at"}.issubset(columns)


# --- 015: 예전 상태값을 검사 기록으로 옮기기 --------------------------------------

def _run_backfill(db):
    with db.cursor() as cursor:
        backfill_search_checks(cursor)
        cursor.execute("SELECT query, video_id, result, fallback_query, checked_at FROM search_checks ORDER BY query, checked_at")
        return cursor.fetchall()


def _legacy_rows(db):
    """운영 DB 에 있던 모양: 곡마다 마지막 결과(risk·fallback_query·last_checked_at)와 7일치 최종 실패(recent_data)."""
    last_run = datetime(2026, 11, 7, 0, 3, 10)  # UTC (DB 세션 시간대가 UTC)
    previous = last_run - timedelta(hours=8)
    rows = [
        # 검색어, 영상, 위험도, cover 검색어, 마지막 검사
        ("막힌 곡", "v1", 28, None, last_run),
        ("cover 곡", "v2", 28, "cover 곡 cover", last_run),
        ("회복 곡", "v3", 27, None, last_run),        # 직전 회차에 막혔고 이번엔 보였다
        ("정상 곡", "v4", 0, None, last_run - timedelta(days=3)),
        ("검사 안 된 곡", "v5", 0, None, None),        # 10/20 이후 한 번도 검사하지 않았다
        ("영상 바뀐 곡", "v6-new", 0, None, last_run),
    ]
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO song_infos (query, video_id, risk, fallback_query, last_checked_at) VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
        epoch = lambda moment: moment.replace(tzinfo=timezone.utc).timestamp()  # noqa: E731
        cursor.executemany(
            "INSERT INTO recent_data (video_id, query, searched_time) VALUES (%s, %s, %s)",
            [
                ("v1", "막힌 곡", epoch(last_run + timedelta(minutes=6))),   # 마지막 검사와 같은 회차 → 겹침
                ("v3", "회복 곡", epoch(previous + timedelta(minutes=6))),   # 이전 회차의 막힘
                ("v6-old", "영상 바뀐 곡", epoch(previous)),                  # 예전 영상의 기록 → 버림
                ("v9", "목록에 없는 곡", epoch(previous)),                     # 지운 곡 → 버림
            ],
        )
    return last_run, previous


def test_backfill_turns_the_old_snapshot_into_check_records(db, clean_db):
    last_run, previous = _legacy_rows(db)
    rows = _run_backfill(db)

    assert [(r["query"], r["video_id"], r["result"], r["fallback_query"], r["checked_at"]) for r in rows] == [
        ("cover 곡", "v2", "cover_only", "cover 곡 cover", last_run),
        ("막힌 곡", "v1", "blocked", None, last_run),
        ("영상 바뀐 곡", "v6-new", "visible", None, last_run),
        ("정상 곡", "v4", "visible", None, last_run - timedelta(days=3)),
        ("회복 곡", "v3", "blocked", None, previous + timedelta(minutes=6)),
        ("회복 곡", "v3", "visible", None, last_run),
    ]


def test_backfill_runs_only_once(db, clean_db):
    _legacy_rows(db)
    first = _run_backfill(db)
    assert _run_backfill(db) == first


def test_016_fills_the_run_start_of_older_records(db, clean_db):
    """016 전 기록은 모두 정기 회차(UTC 0·8·16시 시작)에서 나왔으므로 검사 시각을 그 경계로 내린다."""
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO search_checks (query, video_id, result, checked_at) VALUES (%s, %s, %s, %s)",
            [
                ("09시 회차", "v", "blocked", datetime(2026, 11, 7, 0, 10, 29)),
                ("17시 회차", "v", "visible", datetime(2026, 11, 6, 8, 2, 21)),
            ],
        )
        cursor.execute(
            "INSERT INTO search_checks (query, video_id, result, checked_at, run_started_at) VALUES (%s, %s, %s, %s, %s)",
            ("새 기록", "v", "visible", datetime(2026, 11, 7, 3, 5), datetime(2026, 11, 7, 3, 0)),
        )
        backfill_search_run_started_at(cursor)
        cursor.execute("SELECT query, run_started_at FROM search_checks ORDER BY query")
        rows = {row["query"]: row["run_started_at"] for row in cursor.fetchall()}
    assert rows == {
        "09시 회차": datetime(2026, 11, 7, 0, 0),
        "17시 회차": datetime(2026, 11, 6, 8, 0),
        "새 기록": datetime(2026, 11, 7, 3, 0),  # 이미 있는 값(관리자 즉시 실행 등)은 건드리지 않는다
    }


def test_backfilled_records_feed_the_new_judgment(client, db, clean_db):
    """옮긴 기록이 새 판정에서 예전 화면의 뜻대로 읽히는지: 지금 막힘·최근 7일·cover·검사 전."""
    from unittest.mock import patch

    last_run, _ = _legacy_rows(db)
    _run_backfill(db)
    with patch("stelline.apis.search.tasks.utc_now", return_value=last_run + timedelta(hours=1)):
        songs = {s["query"]: (s["state"], s["recent"]) for s in client.get("/api/search/status").get_json()["songs"]}
    assert songs == {
        "막힌 곡": ("blocked", True),
        "cover 곡": ("cover_only", True),
        "회복 곡": ("visible", True),       # 직전 회차의 막힘(recent_data)이 7일 기록으로 남는다
        "정상 곡": ("visible", False),
        "검사 안 된 곡": ("unchecked", False),
        "영상 바뀐 곡": ("visible", False),  # 예전 영상의 막힘은 이 곡의 기록이 아니다
    }
