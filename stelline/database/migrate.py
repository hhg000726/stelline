"""코드로 정의한 MySQL 마이그레이션을 적용하는 명시적 명령."""

from stelline.database.connection import get_connection
from stelline.database.schema import MIGRATIONS


def apply_migrations():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(100) PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4")
            for version, statements in MIGRATIONS:
                cursor.execute("SELECT version FROM schema_migrations WHERE version = %s", (version,))
                if cursor.fetchone():
                    continue
                for statement in statements:
                    cursor.execute(statement)
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    apply_migrations()
    print("Database migrations applied.")
