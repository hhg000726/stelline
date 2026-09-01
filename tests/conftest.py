"""공용 픽스처.

- 환경 변수를 앱 import 전에 고정한다.
- MySQL이 닿지 않는 환경에서는 DB 의존 테스트를 skip 한다(순수 단위 테스트는 계속 실행).
- CI에서는 MySQL 서비스 컨테이너가 있으므로 통합 테스트가 실제로 돈다.
"""

import os

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("START_BACKGROUND_TASKS", "false")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SERVICE_ACCOUNT_FILE", "")
os.environ.setdefault("TURNSTILE_SECRET_KEY", "")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("RDS_HOST", "127.0.0.1")
os.environ.setdefault("RDS_PORT", "3306")
os.environ.setdefault("RDS_USER", "root")
os.environ.setdefault("RDS_PASSWORD", "root")
os.environ.setdefault("RDS_DB", "stelline_test")

import pymysql  # noqa: E402

from stelline import app as flask_app  # noqa: E402
from stelline.database.connection import get_connection  # noqa: E402

# 관리자/마이그레이션이 다루는 전체 테이블. 통합 테스트는 매번 이 목록을 비운다.
CONTENT_AND_STATE_TABLES = (
    "song_infos",
    "songs_data",
    "recent_data",
    "targets",
    "events",
    "twits",
    "song_counts",
    "fcm_tokens",
    "offline",
    "song_reports",
    "view_reports",
    "karaoke_songs",
    "karaoke_members",
    "karaoke_reports",
    "site_contents",
)
SEED_TABLES = ("record_main", "record_search", "record_karaoke", "main_buttons")


def _mysql_reachable():
    try:
        conn = pymysql.connect(
            host=os.environ["RDS_HOST"],
            port=int(os.environ["RDS_PORT"]),
            user=os.environ["RDS_USER"],
            password=os.environ["RDS_PASSWORD"],
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


DB_AVAILABLE = _mysql_reachable()

# CI에서는 REQUIRE_DB=1 로 두어, MySQL이 없으면 통합 테스트를 skip 하지 않고
# 즉시 실패시킨다(서비스 컨테이너 장애를 초록불로 넘기지 않기 위함).
if os.environ.get("REQUIRE_DB") == "1" and not DB_AVAILABLE:
    raise RuntimeError(
        "REQUIRE_DB=1 이지만 MySQL에 연결할 수 없습니다. "
        f"({os.environ['RDS_HOST']}:{os.environ['RDS_PORT']})"
    )

# 통합 테스트 모듈은 `pytestmark = requires_db` 를 선언한다.
requires_db = pytest.mark.skipif(not DB_AVAILABLE, reason="MySQL 서버에 연결할 수 없습니다")


@pytest.fixture(scope="session")
def _schema():
    """테스트 DB를 만들고 마이그레이션을 1회 적용한다."""
    bootstrap = pymysql.connect(
        host=os.environ["RDS_HOST"],
        port=int(os.environ["RDS_PORT"]),
        user=os.environ["RDS_USER"],
        password=os.environ["RDS_PASSWORD"],
    )
    try:
        with bootstrap.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{os.environ['RDS_DB']}` CHARACTER SET utf8mb4"
            )
        bootstrap.commit()
    finally:
        bootstrap.close()

    from stelline.database.migrate import apply_migrations

    apply_migrations()
    return True


def _reset_tables():
    """모든 테이블을 초기 상태로 되돌린다.

    - TRUNCATE 대신 DELETE: 거의 빈 테이블에서 훨씬 빠르고, DDL 암묵적 커밋이
      없어 다른 커넥션의 메타데이터 락과 충돌하지 않는다.
    - lock_wait_timeout 을 짧게 잡아 혹시 걸리면 무한 대기 대신 즉시 실패한다.
    """
    conn = get_connection()
    conn.autocommit(True)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION lock_wait_timeout = 15")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 15")
            for table in (*CONTENT_AND_STATE_TABLES, *SEED_TABLES):
                cursor.execute(f"DELETE FROM `{table}`")
            cursor.execute("INSERT INTO record_main (copy_count) VALUES (0)")
            cursor.execute(
                "INSERT INTO record_search (total_plays, total_play_time, copy_count) VALUES (0, 0, 0)"
            )
            cursor.execute("INSERT INTO record_karaoke (copy_count) VALUES (0)")
            cursor.executemany(
                "INSERT INTO main_buttons (button_key, label, visible, display_order) VALUES (%s, %s, %s, %s)",
                [("search", "검색 안되는 노래 보기", 1, 1),
                 ("karaoke", "노래방 번호 찾기", 1, 2),
                 ("congratulation", "조회수 축하 알림", 1, 3)],
            )
    finally:
        conn.close()


@pytest.fixture
def clean_db(_schema):
    """각 통합 테스트 *전에* 모든 테이블을 초기 상태로 되돌린다.

    테스트가 끝나면 `db` 커넥션이 닫히며 미완료 트랜잭션이 롤백되므로,
    다음 테스트의 사전 초기화만으로 격리가 보장된다(사후 초기화 불필요).
    """
    _reset_tables()
    yield


@pytest.fixture
def db(_schema):
    conn = get_connection()
    conn.autocommit(True)  # bare SELECT가 트랜잭션/MDL을 붙들지 않도록
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def app():
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    """관리자 세션 + CSRF 토큰이 준비된 test client."""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["admin_csrf"] = "test-csrf-token"
    client.csrf = "test-csrf-token"
    return client
