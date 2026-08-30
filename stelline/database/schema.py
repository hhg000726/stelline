"""MySQL 스키마의 코드 기준(source of truth)."""


def migrate_song_infos_primary_key(cursor):
    cursor.execute("DELETE FROM song_infos WHERE query IS NULL")
    cursor.execute("DELETE s1 FROM song_infos s1 INNER JOIN song_infos s2 ON s1.query = s2.query AND s1.video_id > s2.video_id")
    cursor.execute(
        """SELECT COUNT(*) AS primary_key_count
           FROM information_schema.TABLE_CONSTRAINTS
          WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'song_infos'
            AND CONSTRAINT_TYPE = 'PRIMARY KEY'"""
    )
    if cursor.fetchone()["primary_key_count"]:
        cursor.execute("ALTER TABLE song_infos DROP PRIMARY KEY")
    cursor.execute("ALTER TABLE song_infos MODIFY query VARCHAR(512) NOT NULL")
    cursor.execute(
        """SELECT COUNT(*) AS primary_key_count
           FROM information_schema.KEY_COLUMN_USAGE
          WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'song_infos'
            AND CONSTRAINT_NAME = 'PRIMARY'"""
    )
    if not cursor.fetchone()["primary_key_count"]:
        cursor.execute("ALTER TABLE song_infos ADD PRIMARY KEY (query)")

def add_column_if_missing(table, column, definition):
    """ALTER TABLE은 되돌릴 수 없어, 중간에 실패해도 다시 실행할 수 있게 존재 여부를 먼저 본다."""
    def migrate(cursor):
        cursor.execute(
            """SELECT COUNT(*) AS column_count
                 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
            (table, column),
        )
        if not cursor.fetchone()["column_count"]:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
    return migrate


MIGRATIONS = [
    ("001_initial_schema", [
        """CREATE TABLE IF NOT EXISTS song_infos (video_id VARCHAR(32) NOT NULL, query VARCHAR(512) PRIMARY KEY, risk INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS songs_data (video_id VARCHAR(32) PRIMARY KEY, query VARCHAR(512) NOT NULL, searched_time DOUBLE NOT NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS recent_data (id BIGINT AUTO_INCREMENT PRIMARY KEY, video_id VARCHAR(32) NOT NULL, query VARCHAR(512) NOT NULL, searched_time DOUBLE NOT NULL, INDEX recent_data_searched_time_idx (searched_time)) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS record_main (copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_main (copy_count) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM record_main)",
        """CREATE TABLE IF NOT EXISTS record_search (total_plays BIGINT NOT NULL DEFAULT 0, total_play_time DOUBLE NOT NULL DEFAULT 0, copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_search (total_plays, total_play_time, copy_count) SELECT 0, 0, 0 WHERE NOT EXISTS (SELECT 1 FROM record_search)",
        """CREATE TABLE IF NOT EXISTS targets (name VARCHAR(255) PRIMARY KEY, title VARCHAR(255) NOT NULL, url_number INT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS events (title VARCHAR(255) PRIMARY KEY, link TEXT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS twits (title VARCHAR(255) PRIMARY KEY, time VARCHAR(255) NULL, tags TEXT NOT NULL, keywords TEXT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS song_counts (video_id VARCHAR(32) PRIMARY KEY, title VARCHAR(512) NOT NULL, count BIGINT NOT NULL DEFAULT 0, counted_time DATETIME NOT NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS fcm_tokens (id BIGINT AUTO_INCREMENT PRIMARY KEY, token TEXT NOT NULL, registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY fcm_tokens_token_idx (token(255))) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS offline (name VARCHAR(255) PRIMARY KEY, location_name VARCHAR(255) NULL, description TEXT NULL, latitude DOUBLE NOT NULL DEFAULT 0, longitude DOUBLE NOT NULL DEFAULT 0, start_date DATETIME NULL, end_date DATETIME NULL, address TEXT NULL, always BOOLEAN NOT NULL DEFAULT FALSE) CHARACTER SET utf8mb4""",
    ]),
    ("002_change_song_infos_pk", [
        migrate_song_infos_primary_key,
    ]),
    ("003_song_reports", [
        """CREATE TABLE IF NOT EXISTS song_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
    ("004_view_reports", [
        """CREATE TABLE IF NOT EXISTS view_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
    ("005_karaoke", [
        """CREATE TABLE IF NOT EXISTS karaoke_songs (id BIGINT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255) NOT NULL, title_alt VARCHAR(255) NULL, artist VARCHAR(255) NOT NULL, members VARCHAR(512) NULL, section VARCHAR(16) NOT NULL DEFAULT 'solo', category VARCHAR(16) NOT NULL DEFAULT 'cover', tj VARCHAR(16) NULL, ky VARCHAR(16) NULL, note VARCHAR(255) NULL, sort_order INT NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, UNIQUE KEY karaoke_songs_title_artist_idx (title, artist), INDEX karaoke_songs_sort_idx (sort_order)) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS karaoke_members (name VARCHAR(64) PRIMARY KEY, unit VARCHAR(64) NULL, display_order INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS karaoke_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS record_karaoke (copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_karaoke (copy_count) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM record_karaoke)",
    ]),
    ("006_karaoke_member_history", [
        add_column_if_missing("karaoke_songs", "release_date", "DATE NULL AFTER ky"),
        add_column_if_missing("karaoke_members", "former_units", "VARCHAR(128) NULL"),
        add_column_if_missing("karaoke_members", "debut_date", "DATE NULL"),
        add_column_if_missing("karaoke_members", "graduated_at", "DATE NULL"),
        """ALTER TABLE karaoke_members MODIFY unit VARCHAR(64) NULL""",
    ]),
    ("007_main_buttons", [
        """CREATE TABLE IF NOT EXISTS main_buttons (button_key VARCHAR(64) PRIMARY KEY, label VARCHAR(255) NOT NULL, visible BOOLEAN NOT NULL DEFAULT TRUE, display_order INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        # 메인 화면에 이미 있는 버튼을 기본값(표시)으로 등록한다.
        """INSERT INTO main_buttons (button_key, label, visible, display_order)
           VALUES ('search', '검색 안되는 노래 보기', TRUE, 1),
                  ('karaoke', '노래방 번호 찾기', TRUE, 2),
                  ('congratulation', '조회수 축하 알림', TRUE, 3)
           ON DUPLICATE KEY UPDATE button_key = button_key""",
    ]),
]
