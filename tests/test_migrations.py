"""스키마 마이그레이션 검증 (실제 MySQL)."""

from stelline.database.connection import get_connection
from stelline.database.migrate import apply_migrations
from stelline.database.schema import MIGRATIONS
from tests.conftest import requires_db

pytestmark = requires_db

EXPECTED_TABLES = {
    "song_infos",
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
