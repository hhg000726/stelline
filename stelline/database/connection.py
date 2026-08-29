"""데이터베이스 연결을 만드는 단일 진입점."""

from contextlib import contextmanager

import pymysql

from stelline.config import RDS_DB, RDS_HOST, RDS_PASSWORD, RDS_PORT, RDS_USER


def get_connection():
    return pymysql.connect(
        host=RDS_HOST,
        port=RDS_PORT,
        user=RDS_USER,
        password=RDS_PASSWORD,
        database=RDS_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@contextmanager
def database_cursor():
    """성공 시 커밋하고 실패 시 롤백하며 연결을 항상 닫는다."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
